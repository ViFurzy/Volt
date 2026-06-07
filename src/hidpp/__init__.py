"""
HID++ 2.0 protocol implementation for Volt.

Provides message construction, send/receive, feature discovery, and battery probe
chain over the hidapi (usage_page=0xFF00) vendor-specific interface. All HID device
handles must be opened via open_path() after filtering for usage_page=0xFF00 — the
primary mouse/keyboard interface (usage_page=0x0001) is locked by Windows.
"""
