# Feature Landscape

**Domain:** Windows background utility — wireless gaming peripheral battery monitor
**Researched:** 2026-06-01
**Sources:** Solaar (Linux), LGSTrayBattery, SteelSeries battery tray apps, Bluetooth Battery Monitor (bluetoothgoodies.com), Microsoft PowerToys issue #28614, community discussions

---

## Table Stakes

Features users expect from any peripheral battery monitor. Missing = product feels incomplete or broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Battery percentage display | Core purpose; integer % is the universal mental model | Low | Raw HID value is already 0–100 in most protocols |
| System tray icon | Background utilities must live in tray; no other pattern is acceptable | Low | Icon should encode battery level visually, not just be a static logo |
| Tooltip on hover | Standard tray app interaction; shows device name + % without opening UI | Low | Multi-device: list all devices in tooltip |
| Low battery notification | Users must know before peripheral dies mid-session | Low-Med | One notification at threshold; do not repeat every poll cycle |
| Auto-start with Windows | Utility is useless if you must remember to launch it | Low | Registry run key or Task Scheduler; offer as opt-in during first run |
| Device name display | "Device 1" is not acceptable; show "G Pro X Wireless" or user-set alias | Low | Pull from HID product string or hardcode known devices |
| Charging status indicator | Users want to know if device is on charger vs draining | Med | Not all HID reports expose this; mark "unknown" if not available |
| Minimize / close to tray | Closing the window should not kill the app | Low | Window X button hides to tray; tray menu has "Quit" |
| Multiple device support | Users commonly have mouse + headset both wireless | Low | Each device gets its own row / tray entry |

---

## Differentiators

Features that elevate the app from functional to excellent. Not universally expected, but clearly valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Numeric % in tray icon | Removes need to hover; fastest possible glance-check | Med | Render % as 16×16 or 32×32 text icon; Windows 11 itself now ships this for laptop battery |
| Color-coded tray icon | Green/yellow/red encodes urgency instantly (traffic-light semantics) | Low | Green >40%, yellow 20–40%, red <20% — thresholds configurable |
| Configurable alert threshold | Default 15% is wrong for half the users; some want 25%, others 5% | Low | Per-device threshold is ideal but single global threshold is acceptable MVP |
| Last-seen / last-polled timestamp | Confirms the reading is fresh, not stale from before device was pocketed | Low | "Updated 2 min ago" in tooltip or main window |
| Main window device cards | Visual summary beyond the tray; useful when checking before leaving desk | Med | Card per device: name, %, charging badge, last-seen |
| Notification snooze / cooldown | Prevents alert spam when device sits below threshold for hours | Low | After first alert, suppress repeats for N hours (e.g. 4h) |
| Device offline / disconnected state | Distinguish "battery unknown" from "device not responding" | Med | Show greyed icon or "offline" badge rather than stale % |
| Dark/light theme follow | Tray icon must be legible on both dark and light taskbars | Low | Use adaptive icon colors or offer both variants |
| Per-device polling interval | Power users want faster updates; others want lower CPU overhead | Low | Default 60s; allow 15s–300s range |
| Startup notification summary | On app launch, show a brief toast listing all device statuses | Low | Useful first thing in the morning; opt-in |

---

## Anti-Features

Features that add complexity, maintenance burden, or user annoyance without proportional value. Explicitly avoid these.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Device settings / remapping | Scope creep; Logitech GHUB and OpenRGB already do this far better | Read-only battery data only |
| RGB lighting control | Completely orthogonal to battery monitoring; attracts massive maintenance burden | Out of scope entirely |
| Battery health analytics / graphs | Wireless peripheral batteries are not user-serviceable; historical data provides no actionable insight | Show current % only |
| Cloud sync / account login | A battery monitor requires no cloud; account systems are trust barriers | Local-only, no telemetry |
| Repeated low-battery notifications | Notifying every poll cycle once below threshold is the #1 user complaint across all platform discussions | Fire once per crossing event, then snooze |
| Manufacturer software detection / launch | Fragile, brittle; GHUB install path changes, version detection breaks | Operate fully independently of manufacturer software |
| Auto-update mechanism | Adds background network calls and complexity for a simple utility | Ship as installable; let user update manually |
| Sound alerts | Jarring for a background utility; Windows toast notifications are already audio-capable if user has that enabled | Rely on Windows notification sound settings |
| Predictive "time remaining" | Peripheral batteries have wildly inconsistent drain curves; predicted time is usually wrong and erodes trust | Show % only; do not predict |
| Signal strength display | Not exposed by HID++ or SteelSeries HID protocols at the level accessible without manufacturer SDK | Omit; show connection status (connected/disconnected) only |

