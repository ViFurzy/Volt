"""Unit tests for monitor.service.MonitorService.

All tests exercise discover() and poll_once() directly via asyncio.run() —
no real hardware, no real threads. find_receiver, open_receiver, and
battery_probe_chain are patched at the monitor.service module namespace.
"""

import asyncio
import queue

import pytest

from hidpp.receiver import DEVICE_IDX
from hidpp.features import BatteryResult
from monitor.registry import DeviceRegistry
from monitor.service import MonitorService
from monitor.state import DeviceStatus, KNOWN_DEVICES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GPRO_VID = 0x046D
GPRO_PID = 0x0ABA
GPRO_KEY = (GPRO_VID, GPRO_PID, DEVICE_IDX)

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
        mocker.patch("monitor.service.open_receiver", side_effect=OSError("access denied"))

        asyncio.run(service.discover())

        assert registry.all() == []
        assert ui_queue.empty()


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

        mocker.patch(
            "monitor.service.battery_probe_chain",
            return_value=BatteryResult(percent=75, charging=False, feature_used="0x06/0x0D"),
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

        mocker.patch(
            "monitor.service.battery_probe_chain",
            return_value=BatteryResult(percent=60, charging=True, feature_used="0x06/0x0D"),
        )

        asyncio.run(service.poll_once())

        state = registry.get(GPRO_KEY)
        assert state.status == DeviceStatus.CHARGING

        queued = ui_queue.get_nowait()
        assert queued.status == DeviceStatus.CHARGING

    def test_none_result_marks_offline_and_removes_handle(self, mocker):
        """poll_once() with battery_probe_chain=None marks OFFLINE, closes handle, clears _open."""
        service, mock_handle, ui_queue, registry = self._setup_with_open_device(mocker)

        mocker.patch("monitor.service.battery_probe_chain", return_value=None)

        asyncio.run(service.poll_once())

        # Handle removed from _open
        assert GPRO_KEY not in service._open
        mock_handle.close.assert_called_once()

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

        mocker.patch("monitor.service.battery_probe_chain", return_value=None)

        asyncio.run(service.poll_once())

        # Handle still removed
        assert GPRO_KEY not in service._open
        # Queue empty (mark_offline returned None → no put)
        assert ui_queue.empty()


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
