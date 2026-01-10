
import os
import torch
from TTS.api import TTS
import time

print("Checking MPS availability...")
if torch.backends.mps.is_available():
    print("MPS is available!")
    device = "mps"
else:
    print("MPS not available, using cpu")
    device = "cpu"

print(f"Loading TTS model on {device}...")
try:
    # Set env vars to avoid download issues
    os.environ["COQUI_TOS_AGREED"] = "1"
    
    start_time = time.time()
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    tts.to(device)
    print(f"Model loaded in {time.time() - start_time:.2f}s")
    
    print("Synthesizing text...")
    start_time = time.time()
    tts.tts_to_file(text="Hello world! This is a test of MPS on Mac.", 
                    file_path="/tmp/mps_test.wav",
                    speaker_wav="services/tts/voices/default.wav" if os.path.exists("services/tts/voices/default.wav") else None,
                    language="en")
    print(f"Synthesis complete in {time.time() - start_time:.2f}s")
    
except Exception as e:
    print(f"Error: {e}")
