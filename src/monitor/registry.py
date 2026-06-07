"""
Thread-safe DeviceState store for Volt.

DeviceRegistry is shared between the asyncio background thread (writes via upsert)
and the Qt main thread (reads via get/all). Every method acquires a threading.Lock
before touching the internal dict — this matches the threading model in
threading_stub.py where queue.Queue is the only cross-thread channel, but registry
reads from the main thread (e.g. building the UI snapshot) are safe under a lock.
"""

import dataclasses
import threading

from monitor.state import DeviceState, DeviceStatus


class DeviceRegistry:
    """Thread-safe store keyed by (vid, pid, dev_idx).

    All public methods are safe to call from any thread. They acquire
    self._lock for their entire body, then release it on exit.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._devices: dict[tuple[int, int, int], DeviceState] = {}

    def upsert(self, state: DeviceState) -> None:
        """Store `state` under its (vid, pid, dev_idx) key; overwrites if present."""
        key = (state.vid, state.pid, state.dev_idx)
        with self._lock:
            self._devices[key] = state

    def get(self, key: tuple[int, int, int]) -> DeviceState | None:
        """Return the stored DeviceState for `key`, or None if not present."""
        with self._lock:
            return self._devices.get(key)

    def all(self) -> list[DeviceState]:
        """Return a snapshot copy of all stored DeviceState values.

        Returns a new list — not a live view — so callers can iterate without
        holding the lock and without risking concurrent-mutation errors.
        """
        with self._lock:
            return list(self._devices.values())

    def mark_offline(self, key: tuple[int, int, int]) -> DeviceState | None:
        """Set the stored device to OFFLINE and clear its percent.

        Uses dataclasses.replace() to produce an immutable snapshot copy with
        status=OFFLINE and percent=None, then stores and returns it.
        Returns None if `key` is not present (idempotent absent-key behaviour).

        This is the HID-04 teardown helper consumed by the hot-plug unplug path
        in plan 03-03.
        """
        with self._lock:
            existing = self._devices.get(key)
            if existing is None:
                return None
            updated = dataclasses.replace(
                existing, status=DeviceStatus.OFFLINE, percent=None
            )
            self._devices[key] = updated
            return updated
