import sys
sys.coinit_flags = 0  # MUST be here — before any other import. pythoncom reads this flag exactly once on first COM init. PySide6/pywin32 imports initialize COM as STA; bleak WinRT backend requires MTA. If STA is set first, await client.connect() hangs forever silently.

import threading
import asyncio
import queue


def main() -> None:
    print("PeriphWatcher __main__ loaded")


if __name__ == "__main__":
    main()
