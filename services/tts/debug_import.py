import sys
import os

print(f"Python: {sys.version}")
print(f"CWD: {os.getcwd()}")

try:
    print("Attempting to import torch...")
    import torch
    print(f"Torch version: {torch.__version__}")
    print(f"MPS available: {torch.backends.mps.is_available()}")
except Exception as e:
    print(f"Failed to import torch: {e}")

try:
    print("Attempting to import TTS...")
    from TTS.api import TTS
    print("TTS imported successfully")
except Exception as e:
    print(f"Failed to import TTS: {e}")
    import traceback
    traceback.print_exc()

try:
    print("Checking dependencies...")
    import numpy
    print(f"Numpy: {numpy.__version__}")
    import scipy
    print(f"Scipy: {scipy.__version__}")
except Exception as e:
    print(f"Dependency check failed: {e}")
