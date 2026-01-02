"""Audio-text alignment using Whisper for word-level timing."""
import io
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import structlog

logger = structlog.get_logger()

# CMU Phoneme to Viseme mapping for lip sync
# Based on standard viseme sets used in facial animation
PHONEME_TO_VISEME = {
    # Silence
    "": "sil", "sp": "sil", "spn": "sil", "SIL": "sil",
    
    # Bilabial - lips pressed together (P, B, M)
    "P": "PP", "B": "PP", "M": "PP",
    "p": "PP", "b": "PP", "m": "PP",
    
    # Labiodental - lower lip against upper teeth (F, V)
    "F": "FF", "V": "FF",
    "f": "FF", "v": "FF",
    
    # Interdental - tongue between teeth (TH)
    "TH": "TH", "DH": "TH",
    "th": "TH", "dh": "TH",
    
    # Alveolar - tongue behind upper teeth (T, D, S, Z, N, L)
    "T": "DD", "D": "DD", "N": "DD", "L": "DD",
    "t": "DD", "d": "DD", "n": "DD", "l": "DD",
    "S": "SS", "Z": "SS",
    "s": "SS", "z": "SS",
    
    # Post-alveolar (SH, ZH, CH, JH)
    "SH": "CH", "ZH": "CH", "CH": "CH", "JH": "CH",
    "sh": "CH", "zh": "CH", "ch": "CH", "jh": "CH",
    
    # Velar - back of tongue against soft palate (K, G, NG)
    "K": "kk", "G": "kk", "NG": "kk",
    "k": "kk", "g": "kk", "ng": "kk",
    
    # Glottal (H)
    "HH": "kk", "H": "kk",
    "hh": "kk", "h": "kk",
    
    # Approximants
    "R": "RR", "W": "ww", "Y": "CH",
    "r": "RR", "w": "ww", "y": "CH",
    
    # Vowels - different mouth shapes
    "AA": "aa", "AE": "aa", "AH": "aa", "AO": "aa", "AW": "aa", "AY": "aa",
    "aa": "aa", "ae": "aa", "ah": "aa", "ao": "aa", "aw": "aa", "ay": "aa",
    
    "EH": "E", "ER": "E", "EY": "E",
    "eh": "E", "er": "E", "ey": "E",
    
    "IH": "I", "IY": "I",
    "ih": "I", "iy": "I",
    
    "OW": "O", "OY": "O",
    "ow": "O", "oy": "O",
    
    "UH": "U", "UW": "U",
    "uh": "U", "uw": "U",
}

# Viseme blend shapes for animation
VISEME_BLEND_SHAPES = {
    "sil": {"jawOpen": 0.0, "mouthPucker": 0.0, "mouthSmile": 0.0},
    "PP": {"jawOpen": 0.0, "mouthPucker": 0.3, "mouthSmile": 0.0},  # Lips closed
    "FF": {"jawOpen": 0.1, "mouthPucker": 0.0, "mouthSmile": 0.2},  # Teeth on lip
    "TH": {"jawOpen": 0.2, "mouthPucker": 0.0, "mouthSmile": 0.1},  # Tongue out
    "DD": {"jawOpen": 0.3, "mouthPucker": 0.0, "mouthSmile": 0.1},  # Tongue up
    "kk": {"jawOpen": 0.3, "mouthPucker": 0.0, "mouthSmile": 0.0},  # Back tongue
    "CH": {"jawOpen": 0.2, "mouthPucker": 0.4, "mouthSmile": 0.0},  # Pursed
    "SS": {"jawOpen": 0.2, "mouthPucker": 0.0, "mouthSmile": 0.3},  # Teeth close
    "RR": {"jawOpen": 0.3, "mouthPucker": 0.2, "mouthSmile": 0.0},  # R sound
    "ww": {"jawOpen": 0.2, "mouthPucker": 0.6, "mouthSmile": 0.0},  # W/O sounds
    "aa": {"jawOpen": 0.7, "mouthPucker": 0.0, "mouthSmile": 0.0},  # Open A
    "E": {"jawOpen": 0.4, "mouthPucker": 0.0, "mouthSmile": 0.4},   # E sounds
    "I": {"jawOpen": 0.3, "mouthPucker": 0.0, "mouthSmile": 0.5},   # I sounds
    "O": {"jawOpen": 0.5, "mouthPucker": 0.4, "mouthSmile": 0.0},   # O sounds
    "U": {"jawOpen": 0.3, "mouthPucker": 0.5, "mouthSmile": 0.0},   # U sounds
}


