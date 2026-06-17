import sys
sys.coinit_flags = 0

import asyncio
from monitor.bt_backend import winrt_enumerate_bt

async def main():
    print("Running winrt_enumerate_bt()...")
    devices = await winrt_enumerate_bt()
    print(f"Enumerated {len(devices)} Bluetooth devices:")
    for d in devices:
        print(f"- Name: {d['name']}")
        print(f"  ID: {d['id']}")
        print(f"  Connected: {d['connected']}")
        print(f"  Address: {d['ble_address']}")
        print(f"  Battery pre-fetch: {d['battery']}")

if __name__ == "__main__":
    asyncio.run(main())
