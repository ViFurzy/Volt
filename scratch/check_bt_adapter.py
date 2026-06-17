import sys
sys.coinit_flags = 0

import asyncio
from winrt.windows.devices.bluetooth import BluetoothAdapter

async def main():
    print("Querying default Bluetooth adapter...")
    try:
        adapter = await BluetoothAdapter.get_default_async()
        if adapter:
            print("Bluetooth Adapter found:")
            print(f"  Device ID: {adapter.device_id}")
            print(f"  Is Low Energy supported: {adapter.is_low_energy_supported}")
            print(f"  Is Central Role supported: {adapter.is_central_role_supported}")
        else:
            print("No Bluetooth Adapter found on this PC (get_default_async returned None).")
    except Exception as e:
        print(f"Error querying Bluetooth adapter: {e}")

if __name__ == "__main__":
    asyncio.run(main())
