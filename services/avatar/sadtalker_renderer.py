"""
SadTalker Renderer - Wrapper for SadTalker model integration.

This module provides a high-level interface for the SadTalker model,
enabling emotion-aware facial expressions and natural head movements.
"""

import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any
import numpy as np
import cv2

# PATCH: Fix numpy compatibility for legacy code (SadTalker/libs)
if not hasattr(np, 'float'):
    np.float = float
if not hasattr(np, 'int'):
    np.int = int
import structlog
import shutil
import tempfile

logger = structlog.get_logger()

# Add SadTalker source to path
SADTALKER_SRC = Path(__file__).parent / "models" / "sadtalker_src"
if SADTALKER_SRC.exists():
    sys.path.insert(0, str(SADTALKER_SRC)) 
    sys.path.insert(0, str(SADTALKER_SRC / "src"))

class SadTalkerRenderer:
    """Wrapper for SadTalker model."""
    
    def __init__(self, model_path: str = "models/sadtalker", device: str = "cpu", resolution: int = 256):
        self.model_path = Path(model_path)
        self.device = device
        self.resolution = resolution
        self._initialized = False
        logger.info("SadTalkerRenderer created", device=device, resolution=resolution)
    
    async def initialize(self):
        if self._initialized: return
        try:
            logger.info("Loading SadTalker models...")
            from src.utils.preprocess import CropAndExtract
            from src.test_audio2coeff import Audio2Coeff  
            from src.facerender.animate import AnimateFromCoeff
            from src.utils.init_path import init_path
            
            checkpoint_dir = self.model_path / "checkpoints"
            config_dir = SADTALKER_SRC / "src" / "config"
            
            self.sadtalker_paths = init_path(str(checkpoint_dir), str(config_dir), self.resolution, False, 'full')
            self.preprocess_model = CropAndExtract(self.sadtalker_paths, self.device)
            self.audio_to_coeff = Audio2Coeff(self.sadtalker_paths, self.device)
            self.animate_from_coeff = AnimateFromCoeff(self.sadtalker_paths, self.device)
            
            self._initialized = True
            logger.info("SadTalker models loaded successfully")
        except Exception as e:
            logger.error("Failed to initialize SadTalker", error=str(e))
            raise RuntimeError(f"SadTalker initialization failed: {e}")
    
    async def render(self, avatar_image: np.ndarray, audio_path: str, emotion: str = "neutral", expression_scale: float = 1.0, head_pose_scale: float = 1.0, output_path: Optional[str] = None, enhancer: str = "gfpgan", preprocess: str = "full", still: bool = True) -> str:
        if not self._initialized: await self.initialize()
        
        logger.info("Rendering with SadTalker", emotion=emotion, enhancer=enhancer, preprocess=preprocess, still=still)
        from src.generate_batch import get_data
        from src.generate_facerender_batch import get_facerender_data
        
        temp_dir = tempfile.mkdtemp()
        try:
            pic_path = os.path.join(temp_dir, "source.png")
            cv2.imwrite(pic_path, avatar_image)
            save_dir = os.path.join(temp_dir, "results")
            os.makedirs(save_dir, exist_ok=True)
            
            # Preprocess
            first_frame_dir = os.path.join(save_dir, 'first_frame_dir')
            os.makedirs(first_frame_dir, exist_ok=True)
            # Use same preprocess mode for extraction
            first_coeff_path, crop_pic_path, crop_info = self.preprocess_model.generate(pic_path, first_frame_dir, preprocess, True, self.resolution)
            if first_coeff_path is None: raise RuntimeError("Failed to extract coeffs")

            # Run blocking inference in a separate thread to avoid blocking the event loop
            def run_inference():
                # Audio to Coeff
                batch = get_data(first_coeff_path, audio_path, self.device, ref_eyeblink_coeff_path=None, still=still)
                coeff_path = self.audio_to_coeff.generate(batch, save_dir, 0, None)

                # Render
                data = get_facerender_data(coeff_path, crop_pic_path, first_coeff_path, audio_path, 1, None, None, None, expression_scale, still, preprocess, self.resolution)
                return self.animate_from_coeff.generate(data, save_dir, pic_path, crop_info, enhancer, None, preprocess, self.resolution)

            import asyncio
            loop = asyncio.get_running_loop()
            result_path = await loop.run_in_executor(None, run_inference)
            
            if output_path:
                shutil.copy(result_path, output_path)
                return output_path
            return result_path
        except Exception as e:
            import traceback
            logger.error("SadTalker rendering failed", error=str(e))
            print(f"❌ SadTalker Traceback:\n{traceback.format_exc()}")
            raise RuntimeError(f"Rendering failed: {e}")
        finally:
            if output_path: shutil.rmtree(temp_dir, ignore_errors=True)

    def get_info(self) -> Dict[str, Any]:
        return {"model": "SadTalker", "version": "0.0.2", "device": self.device, "resolution": self.resolution, "initialized": self._initialized}
