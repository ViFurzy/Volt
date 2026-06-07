"""HID++ 2.0 low-level protocol: message construction, send/receive, error detection."""

REPORT_ID_SHORT = 0x10
REPORT_ID_LONG  = 0x11
ERROR_SENTINEL  = 0xFF   # response[2] == ERROR_SENTINEL signals a HID++ 2.0 error
ERROR_OFFLINE   = 0x05   # LOGITECH_INTERNAL — device off or out of range
ERROR_BUSY      = 0x08   # device temporarily busy — retry


class HIDppError(Exception):
    def __init__(self, code: int) -> None:
        self.code = code
        super().__init__(f"HID++ error 0x{code:02X}")


def build_short_msg(
    device_idx: int,
    feature_idx: int,
    function: int,
    params: tuple = (0, 0, 0),
) -> list[int]:
    """Return a 7-byte HID++ short message. software_id nibble is always 0x01."""
    return [REPORT_ID_SHORT, device_idx, feature_idx, (function << 4) | 0x01, params[0], params[1], params[2]]


def send_and_recv(
    device,
    msg: list[int],
    timeout_ms: int = 100,
    min_len: int = 7,
) -> list[int] | None:
    """
    Write msg to device and read the response.

    Returns None on timeout or short/malformed response.
    Raises HIDppError when response[2] == ERROR_SENTINEL.
    Raises OSError on hidapi write/read failure.
    """
    try:
        device.write(msg)
    except OSError:
        raise

    try:
        response = device.read(20, timeout_ms=timeout_ms)
    except OSError:
        raise

    if not response:
        return None

    response = list(response)

    if len(response) < min_len:
        return None

    if response[2] in (0x8F, ERROR_SENTINEL):
        raise HIDppError(response[5])

    return response

