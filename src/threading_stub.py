import sys
sys.coinit_flags = 0  # MUST be here — before any other import. pythoncom reads this flag once on first COM init; PySide6 imports must not precede it. 0 = COINIT_MULTITHREADED (MTA); required for bleak WinRT backend.

import asyncio
import queue
import threading
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import QTimer

# Module-level shared cross-thread queue.
# This is the ONLY communication channel between threads.
# asyncio background thread calls ui_queue.put(); Qt main thread calls ui_queue.get_nowait().
# Do NOT use asyncio's Queue class here — it is not thread-safe across threads (only safe within one event loop).
ui_queue: queue.Queue = queue.Queue()


async def background_task(loop: asyncio.AbstractEventLoop) -> None:
    """Simulates async I/O work on the background thread. Posts one message and stops the loop."""
    await asyncio.sleep(0.5)          # simulate async I/O latency
    ui_queue.put("hello from asyncio")  # thread-safe: queue.Queue.put() is always safe
    loop.call_soon_threadsafe(loop.stop)  # signal the loop to stop after this coroutine


def run_background(loop: asyncio.AbstractEventLoop) -> None:
    """Entry point for the daemon background thread. Runs the asyncio event loop."""
    asyncio.set_event_loop(loop)
    loop.run_forever()
    # run_forever() blocks until loop.stop() is called.
    # After stop(), any pending callbacks complete, then this function returns.


def drain_queue(label: QLabel) -> None:
    """Called by QTimer every 500ms on the Qt main thread. Drains all pending messages."""
    try:
        while True:
            msg = ui_queue.get_nowait()  # raises queue.Empty when nothing left
            label.setText(f"Received: {msg}")
            print(f"[main thread] drain_queue: {msg}")
    except queue.Empty:
        pass  # normal: nothing to drain this tick


def main() -> None:
    app = QApplication([])

    # Create a minimal window to show the received message
    window = QWidget()
    window.setWindowTitle("Threading Stub PoC")
    layout = QVBoxLayout(window)
    label = QLabel("Waiting...")
    layout.addWidget(label)
    window.show()

    # Start asyncio background thread (daemon=True so it does not block process exit)
    bg_loop = asyncio.new_event_loop()
    bg_thread = threading.Thread(target=run_background, args=(bg_loop,), daemon=True)
    bg_thread.start()

    # Submit the background coroutine from the main thread (thread-safe)
    # run_coroutine_threadsafe returns a Future; we discard it here (fire and forget for PoC)
    asyncio.run_coroutine_threadsafe(background_task(bg_loop), bg_loop)

    # QTimer drains the queue on the main thread every 500ms
    timer = QTimer()
    timer.timeout.connect(lambda: drain_queue(label))
    timer.start(500)

    # Auto-close the window 2 seconds after the message arrives so the PoC exits without user action
    # This is achieved by connecting a second QTimer that fires once after 2500ms
    close_timer = QTimer()
    close_timer.setSingleShot(True)
    close_timer.timeout.connect(app.quit)
    close_timer.start(2500)  # 500ms for message + 2000ms for human to observe

    app.exec()

    # Clean shutdown: stop the asyncio loop and wait for the thread to exit
    # This is the canonical shutdown sequence — do not skip join()
    bg_loop.call_soon_threadsafe(bg_loop.stop)
    bg_thread.join(timeout=5.0)
    if bg_thread.is_alive():
        print("[main] WARNING: background thread did not stop within 5 seconds")
    else:
        print("[main] background thread joined cleanly")


if __name__ == "__main__":
    main()
