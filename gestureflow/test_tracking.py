import time
from gesture_engine import GestureEngine

engine = GestureEngine()
engine.start()

print("Engine started. Show your hand to the camera.")
try:
    for _ in range(50):
        frame = engine.process_frame()
        if frame is not None:
            # We just want to see if process_frame throws an error internally or prints something
            pass
        time.sleep(0.1)
except KeyboardInterrupt:
    pass
finally:
    engine.stop()
    print("Test complete.")
