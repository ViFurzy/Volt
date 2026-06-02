"""Tests for DeviceState, DeviceStatus, KNOWN_DEVICES, and DeviceRegistry."""
import threading
from monitor.state import DeviceState, DeviceStatus, KNOWN_DEVICES
from monitor.registry import DeviceRegistry


# ---------------------------------------------------------------------------
# DeviceStatus tests
# ---------------------------------------------------------------------------

def test_device_status_has_three_members():
    members = list(DeviceStatus)
    assert len(members) == 3


def test_device_status_names():
    names = {m.name for m in DeviceStatus}
    assert names == {"ONLINE", "OFFLINE", "CHARGING"}


# ---------------------------------------------------------------------------
# KNOWN_DEVICES tests
# ---------------------------------------------------------------------------

def test_known_devices_has_gpro_x():
    assert KNOWN_DEVICES[(0x046D, 0x0ABA)] == "G Pro X Wireless"


def test_known_devices_is_dict():
    assert isinstance(KNOWN_DEVICES, dict)


# ---------------------------------------------------------------------------
# DeviceState tests
# ---------------------------------------------------------------------------

def test_device_state_holds_all_fields():
    state = DeviceState(
        vid=0x046D,
        pid=0x0ABA,
        dev_idx=0xFF,
        device_name="G Pro X Wireless",
        percent=80,
        charging=False,
        status=DeviceStatus.ONLINE,
    )
    assert state.vid == 0x046D
    assert state.pid == 0x0ABA
    assert state.dev_idx == 0xFF
    assert state.device_name == "G Pro X Wireless"
    assert state.percent == 80
    assert state.charging is False
    assert state.status == DeviceStatus.ONLINE


def test_device_state_accepts_none_percent():
    state = DeviceState(
        vid=0x046D,
        pid=0x0ABA,
        dev_idx=0xFF,
        device_name="G Pro X Wireless",
        percent=None,
        charging=False,
        status=DeviceStatus.OFFLINE,
    )
    assert state.percent is None


def test_device_state_charging_carries_charging_status():
    state = DeviceState(
        vid=0x046D,
        pid=0x0ABA,
        dev_idx=0xFF,
        device_name="G Pro X Wireless",
        percent=50,
        charging=True,
        status=DeviceStatus.CHARGING,
    )
    assert state.charging is True
    assert state.status == DeviceStatus.CHARGING


# ---------------------------------------------------------------------------
# DeviceRegistry tests
# ---------------------------------------------------------------------------

def _make_state(percent=75, charging=False, status=DeviceStatus.ONLINE):
    return DeviceState(
        vid=0x046D,
        pid=0x0ABA,
        dev_idx=0xFF,
        device_name="G Pro X Wireless",
        percent=percent,
        charging=charging,
        status=status,
    )


def test_registry_upsert_then_get_roundtrip():
    reg = DeviceRegistry()
    state = _make_state()
    reg.upsert(state)
    result = reg.get((0x046D, 0x0ABA, 0xFF))
    assert result == state


def test_registry_upsert_overwrites():
    reg = DeviceRegistry()
    reg.upsert(_make_state(percent=50))
    reg.upsert(_make_state(percent=90))
    result = reg.get((0x046D, 0x0ABA, 0xFF))
    assert result.percent == 90


def test_registry_get_unknown_key_returns_none():
    reg = DeviceRegistry()
    assert reg.get((0x046D, 0x0ABA, 0x01)) is None


def test_registry_all_returns_snapshot():
    reg = DeviceRegistry()
    state = _make_state()
    reg.upsert(state)
    snapshot = reg.all()
    assert isinstance(snapshot, list)
    assert state in snapshot


def test_registry_all_empty():
    reg = DeviceRegistry()
    assert reg.all() == []


def test_registry_mark_offline_sets_status_and_clears_percent():
    reg = DeviceRegistry()
    reg.upsert(_make_state(percent=75))
    key = (0x046D, 0x0ABA, 0xFF)
    updated = reg.mark_offline(key)
    assert updated is not None
    assert updated.status == DeviceStatus.OFFLINE
    assert updated.percent is None
    # Stored state is also updated
    stored = reg.get(key)
    assert stored.status == DeviceStatus.OFFLINE
    assert stored.percent is None


def test_registry_mark_offline_unknown_key_returns_none():
    reg = DeviceRegistry()
    result = reg.mark_offline((0x046D, 0x0ABA, 0x01))
    assert result is None


def test_registry_concurrency():
    """Concurrent upserts from multiple threads do not corrupt the store."""
    reg = DeviceRegistry()
    errors = []
    iterations = 100

    def worker(dev_idx):
        try:
            for i in range(iterations):
                state = DeviceState(
                    vid=0x046D,
                    pid=0x0ABA,
                    dev_idx=dev_idx,
                    device_name="G Pro X Wireless",
                    percent=i % 100,
                    charging=False,
                    status=DeviceStatus.ONLINE,
                )
                reg.upsert(state)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrency errors: {errors}"
    # Each thread used a unique dev_idx (0-9), so we expect 10 entries
    assert len(reg.all()) == 10
