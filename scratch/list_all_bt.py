import sys
sys.coinit_flags = 0

import asyncio
from winrt.windows.devices.enumeration import DeviceInformation, DeviceInformationKind

async def main():
    props = [
        "System.ItemNameDisplay",
        "System.Devices.Aep.IsConnected",
        "System.Devices.Aep.IsPaired",
        "System.Devices.Aep.ContainerId",
        "System.Devices.Aep.DeviceAddress",
    ]
    
    print("Querying Bluetooth Association Endpoints (AEP)...")
    try:
        # AQS filter for Bluetooth devices
        aqs_filter = "System.Devices.Aep.ProtocolId:=\"{e0cbf06c-cd8b-4647-bb8a-263b43f0f974}\""
        devices = await DeviceInformation.find_all_async_with_kind_aqs_filter_and_additional_properties(
            aqs_filter, props, DeviceInformationKind.ASSOCIATION_ENDPOINT
        )
        print(f"Found {len(devices)} Bluetooth endpoints.")
        
        from winrt.windows.foundation import IPropertyValue
        
        for d in devices:
            name = d.properties.get("System.ItemNameDisplay")
            if name:
                try:
                    name_str = name.as_(IPropertyValue).get_string() if hasattr(name, "as_") else str(name)
                except Exception:
                    name_str = str(name)
                
                # Check for Logitech, Logi, Pop, Mouse, Keyboard
                name_lower = name_str.lower()
                is_target = any(word in name_lower for word in ["logi", "pop", "mouse", "keyboard", "key", "stadia", "headset"])
                
                # Get connection status
                connected = False
                conn_prop = d.properties.get("System.Devices.Aep.IsConnected")
                if conn_prop:
                    try:
                        connected = conn_prop.as_(IPropertyValue).get_boolean() if hasattr(conn_prop, "as_") else bool(conn_prop)
                    except Exception:
                        connected = bool(conn_prop)
                        
                paired = False
                paired_prop = d.properties.get("System.Devices.Aep.IsPaired")
                if paired_prop:
                    try:
                        paired = paired_prop.as_(IPropertyValue).get_boolean() if hasattr(paired_prop, "as_") else bool(paired_prop)
                    except Exception:
                        paired = bool(paired_prop)
                        
                addr = ""
                addr_prop = d.properties.get("System.Devices.Aep.DeviceAddress")
                if addr_prop:
                    try:
                        addr = addr_prop.as_(IPropertyValue).get_string() if hasattr(addr_prop, "as_") else str(addr_prop)
                    except Exception:
                        addr = str(addr_prop)
                
                if is_target or connected or paired:
                    print(f"- Name: {name_str} | Address: {addr} | Connected: {connected} | Paired: {paired}")
                    
    except Exception as e:
        print(f"Query failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