---

## Feature Dependencies

```
Auto-start with Windows
  └── Minimize to tray on close (required: must not open a window on startup)

Low battery notification
  └── Configurable threshold (notification fires at threshold)
  └── Notification snooze/cooldown (prevents repeat spam)

Numeric % in tray icon
  └── Per-device tray icon (one icon per device, or combined)

Main window device cards
  └── Device name display
  └── Charging status indicator
  └── Last-seen timestamp
  └── Battery percentage display

Color-coded tray icon
  └── Battery percentage display (needs % to pick color band)
```

---

## MVP Recommendation

**Build first (table stakes + highest-leverage differentiators):**

1. Tray icon per device with color coding (green/yellow/red)
2. Tooltip on hover — device name + battery %
3. Low battery toast notification at configurable threshold (default 15%), with 4-hour snooze
4. Charging status badge (if HID data exposes it; "unknown" otherwise)
5. Minimize / close to tray; tray right-click menu with "Open" and "Quit"
6. Auto-start with Windows (opt-in, set during first run or in settings)
7. Main window with per-device cards showing %, charging state, last-polled time

**Defer to later iteration:**

- Numeric % rendered into the tray icon itself (non-trivial on Windows without a custom icon renderer, but very high user value — do in phase 2)
- Per-device configurable poll interval
- Startup notification summary
- Dark/light theme adaptive icons

---

## Notification / Alert Pattern Detail

Based on cross-platform community research, the following pattern avoids both under-notification and alert spam:

1. **Single crossing event trigger:** Notify when % drops *through* the threshold (e.g. 21% → 19% with threshold=20%). Do not notify if the app starts and device is already below threshold (user already knows).
2. **Cooldown window:** After firing, suppress further notifications for that device for 4 hours or until the device charges above threshold and drops again.
3. **Content:** "G Pro X Wireless battery is low (18%). Plug in to charge." — specific, actionable, non-alarmist.
4. **No sound override:** Respect Windows Focus Assist / Do Not Disturb. Use standard `winsdk` toast; do not play custom sounds.
5. **No repeated OS nags:** One notification. If user dismisses it, that is their decision.

---

## Device Status UI: What to Show

Beyond battery percentage, the following data points are consistently valued (sourced from Solaar, LGSTrayBattery, bluetoothgoodies.com, PowerToys issue discussion):

| Data Point | Source | Fallback if Unavailable |
|------------|--------|------------------------|
| Battery % | HID report | "—" (em dash) |
| Charging status | HID report (not always present) | "Unknown" badge |
| Device name | HID product string | Hardcoded map by VID/PID |
| Connection state | Poll success/failure | "Offline" with grey icon |
| Last polled | App internal clock | Always available |
| Signal strength / RSSI | NOT exposed via HID++ or standard HID | Omit entirely |
| Individual pod/case levels (earbuds) | Vendor-specific; not applicable to mouse/keyboard | N/A for this project's devices |

**Explicitly out of scope for this project's target devices (G Pro X Wireless, Aerox 5 Wireless):**
- Signal strength (not in accessible HID reports)
- Voltage (raw voltage available on some Logitech devices via LGSTrayBattery; display only if easily accessible, otherwise omit)
- Firmware version
- DPI / sensitivity settings

---

## Sources

- [Solaar Usage Documentation](https://pwr-solaar.github.io/Solaar/usage/) — Logitech Linux manager; reference for device status UI patterns
- [LGSTrayBattery (GitHub)](https://github.com/andyvorld/LGSTrayBattery) — Windows Logitech tray app; numeric icon, tooltip, HTTP API patterns
- [SteelSeries Wireless Battery Tray (GitHub)](https://github.com/mtadin/steelseries-wireless-battery-tray) — dynamic % icon in tray, context menu patterns
- [Bluetooth Battery Monitor](https://www.bluetoothgoodies.com/) — multi-device consolidated view, color-coded tray icon
- [Microsoft PowerToys Issue #28614](https://github.com/microsoft/PowerToys/issues/28614) — user expectations: separate icons per device, color customization, native feel
- [aarol.dev Arctis HID post](https://aarol.dev/posts/arctis-hid/) — what device status data is actually accessible at HID level
- Community discussions on Apple, HP, Android forums — notification spam as primary complaint pattern