@dataclass
class AlignedWord:
    """Word with timing information."""
    word: str
    start: float  # seconds
    end: float  # seconds
    confidence: float = 1.0
    phonemes: Optional[List[str]] = None
    visemes: Optional[List[Dict]] = None


@dataclass
class AlignedSegment:
    """Segment with words and timing."""
    text: str
    start: float
    end: float
    words: List[AlignedWord]


class AudioAligner:
    """
    Audio-text alignment using Whisper for word-level timing.
    
    This provides accurate word timings for lip sync.
    """

    def __init__(self, model_size: str = "base"):
        """
        Initialize aligner.
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large)
        """
        self.model_size = model_size
        self._model = None
        self._g2p = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize Whisper model and G2P."""
        if self._initialized:
            return

        logger.info("Initializing audio aligner", model_size=self.model_size)

        # Try to load Whisper
        try:
            import whisper
            self._model = whisper.load_model(self.model_size)
            logger.info("Whisper model loaded", model_size=self.model_size)
        except ImportError:
            logger.warning("Whisper not available, using fallback alignment")
        except Exception as e:
            logger.warning("Failed to load Whisper", error=str(e))

        # Try to load G2P for phoneme conversion
        try:
            from g2p_en import G2p
            self._g2p = G2p()
            logger.info("G2P initialized")
        except ImportError:
            logger.warning("g2p_en not available, using simple phoneme estimation")

        self._initialized = True

    async def align(
        self,
        audio: np.ndarray,
        text: str,
        sample_rate: int = 22050,
    ) -> List[AlignedSegment]:
        """
        Align audio with text to get word timings.
        
        Args:
            audio: Audio data as numpy array
            text: Text that was spoken
            sample_rate: Audio sample rate
        
        Returns:
            List of aligned segments with word timings
        """
        if not self._initialized:
            await self.initialize()

        logger.info("Aligning audio with text", text_length=len(text))

        # If Whisper is available, use it
        if self._model is not None:
            return await self._align_with_whisper(audio, text, sample_rate)

        # Fallback: estimate timings based on text
        return self._estimate_timings(audio, text, sample_rate)

    async def align_from_file(
        self,
        audio_path: str,
        text: str,
    ) -> List[AlignedSegment]:
        """Align audio file with text."""
        import wave
        
        with wave.open(audio_path, 'rb') as wav:
            frames = wav.readframes(wav.getnframes())
            audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            sample_rate = wav.getframerate()
        
        return await self.align(audio, text, sample_rate)

    async def _align_with_whisper(
        self,
        audio: np.ndarray,
        text: str,
        sample_rate: int,
    ) -> List[AlignedSegment]:
        """Use Whisper for accurate alignment."""
        import whisper
        
        # Resample to 16kHz if needed (Whisper requirement)
        if sample_rate != 16000:
            try:
                import librosa
                audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)
            except ImportError:
                # Simple resampling fallback
                ratio = 16000 / sample_rate
                new_length = int(len(audio) * ratio)
                indices = np.linspace(0, len(audio) - 1, new_length).astype(int)
                audio = audio[indices]
        
        # Run Whisper transcription with word timestamps
        result = self._model.transcribe(
            audio,
            word_timestamps=True,
            language="en",
        )
        
        return self._parse_whisper_result(result, text)

    def _estimate_timings(
        self,
        audio: np.ndarray,
        text: str,
        sample_rate: int,
    ) -> List[AlignedSegment]:
        """Estimate word timings based on text length."""
        duration = len(audio) / sample_rate
        words = text.split()
        
        if not words:
            return []

        # Estimate based on word length and common speech patterns
        total_chars = sum(len(w) for w in words)
        if total_chars == 0:
            total_chars = 1
        
        aligned_words = []
        current_time = 0.0
        
        for word in words:
            # Word duration proportional to length
            word_ratio = len(word) / total_chars
            word_duration = duration * word_ratio
            
            # Add phonemes and visemes
            phonemes = self.get_phonemes(word)
            visemes = self.phonemes_to_visemes(phonemes, current_time, word_duration)
            
            aligned_words.append(AlignedWord(
                word=word,
                start=current_time,
                end=current_time + word_duration,
                confidence=0.7,
                phonemes=phonemes,
                visemes=visemes,
            ))
            current_time += word_duration

        return [AlignedSegment(
            text=text,
            start=0.0,
            end=duration,
            words=aligned_words,
        )]

    def _parse_whisper_result(
        self,
        result: dict,
        original_text: str,
    ) -> List[AlignedSegment]:
        """Parse Whisper transcription result."""
        segments = []
        
        for seg in result.get("segments", []):
            words = []
            for word_info in seg.get("words", []):
                word = word_info["word"].strip()
                phonemes = self.get_phonemes(word)
                word_duration = word_info["end"] - word_info["start"]
                visemes = self.phonemes_to_visemes(
                    phonemes, word_info["start"], word_duration
                )
                
                words.append(AlignedWord(
                    word=word,
                    start=word_info["start"],
                    end=word_info["end"],
                    confidence=word_info.get("probability", 1.0),
                    phonemes=phonemes,
                    visemes=visemes,
                ))
            
            segments.append(AlignedSegment(
                text=seg["text"].strip(),
                start=seg["start"],
                end=seg["end"],
                words=words,
            ))
        
        return segments

    def get_phonemes(self, word: str, language: str = "en") -> List[str]:
        """
        Get phonemes for a word.
        
        Args:
            word: Input word
            language: Language code
        
        Returns:
            List of phoneme strings
        """
        word = word.strip().lower()
        
        if not word or not word.isalpha():
            return ["SIL"]
        
        # Use G2P if available
        if self._g2p is not None:
            try:
                phonemes = self._g2p(word)
                # Filter out stress markers
                return [p for p in phonemes if p.isalpha()]
            except:
                pass
        
        # Fallback: simple rule-based phoneme estimation
        return self._estimate_phonemes(word)

    def _estimate_phonemes(self, word: str) -> List[str]:
        """Simple rule-based phoneme estimation."""
        phonemes = []
        word = word.lower()
        
        # Common digraphs
        digraphs = {
            'th': 'TH', 'sh': 'SH', 'ch': 'CH', 'wh': 'W',
            'ph': 'F', 'ng': 'NG', 'ck': 'K', 'qu': 'KW',
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
            
            # Map single characters
            if char in 'aeiou':
                vowel_map = {'a': 'AA', 'e': 'EH', 'i': 'IY', 'o': 'OW', 'u': 'UW'}
                phonemes.append(vowel_map[char])
            elif char.isalpha():
                consonant_map = {
                    'b': 'B', 'c': 'K', 'd': 'D', 'f': 'F', 'g': 'G',
                    'h': 'HH', 'j': 'JH', 'k': 'K', 'l': 'L', 'm': 'M',
                    'n': 'N', 'p': 'P', 'r': 'R', 's': 'S', 't': 'T',
                    'v': 'V', 'w': 'W', 'x': 'KS', 'y': 'Y', 'z': 'Z',
                }
                phonemes.append(consonant_map.get(char, char.upper()))
            
            i += 1
        
        return phonemes if phonemes else ["SIL"]

    def phonemes_to_visemes(
        self,
        phonemes: List[str],
        start_time: float,
        duration: float,
    ) -> List[Dict]:
        """
        Convert phonemes to viseme timeline for lip sync.
        
        Args:
            phonemes: List of phoneme strings
            start_time: Start time in seconds
            duration: Total duration in seconds
        
        Returns:
            List of viseme dictionaries with timing and blend shapes
        """
        if not phonemes:
            return [{
                "viseme": "sil",
                "start": start_time,
                "end": start_time + duration,
                "blendShapes": VISEME_BLEND_SHAPES["sil"],
            }]
        
        visemes = []
        time_per_phoneme = duration / len(phonemes)
        current_time = start_time
        
        for phoneme in phonemes:
            viseme_id = PHONEME_TO_VISEME.get(phoneme, "sil")
            blend_shapes = VISEME_BLEND_SHAPES.get(viseme_id, VISEME_BLEND_SHAPES["sil"])
            
            visemes.append({
                "viseme": viseme_id,
                "phoneme": phoneme,
                "start": current_time,
                "end": current_time + time_per_phoneme,
                "blendShapes": blend_shapes.copy(),
            })
            current_time += time_per_phoneme
        
        return visemes

    def adjust_for_speed(
        self,
        segments: List[AlignedSegment],
        speed_factor: float,
    ) -> List[AlignedSegment]:
        """Adjust timings for different playback speed."""
        adjusted = []
        
        for seg in segments:
            adjusted_words = []
            for word in seg.words:
                # Adjust viseme timings too
                adjusted_visemes = None
                if word.visemes:
                    adjusted_visemes = []
                    for v in word.visemes:
                        adjusted_visemes.append({
                            **v,
                            "start": v["start"] / speed_factor,
                            "end": v["end"] / speed_factor,
                        })
                
                adjusted_words.append(AlignedWord(
                    word=word.word,
                    start=word.start / speed_factor,
                    end=word.end / speed_factor,
                    confidence=word.confidence,
                    phonemes=word.phonemes,
                    visemes=adjusted_visemes,
                ))
            
            adjusted.append(AlignedSegment(
                text=seg.text,
                start=seg.start / speed_factor,
                end=seg.end / speed_factor,
                words=adjusted_words,
            ))
        
        return adjusted

    def get_viseme_at_time(
        self,
        segments: List[AlignedSegment],
        time: float,
    ) -> Dict:
        """Get the viseme active at a specific time."""
        for segment in segments:
            if segment.start <= time <= segment.end:
                for word in segment.words:
                    if word.start <= time <= word.end and word.visemes:
                        for viseme in word.visemes:
                            if viseme["start"] <= time <= viseme["end"]:
                                return viseme
        
        return {
            "viseme": "sil",
            "start": time,
            "end": time,
            "blendShapes": VISEME_BLEND_SHAPES["sil"],
        }

    def interpolate_visemes(
        self,
        visemes: List[Dict],
        fps: int = 30,
    ) -> List[Dict]:
        """
        Interpolate visemes to create smooth animation frames.
        
        Args:
            visemes: List of viseme dictionaries
            fps: Target frames per second
        
        Returns:
            List of interpolated blend shape frames
        """
        if not visemes:
            return []
        
        frames = []
        start_time = visemes[0]["start"]
        end_time = visemes[-1]["end"]
        total_frames = int((end_time - start_time) * fps)
        
        for frame_idx in range(total_frames):
            time = start_time + (frame_idx / fps)
            
            # Find surrounding visemes
            prev_viseme = None
            next_viseme = None
            
            for i, v in enumerate(visemes):
                if v["end"] >= time:
                    next_viseme = v
                    if i > 0:
                        prev_viseme = visemes[i - 1]
                    else:
                        prev_viseme = v
                    break
            
            if not next_viseme:
                next_viseme = visemes[-1]
                prev_viseme = visemes[-1]
            
            # Interpolate blend shapes
            if prev_viseme == next_viseme:
                blend_shapes = prev_viseme["blendShapes"].copy()
            else:
                # Linear interpolation
                t = (time - prev_viseme["end"]) / max(
                    next_viseme["start"] - prev_viseme["end"], 0.001
                )
                t = max(0, min(1, t))
                
                blend_shapes = {}
                for key in prev_viseme["blendShapes"]:
                    prev_val = prev_viseme["blendShapes"].get(key, 0)
                    next_val = next_viseme["blendShapes"].get(key, 0)
                    blend_shapes[key] = prev_val + (next_val - prev_val) * t
            
            frames.append({
                "frame": frame_idx,
                "time": time,
                "blendShapes": blend_shapes,
            })
        
        return frames


# Singleton instance
_aligner_instance: Optional[AudioAligner] = None


async def get_aligner(model_size: str = "base") -> AudioAligner:
    """Get or create singleton aligner instance."""
    global _aligner_instance
    
    if _aligner_instance is None:
        _aligner_instance = AudioAligner(model_size)
        await _aligner_instance.initialize()
    
    return _aligner_instance
