try:
    from logitech_receiver.hidpp20_constants import ErrorCode
    print("logitech_receiver ErrorCodes:")
    for x in ErrorCode:
        print(f"  {x.name}: 0x{x.value:02X}")
except Exception as e:
    print("Could not import from logitech_receiver:", e)

try:
    from solaar.hidpp20_constants import ErrorCode
    print("solaar ErrorCodes:")
    for x in ErrorCode:
        print(f"  {x.name}: 0x{x.value:02X}")
except Exception as e:
    print("Could not import from solaar:", e)
