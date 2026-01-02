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
    PP = "PP"  # P, B, M - lips together
    FF = "FF"  # F, V - teeth on lip
    TH = "TH"  # Th - tongue between teeth
    DD = "DD"  # T, D, N, L - tongue behind teeth
    KK = "KK"  # K, G, NG - back tongue
    CH = "CH"  # Ch, J, Sh - pursed lips
    SS = "SS"  # S, Z - teeth together
    NN = "NN"  # N, NG - nasal
    RR = "RR"  # R - slightly open
    AA = "AA"  # A - wide open
    EE = "EE"  # E - wide smile
    II = "II"  # I - narrow smile
    OO = "OO"  # O - rounded lips
    UU = "UU"  # U, W - small rounded


# Viseme blend shapes for facial animation
VISEME_BLEND_SHAPES = {
    Viseme.SILENCE: {
        "jawOpen": 0.0,
        "mouthOpen": 0.0,
        "mouthWide": 0.0,
        "mouthPucker": 0.0,
        "mouthSmile": 0.0,
        "lipPress": 0.0,
    },
    Viseme.PP: {
        "jawOpen": 0.0,
        "mouthOpen": 0.0,
        "mouthWide": 0.1,
        "mouthPucker": 0.2,
        "mouthSmile": 0.0,
        "lipPress": 0.8,
    },
    Viseme.FF: {
        "jawOpen": 0.1,
        "mouthOpen": 0.1,
        "mouthWide": 0.2,
        "mouthPucker": 0.0,
        "mouthSmile": 0.1,
        "lipPress": 0.0,
    },
    Viseme.TH: {
        "jawOpen": 0.2,
        "mouthOpen": 0.2,
        "mouthWide": 0.2,
        "mouthPucker": 0.0,
        "mouthSmile": 0.0,
        "lipPress": 0.0,
    },
    Viseme.DD: {
        "jawOpen": 0.3,
        "mouthOpen": 0.2,
        "mouthWide": 0.2,
        "mouthPucker": 0.0,
        "mouthSmile": 0.1,
        "lipPress": 0.0,
    },
    Viseme.KK: {
        "jawOpen": 0.4,
        "mouthOpen": 0.3,
        "mouthWide": 0.2,
        "mouthPucker": 0.0,
        "mouthSmile": 0.0,
        "lipPress": 0.0,
    },
    Viseme.CH: {
        "jawOpen": 0.3,
        "mouthOpen": 0.2,
        "mouthWide": 0.0,
        "mouthPucker": 0.5,
        "mouthSmile": 0.0,
        "lipPress": 0.0,
    },
    Viseme.SS: {
        "jawOpen": 0.2,
        "mouthOpen": 0.1,
        "mouthWide": 0.4,
        "mouthPucker": 0.0,
        "mouthSmile": 0.3,
        "lipPress": 0.0,
    },
    Viseme.NN: {
        "jawOpen": 0.2,
        "mouthOpen": 0.1,
        "mouthWide": 0.2,
        "mouthPucker": 0.0,
        "mouthSmile": 0.0,
        "lipPress": 0.0,
    },
    Viseme.RR: {
        "jawOpen": 0.3,
        "mouthOpen": 0.2,
        "mouthWide": 0.0,
        "mouthPucker": 0.3,
        "mouthSmile": 0.0,
        "lipPress": 0.0,
    },
    Viseme.AA: {
        "jawOpen": 0.8,
        "mouthOpen": 0.7,
        "mouthWide": 0.4,
        "mouthPucker": 0.0,
        "mouthSmile": 0.0,
        "lipPress": 0.0,
    },
    Viseme.EE: {
        "jawOpen": 0.4,
        "mouthOpen": 0.3,
        "mouthWide": 0.6,
        "mouthPucker": 0.0,
        "mouthSmile": 0.5,
        "lipPress": 0.0,
    },
    Viseme.II: {
        "jawOpen": 0.3,
        "mouthOpen": 0.2,
        "mouthWide": 0.5,
        "mouthPucker": 0.0,
        "mouthSmile": 0.4,
        "lipPress": 0.0,
    },
    Viseme.OO: {
        "jawOpen": 0.6,
        "mouthOpen": 0.5,
        "mouthWide": 0.0,
        "mouthPucker": 0.6,
        "mouthSmile": 0.0,
        "lipPress": 0.0,
    },
    Viseme.UU: {
        "jawOpen": 0.4,
        "mouthOpen": 0.3,
        "mouthWide": 0.0,
        "mouthPucker": 0.7,
        "mouthSmile": 0.0,
        "lipPress": 0.0,
    },
}


