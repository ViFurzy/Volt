"""Unit tests for monitor.service.MonitorService.

All tests exercise discover() and poll_once() directly via asyncio.run() —
no real hardware, no real threads. find_receiver, open_receiver, find_dongle,
and DEVICE_PROBES are patched at the monitor.service module namespace.
"""

import asyncio
import queue

import pytest

from hidpp.receiver import DEVICE_IDX
from hidpp.features import BatteryResult
from monitor.registry import DeviceRegistry
from monitor.service import MonitorService
from monitor.state import DeviceStatus, KNOWN_DEVICES, BtDeviceInfo, BtScanResultEvent
from steelseries.driver import SS_DEVICE_IDX
from steelseries.driver import ss_battery_probe as _ss_battery_probe


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GPRO_VID = 0x046D
GPRO_PID = 0x0ABA
GPRO_KEY = (GPRO_VID, GPRO_PID, DEVICE_IDX)

SS_VID = 0x1038
SS_PID = 0x1852
SS_KEY = (SS_VID, SS_PID, SS_DEVICE_IDX)
SS_INTERFACE = {
    "vendor_id": SS_VID,
    "product_id": SS_PID,
    "interface_number": 3,
    "usage_page": 0xFFC0,
    "path": b"/dev/hid3",
}

GPRO_INTERFACE = {
    "vendor_id": GPRO_VID,
    "product_id": GPRO_PID,
    "usage_page": 0xFF43,
    "usage": 0x01,
    "path": b"/dev/hid0",
}

UNKNOWN_INTERFACE = {
    "vendor_id": 0x046D,
    "product_id": 0xDEAD,  # not in KNOWN_DEVICES
    "usage_page": 0xFF43,
    "usage": 0x01,
    "path": b"/dev/hid1",
}


def make_service(ui_queue=None, registry=None):
    """Create a MonitorService with real queue/registry (no bg thread started)."""
    if ui_queue is None:
        ui_queue = queue.Queue()
    if registry is None:
        registry = DeviceRegistry()
    return MonitorService(ui_queue, registry, poll_interval=60.0)


# ---------------------------------------------------------------------------
# discover() tests
# ---------------------------------------------------------------------------

