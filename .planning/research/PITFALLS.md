# Domain Pitfalls: Windows Peripheral Battery Monitor

**Domain:** Python Windows 11 app reading battery from wireless gaming peripherals via HID++ 2.0 and proprietary HID without manufacturer software
**Researched:** 2026-06-01
**Confidence:** MEDIUM-HIGH (core HID/Windows findings from official sources and kernel code; BLE from official bleak docs; packaging from PyInstaller issues)

---

## Critical Pitfalls

Mistakes that cause hard-to-debug failures, crashes, or rewrites.

---

### Pitfall 1: Opening the Wrong HID Interface (Access Denied on the Primary Interface)

**What goes wrong:** You enumerate the device by VID/PID and open the first result. On Windows, the first interface returned is typically the standard mouse or keyboard interface owned by HidUsb/kbdhid drivers. hidapi opens it with `GENERIC_READ | GENERIC_WRITE` but Windows returns ERROR_ACCESS_DENIED or ERROR_SHARING_VIOLATION (error 32) for usage-page 0x0001 (Generic Desktop) mouse/keyboard interfaces.

**Why it happens:** Windows OS locks `HID_USAGE_PAGE_GENERIC` mouse (`usage 0x02`) and keyboard (`usage 0x06`) interfaces. This is a deliberate OS security decision: applications cannot inject or intercept input. Gaming peripherals expose *multiple* HID collections on separate interfaces. The receiver or the vendor-specific interface (usage page 0xFF00 or similar) is on a different interface index — that one is accessible.

**Consequences:** All writes and feature-report reads silently fail or raise exceptions. Battery polling never works.

**Prevention:**
1. Always enumerate *all* interfaces for a given VID/PID using `hid.enumerate(VID, PID)` (Python `hid` package).
2. Filter to usage page 0xFF00 (vendor-specific) or usage page 0x0001 with usage 0x00 (no specific usage) for battery/config interfaces.
3. Never open interface with usage_page=0x0001 AND usage=0x02 (mouse) or usage=0x06 (keyboard).

**Detection warning signs:** `hidapi` returns -1, `OSError` "Access denied", or `WriteFile: Fonction incorrecte` on Windows. All reads return zeros.

**Phase:** Must be solved in Phase 1 (device connectivity proof-of-concept) before any protocol work.

