import sys
import asyncio
import os
sys.path.insert(0, 'src')
from monitor.service import MonitorService
import queue
from monitor.registry import DeviceRegistry

async def main():
    ui_queue = queue.Queue()
    registry = DeviceRegistry()
    service = MonitorService(ui_queue, registry)
    print("Starting discover...")
    try:
        await service.discover()
        print("Discover done!")
    except Exception as e:
        import traceback
        traceback.print_exc()
        
    while not ui_queue.empty():
        print("Queue item:", ui_queue.get())

if __name__ == '__main__':
    asyncio.run(main())
