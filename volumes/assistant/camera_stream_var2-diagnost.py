# volumes/assistant/camera_stream.py

import sys
import os

print("=== PYTHON DIAGNOSTIC ===")
print("executable:", sys.executable)
print("version:", sys.version)
print("cwd:", os.getcwd())
print("path:")
for p in sys.path:
    print(" -", p)

try:
    import flask
    print("FLASK OK:", flask.__version__)
except Exception as e:
    print("FLASK FAIL:", repr(e))

try:
    import camera_controller
    print("camera_controller OK")
except Exception as e:
    print("camera_controller FAIL:", repr(e))