**Sources:** [hidapi issue #228](https://github.com/libusb/hidapi/issues/228), [hidapi issue #135](https://github.com/libusb/hidapi/blob/master/windows/hid.c), [hidapi issue #134](https://github.com/libusb/hidapi/issues/134)

---

### Pitfall 2: HID++ Battery Feature Variant Mismatch (0x1000 vs 0x1001 vs 0x1004)

**What goes wrong:** You hardcode feature 0x1000 (Battery Level Status) for all Logitech devices. Newer devices (G Pro X Wireless and many post-2019 mice) implement 0x1004 (Unified Battery). Older voltage-reporting devices use 0x1001 (Battery Voltage). Querying the wrong feature index returns garbage bytes or error code 2 ("invalid argument").

**Why it happens:** Three distinct battery feature pages exist with incompatible response structures:

| Feature | Returns | Notes |
|---------|---------|-------|
| 0x1000 | level (0-100), next_level, status enum | Reports 0% when plugged in |
| 0x1001 | millivolts + status enum | Requires voltage-to-percent conversion via LiPo curve |
| 0x1004 | optional `state_of_charge` (0-100) + level enum | Preferred; not all devices implement the percentage field |

Feature pages are not at fixed indices — you must first ask the Root feature (always at index 0x00 of feature 0x0000) for the feature's runtime index, then use that index to call functions.

**Consequences:** Wrong feature returns error 2; querying a missing feature returns feature index 0 (root), which will respond with its own data, causing silent misinterpretation.

**Prevention:**
1. Always resolve feature index via IRoot: send `[0x10, device_index, 0x00, 0x00, MSB(feature_id), LSB(feature_id), 0x00]` and read back the runtime index.
2. Probe in priority order: check for 0x1004 first, fall back to 0x1000, then 0x1001.
3. If feature index response is 0x00 (not found), that feature is absent — do not call it.
4. For 0x1004, check the `capabilities` bitmask: not all devices implementing 0x1004 expose `state_of_charge`. Some only report categorical levels (critical/low/good/full).

**Detection warning signs:** Battery reports 0% while device is charging, or reads a fixed value regardless of actual charge, or feature request returns error code 2.

**Phase:** Core of Phase 2 (HID++ protocol implementation). Requires device-specific testing.

**Sources:** [LKML patch for 0x1004](https://yhbt.net/lore/all/nycvar.YFH.7.76.2101081438530.13752@cbobk.fhfr.pm/T/), [libratbag DeepWiki](https://deepwiki.com/libratbag/libratbag/3.2-logitech-hid++-2.0-driver), [Linux kernel hidpp.c](https://github.com/torvalds/linux/blob/master/drivers/hid/hid-logitech-hidpp.c)

---

### Pitfall 3: Receiver vs Wired Device Index (0xFF vs 0x01-0x0F)

**What goes wrong:** When sending HID++ commands through a Lightspeed USB receiver, you use device index 0xFF (which addresses the receiver itself, not the mouse). The receiver responds normally but the response pertains to the dongle firmware, not the paired peripheral.

**Why it happens:** HID++ uses the second byte of every message as the *device index*:
- `0xFF` = the USB receiver/dongle itself
- `0x01`-`0x0E` = paired wireless devices (index assigned by the receiver)
- Wired devices always use `0xFF` as their own address when responding

For a wireless mouse paired to a receiver, you must use index `0x01` (or whichever slot it occupies). You discover this by querying the receiver's device count and device descriptors, or by listening for device notification messages at startup.

**Consequences:** All battery queries silently target the dongle instead of the mouse. The dongle may lack battery features entirely (returns feature-not-found error 2), or returns its own firmware state.

**Prevention:**
1. Query the receiver (0xFF) for paired device list first: feature 0x0004 (Receiver Device Count) or listen for receiver pairing notifications.
2. Try device index 0x01 through 0x06 until you get a valid device name response.
3. Cache device index per session; do not assume index 1 always maps to your mouse.

**Detection warning signs:** Battery feature query returns error 2 on what you believe is your mouse, or device name response contains receiver firmware version instead of mouse model name.

**Phase:** Phase 2 (HID++ receiver communication), before battery reading.

**Sources:** [HID++ 1.0 spec (lekensteyn)](https://lekensteyn.nl/files/logitech/logitech_hidpp10_specification_for_Unifying_Receivers.pdf), [libratbag DeepWiki](https://deepwiki.com/libratbag/libratbag/3.2-logitech-hid++-2.0-driver)

---

### Pitfall 4: HID++ Offline Device Errors Crash the Application

**What goes wrong:** You query battery when the wireless peripheral is turned off or out of range. The receiver is still visible to the OS, but all HID++ feature requests to device index 0x01 return HID++ error code 5 (`logitech_internal` / device unreachable). If unhandled, this raises an exception that propagates through your polling loop and crashes the background thread.

**Why it happens:** Wireless Logitech devices can power off while the receiver remains plugged in. The OS still enumerates the receiver as a valid HID device. The receiver itself accepts your commands but replies with error 5 for the offline device.

**Consequences:** Unhandled exception in polling thread kills it silently; UI shows stale battery percentage indefinitely. Crash logs fill up. Solaar itself has exhibited this as a `KeyError: None` at startup when devices are offline.

**Prevention:**
1. Treat HID++ error 5 as "device offline" — return `None` for battery level rather than raising.
2. Implement a state machine: `ONLINE`, `OFFLINE`, `UNKNOWN`. Transition to OFFLINE on error 5; retry every N minutes.
3. Do not enumerate features at startup if device is offline — defer until first successful ping.
4. Catch `OSError` and `ValueError` around all `hid.read()` / `hid.write()` calls.

**Detection warning signs:** `KeyError: None` during device type lookup; repeated error 5 in debug logs; UI freezes after device is switched off.

**Phase:** Phase 2 implementation; Phase 3 (error handling / resilience).

**Sources:** [Solaar issue #2600](https://github.com/pwr-Solaar/Solaar/issues/2600), [Solaar issue #3036](https://github.com/pwr-Solaar/Solaar/issues/3036)

---

### Pitfall 5: bleak WinRT STA Threading Conflict with PyQt6

**What goes wrong:** You import `PyQt6` (or `pywin32` for WM_DEVICECHANGE handling) before starting bleak. These libraries initialize COM in Single Threaded Apartment (STA) mode. bleak on Windows uses WinRT async APIs that require Multi Threaded Apartment (MTA) mode. Result: bleak hangs forever on `await client.connect()` with no error or timeout — the WinRT callbacks never fire.

**Why it happens:** The official bleak documentation states explicitly: "Bleak will hang forever if the current thread is not MTA — unless there is a Windows event loop running that is properly integrated with asyncio in Python." `PyQt6` initializes COM in a way that can leave the main thread in STA. `pywin32`/`pythoncom` always STA-initializes unless you override `sys.coinit_flags`.

**Consequences:** BLE connect calls block indefinitely. No exception is raised. Application appears to hang.

**Prevention — two valid approaches:**

**Option A (recommended for BLE-heavy code):** Set `sys.coinit_flags = 0` *before* any other imports:
```python
import sys
sys.coinit_flags = 0  # MTA — must be before PyQt6/pywin32 imports
import PyQt6
import bleak
```

**Option B (recommended when Qt event loop is properly integrated with asyncio):** After setting up qasync and confirming the Qt event loop drives asyncio, call:
```python
from bleak.backends.winrt.util import allow_sta
allow_sta()
```
This tells bleak "trust that the GUI framework handles async dispatch correctly."

Do not mix both. Do not call `asyncio.run()` after the Qt event loop has started.

**Detection warning signs:** `await BleakClient.connect()` never returns or times out without any exception; bleak issue tracker references "MAIN_STA" in the thread name.

**Phase:** Phase 1 (architecture) — must be decided before writing any BLE code.

**Sources:** [bleak troubleshooting](https://bleak.readthedocs.io/en/latest/troubleshooting.html), [bleak Windows backend](https://bleak.readthedocs.io/en/latest/backends/windows.html), [bleak discussion #1564](https://github.com/hbldh/bleak/discussions/1564)

---

### Pitfall 6: asyncio.run() Called Multiple Times / Event Loop Fragmentation

**What goes wrong:** You wrap individual BLE operations in separate `asyncio.run()` calls (one per battery poll). Each call creates a new event loop, runs to completion, and destroys it. bleak objects (BleakClient, BleakScanner) created in one loop cannot be used in another. This causes `RuntimeError: no running event loop` or silent failures on the second call.

**Why it happens:** bleak documentation states: "Bleak requires the same asyncio run loop to be used for all of its operations." This is a hard constraint. When using qasync, the Qt event loop *is* the asyncio event loop — there is only one, running for the application lifetime.

**Consequences:** BLE polling works once then fails on all subsequent polls. Exceptions are hard to trace because they appear inside asyncio internals.

**Prevention:**
1. Use qasync: set up one `QEventLoop` at app start, never call `asyncio.run()` directly.
2. Keep BleakClient objects alive across poll cycles; only reconnect when connection drops.
3. Use `asyncio.ensure_future()` or `asyncio.create_task()` inside the running loop, not `asyncio.run()`.

**Phase:** Phase 1 (architecture decision).

**Sources:** [bleak troubleshooting](https://bleak.readthedocs.io/en/latest/troubleshooting.html), [qasync PyPI](https://pypi.org/project/qasync/)

---

## Moderate Pitfalls

---

### Pitfall 7: BLE Address String vs BLEDevice Object Causes Implicit Scan

**What goes wrong:** You call `BleakClient("AA:BB:CC:DD:EE:FF")` with a string address instead of a `BLEDevice` object. On Windows, passing a raw address triggers an implicit `BleakScanner.discover()` inside `connect()`. If the device is already paired but not currently advertising (e.g., connected via 2.4 GHz dongle mode), the scan returns nothing and the connection silently fails.

**Why it happens:** Windows BLE stack only reliably connects to devices that are actively advertising or already in the OS's paired cache. A scan-by-address bypasses the paired device cache lookup that a `BLEDevice` object enables.

**Prevention:** Always call `BleakScanner.find_device_by_name()` or `BleakScanner.find_device_by_filter()` first, store the `BLEDevice` object, and pass that to `BleakClient`. For paired devices not advertising, use `BleakScanner` with `service_uuids` filter or scan with a short timeout then check OS paired cache.

**Detection warning signs:** Connect succeeds in test but fails in production when device is not in discovery mode.

**Phase:** Phase 3 (BLE backend implementation).

**Sources:** [BleakClient docs](https://bleak.readthedocs.io/en/latest/api/client.html), [bleak issue #1238](https://github.com/hbldh/bleak/issues/1238)

---

### Pitfall 8: Battery Percentage Accuracy — Categorical Levels vs True Percentage

**What goes wrong:** You display the raw value from HID++ 0x1004 as a percentage, but the device only supports categorical levels (critical=10%, low=30%, good=60%, full=100%) rather than a true 0-100 `state_of_charge`. Users see battery jump from 30% to 10% with no intermediate values.

**Why it happens:** 0x1004 defines `state_of_charge` as *optional*. Devices that implement 0x1004 but not `state_of_charge` report only level buckets. Additionally, 0x1001 (voltage feature) returns millivolts — you must convert using a LiPo discharge curve, which introduces ~5-10% error. LGSTrayBattery documents that "native HID and GHUB do not provide similar percentages" because GHUB uses a device-specific lookup table while raw voltage uses a generic LiPo curve.

**Prevention:**
1. Check the 0x1004 capability bitmask for `HAS_SOC` flag before reading state_of_charge field.
2. If SOC unavailable, map levels to representative percentages and document this in the UI ("~30%").
3. For 0x1001 (voltage), implement a standard LiPo curve (3.0V=0%, 3.7V=50%, 4.2V=100%) but display with explicit caveat.
4. Never display 0% when a device is on charge — 0x1000 explicitly returns 0% during charging; substitute charging status string instead.

**Phase:** Phase 2 (HID++ implementation) and Phase 4 (UI display logic).

**Sources:** [LGSTrayBattery](https://github.com/andyvorld/LGSTrayBattery), [LKML 0x1004 patch](https://yhbt.net/lore/all/nycvar.YFH.7.76.2101081438530.13752@cbobk.fhfr.pm/T/)

---

### Pitfall 9: HID++ Short vs Long Report Format

**What goes wrong:** You always send 7-byte (short) HID++ reports. Some devices only accept 16-byte (long) reports for feature functions with large parameters or return values. Sending a short report when a long is required results in the receiver ignoring the command or returning a malformed response.

**Why it happens:** HID++ defines two report formats by Report ID: short (ID 0x10, 7 bytes total) and long (ID 0x11, 16 bytes total). The device's HID descriptor declares which it supports. Some devices support both; some only long. The `supported_report_types` bitmask in libratbag's implementation tracks this per device.

**Prevention:**
1. Check which report IDs the device's HID descriptor declares.
2. Prefer long reports (0x11) for all feature function calls if the device supports them — they accommodate all response sizes.
3. Read the Report ID from the response to validate it matches what you sent.

**Phase:** Phase 2 (HID++ protocol layer).

**Sources:** [libratbag DeepWiki](https://deepwiki.com/libratbag/libratbag/3.2-logitech-hid++-2.0-driver)

---

### Pitfall 10: DBT_DEVNODES_CHANGED Fires 5-6 Times Per Plug Event

**What goes wrong:** You listen for `WM_DEVICECHANGE` with `DBT_DEVNODES_CHANGED` to detect receiver plug/unplug. When a single device is inserted, Windows fires this event 5-6 times in rapid succession. Your handler re-enumerates all HID devices on each event, causing 5-6 redundant HID open/close cycles and potential race conditions if the HID bus hasn't settled.

**Why it happens:** `DBT_DEVNODES_CHANGED` is a generic broadcast (lParam = 0) fired for any PnP tree change, including driver loading stages. It carries no device path information and fires multiple times during USB enumeration.

**Prevention:**
1. Register for `DBT_DEVICEARRIVAL` and `DBT_DEVICEREMOVECOMPLETE` via `RegisterDeviceNotification` with `GUID_DEVINTERFACE_HID` instead of listening to `DBT_DEVNODES_CHANGED`.
2. These specific events include a device path in lParam, allowing you to check if it is your peripheral.
3. If you must handle `DBT_DEVNODES_CHANGED`, implement a 500ms debounce: reset a timer on each event and only act when no new events arrive for 500ms.

**Phase:** Phase 3 (hot-plug / reconnect handling).

**Sources:** [Microsoft DBT_DEVNODES_CHANGED docs](https://learn.microsoft.com/en-us/windows/win32/devio/dbt-devnodes-changed), [REFramework issue #1298](https://github.com/praydog/REFramework/issues/1298)

---

### Pitfall 11: HID++ Feature Enumeration Probing Hidden Features on New Firmware

**What goes wrong:** You enumerate all features (IFeatureSet 0x0001, call GetCount then GetFeatureID for each index) and query each one. On Logitech G Pro X Wireless with post-1.1.16 firmware, some features are marked as "hidden" or "restricted" in firmware. Attempting to call functions on them returns error 5 (logitech_internal/unsupported). Solaar itself broke this way — aggressive feature probing on startup caused failures with newer G Pro X Superlight firmware.

**Prevention:**
1. Do not enumerate all features speculatively. Query only the specific features you need (0x0000 Root, 0x0001 FeatureSet count, your target battery feature).
2. Treat error 5 on feature function call as "feature restricted" — log and skip, do not retry in a loop.
3. Use feature obsolete/hidden bits in the GetFeatureID response to skip hidden features.

**Phase:** Phase 2 (HID++ implementation).

**Sources:** [Solaar issue #3036](https://github.com/pwr-Solaar/Solaar/issues/3036)

---

### Pitfall 12: SteelSeries Aerox 5 — Report ID 0 vs Feature Reports

**What goes wrong:** You use `hid.send_feature_report()` for SteelSeries devices following the same pattern as Logitech. SteelSeries proprietary protocol uses standard Output Reports (report ID embedded in the first byte of the data, often 0x00) written via `hid.write()`, not feature reports. Using the wrong call returns error or no response.

**Why it happens:** SteelSeries does not use HID++ 2.0. Their protocol is entirely proprietary: write a specific byte sequence as an Output report, then read back the Input report. The Aerox 5 uses VID 0x1038 and communicates via vendor-specific usage page. Sending battery query requires writing `0x00, 0xb0` (or device-specific command bytes) and reading the 64-byte response where specific bytes encode battery level and charging state.

**Prevention:**
1. Source the exact command bytes from rivalcfg or HeadsetControl projects — these have been reverse-engineered from USB traffic captures.
2. Use `hid.write()` for SteelSeries, not `hid.send_feature_report()`.
3. Always verify you are writing to the vendor-specific interface (usage_page=0xFF00), not the standard mouse interface.
4. Command bytes may change across firmware versions — treat them as fragile and version-gate if possible.

**Phase:** Phase 3 (SteelSeries backend).

**Sources:** [flozz Arctis gist](https://gist.github.com/flozz/df45b59d6d3594c4b843e00c5df16dd0), [LennardKittner Aerox_5](https://github.com/LennardKittner/Aerox_5)

---

## Minor Pitfalls

---

### Pitfall 13: Naming Your Script `bleak.py`

**What goes wrong:** Script named `bleak.py` in the project root causes circular import — Python imports your file instead of the bleak package. All `import bleak` calls fail with confusing `AttributeError`.

**Prevention:** Name scripts `ble_backend.py`, `ble_client.py`, etc. Never use the same name as a dependency.

**Phase:** Day 1.

**Sources:** [bleak troubleshooting](https://bleak.readthedocs.io/en/latest/troubleshooting.html)

---

### Pitfall 14: PyInstaller --onefile DLL Missing for hidapi

**What goes wrong:** `hid` Python package loads `hidapi.dll` or `libhidapi-0.dll` via ctypes at runtime. PyInstaller does not automatically include this DLL because it is not a Python import. The packaged `.exe` crashes at startup with `ImportError: Unable to load any of the following libraries: ['hidapi.dll', 'libhidapi-0.dll']`.

**Prevention:**
1. Locate the DLL path: typically in `site-packages/hid/` or installed separately.
2. Add to spec file:
   ```python
   binaries=[('path/to/hidapi.dll', '.')]
   ```
3. Use `--collect-binaries hid` if using PyInstaller hooks, or write a custom hook at `hooks/hook-hid.py`.
4. Test the packaged executable on a clean machine (no Python installed) before shipping.

**Detection warning signs:** Works in development virtualenv, fails on clean machine at startup.

**Phase:** Phase 5 (packaging / distribution).

**Sources:** [hidapi issue #267](https://github.com/libusb/hidapi/issues/267), [PyInstaller spec files docs](https://pyinstaller.org/en/stable/spec-files.html)

---

### Pitfall 15: PyInstaller --uac-admin UAC Prompt Silently Does Nothing

**What goes wrong:** You add `--uac-admin` to PyInstaller expecting Windows to prompt for elevation. On many configurations (especially when no icon is specified, or in --onefile mode), the UAC manifest is not properly embedded and the application runs without elevation — HID access that requires admin fails silently.

**Prevention:**
1. HID access for gaming peripherals (vendor-specific interfaces) does NOT require admin on Windows 11 — avoid this requirement by design.
2. Only standard keyboard/mouse interfaces are locked; vendor HID interfaces open fine as a standard user.
3. If elevation truly is needed, use `ShellExecute` with `runas` verb to re-launch self elevated, rather than relying on PyInstaller UAC manifest.

**Phase:** Phase 5 (packaging).

**Sources:** [PyInstaller issue #9341](https://github.com/pyinstaller/pyinstaller/issues/9341), [PyInstaller issue #4752](https://github.com/pyinstaller/pyinstaller/issues/4752)

---

### Pitfall 16: Tight Polling Loop Pegs CPU

**What goes wrong:** You poll HID battery in a `while True: read(); time.sleep(0.01)` loop at 100Hz. Battery level changes at most once per minute. This consumes unnecessary CPU and wakes the CPU from low-power states, reducing laptop battery life.

**Prevention:**
1. Poll at 60-second intervals for battery level — it changes slowly.
2. Use `asyncio.sleep(60)` inside the async polling coroutine (not `time.sleep` which blocks the event loop).
3. Use `asyncio.sleep(0)` only when yielding control within intensive enumeration loops, not as a rate-limiter.

**Phase:** Phase 2-3 (polling implementation).

**Sources:** [asyncio issue #398](https://github.com/python/asyncio/issues/398)

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| HID connectivity PoC | Opening wrong interface (Pitfall 1) | Enumerate all VID/PID interfaces; filter by usage_page |
| HID++ protocol layer | Feature variant mismatch (Pitfall 2), wrong device index (Pitfall 3) | Probe 0x1004→0x1000→0x1001; discover device index dynamically |
| Offline/error handling | Unhandled error 5 crashes thread (Pitfall 4) | Treat error 5 as offline state; do not raise |
| BLE architecture | STA/MTA threading conflict (Pitfall 5), event loop fragmentation (Pitfall 6) | Set `sys.coinit_flags = 0` before all imports; use qasync once |
| SteelSeries backend | Wrong HID call type (Pitfall 12) | Use `hid.write()` + specific byte commands; source from rivalcfg |
| Hot-plug detection | DBT_DEVNODES_CHANGED storm (Pitfall 10) | Use RegisterDeviceNotification with HID GUID; 500ms debounce |
| UI battery display | Categorical-level misrepresentation (Pitfall 8) | Check SOC capability flag; show "~30%" not "30%" when estimated |
| Packaging | Missing hidapi.dll (Pitfall 14), UAC issues (Pitfall 15) | Manual binaries spec entry; vendor HID does not need admin |

---

## Sources

- [bleak troubleshooting docs](https://bleak.readthedocs.io/en/latest/troubleshooting.html)
- [bleak Windows backend docs](https://bleak.readthedocs.io/en/latest/backends/windows.html)
- [libratbag HID++ 2.0 Driver — DeepWiki](https://deepwiki.com/libratbag/libratbag/3.2-logitech-hid++-2.0-driver)
- [Linux kernel hid-logitech-hidpp.c](https://github.com/torvalds/linux/blob/master/drivers/hid/hid-logitech-hidpp.c)
- [LKML patch: Unified Battery 0x1004](https://yhbt.net/lore/all/nycvar.YFH.7.76.2101081438530.13752@cbobk.fhfr.pm/T/)
- [hidapi issue #228 — gaming mouse access denied](https://github.com/libusb/hidapi/issues/228)
- [hidapi issue #135 — non-zero interface](https://github.com/libusb/hidapi/issues/135)
- [Solaar issue #2600 — offline device errors](https://github.com/pwr-Solaar/Solaar/issues/2600)
- [Solaar issue #3036 — hidden firmware features](https://github.com/pwr-Solaar/Solaar/issues/3036)
- [LGSTrayBattery — native HID vs GHUB percentage discrepancy](https://github.com/andyvorld/LGSTrayBattery)
- [flozz Arctis 7 HID gist](https://gist.github.com/flozz/df45b59d6d3594c4b843e00c5df16dd0)
- [Microsoft DBT_DEVNODES_CHANGED docs](https://learn.microsoft.com/en-us/windows/win32/devio/dbt-devnodes-changed)
- [PyInstaller spec files](https://pyinstaller.org/en/stable/spec-files.html)
- [PyInstaller issue #9341 — UAC manifest](https://github.com/pyinstaller/pyinstaller/issues/9341)
- [qasync](https://pypi.org/project/qasync/)
- [bleak discussion #1564 — MAIN_STA](https://github.com/hbldh/bleak/discussions/1564)
- [Logitech HID++ 1.0 spec](https://lekensteyn.nl/files/logitech/logitech_hidpp10_specification_for_Unifying_Receivers.pdf)
