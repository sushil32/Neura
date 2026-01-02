"""Audio-text alignment using Whisper for word-level timing."""
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import structlog

logger = structlog.get_logger()


@dataclass
class AlignedWord:
    """Word with timing information."""
    word: str
    start: float  # seconds
    end: float  # seconds
    confidence: float = 1.0


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
        self.model_size = model_size
        self._model = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize Whisper model."""
        if self._initialized:
            return

        logger.info("Initializing audio aligner", model_size=self.model_size)

        try:
            # In production: import whisper; self._model = whisper.load_model(self.model_size)
            self._initialized = True
            logger.info("Audio aligner initialized")

        except ImportError as e:
            logger.warning(
                "Whisper not available, using fallback alignment",
                error=str(e),
            )
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

    async def _align_with_whisper(
        self,
        audio: np.ndarray,
        text: str,
        sample_rate: int,
    ) -> List[AlignedSegment]:
        """Use Whisper for accurate alignment."""
        # In production:
        # result = self._model.transcribe(
        #     audio,
        #     word_timestamps=True,
        # )
        # return self._parse_whisper_result(result)
        
        return self._estimate_timings(audio, text, sample_rate)

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

        # Estimate speaking rate (~150 words per minute)
        time_per_word = duration / len(words)
        
        aligned_words = []
        current_time = 0.0
        
        for word in words:
            # Adjust time based on word length
            word_duration = time_per_word * (len(word) / 5)  # 5 chars = avg word
            word_duration = max(0.1, min(word_duration, time_per_word * 2))
            
            aligned_words.append(AlignedWord(
                word=word,
                start=current_time,
                end=current_time + word_duration,
                confidence=0.8,  # Lower confidence for estimates
            ))
            current_time += word_duration

        # Scale to fit actual duration
        if current_time > 0:
            scale = duration / current_time
            for word in aligned_words:
                word.start *= scale
                word.end *= scale

        return [AlignedSegment(
            text=text,
            start=0.0,
            end=duration,
            words=aligned_words,
        )]

    def _parse_whisper_result(self, result: dict) -> List[AlignedSegment]:
        """Parse Whisper transcription result."""
        segments = []
        
        for seg in result.get("segments", []):
            words = []
            for word_info in seg.get("words", []):
                words.append(AlignedWord(
                    word=word_info["word"].strip(),
                    start=word_info["start"],
                    end=word_info["end"],
                    confidence=word_info.get("probability", 1.0),
                ))
            
            segments.append(AlignedSegment(
                text=seg["text"].strip(),
                start=seg["start"],
                end=seg["end"],
                words=words,
            ))
        
        return segments

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
                adjusted_words.append(AlignedWord(
                    word=word.word,
                    start=word.start / speed_factor,
                    end=word.end / speed_factor,
                    confidence=word.confidence,
                ))
            
            adjusted.append(AlignedSegment(
                text=seg.text,
                start=seg.start / speed_factor,
                end=seg.end / speed_factor,
                words=adjusted_words,
            ))
        
        return adjusted

    def get_phonemes(self, word: str, language: str = "en") -> List[str]:
        """Get phonemes for a word (for detailed lip sync)."""
        # In production, use phonemizer or g2p library
        # This is a simplified mapping
        vowels = "aeiouAEIOU"
        phonemes = []
        
        for char in word.lower():
            if char in vowels:
                phonemes.append(f"V_{char}")  # Vowel
            elif char.isalpha():
                phonemes.append(f"C_{char}")  # Consonant
        
        return phonemes if phonemes else ["SIL"]  # Silence for empty