class TestDiscover:
    def test_registers_online_state_for_known_device(self, mocker):
        """discover() with a G Pro X 0xFF43 interface registers ONE ONLINE DeviceState."""
        ui_queue = queue.Queue()
        registry = DeviceRegistry()
        service = make_service(ui_queue, registry)

        mock_handle = mocker.MagicMock()
        mocker.patch("monitor.service.find_receiver", return_value=[GPRO_INTERFACE])
        mocker.patch("monitor.service.find_dongle", return_value=[])
        mocker.patch("monitor.service.open_receiver", return_value=mock_handle)

        asyncio.run(service.discover())

        # Registry should hold the device
        state = registry.get(GPRO_KEY)
        assert state is not None
        assert state.device_name == "G Pro X Wireless"
        assert state.status == DeviceStatus.ONLINE
        assert state.vid == GPRO_VID
        assert state.pid == GPRO_PID
        assert state.dev_idx == DEVICE_IDX

    def test_puts_state_on_queue(self, mocker):
        """discover() pushes the initial ONLINE DeviceState to ui_queue."""
        ui_queue = queue.Queue()
        service = make_service(ui_queue)

        mock_handle = mocker.MagicMock()
        mocker.patch("monitor.service.find_receiver", return_value=[GPRO_INTERFACE])
        mocker.patch("monitor.service.find_dongle", return_value=[])
        mocker.patch("monitor.service.open_receiver", return_value=mock_handle)

        asyncio.run(service.discover())

        assert not ui_queue.empty()
        state = ui_queue.get_nowait()
        assert state.device_name == "G Pro X Wireless"
        assert state.status == DeviceStatus.ONLINE

    def test_skips_unknown_vid_pid(self, mocker):
        """discover() skips an interface whose (vid,pid) is not in KNOWN_DEVICES."""
        ui_queue = queue.Queue()
        registry = DeviceRegistry()
        service = make_service(ui_queue, registry)

        mocker.patch("monitor.service.find_receiver", return_value=[UNKNOWN_INTERFACE])
        mocker.patch("monitor.service.find_dongle", return_value=[])
        mock_open = mocker.patch("monitor.service.open_receiver")

        asyncio.run(service.discover())

        # Nothing opened, nothing registered, nothing on queue
        mock_open.assert_not_called()
        assert registry.all() == []
        assert ui_queue.empty()

    def test_does_not_reopen_already_open_device(self, mocker):
        """discover() skips open_receiver if the device is already in self._open."""
        service = make_service()

        mock_handle = mocker.MagicMock()
        mocker.patch("monitor.service.find_receiver", return_value=[GPRO_INTERFACE])
        mocker.patch("monitor.service.find_dongle", return_value=[])
        mock_open = mocker.patch("monitor.service.open_receiver", return_value=mock_handle)

        asyncio.run(service.discover())  # first call opens
        asyncio.run(service.discover())  # second call should not reopen

        mock_open.assert_called_once()  # only once total

    def test_skips_device_on_oserror(self, mocker):
        """discover() skips a device if open_receiver raises OSError."""
        ui_queue = queue.Queue()
        registry = DeviceRegistry()
        service = make_service(ui_queue, registry)

        mocker.patch("monitor.service.find_receiver", return_value=[GPRO_INTERFACE])
        mocker.patch("monitor.service.find_dongle", return_value=[])
        mocker.patch("monitor.service.open_receiver", side_effect=OSError("access denied"))

        asyncio.run(service.discover())

        assert registry.all() == []
        assert ui_queue.empty()

    def test_ss_dongle_unplug_marks_offline(self, mocker):
        """discover() with SS dongle gone marks SS key OFFLINE and removes from _open."""
        ui_queue = queue.Queue()
        registry = DeviceRegistry()
        service = make_service(ui_queue, registry)

        # Pre-populate as if SS was already discovered
        service._open[SS_KEY] = SS_INTERFACE
        from monitor.state import DeviceState
        registry.upsert(DeviceState(
            vid=SS_VID, pid=SS_PID, dev_idx=SS_DEVICE_IDX,
            device_name="Aerox 5 Wireless", percent=50,
            charging=False, status=DeviceStatus.ONLINE,
        ))
        # Drain initial queue entry
        try:
            while not ui_queue.empty():
                ui_queue.get_nowait()
        except Exception:
            pass

        # Both Logitech and SteelSeries gone
        mocker.patch("monitor.service.find_receiver", return_value=[])
        mocker.patch("monitor.service.find_dongle", return_value=[])

        asyncio.run(service.discover())

        assert SS_KEY not in service._open
        assert registry.get(SS_KEY).status == DeviceStatus.OFFLINE

    def test_ss_discover_stores_info_dict(self, mocker):
        """discover() with SS interface stores info dict (not handle) in self._open."""
        ui_queue = queue.Queue()
        registry = DeviceRegistry()
        service = make_service(ui_queue, registry)

        mocker.patch("monitor.service.find_receiver", return_value=[])
        mocker.patch("monitor.service.find_dongle", return_value=[SS_INTERFACE])

        asyncio.run(service.discover())

        assert SS_KEY in service._open
        assert isinstance(service._open[SS_KEY], dict)


# ---------------------------------------------------------------------------
# poll_once() tests
# ---------------------------------------------------------------------------

