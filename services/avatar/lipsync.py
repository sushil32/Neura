"""Lip sync processing for avatar animation."""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import structlog

logger = structlog.get_logger()


class Viseme(str, Enum):
    """
    Viseme types for lip sync.
    Based on Preston Blair phoneme set.
    """
    SILENCE = "sil"  # Closed mouth
    PP = "PP"  # P, B, M
    FF = "FF"  # F, V
    TH = "TH"  # Th
    DD = "DD"  # T, D, N, L
    KK = "KK"  # K, G, NG
    CH = "CH"  # Ch, J, Sh
    SS = "SS"  # S, Z
    NN = "NN"  # N, NG
    RR = "RR"  # R
    AA = "AA"  # A
    EE = "EE"  # E, I
    II = "II"  # I
    OO = "OO"  # O
    UU = "UU"  # U, W


@dataclass
class VisemeMapping:
    """Mapping from phonemes to visemes."""
    
    # Phoneme to viseme mapping
    PHONEME_TO_VISEME = {
        # Consonants
        "P": Viseme.PP,
        "B": Viseme.PP,
        "M": Viseme.PP,
        "F": Viseme.FF,
        "V": Viseme.FF,
        "TH": Viseme.TH,
        "DH": Viseme.TH,
        "T": Viseme.DD,
        "D": Viseme.DD,
        "N": Viseme.NN,
        "L": Viseme.DD,
        "K": Viseme.KK,
        "G": Viseme.KK,
        "NG": Viseme.KK,
        "CH": Viseme.CH,
        "JH": Viseme.CH,
        "SH": Viseme.CH,
        "ZH": Viseme.CH,
        "S": Viseme.SS,
        "Z": Viseme.SS,
        "R": Viseme.RR,
        "W": Viseme.UU,
        "Y": Viseme.EE,
        "H": Viseme.SILENCE,
        # Vowels
        "AA": Viseme.AA,
        "AE": Viseme.AA,
        "AH": Viseme.AA,
        "AO": Viseme.OO,
        "AW": Viseme.AA,
        "AY": Viseme.AA,
        "EH": Viseme.EE,
        "ER": Viseme.RR,
        "EY": Viseme.EE,
        "IH": Viseme.II,
        "IY": Viseme.II,
        "OW": Viseme.OO,
        "OY": Viseme.OO,
        "UH": Viseme.UU,
        "UW": Viseme.UU,
    }

    @classmethod
    def get_viseme(cls, phoneme: str) -> Viseme:
        """Get viseme for a phoneme."""
        return cls.PHONEME_TO_VISEME.get(phoneme.upper(), Viseme.SILENCE)


@dataclass
class LipSyncFrame:
    """Lip sync data for a single frame."""
    timestamp: float
    viseme: Viseme
    intensity: float  # 0.0 to 1.0
    mouth_open: float  # 0.0 to 1.0
    mouth_wide: float  # 0.0 to 1.0
    jaw_open: float  # 0.0 to 1.0


