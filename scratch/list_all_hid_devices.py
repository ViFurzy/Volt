import hid

def main():
    print("=== Listing ALL connected HID devices ===")
    devices = hid.enumerate(0, 0)
    seen = set()
    for d in devices:
        vid = d['vendor_id']
        pid = d['product_id']
        iface = d.get('interface_number', -1)
        usage_page = d.get('usage_page', 0)
        prod = d.get('product_string', 'Unknown')
        mfg = d.get('manufacturer_string', 'Unknown')
        
        key = (vid, pid, iface)
        if key not in seen:
            seen.add(key)
            print(f"VID: 0x{vid:04X} | PID: 0x{pid:04X} | Iface: {iface} | UsagePage: 0x{usage_page:04X} | Mfg: {mfg} | Prod: {prod}")

if __name__ == "__main__":
    main()