@dataclass
class VisemeMapping:
    """Mapping from phonemes to visemes."""
    
    # Phoneme to viseme mapping (CMU phoneme set)
    PHONEME_TO_VISEME = {
        # Consonants
        "P": Viseme.PP, "B": Viseme.PP, "M": Viseme.PP,
        "F": Viseme.FF, "V": Viseme.FF,
        "TH": Viseme.TH, "DH": Viseme.TH,
        "T": Viseme.DD, "D": Viseme.DD, "L": Viseme.DD,
        "N": Viseme.NN, "NG": Viseme.NN,
        "K": Viseme.KK, "G": Viseme.KK,
        "CH": Viseme.CH, "JH": Viseme.CH, "SH": Viseme.CH, "ZH": Viseme.CH,
        "S": Viseme.SS, "Z": Viseme.SS,
        "R": Viseme.RR,
        "W": Viseme.UU, "Y": Viseme.EE,
        "H": Viseme.SILENCE, "HH": Viseme.SILENCE,
        # Vowels
        "AA": Viseme.AA, "AE": Viseme.AA, "AH": Viseme.AA,
        "AO": Viseme.OO, "AW": Viseme.AA, "AY": Viseme.AA,
        "EH": Viseme.EE, "ER": Viseme.RR, "EY": Viseme.EE,
        "IH": Viseme.II, "IY": Viseme.II,
        "OW": Viseme.OO, "OY": Viseme.OO,
        "UH": Viseme.UU, "UW": Viseme.UU,
    }

    @classmethod
    def get_viseme(cls, phoneme: str) -> Viseme:
        """Get viseme for a phoneme."""
        # Strip stress markers (numbers at end of CMU phonemes)
        phoneme = ''.join(c for c in phoneme.upper() if not c.isdigit())
        return cls.PHONEME_TO_VISEME.get(phoneme, Viseme.SILENCE)


@dataclass
class LipSyncFrame:
    """Lip sync data for a single frame."""
    timestamp: float
    viseme: Viseme
    intensity: float  # 0.0 to 1.0
    blend_shapes: Dict[str, float]


