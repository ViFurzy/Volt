"""
monitor — Phase 3 background service package for Volt.

Provides DeviceState, DeviceStatus, KNOWN_DEVICES (state.py), DeviceRegistry
(registry.py), and the MonitorService polling loop (service.py). Architecture
invariant: all cross-thread DeviceState updates flow through queue.Queue only —
the asyncio background thread puts snapshots; the Qt main thread drains them via
QTimer. Direct method calls across the thread boundary are forbidden.
"""