class TestPollOnce:
    def _setup_with_open_device(self, mocker, ui_queue=None, registry=None):
        """Create service with the G Pro X already in self._open."""
        if ui_queue is None:
            ui_queue = queue.Queue()
        if registry is None:
            registry = DeviceRegistry()
        service = make_service(ui_queue, registry)

        mock_handle = mocker.MagicMock()
        service._open[GPRO_KEY] = mock_handle
        # Pre-populate registry with an ONLINE state so mark_offline has something to work with
        from monitor.state import DeviceState
        registry.upsert(DeviceState(
            vid=GPRO_VID, pid=GPRO_PID, dev_idx=DEVICE_IDX,
            device_name="G Pro X Wireless", percent=None,
            charging=False, status=DeviceStatus.ONLINE,
        ))
        return service, mock_handle, ui_queue, registry

    def test_online_battery_result_upserts_and_queues(self, mocker):
        """poll_once() with BatteryResult(75, False) upserts ONLINE, percent=75."""
        service, _, ui_queue, registry = self._setup_with_open_device(mocker)

        mocker.patch.dict(
            "monitor.service.DEVICE_PROBES",
            {(GPRO_VID, GPRO_PID): lambda h, i: BatteryResult(percent=75, voltage_mv=3990, charging=False, feature_used="0x06/0x0D")},
        )

        asyncio.run(service.poll_once())

        state = registry.get(GPRO_KEY)
        assert state.status == DeviceStatus.ONLINE
        assert state.percent == 75
        assert state.charging is False

        queued = ui_queue.get_nowait()
        assert queued.percent == 75
        assert queued.status == DeviceStatus.ONLINE

    def test_charging_result_yields_charging_status(self, mocker):
        """poll_once() with BatteryResult(charging=True) yields status=CHARGING."""
        service, _, ui_queue, registry = self._setup_with_open_device(mocker)

        mocker.patch.dict(
            "monitor.service.DEVICE_PROBES",
            {(GPRO_VID, GPRO_PID): lambda h, i: BatteryResult(percent=60, voltage_mv=3894, charging=True, feature_used="0x06/0x0D")},
        )

        asyncio.run(service.poll_once())

        state = registry.get(GPRO_KEY)
        assert state.status == DeviceStatus.CHARGING

        queued = ui_queue.get_nowait()
        assert queued.status == DeviceStatus.CHARGING

    def test_none_result_marks_offline_keeps_handle(self, mocker):
        """poll_once() with probe returning None marks OFFLINE but keeps handle open.

        The handle is kept so the next poll cycle can detect recovery when the
        headset turns back on without the dongle being replugged. Handles are
        only closed by discover() when the dongle is physically unplugged.
        """
        service, mock_handle, ui_queue, registry = self._setup_with_open_device(mocker)

        mocker.patch.dict(
            "monitor.service.DEVICE_PROBES",
            {(GPRO_VID, GPRO_PID): lambda h, i: None},
        )

        asyncio.run(service.poll_once())

        # Handle KEPT in _open (recovery without replug)
        assert GPRO_KEY in service._open
        mock_handle.close.assert_not_called()

        # Registry shows OFFLINE
        state = registry.get(GPRO_KEY)
        assert state.status == DeviceStatus.OFFLINE
        assert state.percent is None

        # Queue received OFFLINE snapshot
        queued = ui_queue.get_nowait()
        assert queued.status == DeviceStatus.OFFLINE

    def test_none_result_does_not_queue_if_not_in_registry(self, mocker):
        """poll_once() with None result and no registry entry: no queue put (edge case)."""
        ui_queue = queue.Queue()
        service = make_service(ui_queue)
        mock_handle = mocker.MagicMock()
        service._open[GPRO_KEY] = mock_handle  # open but NOT in registry

        mocker.patch.dict(
            "monitor.service.DEVICE_PROBES",
            {(GPRO_VID, GPRO_PID): lambda h, i: None},
        )

        asyncio.run(service.poll_once())

        # Handle KEPT (new contract — only discover() closes handles)
        assert GPRO_KEY in service._open
        # Queue empty (mark_offline returned None → no put)
        assert ui_queue.empty()

    def test_dispatches_via_device_probes(self, mocker):
        """poll_once() calls the probe_fn from DEVICE_PROBES, not battery_probe_chain."""
        service, mock_handle, _, _ = self._setup_with_open_device(mocker)

        mock_probe = mocker.MagicMock(
            return_value=BatteryResult(percent=75, voltage_mv=3990, charging=False, feature_used="0x06/0x0D")
        )
        mocker.patch.dict("monitor.service.DEVICE_PROBES", {(GPRO_VID, GPRO_PID): mock_probe})

        asyncio.run(service.poll_once())

        mock_probe.assert_called_once()
        assert mock_probe.call_args[0] == (mock_handle, DEVICE_IDX)

    def test_zero_voltage_skips_smoothing(self, mocker):
        """SteelSeries (voltage_mv=0) uses result.percent directly; no smoothing deque update."""
        service, _, ui_queue, registry = self._setup_with_open_device(mocker)

        # Inject SS key alongside G Pro X (info dict, not a handle)
        ss_info = {"vendor_id": SS_VID, "product_id": SS_PID, "interface_number": 3, "path": b"/dev/hid3"}
        service._open[SS_KEY] = ss_info
        from monitor.state import DeviceState
        registry.upsert(DeviceState(
            vid=SS_VID, pid=SS_PID, dev_idx=SS_DEVICE_IDX,
            device_name="Aerox 5 Wireless", percent=None,
            charging=False, status=DeviceStatus.ONLINE,
        ))

        # Configure mock handle so real ss_battery_probe returns BatteryResult(20, 0, ...)
        # raw=5 → pct=(5-1)*5=20, not charging (bit 7 clear)
        mock_fresh_handle = mocker.MagicMock()
        mock_fresh_handle.read.side_effect = (
            [[], [], []]                          # 3 warmup reads → empty
            + [[0xD2, 0x05] + [0x00] * 62]       # battery response: raw=5 → pct=20
        )
        mocker.patch("monitor.service.open_dongle", return_value=mock_fresh_handle)
        mocker.patch.dict("monitor.service.DEVICE_PROBES", {
            (GPRO_VID, GPRO_PID): lambda h, i: BatteryResult(75, 3990, False, "0x06/0x0D"),
            (SS_VID, SS_PID): _ss_battery_probe,
        })

        asyncio.run(service.poll_once())

        ss_state = registry.get(SS_KEY)
        assert ss_state is not None
        assert ss_state.percent == 20
        # Voltage history must NOT have been updated for the SS key (no smoothing)
        assert SS_KEY not in service._voltage_history