class LipSyncProcessor:
    """
    Process audio and word timings into lip sync animation data.
    
    Features:
    - Phoneme-to-viseme conversion
    - Smooth viseme transitions
    - Intensity based on audio amplitude
    - Coarticulation handling
    - Frame synchronization
    """

    def __init__(self):
        self._g2p_model = None  # Grapheme-to-phoneme model
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize G2P model if available."""
        if self._initialized:
            return
        
        try:
            from g2p_en import G2p
            self._g2p_model = G2p()
            logger.info("G2P model loaded")
        except ImportError:
            logger.warning("g2p_en not available, using fallback phoneme estimation")
        
        self._initialized = True

    async def process(
        self,
        audio_path: str,
        word_timings: List[Dict],
        fps: int = 30,
    ) -> List[Dict]:
        """
        Process audio file into lip sync frames.
        
        Args:
            audio_path: Path to audio file
            word_timings: Word timing data from TTS
            fps: Output frame rate
        
        Returns:
            List of lip sync frame data
        """
        await self.initialize()
        logger.info("Processing lip sync from file", fps=fps)

        # Load audio for amplitude analysis
        audio_data = await self._load_audio(audio_path)
        
        return await self.process_audio(audio_data, 22050, word_timings, fps)

    async def process_audio(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        word_timings: List[Dict],
        fps: int = 30,
    ) -> List[Dict]:
        """
        Process audio array into lip sync frames.
        
        Args:
            audio_data: Audio samples as numpy array
            sample_rate: Audio sample rate
            word_timings: Word timing data from TTS
            fps: Output frame rate
        
        Returns:
            List of lip sync frame data
        """
        await self.initialize()
        logger.info("Processing lip sync", fps=fps, duration=len(audio_data)/sample_rate)
        
        # Get total duration
        if word_timings:
            duration = max(
                wt.get("end", wt.get("end_time", 0)) 
                for wt in word_timings
            )
        else:
            duration = len(audio_data) / sample_rate
        
        # Ensure minimum duration
        duration = max(duration, 0.1)
        
        total_frames = int(duration * fps)
        frame_duration = 1.0 / fps
        
        # Generate lip sync frames
        frames = []
        for frame_idx in range(total_frames):
            timestamp = frame_idx * frame_duration
            
            # Get current phoneme/viseme
            viseme, intensity = self._get_viseme_at_time(word_timings, timestamp)
            
            # Get audio amplitude for this frame
            amplitude = self._get_amplitude_at_time(
                audio_data, timestamp, frame_duration, sample_rate
            )
            
            # Calculate mouth shape parameters
            blend_shapes = self._calculate_blend_shapes(viseme, intensity, amplitude)
            
            # Legacy mouth_open for backward compatibility
            mouth_open = blend_shapes.get("mouthOpen", 0.3) * intensity * (0.5 + 0.5 * amplitude)
            mouth_wide = blend_shapes.get("mouthWide", 0.3) * intensity
            
            frames.append({
                "frame": frame_idx,
                "timestamp": timestamp,
                "viseme": viseme.value,
                "intensity": intensity,
                "amplitude": amplitude,
                "mouth_open": mouth_open,
                "mouth_wide": mouth_wide,
                "jaw_open": blend_shapes.get("jawOpen", 0.3) * intensity,
                "blend_shapes": blend_shapes,
            })
        
        # Apply smoothing
        frames = self._smooth_frames(frames, fps)
        
        logger.info(f"Generated {len(frames)} lip sync frames")
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
            start = wt.get("start", wt.get("start_time", 0))
            end = wt.get("end", wt.get("end_time", 0))
            if start <= timestamp < end:
                current_word = wt
                break
        
        if not current_word:
            return Viseme.SILENCE, 0.0
        
        word = current_word.get("word", "")
        word_start = current_word.get("start", current_word.get("start_time", 0))
        word_end = current_word.get("end", current_word.get("end_time", 0))
        word_duration = word_end - word_start
        
        if word_duration <= 0:
            return Viseme.SILENCE, 0.0
        
        # Calculate position within word (0.0 to 1.0)
        word_progress = (timestamp - word_start) / word_duration
        
        # Get phonemes for word
        phonemes = self._word_to_phonemes(word)
        
        if not phonemes:
            return Viseme.AA, 0.5  # Default to open mouth
        
        # Get phoneme at current position
        phoneme_idx = int(word_progress * len(phonemes))
        phoneme_idx = min(phoneme_idx, len(phonemes) - 1)
        
        phoneme = phonemes[phoneme_idx]
        viseme = VisemeMapping.get_viseme(phoneme)
        
        # Calculate intensity with smooth envelope
        # Peak in middle of phoneme
        phoneme_progress = (word_progress * len(phonemes)) - phoneme_idx
        intensity = 0.6 + 0.4 * np.sin(phoneme_progress * np.pi)
        
        return viseme, intensity

    def _word_to_phonemes(self, word: str) -> List[str]:
        """Convert word to phonemes."""
        word = word.strip()
        if not word or not any(c.isalpha() for c in word):
            return ["SIL"]
        
        # Clean word
        word = ''.join(c for c in word.lower() if c.isalpha())
        
        # Use G2P if available
        if self._g2p_model is not None:
            try:
                phonemes = self._g2p_model(word)
                # Filter valid phonemes
                return [p for p in phonemes if p.isalpha() or p.isalnum()]
            except:
                pass
        
        # Fallback: simple rule-based estimation
        return self._estimate_phonemes(word)

    def _estimate_phonemes(self, word: str) -> List[str]:
        """Simple rule-based phoneme estimation."""
        phonemes = []
        word = word.lower()
        
        # Common digraphs
        digraphs = {
            'th': 'TH', 'ch': 'CH', 'sh': 'SH', 'ng': 'NG',
            'wh': 'W', 'ph': 'F', 'ck': 'K',
        }
        
        # Vowel mappings
        vowel_map = {
            'a': 'AA', 'e': 'EH', 'i': 'IY', 'o': 'OW', 'u': 'UW',
        }
        
        # Consonant mappings
        consonant_map = {
            'b': 'B', 'c': 'K', 'd': 'D', 'f': 'F', 'g': 'G',
            'h': 'HH', 'j': 'JH', 'k': 'K', 'l': 'L', 'm': 'M',
            'n': 'N', 'p': 'P', 'q': 'K', 'r': 'R', 's': 'S',
            't': 'T', 'v': 'V', 'w': 'W', 'x': 'K', 'y': 'Y', 'z': 'Z',
        }
        
        i = 0
        while i < len(word):
            # Check for digraphs
            if i < len(word) - 1:
                digraph = word[i:i+2]
                if digraph in digraphs:
                    phonemes.append(digraphs[digraph])
                    i += 2
                    continue
            
            char = word[i]
            if char in vowel_map:
                phonemes.append(vowel_map[char])
            elif char in consonant_map:
                phonemes.append(consonant_map[char])
            
            i += 1
        
        return phonemes if phonemes else ["AA"]

    def _get_amplitude_at_time(
        self,
        audio_data: np.ndarray,
        timestamp: float,
        duration: float,
        sample_rate: int,
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
        
        # Normalize with some gain for visibility
        return min(rms * 4, 1.0)

    def _calculate_blend_shapes(
        self,
        viseme: Viseme,
        intensity: float,
        amplitude: float,
    ) -> Dict[str, float]:
        """Calculate blend shapes for a viseme."""
        base_shapes = VISEME_BLEND_SHAPES.get(viseme, VISEME_BLEND_SHAPES[Viseme.SILENCE])
        
        # Scale by intensity and amplitude
        result = {}
        for key, value in base_shapes.items():
            if key in ["jawOpen", "mouthOpen"]:
                # These respond more to amplitude
                result[key] = value * intensity * (0.5 + 0.5 * amplitude)
            else:
                # These respond more to phoneme shape
                result[key] = value * intensity
        
        return result

    def _smooth_frames(
        self,
        frames: List[Dict],
        fps: int,
        smoothing_window: float = 0.04,
    ) -> List[Dict]:
        """Apply smoothing to lip sync frames for natural motion."""
        if len(frames) < 3:
            return frames
        
        window_size = max(1, int(smoothing_window * fps))
        
        # Parameters to smooth
        smooth_keys = ["mouth_open", "mouth_wide", "jaw_open", "intensity"]
        
        def smooth_array(values: List[float]) -> List[float]:
            """Apply moving average smoothing."""
            smoothed = []
            for i in range(len(values)):
                start = max(0, i - window_size)
                end = min(len(values), i + window_size + 1)
                smoothed.append(np.mean(values[start:end]))
            return smoothed
        
        # Smooth each parameter
        for key in smooth_keys:
            values = [f[key] for f in frames]
            smoothed = smooth_array(values)
            for i, frame in enumerate(frames):
                frame[key] = smoothed[i]
        
        # Also smooth blend shapes
        blend_shape_keys = list(frames[0].get("blend_shapes", {}).keys())
        for bs_key in blend_shape_keys:
            values = [f.get("blend_shapes", {}).get(bs_key, 0) for f in frames]
            smoothed = smooth_array(values)
            for i, frame in enumerate(frames):
                if "blend_shapes" not in frame:
                    frame["blend_shapes"] = {}
                frame["blend_shapes"][bs_key] = smoothed[i]
        
        return frames

    async def _load_audio(self, audio_path: str) -> np.ndarray:
        """Load audio file as numpy array."""
        try:
            # Try librosa first for better resampling
            import librosa
            audio, sr = librosa.load(audio_path, sr=22050)
            return audio
        except ImportError:
            pass
        
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

    def get_viseme_at_frame(
        self,
        frames: List[Dict],
        frame_idx: int,
    ) -> Dict:
        """Get lip sync data for a specific frame."""
        if not frames or frame_idx < 0 or frame_idx >= len(frames):
            return {
                "viseme": Viseme.SILENCE.value,
                "mouth_open": 0.0,
                "intensity": 0.0,
            }
        return frames[frame_idx]

    def interpolate_frames(
        self,
        frame_a: Dict,
        frame_b: Dict,
        t: float,
    ) -> Dict:
        """Interpolate between two frames for sub-frame precision."""
        result = {}
        
        for key in ["mouth_open", "mouth_wide", "jaw_open", "intensity"]:
            val_a = frame_a.get(key, 0)
            val_b = frame_b.get(key, 0)
            result[key] = val_a + (val_b - val_a) * t
        
        # Interpolate blend shapes
        result["blend_shapes"] = {}
        bs_a = frame_a.get("blend_shapes", {})
        bs_b = frame_b.get("blend_shapes", {})
        all_keys = set(bs_a.keys()) | set(bs_b.keys())
        
        for key in all_keys:
            val_a = bs_a.get(key, 0)
            val_b = bs_b.get(key, 0)
            result["blend_shapes"][key] = val_a + (val_b - val_a) * t
        
        # Take viseme from closest frame
        result["viseme"] = frame_b["viseme"] if t > 0.5 else frame_a["viseme"]
        
        return result
