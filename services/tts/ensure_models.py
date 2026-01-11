#!/usr/bin/env python3
"""
Ensure TTS models are downloaded.
This script checks if the XTTS v2 model is present and downloads it if not.
"""
import os
import sys
from pathlib import Path
import structlog
import torch

# Configure logger
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

def ensure_models():
    """Download TTS models if missing."""
    model_path = os.getenv("TTS_MODEL_PATH", "/app/models")
    logger.info("Checking for TTS models", path=model_path)
    
    try:
        # Import Coqui TTS
        from TTS.api import TTS
        
        # Check if we need to accept license
        os.environ["COQUI_TOS_AGREED"] = "1"
        
        # Initialize TTS to trigger download
        # We use a specific model name to ensure consistency
        model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
        
        logger.info("Initializing TTS to ensure model download...")
        TTS(model_name=model_name, progress_bar=True)
        
        logger.info("TTS models verified successfully")
        return True
        
    except Exception as e:
        logger.error("Failed to ensure TTS models", error=str(e))
        return False

if __name__ == "__main__":
    success = ensure_models()
    sys.exit(0 if success else 1)
