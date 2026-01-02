"""Text-to-Speech Engine using Coqui XTTS v2."""
import io
import os
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Tuple

import numpy as np
import structlog

logger = structlog.get_logger()

# Viseme mapping for lip sync (phoneme to mouth shape)
PHONEME_TO_VISEME = {
    # Silence
    "": "sil", "sp": "sil", "spn": "sil",
    # Bilabial (lips together)
    "p": "PP", "b": "PP", "m": "PP",
    # Labiodental (teeth on lip)
    "f": "FF", "v": "FF",
    # Dental/Alveolar
    "th": "TH", "dh": "TH",
    "t": "DD", "d": "DD", "n": "DD", "l": "DD",
    "s": "SS", "z": "SS",
    # Post-alveolar
    "sh": "SS", "zh": "SS", "ch": "SS", "jh": "SS",
    # Velar
    "k": "kk", "g": "kk", "ng": "kk",
    # Glottal
    "hh": "kk", "h": "kk",
    # Approximants
    "r": "RR", "w": "ww", "y": "CH",
    # Vowels
    "aa": "aa", "ae": "aa", "ah": "aa", "ao": "aa", "aw": "aa",
    "ay": "aa", "eh": "E", "er": "E", "ey": "E",
    "ih": "I", "iy": "I",
    "ow": "O", "oy": "O",
    "uh": "U", "uw": "U",
}


@dataclass
class WordTiming:
    """Word timing information for lip sync."""
    word: str
    start_time: float  # seconds
    end_time: float  # seconds
    phonemes: Optional[List[str]] = None


@dataclass
class TTSResult:
    """TTS generation result."""
    audio_data: bytes
    sample_rate: int
    duration: float  # seconds
    word_timings: List[WordTiming]
    format: str = "wav"


