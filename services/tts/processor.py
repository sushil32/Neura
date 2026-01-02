"""Audio processing utilities for TTS."""
import io
from typing import List, Optional, Tuple

import numpy as np
import structlog

logger = structlog.get_logger()


class AudioProcessor:
    """
    Audio processing utilities for TTS output.
    
    Features:
    - Audio format conversion
    - Noise reduction
    - Volume normalization
    - Audio concatenation
    - Silence detection and trimming
    """

    def __init__(self, sample_rate: int = 22050):
        self.sample_rate = sample_rate

    def normalize_volume(
        self,
        audio: np.ndarray,
        target_db: float = -20.0,
    ) -> np.ndarray:
        """Normalize audio to target dB level."""
        # Calculate RMS
        rms = np.sqrt(np.mean(audio ** 2))
        if rms == 0:
            return audio
        
        # Calculate target RMS from dB
        target_rms = 10 ** (target_db / 20)
        
        # Scale audio
        return audio * (target_rms / rms)

    def remove_silence(
        self,
        audio: np.ndarray,
        threshold_db: float = -40.0,
        min_silence_duration: float = 0.3,
    ) -> np.ndarray:
        """Remove silence from start and end of audio."""
        threshold = 10 ** (threshold_db / 20)
        min_samples = int(min_silence_duration * self.sample_rate)
        
        # Find start (first non-silent sample)
        abs_audio = np.abs(audio)
        start_idx = 0
        for i in range(0, len(audio) - min_samples, min_samples):
            if np.mean(abs_audio[i:i+min_samples]) > threshold:
                start_idx = max(0, i - min_samples // 2)
                break
        
        # Find end (last non-silent sample)
        end_idx = len(audio)
        for i in range(len(audio) - min_samples, min_samples, -min_samples):
            if np.mean(abs_audio[i:i+min_samples]) > threshold:
                end_idx = min(len(audio), i + min_samples + min_samples // 2)
                break
        
        return audio[start_idx:end_idx]

    def add_silence(
        self,
        audio: np.ndarray,
        start_silence: float = 0.0,
        end_silence: float = 0.0,
    ) -> np.ndarray:
        """Add silence to start and/or end of audio."""
        start_samples = int(start_silence * self.sample_rate)
        end_samples = int(end_silence * self.sample_rate)
        
        parts = []
        if start_samples > 0:
            parts.append(np.zeros(start_samples, dtype=audio.dtype))
        parts.append(audio)
        if end_samples > 0:
            parts.append(np.zeros(end_samples, dtype=audio.dtype))
        
        return np.concatenate(parts)

    def concatenate(
        self,
        audio_chunks: List[np.ndarray],
        crossfade_duration: float = 0.05,
    ) -> np.ndarray:
        """Concatenate audio chunks with crossfade."""
        if not audio_chunks:
            return np.array([], dtype=np.float32)
        
        if len(audio_chunks) == 1:
            return audio_chunks[0]
        
        crossfade_samples = int(crossfade_duration * self.sample_rate)
        
        result = audio_chunks[0].copy()
        
        for chunk in audio_chunks[1:]:
            if crossfade_samples > 0 and len(result) > crossfade_samples:
                # Create crossfade
                fade_out = np.linspace(1, 0, crossfade_samples)
                fade_in = np.linspace(0, 1, crossfade_samples)
                
                # Apply crossfade
                result[-crossfade_samples:] *= fade_out
                chunk[:crossfade_samples] *= fade_in
                result[-crossfade_samples:] += chunk[:crossfade_samples]
                result = np.concatenate([result, chunk[crossfade_samples:]])
            else:
                result = np.concatenate([result, chunk])
        
        return result

    def apply_fade(
        self,
        audio: np.ndarray,
        fade_in_duration: float = 0.01,
        fade_out_duration: float = 0.01,
    ) -> np.ndarray:
        """Apply fade in/out to audio."""
        audio = audio.copy()
        
        fade_in_samples = int(fade_in_duration * self.sample_rate)
        fade_out_samples = int(fade_out_duration * self.sample_rate)
        
        if fade_in_samples > 0 and len(audio) > fade_in_samples:
            fade_in = np.linspace(0, 1, fade_in_samples)
            audio[:fade_in_samples] *= fade_in
        
        if fade_out_samples > 0 and len(audio) > fade_out_samples:
            fade_out = np.linspace(1, 0, fade_out_samples)
            audio[-fade_out_samples:] *= fade_out
        
        return audio

    def resample(
        self,
        audio: np.ndarray,
        orig_sr: int,
        target_sr: int,
    ) -> np.ndarray:
        """Resample audio to target sample rate."""
        if orig_sr == target_sr:
            return audio
        
        # Simple resampling using interpolation
        duration = len(audio) / orig_sr
        new_length = int(duration * target_sr)
        
        x_old = np.linspace(0, 1, len(audio))
        x_new = np.linspace(0, 1, new_length)
        
        return np.interp(x_new, x_old, audio).astype(audio.dtype)

    def convert_format(
        self,
        audio_bytes: bytes,
        input_format: str,
        output_format: str,
    ) -> bytes:
        """Convert audio between formats."""
        # In production, use pydub or ffmpeg
        # For now, return unchanged for WAV
        if input_format == output_format:
            return audio_bytes
        
        logger.warning(
            "Audio format conversion not fully implemented",
            input_format=input_format,
            output_format=output_format,
        )
        return audio_bytes

    def get_duration(self, audio: np.ndarray) -> float:
        """Get audio duration in seconds."""
        return len(audio) / self.sample_rate

    def detect_speech_segments(
        self,
        audio: np.ndarray,
        threshold_db: float = -35.0,
        min_speech_duration: float = 0.1,
        min_silence_duration: float = 0.2,
    ) -> List[Tuple[float, float]]:
        """Detect speech segments in audio."""
        threshold = 10 ** (threshold_db / 20)
        min_speech_samples = int(min_speech_duration * self.sample_rate)
        min_silence_samples = int(min_silence_duration * self.sample_rate)
        
        segments = []
        in_speech = False
        speech_start = 0
        silence_count = 0
        
        # Calculate RMS in windows
        window_size = int(0.01 * self.sample_rate)  # 10ms windows
        
        for i in range(0, len(audio) - window_size, window_size):
            window = audio[i:i+window_size]
            rms = np.sqrt(np.mean(window ** 2))
            
            if rms > threshold:
                if not in_speech:
                    speech_start = i
                    in_speech = True
                silence_count = 0
            else:
                if in_speech:
                    silence_count += window_size
                    if silence_count >= min_silence_samples:
                        speech_end = i - silence_count + window_size
                        if speech_end - speech_start >= min_speech_samples:
                            segments.append((
                                speech_start / self.sample_rate,
                                speech_end / self.sample_rate,
                            ))
                        in_speech = False
        
        # Handle last segment
        if in_speech:
            segments.append((
                speech_start / self.sample_rate,
                len(audio) / self.sample_rate,
            ))
        
        return segments

