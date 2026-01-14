"""Avatar rendering engine with Wav2Lip support."""
import asyncio
import io
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator, Callable, Dict, List, Optional, Tuple

import numpy as np
import torch
import structlog

from models_wav2lip import Wav2Lip

logger = structlog.get_logger()


@dataclass
class RenderConfig:
    """Configuration for avatar rendering."""
    width: int = 1920
    height: int = 1080
    fps: int = 30
    quality: str = "balanced"  # fast, balanced, high
    background_color: str = "#000000"
    background_image: Optional[str] = None
    output_format: str = "mp4"
    codec: str = "h264"
    
    # SadTalker config
    emotion: str = "neutral"
    expression_scale: float = 1.0
    head_pose_scale: float = 1.0
    use_sadtalker: bool = True


@dataclass
class AvatarFrame:
    """Single rendered avatar frame."""
    frame_number: int
    timestamp: float  # seconds
    image_data: bytes
    width: int
    height: int


@dataclass
class RenderProgress:
    """Render progress information."""
    current_frame: int
    total_frames: int
    current_step: str
    progress: float  # 0.0 to 1.0
    estimated_remaining: float  # seconds
    error: Optional[str] = None


class Wav2LipProcessor:
    """
    Wav2Lip inference processor for lip sync.
    
    This handles the actual Wav2Lip model inference to generate
    lip-synced video frames from audio and face images.
    """
    
    def __init__(self, model_path: str = "/app/models"):
        self.model_path = model_path
        self._model = None
        self._face_detector = None
        self._device = "cpu"
        self._initialized = False
    
    async def initialize(self, device: str = "auto") -> None:
        """Initialize Wav2Lip models."""
        if self._initialized:
            return
        
        logger.info("Initializing Wav2Lip processor")
        
        # Detect device
        if device == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    self._device = "cuda"
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    self._device = "mps"
                else:
                    self._device = "cpu"
            except ImportError:
                self._device = "cpu"
        else:
            self._device = device
        
        # Verify the selected device actually works
        if self._device != "cpu":
            try:
                import torch
                if self._device == "cuda":
                    torch.zeros(1).to("cuda")
                elif self._device == "mps":
                    torch.zeros(1).to("mps")
            except Exception:
                logger.warning(f"Device {self._device} not working/linked, falling back to CPU")
                self._device = "cpu"
        
        logger.info(f"Using device: {self._device}")
        
        try:
            # Try to load Wav2Lip model
            await self._load_wav2lip_model()
            await self._load_face_detector()
            print(f"✅ Wav2Lip initialized successfully on {self._device}")
            logger.info("Wav2Lip initialized successfully")
            self._initialized = True
        except Exception as e:
            print(f"❌ Failed to load Wav2Lip: {e}")
            logger.warning(f"Failed to load Wav2Lip: {e}, using fallback")
            self._initialized = True
    
    async def _load_wav2lip_model(self) -> None:
        """Load Wav2Lip model weights."""
        try:
            import torch
            
            model_file = Path(self.model_path) / "wav2lip_gan.pth"
            
            if not model_file.exists():
                logger.warning(f"Wav2Lip model not found at {model_file}")
                # Download model if not present
                await self._download_model(model_file)
            
            if model_file.exists():
                # Load model architecture and weights
                self._model = Wav2Lip()
                
                checkpoint = torch.load(model_file, map_location='cpu')
                s = checkpoint.get('state_dict', checkpoint)
                
                # Strip unnecessary prefixes if any
                new_s = {}
                for k, v in s.items():
                    new_s[k.replace('module.', '')] = v
                
                self._model.load_state_dict(new_s)
                self._model = self._model.to(self._device)
                self._model.eval()
                
                logger.info("Wav2Lip model loaded", device=self._device)
        except ImportError:
            logger.warning("PyTorch not available")
    
    async def _load_face_detector(self) -> None:
        """Load face detection model."""
        try:
            import cv2
            
            # Use OpenCV's DNN face detector or face_alignment
            cascade_file = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self._face_detector = cv2.CascadeClassifier(cascade_file)
            logger.info("Face detector loaded")
        except Exception as e:
            logger.warning(f"Face detector not available: {e}")
    
    async def _download_model(self, model_path: Path) -> None:
        """Download Wav2Lip model weights."""
        # Helper for SSL context on Mac
        import ssl
        try:
             ssl._create_default_https_context = ssl._create_unverified_context
        except AttributeError:
             pass

        model_urls = [
            "https://huggingface.co/camenduru/Wav2Lip/resolve/main/checkpoints/wav2lip_gan.pth",
            "https://huggingface.co/gvecchio/Wav2Lip-GAN/resolve/main/wav2lip_gan.pth",
            "https://github.com/Rudrabha/Wav2Lip/releases/download/v1.0/wav2lip_gan.pth"
        ]
        
        try:
            import urllib.request
            model_path.parent.mkdir(parents=True, exist_ok=True)
            
            success = False
            for url in model_urls:
                try:
                    print(f"Downloading model from {url}...")
                    urllib.request.urlretrieve(url, str(model_path))
                    
                    if model_path.exists() and model_path.stat().st_size > 1000000: # > 1MB
                        logger.info(f"Wav2Lip model downloaded from {url}")
                        success = True
                        break
                    else:
                        logger.warning(f"Download from {url} resulted in invalid file")
                        if model_path.exists(): model_path.unlink()
                except Exception as down_err:
                    logger.warning(f"Failed to download from {url}: {down_err}")
            
            if not success:
                logger.error("All model download attempts failed")
                
        except Exception as e:
            logger.warning(f"Model download process failed: {e}")
    
    async def process_frame(
        self,
        face_image: np.ndarray,
        audio_chunk: np.ndarray,
        mel_chunk: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Process a single frame with Wav2Lip.
        
        Args:
            face_image: Face image as numpy array (BGR)
            audio_chunk: Audio samples for this frame
            mel_chunk: Pre-computed mel spectrogram (optional)
        
        Returns:
            Processed frame with lip sync applied
        """
        if self._model is None:
            # Fallback: return original face
            return face_image
        
        try:
            import torch
            import cv2
            
            # Detect face
            faces = await self._detect_faces(face_image)
            if not faces:
                print("⚠️ No face detected")
                return face_image
            
            # Get the main face
            face_rect = faces[0]
            
            # Extract face region
            x, y, w, h = face_rect
            face_crop = face_image[y:y+h, x:x+w]
            
            # Resize for model
            face_resized = cv2.resize(face_crop, (96, 96))

            # Prepare input tensor (6 channels: Identity + Masked Target)
            # For simplicity, we use same face as identity and target
            # and mask the bottom half of the target face
            face_identity = face_resized.copy()
            face_target = face_resized.copy()
            face_target[96//2:, :] = 0 # Mask mouth area
            
            # Concatenate on channel dimension
            face_combined = np.concatenate([face_target, face_identity], axis=2)
            face_tensor = torch.FloatTensor(face_combined).permute(2, 0, 1).unsqueeze(0)
            face_tensor = face_tensor.to(self._device) / 255.0
            
            print(f"🔹 Face tensor shape: {face_tensor.shape}, device: {self._device}")
            
            # Get mel spectrogram if not provided
            if mel_chunk is None:
                mel_chunk = await self._audio_to_mel(audio_chunk)
            
            print(f"🔹 Mel chunk shape: {mel_chunk.shape}")
            
            # Wav2Lip expects [B, 1, 80, 16]
            if mel_chunk.ndim == 2:
                # [80, 16] -> [1, 1, 80, 16]
                mel_tensor = torch.FloatTensor(mel_chunk).unsqueeze(0).unsqueeze(0)
            elif mel_chunk.ndim == 3:
                # [1, 80, 16] -> [1, 1, 80, 16]
                mel_tensor = torch.FloatTensor(mel_chunk).unsqueeze(1)
            else:
                mel_tensor = torch.FloatTensor(mel_chunk)
            
            mel_tensor = mel_tensor.to(self._device)
            
            print(f"🔹 Mel tensor shape: {mel_tensor.shape}, device: {self._device}")
            
            # Run inference
            self._model.eval() # Force eval mode just in case
            print(f"🔹 Running Wav2Lip inference...")
            with torch.no_grad():
                output = self._model(mel_tensor, face_tensor)
            
            print(f"🔹 Output shape: {output.shape}")
            
            # Post-process output
            output_face = output.squeeze().permute(1, 2, 0).cpu().numpy()
            output_face = (np.clip(output_face, 0, 1) * 255).astype(np.uint8)
            
            # Resize back and paste
            output_face = cv2.resize(output_face, (w, h))
            result = face_image.copy()
            result[y:y+h, x:x+w] = output_face
            
            print("✅ Frame processed successfully")
            return result
            
        except Exception as e:
            import traceback
            print(f"❌ Frame processing failed: {e}")
            print(traceback.format_exc())
            logger.warning(f"Frame processing failed: {e}")
            return face_image
    
    async def _detect_faces(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect faces in image."""
        if self._face_detector is None:
            # Return center region as fallback
            h, w = image.shape[:2]
            return [(w//4, h//4, w//2, h//2)]
        
        try:
            import cv2
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            faces = self._face_detector.detectMultiScale(gray, 1.1, 4)
            
            return [(x, y, w, h) for (x, y, w, h) in faces]
        except:
            h, w = image.shape[:2]
            return [(w//4, h//4, w//2, h//2)]
    
    async def _audio_to_mel(self, audio: np.ndarray, sr: int = 16000) -> np.ndarray:
        """Convert audio to mel spectrogram.
        
        Wav2Lip expects mel spectrograms of shape (80, 16) which corresponds to:
        - 16 mel frames * 200 hop_size = 3200 samples
        - At 16kHz, 3200 samples = 200ms = 0.2 seconds per video frame
        """
        try:
            import librosa
            
            # Wav2Lip standard: 16 mel frames per video frame
            mel_step_size = 16
            
            # Ensure we have exactly the right amount of audio
            # hop_size=200, so 16 frames = 16*200 = 3200 samples
            required_samples = mel_step_size * 200
            
            # Pad or trim audio to required length
            if len(audio) < required_samples:
                audio = np.pad(audio, (0, required_samples - len(audio)), mode='constant')
            else:
                audio = audio[:required_samples]
            
            mel = librosa.feature.melspectrogram(
                y=audio.astype(np.float32),
                sr=sr,
                n_mels=80,
                n_fft=800,
                hop_length=200,
                win_length=800,
            )
            
            # Take exactly 16 frames
            mel = mel[:, :mel_step_size]
            
            # Log scale
            mel = np.log(np.clip(mel, 1e-5, None))
            
            return mel
        except Exception as e:
            logger.warning(f"Mel spectrogram generation failed: {e}")
            # Return placeholder with correct shape
            return np.zeros((80, 16), dtype=np.float32)


class AvatarRenderer:
    """
    Avatar rendering engine with Wav2Lip support.
    
    Features:
    - Face mesh generation
    - Lip sync from audio timings
    - Expression blending
    - Background compositing
    - GPU-accelerated rendering
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "auto",
    ):
        self.model_path = model_path or os.getenv("AVATAR_MODEL_PATH", "/app/models")
        self.device = self._detect_device(device)
        self._wav2lip = None
        self._sadtalker = None
        self._initialized = False

    def _detect_device(self, device: str) -> str:
        """Detect available compute device."""
        selected_device = device
        
        if selected_device == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    selected_device = "cuda"
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    selected_device = "mps"
                else:
                    selected_device = "cpu"
            except ImportError:
                selected_device = "cpu"
        
        # Verify the selected device actually works
        if selected_device != "cpu":
            try:
                import torch
                if selected_device == "cuda":
                    torch.zeros(1).to("cuda")
                elif selected_device == "mps":
                    torch.zeros(1).to("mps")
            except Exception as e:
                print(f"⚠️ Device {selected_device} not working/linked ({e}), falling back to CPU")
                logger.warning(f"Device {selected_device} not working/linked, falling back to CPU")
                selected_device = "cpu"
        
        print(f"🔹 Final selected device: {selected_device}")
        return selected_device

    async def initialize(self) -> None:
        """Initialize avatar rendering models."""
        if self._initialized:
            return

        logger.info("Initializing avatar renderer", device=self.device)

        try:
            # Initialize Wav2Lip processor
            self._wav2lip = Wav2LipProcessor(self.model_path)
            await self._wav2lip.initialize(self.device)
            
            # Initialize SadTalker processor
            try:
                from sadtalker_renderer import SadTalkerRenderer
                self._sadtalker = SadTalkerRenderer(
                    model_path=os.path.join(self.model_path, "sadtalker"),
                    device=self.device
                )
                # Ideally we lazy load or async load SadTalker as it's heavy
                # await self._sadtalker.initialize() 
                logger.info("SadTalker initialized")
            except Exception as e:
                logger.warning(f"SadTalker initialization failed: {e}")
                self._sadtalker = None
            
            self._initialized = True
            logger.info("Avatar renderer initialized")
            logger.info("Avatar renderer initialized")

        except Exception as e:
            logger.warning(f"Avatar initialization warning: {e}")
            self._initialized = True

    async def render_video(
        self,
        avatar_config: Dict,
        audio_path: str,
        word_timings: List[Dict],
        output_path: str,
        config: Optional[RenderConfig] = None,
        progress_callback: Optional[Callable] = None,
    ) -> str:
        """
        Render a complete video with lip-synced avatar.
        
        Args:
            avatar_config: Avatar configuration (avatar_path, avatar_id)
            audio_path: Path to audio file
            word_timings: List of word timing dictionaries
            output_path: Output video path
            config: Render configuration
            progress_callback: Callback for progress updates
        
        Returns:
            Path to rendered video
        """
        if not self._initialized:
            await self.initialize()

        config = config or RenderConfig()
        
        logger.info(
            "Starting video render",
            output=output_path,
            resolution=f"{config.width}x{config.height}",
            fps=config.fps,
        )

        temp_dir = None
        
        try:
            # Create temp directory
            temp_dir = tempfile.mkdtemp()
            frames_dir = Path(temp_dir) / "frames"
            frames_dir.mkdir()
            
            # Step 1: Load audio and analyze
            if progress_callback:
                await progress_callback(RenderProgress(
                    current_frame=0,
                    total_frames=0,
                    current_step="Loading audio",
                    progress=0.05,
                    estimated_remaining=0,
                ))

            audio_data, audio_sr = await self._load_audio(audio_path)
            audio_duration = len(audio_data) / audio_sr
            total_frames = int(audio_duration * config.fps)

            logger.info(f"Audio duration: {audio_duration:.2f}s, Total frames: {total_frames}")

            # Step 2: Load avatar image
            if progress_callback:
                await progress_callback(RenderProgress(
                    current_frame=0,
                    total_frames=total_frames,
                    current_step="Loading avatar",
                    progress=0.1,
                    estimated_remaining=audio_duration * 2,
                ))

            avatar_image = await self._load_avatar(avatar_config, config)

            # SADTALKER RENDERING PATH
            # DEBUG: Temporarily disabled SadTalker to debug blank video issue
            print(f"DEBUG: use_sadtalker={config.use_sadtalker}, _sadtalker={self._sadtalker is not None}")
            
            # DEBUG: SadTalker path enabled
            if config.use_sadtalker and self._sadtalker:
                logger.info("Using SadTalker engine", emotion=config.emotion)
                print("DEBUG: Entering SadTalker path")
                
                if progress_callback:
                    await progress_callback(RenderProgress(
                        current_frame=0, total_frames=100, current_step="SadTalker generation",
                        progress=0.2, estimated_remaining=60
                    ))

                # Render video directly
                video_path = await self._sadtalker.render(
                    avatar_image=avatar_image,
                    audio_path=audio_path,
                    emotion=config.emotion,
                    expression_scale=config.expression_scale,
                    head_pose_scale=config.head_pose_scale,
                    output_path=output_path
                )

                logger.info("SadTalker render complete", output=video_path)
                
                if progress_callback:
                    await progress_callback(RenderProgress(
                        current_frame=100, total_frames=100, 
                        current_step="Complete", progress=1.0, estimated_remaining=0
                    ))
                    
                return video_path

            # WAV2LIP RENDERING PATH (Existing)
            print("DEBUG: Using Wav2Lip fallback path")
            logger.info("Using Wav2Lip fallback")

            # Step 3: Generate lip sync data
            if progress_callback:
                await progress_callback(RenderProgress(
                    current_frame=0,
                    total_frames=total_frames,
                    current_step="Processing lip sync",
                    progress=0.15,
                    estimated_remaining=audio_duration * 1.5,
                ))

            lip_sync_data = await self._generate_lip_sync(
                audio_data,
                audio_sr,
                word_timings,
                config.fps,
            )

            # Step 4: Render frames
            for frame_idx in range(total_frames):
                timestamp = frame_idx / config.fps
                
                # Get audio chunk for this frame
                audio_start = int(timestamp * audio_sr)
                audio_end = int((timestamp + 1/config.fps) * audio_sr)
                audio_chunk = audio_data[audio_start:min(audio_end, len(audio_data))]
                
                # Get lip sync parameters for this frame
                lip_params = self._get_lip_params_at_time(lip_sync_data, timestamp)
                
                # Render frame
                frame = await self._render_frame(
                    avatar_image,
                    audio_chunk,
                    lip_params,
                    config,
                )
                
                # Save frame
                frame_path = frames_dir / f"frame_{frame_idx:06d}.png"
                await self._save_frame(frame, frame_path)
                
                if progress_callback and frame_idx % 10 == 0:
                    remaining = (total_frames - frame_idx) / config.fps
                    await progress_callback(RenderProgress(
                        current_frame=frame_idx,
                        total_frames=total_frames,
                        current_step="Rendering frames",
                        progress=0.15 + 0.7 * (frame_idx / total_frames),
                        estimated_remaining=remaining,
                    ))

            # Step 5: Encode video
            if progress_callback:
                await progress_callback(RenderProgress(
                    current_frame=total_frames,
                    total_frames=total_frames,
                    current_step="Encoding video",
                    progress=0.85,
                    estimated_remaining=audio_duration / 2,
                ))

            await self._encode_video(
                str(frames_dir),
                audio_path,
                output_path,
                config,
            )

            if progress_callback:
                await progress_callback(RenderProgress(
                    current_frame=total_frames,
                    total_frames=total_frames,
                    current_step="Complete",
                    progress=1.0,
                    estimated_remaining=0,
                ))

            logger.info("Video render complete", output=output_path)
            return output_path

        except Exception as e:
            logger.error("Video render failed", error=str(e))
            raise
            
        finally:
            # Cleanup temp files
            if temp_dir:
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass

    async def render_stream(
        self,
        avatar_config: Dict,
        config: Optional[RenderConfig] = None,
    ) -> AsyncGenerator[AvatarFrame, None]:
        """
        Stream rendered avatar frames for live mode.
        
        Yields:
            AvatarFrame objects for real-time streaming
        """
        if not self._initialized:
            await self.initialize()

        config = config or RenderConfig()
        frame_interval = 1.0 / config.fps
        frame_number = 0
        
        # Load avatar once
        avatar_image = await self._load_avatar(avatar_config, config)

        while True:
            timestamp = frame_number * frame_interval
            
            # Render frame with current parameters
            frame = await self._render_frame(
                avatar_image,
                np.zeros(1600, dtype=np.float32),  # Silence
                {},
                config,
            )
            
            # Convert frame to bytes
            frame_bytes = await self._frame_to_bytes(frame)
            
            yield AvatarFrame(
                frame_number=frame_number,
                timestamp=timestamp,
                image_data=frame_bytes,
                width=config.width,
                height=config.height,
            )
            
            frame_number += 1
            await asyncio.sleep(frame_interval)

    async def _load_audio(self, audio_path: str) -> Tuple[np.ndarray, int]:
        """Load audio file."""
        try:
            import librosa
            audio, sr = librosa.load(audio_path, sr=16000)
            return audio, sr
        except ImportError:
            # Fallback: use wave module
            import wave
            with wave.open(audio_path, 'rb') as wav:
                frames = wav.readframes(wav.getnframes())
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                sr = wav.getframerate()
            return audio, sr

    async def _load_avatar(
        self,
        avatar_config: Dict,
        config: RenderConfig,
    ) -> np.ndarray:
        """Load and prepare avatar image."""
        import cv2
        
        avatar_path = avatar_config.get("avatar_path")
        
        if avatar_path and Path(avatar_path).exists():
            # Load custom avatar
            image = cv2.imread(avatar_path)
        else:
            # Create default avatar
            image = await self._create_default_avatar(config)
        
        # Resize to target dimensions
        image = cv2.resize(image, (config.width, config.height))
        
        return image

    async def _create_default_avatar(self, config: RenderConfig) -> np.ndarray:
        """Create a default placeholder avatar."""
        import cv2
        
        # Create blank image with background color
        bg_color = self._hex_to_bgr(config.background_color)
        image = np.full((config.height, config.width, 3), bg_color, dtype=np.uint8)
        
        # Draw a simple face
        center_x, center_y = config.width // 2, config.height // 2
        head_radius = min(config.width, config.height) // 3
        
        # Head
        cv2.circle(image, (center_x, center_y), head_radius, (200, 180, 160), -1)
        cv2.circle(image, (center_x, center_y), head_radius, (150, 130, 110), 3)
        
        # Eyes
        eye_y = center_y - head_radius // 4
        eye_offset = head_radius // 3
        eye_radius = head_radius // 10
        cv2.circle(image, (center_x - eye_offset, eye_y), eye_radius, (255, 255, 255), -1)
        cv2.circle(image, (center_x + eye_offset, eye_y), eye_radius, (255, 255, 255), -1)
        cv2.circle(image, (center_x - eye_offset, eye_y), eye_radius // 2, (50, 40, 30), -1)
        cv2.circle(image, (center_x + eye_offset, eye_y), eye_radius // 2, (50, 40, 30), -1)
        
        # Nose
        nose_y = center_y + head_radius // 10
        cv2.ellipse(image, (center_x, nose_y), (head_radius // 15, head_radius // 8),
                   0, 0, 180, (180, 160, 140), 2)
        
        # Mouth (neutral)
        mouth_y = center_y + head_radius // 2
        mouth_width = head_radius // 3
        cv2.ellipse(image, (center_x, mouth_y), (mouth_width, head_radius // 10),
                   0, 0, 180, (150, 100, 100), -1)
        
        return image

    def _hex_to_bgr(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to BGR."""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (b, g, r)

    async def _generate_lip_sync(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        word_timings: List[Dict],
        fps: int,
    ) -> List[Dict]:
        """Generate lip sync data from audio and word timings."""
        from lipsync import LipSyncProcessor
        
        processor = LipSyncProcessor()
        return await processor.process_audio(audio_data, sample_rate, word_timings, fps)

    def _get_lip_params_at_time(
        self,
        lip_sync_data: List[Dict],
        timestamp: float,
    ) -> Dict:
        """Get lip sync parameters at a specific timestamp."""
        for data in lip_sync_data:
            if data.get("timestamp", 0) >= timestamp:
                return data
        return lip_sync_data[-1] if lip_sync_data else {"mouth_open": 0.1}

    async def _render_frame(
        self,
        avatar_image: np.ndarray,
        audio_chunk: np.ndarray,
        lip_params: Dict,
        config: RenderConfig,
    ) -> np.ndarray:
        """Render a single avatar frame."""
        import cv2
        
        # Try Wav2Lip processing
        if self._wav2lip and len(audio_chunk) > 0:
            try:
                result = await self._wav2lip.process_frame(
                    avatar_image.copy(),
                    audio_chunk,
                )
                return result
            except Exception as e:
                logger.debug(f"Wav2Lip processing skipped: {e}")
        
        # Fallback: simple mouth animation based on lip_params
        result = avatar_image.copy()
        
        # Get mouth parameters
        mouth_open = lip_params.get("mouth_open", 0.1)
        mouth_width = lip_params.get("mouth_width", 1.0)
        
        # Find face center (simple estimation)
        h, w = result.shape[:2]
        center_x, center_y = w // 2, h // 2
        
        # Animate mouth based on parameters
        mouth_y = center_y + h // 6
        mouth_w = int(w // 6 * mouth_width)
        mouth_h = int(h // 20 * max(mouth_open, 0.2))
        
        # Draw animated mouth
        cv2.ellipse(
            result,
            (center_x, mouth_y),
            (mouth_w, mouth_h),
            0, 0, 180,
            (100, 80, 120),
            -1,
        )
        
        return result

    async def _save_frame(self, frame: np.ndarray, path: Path) -> None:
        """Save frame to disk."""
        import cv2
        cv2.imwrite(str(path), frame)

    async def _frame_to_bytes(self, frame: np.ndarray) -> bytes:
        """Convert frame to PNG bytes."""
        import cv2
        _, buffer = cv2.imencode('.png', frame)
        return buffer.tobytes()

    async def _encode_video(
        self,
        frames_dir: str,
        audio_path: str,
        output_path: str,
        config: RenderConfig,
    ) -> None:
        """Encode frames and audio into video."""
        # Determine preset based on quality
        preset_map = {
            "fast": "ultrafast",
            "balanced": "medium",
            "high": "slow",
        }
        preset = preset_map.get(config.quality, "medium")
        
        # Determine CRF based on quality
        crf_map = {
            "fast": "28",
            "balanced": "23",
            "high": "18",
        }
        crf = crf_map.get(config.quality, "23")
        
        # Build ffmpeg command
        cmd = [
            "ffmpeg",
            "-y",
            "-framerate", str(config.fps),
            "-i", f"{frames_dir}/frame_%06d.png",
            "-i", audio_path,
            "-c:v", "libx264" if config.codec == "h264" else config.codec,
            "-preset", preset,
            "-crf", crf,
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ]
        
        logger.info("Encoding video", cmd=" ".join(cmd))
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error("FFmpeg encoding failed", stderr=stderr.decode())
            raise RuntimeError(f"Video encoding failed: {stderr.decode()}")
        
        logger.info("Video encoding complete")

    async def update_lip_sync(
        self,
        viseme: str,
        intensity: float = 1.0,
    ) -> None:
        """Update current lip sync state for live rendering."""
        # This would update internal state for the stream renderer
        pass

    def get_available_avatars(self) -> List[Dict]:
        """Get list of available avatar images."""
        avatars = [
            {"id": "default", "name": "Default Avatar", "type": "builtin"},
            {"id": "professional_male", "name": "Professional Male", "type": "builtin"},
            {"id": "professional_female", "name": "Professional Female", "type": "builtin"},
        ]
        
        # List custom avatars
        avatars_dir = Path(self.model_path) / "avatars"
        if avatars_dir.exists():
            for avatar_file in avatars_dir.glob("*.*"):
                if avatar_file.suffix.lower() in [".png", ".jpg", ".jpeg"]:
                    avatars.append({
                        "id": avatar_file.stem,
                        "name": avatar_file.stem.replace("_", " ").title(),
                        "type": "custom",
                    })
        
        return avatars