class TTSEngine:
    """
    Text-to-Speech engine with Coqui XTTS v2 support.
    
    Features:
    - High-quality voice synthesis
    - Voice cloning from samples
    - Word-level timing for lip sync
    - Streaming audio generation
    - Multiple language support
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "auto",
    ):
        self.model_path = model_path or os.getenv("TTS_MODEL_PATH", "/app/models")
        self.device = self._detect_device(device)
        self._model = None
        self._config = None
        self._initialized = False
        self._use_xtts = False

    def _detect_device(self, device: str) -> str:
        """Detect available compute device."""
        if device != "auto":
            return device
        
        try:
            import torch
            if torch.cuda.is_available():
                logger.info("CUDA available, using GPU")
                return "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                logger.info("MPS available, using Apple Silicon GPU")
                return "mps"
        except ImportError:
            pass
        
        logger.info("Using CPU for TTS")
        return "cpu"

    async def initialize(self) -> None:
        """Initialize TTS models."""
        if self._initialized:
            return

        logger.info("Initializing TTS engine", device=self.device)

        try:
            # Try to load Coqui TTS
            from TTS.api import TTS
            
            # Load XTTS v2 model
            logger.info("Loading XTTS v2 model...")
            self._model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
            
            # Move to device
            if self.device == "cuda":
                self._model.to("cuda")
            
            self._use_xtts = True
            self._initialized = True
            logger.info("XTTS v2 model loaded successfully")

        except ImportError as e:
            logger.warning(
                "TTS library not available, using fallback synthesizer",
                error=str(e),
            )
            self._use_xtts = False
            self._initialized = True

        except Exception as e:
            logger.warning(
                "Failed to load XTTS model, using fallback",
                error=str(e),
            )
            self._use_xtts = False
            self._initialized = True

    async def synthesize(
        self,
        text: str,
        voice_sample: Optional[str] = None,
        language: str = "en",
        speed: float = 1.0,
        pitch: float = 1.0,
    ) -> TTSResult:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            voice_sample: Path to voice sample for cloning
            language: Language code (en, es, fr, de, it, pt, pl, tr, ru, nl, cs, ar, zh-cn, ja, hu, ko)
            speed: Speech speed multiplier
            pitch: Pitch multiplier (not supported in XTTS)
        
        Returns:
            TTSResult with audio data and word timings
        """
        if not self._initialized:
            await self.initialize()

        logger.info(
            "Synthesizing speech",
            text_length=len(text),
            language=language,
            use_xtts=self._use_xtts,
        )

        if self._use_xtts and self._model:
            return await self._synthesize_xtts(text, voice_sample, language, speed)
        else:
            return await self._synthesize_fallback(text, speed)

    async def _synthesize_xtts(
        self,
        text: str,
        voice_sample: Optional[str],
        language: str,
        speed: float,
    ) -> TTSResult:
        """Synthesize using XTTS v2."""
        import torch
        
        # Process text into sentences for better synthesis
        sentences = self._split_sentences(text)
        
        audio_chunks = []
        word_timings = []
        current_time = 0.0
        sample_rate = 24000  # XTTS default
        
        # Get or create voice sample path
        speaker_wav = voice_sample
        if not speaker_wav or not Path(speaker_wav).exists():
            # Use default voice sample
            default_voice = Path(self.model_path) / "default_voice.wav"
            if default_voice.exists():
                speaker_wav = str(default_voice)
            else:
                # Create a simple default voice reference
                speaker_wav = self._create_default_voice()
        
        for sentence in sentences:
            if not sentence.strip():
                continue
            
            # Generate audio with XTTS
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
            
            try:
                # Run synthesis
                self._model.tts_to_file(
                    text=sentence,
                    file_path=tmp_path,
                    speaker_wav=speaker_wav,
                    language=language,
                    split_sentences=False,
                )
                
                # Read the generated audio
                with wave.open(tmp_path, 'rb') as wav:
                    frames = wav.readframes(wav.getnframes())
                    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                    sample_rate = wav.getframerate()
                
                # Adjust speed if needed
                if speed != 1.0:
                    audio = self._change_speed(audio, sample_rate, speed)
                
                audio_chunks.append(audio)
                
                # Generate word timings
                sentence_duration = len(audio) / sample_rate
                sentence_timings = self._estimate_word_timings(
                    sentence, current_time, sentence_duration
                )
                word_timings.extend(sentence_timings)
                current_time += sentence_duration
                
            finally:
                # Cleanup temp file
                try:
                    os.unlink(tmp_path)
                except:
                    pass
        
        # Concatenate audio
        if audio_chunks:
            full_audio = np.concatenate(audio_chunks)
        else:
            full_audio = np.zeros(int(sample_rate * 0.1), dtype=np.float32)
        
        # Convert to bytes
        audio_bytes = self._audio_to_bytes(full_audio, sample_rate)
        
        return TTSResult(
            audio_data=audio_bytes,
            sample_rate=sample_rate,
            duration=len(full_audio) / sample_rate,
            word_timings=word_timings,
            format="wav",
        )

    async def _synthesize_fallback(
        self,
        text: str,
        speed: float,
    ) -> TTSResult:
        """Fallback synthesizer using simple signal generation."""
        sample_rate = 22050
        
        # Split into words
        words = text.split()
        if not words:
            audio = np.zeros(int(sample_rate * 0.1), dtype=np.float32)
            return TTSResult(
                audio_data=self._audio_to_bytes(audio, sample_rate),
                sample_rate=sample_rate,
                duration=0.1,
                word_timings=[],
            )
        
        # Estimate duration (~150 words per minute at normal speed)
        words_per_second = 2.5 * speed
        duration = len(words) / words_per_second
        
        # Generate word timings
        word_timings = []
        time_per_word = duration / len(words)
        for i, word in enumerate(words):
            word_timings.append(WordTiming(
                word=word,
                start_time=i * time_per_word,
                end_time=(i + 1) * time_per_word,
            ))
        
        # Generate audio placeholder (silence with slight noise)
        num_samples = int(duration * sample_rate)
        audio = np.random.randn(num_samples).astype(np.float32) * 0.001
        
        # Add some variation to make it more realistic
        for timing in word_timings:
            start_sample = int(timing.start_time * sample_rate)
            end_sample = int(timing.end_time * sample_rate)
            # Add a slight bump for each word
            word_samples = end_sample - start_sample
            envelope = np.sin(np.linspace(0, np.pi, word_samples)) * 0.01
            audio[start_sample:end_sample] += envelope
        
        audio_bytes = self._audio_to_bytes(audio, sample_rate)
        
        return TTSResult(
            audio_data=audio_bytes,
            sample_rate=sample_rate,
            duration=duration,
            word_timings=word_timings,
        )

    async def synthesize_stream(
        self,
        text: str,
        voice_sample: Optional[str] = None,
        language: str = "en",
        chunk_size: int = 4096,
    ) -> AsyncGenerator[Tuple[bytes, List[WordTiming]], None]:
        """
        Stream synthesized speech in chunks.
        
        Yields:
            Tuple of (audio_chunk, word_timings_for_chunk)
        """
        if not self._initialized:
            await self.initialize()

        # For streaming, we synthesize the full audio then stream chunks
        result = await self.synthesize(text, voice_sample, language)
        
        # Stream in chunks
        audio_data = result.audio_data
        current_pos = 0
        current_time = 0.0
        chunk_duration = chunk_size / result.sample_rate
        
        while current_pos < len(audio_data):
            chunk = audio_data[current_pos:current_pos + chunk_size]
            
            # Find timings for this chunk
            chunk_timings = [
                t for t in result.word_timings
                if t.start_time >= current_time and t.start_time < current_time + chunk_duration
            ]
            
            yield chunk, chunk_timings
            
            current_pos += chunk_size
            current_time += chunk_duration

    async def clone_voice(
        self,
        audio_sample: bytes,
        name: str,
    ) -> Dict:
        """
        Create a voice profile from an audio sample.
        
        Args:
            audio_sample: Audio data of voice sample (WAV format)
            name: Name for the voice profile
        
        Returns:
            Voice profile configuration
        """
        logger.info("Creating voice clone", name=name)
        
        # Save the voice sample
        voices_dir = Path(self.model_path) / "voices"
        voices_dir.mkdir(parents=True, exist_ok=True)
        
        voice_path = voices_dir / f"{name}.wav"
        voice_path.write_bytes(audio_sample)
        
        return {
            "name": name,
            "path": str(voice_path),
            "created": True,
        }

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences for processing."""
        import re
        
        # Handle [PAUSE] markers
        text = re.sub(r'\[PAUSE\]', '.', text)
        
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Filter empty sentences and clean up
        return [s.strip() for s in sentences if s.strip()]

    def _estimate_word_timings(
        self,
        text: str,
        start_time: float,
        duration: float,
    ) -> List[WordTiming]:
        """Estimate word timings from text duration."""
        words = text.split()
        if not words:
            return []
        
        # Simple estimation based on word length
        total_chars = sum(len(w) for w in words)
        if total_chars == 0:
            return []
        
        timings = []
        current_time = start_time
        
        for word in words:
            word_duration = (len(word) / total_chars) * duration
            timings.append(WordTiming(
                word=word,
                start_time=current_time,
                end_time=current_time + word_duration,
                phonemes=self._get_phonemes(word),
            ))
            current_time += word_duration
        
        return timings

    def _get_phonemes(self, word: str) -> List[str]:
        """Get approximate phonemes for a word."""
        # Simple phoneme estimation
        # In production, use g2p (grapheme to phoneme) library
        phonemes = []
        word = word.lower()
        
        vowels = set('aeiou')
        i = 0
        while i < len(word):
            char = word[i]
            
            # Check for digraphs
            if i < len(word) - 1:
                digraph = word[i:i+2]
                if digraph in ['th', 'sh', 'ch', 'wh', 'ph', 'ng']:
                    phonemes.append(digraph)
                    i += 2
                    continue
            
            if char in vowels:
                phonemes.append(char + char)  # Double for long vowel
            elif char.isalpha():
                phonemes.append(char)
            
            i += 1
        
        return phonemes

    def _change_speed(
        self,
        audio: np.ndarray,
        sample_rate: int,
        speed: float,
    ) -> np.ndarray:
        """Change audio playback speed without changing pitch."""
        try:
            import librosa
            return librosa.effects.time_stretch(audio, rate=speed)
        except ImportError:
            # Simple resampling fallback
            new_length = int(len(audio) / speed)
            indices = np.linspace(0, len(audio) - 1, new_length).astype(int)
            return audio[indices]

    def _create_default_voice(self) -> str:
        """Create a default voice sample for XTTS."""
        # Generate a simple sine wave as placeholder
        sample_rate = 22050
        duration = 3.0
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        # Generate speech-like audio
        audio = np.sin(2 * np.pi * 200 * t) * 0.3
        audio += np.sin(2 * np.pi * 400 * t) * 0.2
        audio += np.sin(2 * np.pi * 800 * t) * 0.1
        
        # Add envelope
        envelope = np.ones_like(audio)
        attack = int(0.1 * sample_rate)
        envelope[:attack] = np.linspace(0, 1, attack)
        envelope[-attack:] = np.linspace(1, 0, attack)
        audio *= envelope
        
        # Save to temp file
        voice_path = Path(self.model_path) / "default_voice.wav"
        voice_path.parent.mkdir(parents=True, exist_ok=True)
        
        audio_bytes = self._audio_to_bytes(audio.astype(np.float32), sample_rate)
        voice_path.write_bytes(audio_bytes)
        
        return str(voice_path)

    def _audio_to_bytes(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> bytes:
        """Convert numpy audio to WAV bytes."""
        # Normalize and convert to int16
        audio = np.clip(audio, -1.0, 1.0)
        audio_int16 = (audio * 32767).astype(np.int16)
        
        # Create WAV file in memory
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(audio_int16.tobytes())
        
        return buffer.getvalue()

    def get_available_voices(self) -> List[Dict]:
        """Get list of available voice profiles."""
        voices = [
            {"id": "default", "name": "Default Voice", "language": "en", "type": "builtin"},
        ]
        
        # List cloned voices
        voices_dir = Path(self.model_path) / "voices"
        if voices_dir.exists():
            for voice_file in voices_dir.glob("*.wav"):
                voices.append({
                    "id": voice_file.stem,
                    "name": voice_file.stem.replace("_", " ").title(),
                    "language": "en",
                    "type": "cloned",
                })
        
        return voices

    def get_supported_languages(self) -> List[Dict]:
        """Get list of supported languages."""
        return [
            {"code": "en", "name": "English"},
            {"code": "es", "name": "Spanish"},
            {"code": "fr", "name": "French"},
            {"code": "de", "name": "German"},
            {"code": "it", "name": "Italian"},
            {"code": "pt", "name": "Portuguese"},
            {"code": "pl", "name": "Polish"},
            {"code": "tr", "name": "Turkish"},
            {"code": "ru", "name": "Russian"},
            {"code": "nl", "name": "Dutch"},
            {"code": "cs", "name": "Czech"},
            {"code": "ar", "name": "Arabic"},
            {"code": "zh-cn", "name": "Chinese"},
            {"code": "ja", "name": "Japanese"},
            {"code": "hu", "name": "Hungarian"},
            {"code": "ko", "name": "Korean"},
        ]
