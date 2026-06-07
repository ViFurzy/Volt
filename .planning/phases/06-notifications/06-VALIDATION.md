---
phase: "06"
phase_slug: "notifications"
date: "2026-06-04"
status: pending
---

# Phase 06 — Validation Strategy

## Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | `pytest.ini` (testpaths = tests, pythonpath = src) |
| Quick run command | `pytest tests/test_notification_manager.py -x` |
| Full suite command | `pytest tests/ -x` |

## Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | Plan |
|--------|----------|-----------|-------------------|------|
| NOTIF-01 | Toast fires when percent < threshold (first crossing) | unit | `pytest tests/test_notification_manager.py::test_fires_on_threshold_crossing -x` | 06-01 |
| NOTIF-01 | No toast when percent >= threshold | unit | `pytest tests/test_notification_manager.py::test_no_fire_above_threshold -x` | 06-01 |
| NOTIF-01 | No toast when percent is None (charging/offline) | unit | `pytest tests/test_notification_manager.py::test_no_fire_when_percent_none -x` | 06-01 |
| NOTIF-01 | Default threshold is 15% when no config entry | unit | `pytest tests/test_notification_manager.py::test_default_threshold -x` | 06-01 |
| NOTIF-02 | No second toast within cooldown window | unit | `pytest tests/test_notification_manager.py::test_cooldown_suppresses -x` | 06-01 |
| NOTIF-02 | Toast fires again after cooldown expires | unit | `pytest tests/test_notification_manager.py::test_fires_after_cooldown -x` | 06-01 |
| NOTIF-02 | Cooldown clears when device goes OFFLINE | unit | `pytest tests/test_notification_manager.py::test_cooldown_resets_on_offline -x` | 06-01 |
| NOTIF-01+02 | Toast visible in Action Center on hardware | manual | hardware checkpoint in 06-03 | 06-03 |

## Sampling Rate

- **Per task commit:** `pytest tests/test_notification_manager.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

## Coverage Gaps

- [ ] `tests/test_notification_manager.py` — created in Wave 1 (06-01)
- [ ] Windows 11 AUMID behavior — confirmed at hardware checkpoint (06-03 Task 1)

## Dimension 8 Checklist

- [ ] All NOTIF-01 unit tests passing
- [ ] All NOTIF-02 unit tests passing
- [ ] Full suite (`pytest tests/ -x`) green after Wave 2
- [ ] Hardware checkpoint (06-03) passed with toast visible in Action Center