# ---------------------------------------------------------------------------
# Safety checks
# ---------------------------------------------------------------------------

class TestSafetyInvariants:
    def test_no_pyside6_import(self):
        """MonitorService must not import PySide6."""
        import importlib
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "monitor.service",
            "src/monitor/service.py",
        )
        source = open("src/monitor/service.py").read()
        assert "PySide6" not in source, "MonitorService must not import PySide6"

    def test_no_hid_open_direct_call(self):
        """MonitorService must not call hid.open(vid,pid) directly."""
        import ast, pathlib
        source = pathlib.Path("src/monitor/service.py").read_text()
        tree = ast.parse(source)
        # Walk AST looking for Call nodes that are hid.open(...)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "open"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "hid"
                ):
                    pytest.fail(
                        f"Found forbidden hid.open() call at line {node.lineno}"
                    )


# ---------------------------------------------------------------------------
# BT device integration tests
# ---------------------------------------------------------------------------

class TestBtDevices:
    def test_scan_bt_devices_puts_scan_result_on_queue(self, mocker):
        """_run_bt_scan() with one BT device puts BtScanResultEvent on the queue."""
        mocker.patch(
            "monitor.service.bt_backend.winrt_enumerate_bt",
            return_value=[{"id": "dev://1", "name": "Stadia", "battery": 82, "type": "bt"}],
        )
        service = make_service()

        asyncio.run(service._run_bt_scan())

        assert not service._ui_queue.empty()
        event = service._ui_queue.get_nowait()
        assert isinstance(event, BtScanResultEvent)
        assert event.devices[0]["name"] == "Stadia"

    def test_scan_bt_devices_excludes_hid_entries(self, mocker):
        """_run_bt_scan() only includes BT devices — no hid.enumerate() results."""
        mocker.patch(
            "monitor.service.bt_backend.winrt_enumerate_bt",
            return_value=[{"id": "dev://bt1", "name": "Stadia", "battery": None, "type": "bt", "ble_address": None}],
        )
        service = make_service()

        asyncio.run(service._run_bt_scan())

        event = service._ui_queue.get_nowait()
        assert isinstance(event, BtScanResultEvent)
        assert all(d["type"] == "bt" for d in event.devices)

    def test_scan_bt_devices_does_not_store_in_bt_devices_dict(self, mocker):
        """_run_bt_scan() must NOT populate _bt_devices; only add_bt_device()/discover() do that."""
        mocker.patch(
            "monitor.service.bt_backend.winrt_enumerate_bt",
            return_value=[{"id": "dev://1", "name": "Stadia", "battery": 82, "type": "bt"}],
        )
        service = make_service()

        asyncio.run(service._run_bt_scan())

        assert "dev://1" not in service._bt_devices

    def test_poll_once_refreshes_persisted_bt_device(self, mocker):
        """poll_once() calls resolve_battery for each BT device and puts updated BtDeviceInfo on queue."""
        mocker.patch(
            "monitor.service.bt_backend.resolve_battery",
            return_value=60,
        )
        # Patch HID side so poll_once() doesn't try real HID
        mocker.patch("monitor.service.find_receiver", return_value=[])
        mocker.patch("monitor.service.find_dongle", return_value=[])
        service = make_service()
        service._bt_devices["dev://1"] = BtDeviceInfo(
            bt_id="dev://1",
            name="Stadia",
            battery=None,
            ble_address=None,
            status=DeviceStatus.ONLINE,
        )

        asyncio.run(service.poll_once())

        event = service._ui_queue.get_nowait()
        assert isinstance(event, BtDeviceInfo)
        assert event.battery == 60

    def test_discover_loads_persisted_bt_devices_from_config(self, mocker):
        """discover() reads config['monitored_devices'] and pre-populates _bt_devices."""
        mocker.patch(
            "monitor.service.load_config",
            return_value={
                "monitored_devices": [
                    {"id": "dev://1", "name": "Stadia", "type": "bt", "ble_address": None}
                ]
            },
        )
        mocker.patch("monitor.service.bt_backend.winrt_enumerate_bt", return_value=[])
        mocker.patch("monitor.service.find_receiver", return_value=[])
        mocker.patch("monitor.service.find_dongle", return_value=[])
        service = make_service()

        asyncio.run(service.discover())

        assert "dev://1" in service._bt_devices
