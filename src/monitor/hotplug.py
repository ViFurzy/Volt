"""
HotPlugWatcher — Win32 WM_DEVICECHANGE listener for PeriphWatcher.

Creates a hidden QWidget solely to own a Win32 HWND for RegisterDeviceNotificationW.
Intercepts WM_DEVICECHANGE / DBT_DEVNODES_CHANGED on the Qt main thread and debounces
the 5-6 duplicate events per plug/unplug into a single MonitorService.rescan() call.

Architecture invariants (from CLAUDE.md):
  - WM_DEVICECHANGE is received on the Qt main thread; this file NEVER calls HID
    functions or battery_probe_chain directly.
  - Debounce timer is armed via call_soon_threadsafe → call_later so call_later is
    always invoked on the asyncio bg loop, never from the Qt thread (T-03-07).
  - unregister() releases the Win32 notification handle on teardown (T-03-08).
"""

import asyncio
import ctypes
import ctypes.wintypes
import logging

from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Win32 constants
# ---------------------------------------------------------------------------
WM_DEVICECHANGE = 0x0219
DBT_DEVNODES_CHANGED = 0x0007
DBT_DEVTYP_DEVICEINTERFACE = 0x00000005
DEVICE_NOTIFY_WINDOW_HANDLE = 0x00000000
DEVICE_NOTIFY_ALL_INTERFACE_CLASSES = 0x00000004


# ---------------------------------------------------------------------------
# ctypes structure for RegisterDeviceNotificationW
# ---------------------------------------------------------------------------
class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class _DEV_BROADCAST_DEVICEINTERFACE(ctypes.Structure):
    _fields_ = [
        ("dbcc_size", ctypes.c_ulong),
        ("dbcc_devicetype", ctypes.c_ulong),
        ("dbcc_reserved", ctypes.c_ulong),
        ("dbcc_classguid", _GUID),
        ("dbcc_name", ctypes.c_wchar),
    ]


# ---------------------------------------------------------------------------
# _Debouncer: standalone asyncio-loop-based cancel+reschedule helper
# ---------------------------------------------------------------------------

class _Debouncer:
    """Collapse repeated schedule() calls within `seconds` into a single callback.

    Runs entirely on the asyncio loop — the owner (HotPlugWatcher) arms it from the
    Qt main thread via loop.call_soon_threadsafe(debouncer.schedule).

    No PySide6 dependency; easily unit-tested with a plain asyncio.new_event_loop().
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        seconds: float,
        callback,  # callable with no args, invoked on the loop after debounce
    ) -> None:
        self._loop = loop
        self._seconds = seconds
        self._callback = callback
        self._handle: asyncio.TimerHandle | None = None

    def schedule(self) -> None:
        """Cancel any pending timer and arm a fresh one. MUST run on the asyncio loop."""
        if self._handle is not None:
            self._handle.cancel()
        self._handle = self._loop.call_later(self._seconds, self._fire)

    def _fire(self) -> None:
        """Invoked by call_later after the debounce window. Runs on the asyncio loop."""
        self._handle = None
        self._callback()


# ---------------------------------------------------------------------------
# HotPlugWatcher
# ---------------------------------------------------------------------------

class HotPlugWatcher(QWidget):
    """Hidden QWidget that owns a Win32 HWND for device-change notifications.

    Lifecycle:
        watcher = HotPlugWatcher(service)
        watcher.register()          # call after QApplication exists
        ...
        watcher.unregister()        # call before shutdown
    """

    def __init__(self, service, debounce_seconds: float = 0.5) -> None:
        super().__init__()
        self._service = service
        self._debounce_seconds = debounce_seconds
        self._notify_handle = None
        # _Debouncer lives on the bg asyncio loop; arms via call_soon_threadsafe
        self._debouncer = _Debouncer(
            loop=service._loop,
            seconds=debounce_seconds,
            callback=self._fire_rescan,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self) -> None:
        """Register for WM_DEVICECHANGE using this widget's HWND.

        Must be called after QApplication has been created (so winId() is valid).
        """
        hwnd = int(self.winId())

        notify_filter = _DEV_BROADCAST_DEVICEINTERFACE()
        notify_filter.dbcc_size = ctypes.sizeof(_DEV_BROADCAST_DEVICEINTERFACE)
        notify_filter.dbcc_devicetype = DBT_DEVTYP_DEVICEINTERFACE
        notify_filter.dbcc_reserved = 0

        flags = DEVICE_NOTIFY_WINDOW_HANDLE | DEVICE_NOTIFY_ALL_INTERFACE_CLASSES
        handle = ctypes.windll.user32.RegisterDeviceNotificationW(
            hwnd,
            ctypes.byref(notify_filter),
            flags,
        )
        if not handle:
            err = ctypes.get_last_error()
            logger.error(
                "RegisterDeviceNotificationW failed (error %d) — hot-plug disabled", err
            )
            return
        self._notify_handle = handle
        logger.debug("RegisterDeviceNotificationW succeeded (handle=%s)", handle)

    def unregister(self) -> None:
        """Release the notification handle. Call on application teardown (T-03-08)."""
        if self._notify_handle is not None:
            ctypes.windll.user32.UnregisterDeviceNotification(self._notify_handle)
            self._notify_handle = None

    # ------------------------------------------------------------------
    # Qt event override
    # ------------------------------------------------------------------

    def nativeEvent(self, eventType, message):
        """Intercept WM_DEVICECHANGE / DBT_DEVNODES_CHANGED from the Win32 message pump."""
        if eventType == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_DEVICECHANGE and msg.wParam == DBT_DEVNODES_CHANGED:
                self._schedule_rescan()
        return super().nativeEvent(eventType, message)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _schedule_rescan(self) -> None:
        """Cross-thread debounce arm: posts _debouncer.schedule onto the bg asyncio loop.

        call_later is NOT thread-safe from the Qt thread (T-03-07), so we use
        call_soon_threadsafe to hand off to the loop, where _Debouncer.schedule()
        then calls call_later safely.
        """
        self._service._loop.call_soon_threadsafe(self._debouncer.schedule)

    def _fire_rescan(self) -> None:
        """Runs on the asyncio loop after the debounce window; triggers service.rescan()."""
        self._service.rescan()
