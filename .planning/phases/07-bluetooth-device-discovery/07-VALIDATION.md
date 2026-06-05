---
phase: 07
slug: bluetooth-device-discovery
created: 2026-06-05
---

# Phase 7 Validation Architecture

## Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-mock 3.15.1 + pytest-qt 4.5.0 |
| Config file | none — uses pyproject.toml or command line |
| Quick run command | `python -m pytest tests/test_bt_backend.py tests/test_devices_page.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

## Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BT-01 | WinRT OS battery property read returns int or None | unit | `pytest tests/test_bt_backend.py::test_winrt_battery_returns_int -x` | Wave 0 |
| BT-01 | WinRT enumeration returns list of paired BT devices with names | unit | `pytest tests/test_bt_backend.py::test_winrt_enumerate_returns_devices -x` | Wave 0 |
| BT-02 | gatt_battery returns int when GATT Battery Service present | unit | `pytest tests/test_bt_backend.py::test_gatt_battery_success -x` | Wave 0 |
| BT-02 | gatt_battery returns None when Battery Service absent | unit | `pytest tests/test_bt_backend.py::test_gatt_battery_no_service -x` | Wave 0 |
| BT-02 | gatt_battery returns None on BleakError | unit | `pytest tests/test_bt_backend.py::test_gatt_battery_connection_error -x` | Wave 0 |
| BT-02 | resolve_battery falls through: winrt→None, gatt→int | unit | `pytest tests/test_bt_backend.py::test_resolve_fallthrough_to_gatt -x` | Wave 0 |
| BT-03 | DevicesPage renders scan results in list (BT and HID entries) | unit (pytest-qt) | `pytest tests/test_devices_page.py::TestDevicesPageScanResults -x` | Wave 0 |
| BT-03 | Add device to monitored list persists in config | unit (pytest-qt) | `pytest tests/test_devices_page.py::TestDevicesPageAddRemove -x` | Wave 0 |
| BT-03 | Remove device from monitored list removes dashboard card | unit (pytest-qt) | `pytest tests/test_devices_page.py -x` | Wave 0 |
| BT-03 | _run_bt_scan merges hid.enumerate() entries into BtScanResultEvent.devices | unit | `pytest tests/test_service.py::TestBtDevices::test_scan_bt_devices_includes_hid_entries -x` | Wave 0 |
| BT-04 | MonitorService.discover() loads persisted BT devices from config | unit | `pytest tests/test_service.py::TestBtDevices::test_discover_loads_persisted_bt_devices_from_config -x` | Wave 0 |
| BT-04 | Hardware: Stadia battery via WinRT (manual checkpoint) | manual | N/A — requires Stadia hardware | N/A |

## Sampling Rate

- **Per task commit:** `python -m pytest tests/test_bt_backend.py tests/test_devices_page.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

## Wave 0 Gaps

- [ ] `tests/test_bt_backend.py` — covers BT-01, BT-02
- [ ] `tests/test_devices_page.py` — covers BT-03
- [ ] Add `tests/test_service.py` tests for BT-03 (HID enumeration) and BT-04 (extend existing file)
- [ ] `src/monitor/bt_backend.py` — new module, no tests can run without it
- [ ] Install: `uv pip install bleak==3.0.2 "winrt-Windows.Devices.Enumeration==3.2.1" "winrt-Windows.Devices.Bluetooth==3.2.1"` — required before any import-time test can pass