class LipSyncProcessor:
    """
    Process audio and word timings into lip sync animation data.
    
    Features:
    - Phoneme-to-viseme conversion
    - Smooth viseme transitions
    - Intensity based on audio amplitude
    - Coarticulation handling
    """

    def __init__(self):
        self._g2p_model = None  # Grapheme-to-phoneme model

    async def process(
        self,
        audio_path: str,
        word_timings: List[Dict],
        fps: int = 30,
    ) -> List[Dict]:
        """
        Process audio into lip sync frames.
        
        Args:
            audio_path: Path to audio file
            word_timings: Word timing data from TTS
            fps: Output frame rate
        
        Returns:
            List of lip sync frame data
        """
        logger.info("Processing lip sync", fps=fps)

        # Load audio for amplitude analysis
        audio_data = await self._load_audio(audio_path)
        
        # Get total duration
        if word_timings:
            duration = max(wt.get("end_time", 0) for wt in word_timings)
        else:
            duration = len(audio_data) / 22050  # Assume 22kHz
        
        total_frames = int(duration * fps)
        frame_duration = 1.0 / fps
        
        # Generate lip sync frames
        frames = []
        for frame_idx in range(total_frames):
            timestamp = frame_idx * frame_duration
            
            # Get current phoneme/viseme
            viseme, intensity = self._get_viseme_at_time(
                word_timings,
                timestamp,
            )
            
            # Get audio amplitude for this frame
            amplitude = self._get_amplitude_at_time(
                audio_data,
                timestamp,
                frame_duration,
            )
            
            # Calculate mouth shape parameters
            mouth_params = self._calculate_mouth_params(viseme, intensity, amplitude)
            
            frames.append({
                "timestamp": timestamp,
                "viseme": viseme.value,
                "intensity": intensity,
                **mouth_params,
            })
        
        # Apply smoothing
        frames = self._smooth_frames(frames, fps)
        
        return frames

    def _get_viseme_at_time(
        self,
        word_timings: List[Dict],
        timestamp: float,
    ) -> Tuple[Viseme, float]:
        """Get viseme and intensity at a specific time."""
        # Find current word
        current_word = None
        for wt in word_timings:
            start = wt.get("start_time", 0)
            end = wt.get("end_time", 0)
            if start <= timestamp < end:
                current_word = wt
                break
        
        if not current_word:
            return Viseme.SILENCE, 0.0
        
        word = current_word.get("word", "")
        word_start = current_word.get("start_time", 0)
        word_end = current_word.get("end_time", 0)
        word_duration = word_end - word_start
        
        if word_duration <= 0:
            return Viseme.SILENCE, 0.0
        
        # Calculate position within word (0.0 to 1.0)
        word_progress = (timestamp - word_start) / word_duration
        
        # Get phonemes for word (simplified)
        phonemes = self._word_to_phonemes(word)
        
        if not phonemes:
            return Viseme.AA, 0.5  # Default to open mouth
        
        # Get phoneme at current position
        phoneme_idx = int(word_progress * len(phonemes))
        phoneme_idx = min(phoneme_idx, len(phonemes) - 1)
        
        phoneme = phonemes[phoneme_idx]
        viseme = VisemeMapping.get_viseme(phoneme)
        
        # Calculate intensity based on position in phoneme
        intensity = 0.8 + 0.2 * np.sin(word_progress * np.pi)
        
        return viseme, intensity

    def _word_to_phonemes(self, word: str) -> List[str]:
        """Convert word to phonemes (simplified)."""
        # In production, use a proper G2P model
        # This is a very simplified approximation
        phonemes = []
        vowels = "aeiouAEIOU"
        
        word = word.lower()
        i = 0
        while i < len(word):
            char = word[i]
            
            # Check for digraphs
            if i < len(word) - 1:
                digraph = word[i:i+2]
                if digraph in ["th", "ch", "sh", "ng"]:
                    phonemes.append(digraph.upper())
                    i += 2
                    continue
            
            if char in vowels:
                phonemes.append(char.upper() + char.upper())  # AA, EE, etc.
            elif char.isalpha():
                phonemes.append(char.upper())
            
            i += 1
        
        return phonemes if phonemes else ["AA"]

    def _get_amplitude_at_time(
        self,
        audio_data: np.ndarray,
        timestamp: float,
        duration: float,
        sample_rate: int = 22050,
    ) -> float:
        """Get normalized audio amplitude at timestamp."""
        start_sample = int(timestamp * sample_rate)
        end_sample = int((timestamp + duration) * sample_rate)
        
        if start_sample >= len(audio_data):
            return 0.0
        
        end_sample = min(end_sample, len(audio_data))
        segment = audio_data[start_sample:end_sample]
        
        if len(segment) == 0:
            return 0.0
        
        # Calculate RMS amplitude
        rms = np.sqrt(np.mean(segment ** 2))
        
        # Normalize (assuming max amplitude is 1.0)
        return min(rms * 3, 1.0)  # Scale up for visibility

    def _calculate_mouth_params(
        self,
        viseme: Viseme,
        intensity: float,
        amplitude: float,
    ) -> Dict:
        """Calculate mouth shape parameters for a viseme."""
        # Base shapes for each viseme
        shapes = {
            Viseme.SILENCE: {"mouth_open": 0.0, "mouth_wide": 0.0, "jaw_open": 0.0},
            Viseme.PP: {"mouth_open": 0.0, "mouth_wide": 0.1, "jaw_open": 0.0},
            Viseme.FF: {"mouth_open": 0.1, "mouth_wide": 0.3, "jaw_open": 0.1},
            Viseme.TH: {"mouth_open": 0.2, "mouth_wide": 0.2, "jaw_open": 0.2},
            Viseme.DD: {"mouth_open": 0.3, "mouth_wide": 0.2, "jaw_open": 0.3},
            Viseme.KK: {"mouth_open": 0.4, "mouth_wide": 0.2, "jaw_open": 0.4},
            Viseme.CH: {"mouth_open": 0.3, "mouth_wide": 0.4, "jaw_open": 0.3},
            Viseme.SS: {"mouth_open": 0.2, "mouth_wide": 0.5, "jaw_open": 0.2},
            Viseme.NN: {"mouth_open": 0.2, "mouth_wide": 0.2, "jaw_open": 0.2},
            Viseme.RR: {"mouth_open": 0.3, "mouth_wide": 0.3, "jaw_open": 0.3},
            Viseme.AA: {"mouth_open": 0.8, "mouth_wide": 0.4, "jaw_open": 0.7},
            Viseme.EE: {"mouth_open": 0.4, "mouth_wide": 0.7, "jaw_open": 0.3},
            Viseme.II: {"mouth_open": 0.3, "mouth_wide": 0.6, "jaw_open": 0.2},
            Viseme.OO: {"mouth_open": 0.6, "mouth_wide": 0.2, "jaw_open": 0.5},
            Viseme.UU: {"mouth_open": 0.4, "mouth_wide": 0.1, "jaw_open": 0.4},
        }
        
        base_shape = shapes.get(viseme, shapes[Viseme.SILENCE])
        
        # Apply intensity and amplitude
        return {
            "mouth_open": base_shape["mouth_open"] * intensity * (0.5 + 0.5 * amplitude),
            "mouth_wide": base_shape["mouth_wide"] * intensity,
            "jaw_open": base_shape["jaw_open"] * intensity * (0.5 + 0.5 * amplitude),
        }

    def _smooth_frames(
        self,
        frames: List[Dict],
        fps: int,
        smoothing_window: float = 0.05,
    ) -> List[Dict]:
        """Apply smoothing to lip sync frames."""
        if len(frames) < 2:
            return frames
        
        window_size = max(1, int(smoothing_window * fps))
        
        # Extract values
        mouth_open = [f["mouth_open"] for f in frames]
        mouth_wide = [f["mouth_wide"] for f in frames]
        jaw_open = [f["jaw_open"] for f in frames]
        
        # Apply moving average
        def smooth(values):
            smoothed = []
            for i in range(len(values)):
                start = max(0, i - window_size // 2)
                end = min(len(values), i + window_size // 2 + 1)
                smoothed.append(np.mean(values[start:end]))
            return smoothed
        
        mouth_open = smooth(mouth_open)
        mouth_wide = smooth(mouth_wide)
        jaw_open = smooth(jaw_open)
        
        # Update frames
        for i, frame in enumerate(frames):
            frame["mouth_open"] = mouth_open[i]
            frame["mouth_wide"] = mouth_wide[i]
            frame["jaw_open"] = jaw_open[i]
        
        return frames

    async def _load_audio(self, audio_path: str) -> np.ndarray:
        """Load audio file as numpy array."""
        try:
            import wave
            
            with wave.open(audio_path, 'rb') as wav:
                frames = wav.readframes(-1)
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
                audio /= 32768.0  # Normalize to -1.0 to 1.0
                return audio
        except Exception as e:
            logger.warning("Failed to load audio", error=str(e))
            return np.zeros(22050, dtype=np.float32)  # 1 second of silence

