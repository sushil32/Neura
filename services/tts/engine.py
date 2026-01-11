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
import subprocess

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
        self.use_mastering = os.getenv("TTS_USE_MASTERING", "true").lower() == "true"

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

        if os.getenv("FORCE_FALLBACK_TTS", "").lower() == "true":
            logger.info("FORCE_FALLBACK_TTS enabled, skipping XTTS load")
            self._use_xtts = False
            self._initialized = True
            return

        logger.info("Initializing TTS engine", device=self.device)

        try:
            # Try to load Coqui TTS
            from TTS.api import TTS
            
            # Fix for PyTorch 2.6+ weights_only=True default
            # Register TTS config classes as safe for unpickling
            import torch
            try:
                # Import and register all needed TTS classes
                from TTS.tts.configs.xtts_config import XttsConfig
                from TTS.tts.models.xtts import XttsArgs, XttsAudioConfig
                from TTS.config import BaseDatasetConfig
                safe_classes = [XttsConfig, XttsArgs, XttsAudioConfig, BaseDatasetConfig]
                torch.serialization.add_safe_globals(safe_classes)
                logger.info("Registered TTS config classes for PyTorch 2.6+ compatibility")
            except Exception as e:
                logger.warning(f"Could not register safe globals, will try with weights_only=False: {e}")
                # Fallback: monkeypatch torch.load to use weights_only=False
                original_torch_load = torch.load
                def patched_load(*args, **kwargs):
                    kwargs['weights_only'] = False
                    return original_torch_load(*args, **kwargs)
                torch.load = patched_load
                logger.info("Patched torch.load to use weights_only=False")
            
            # Load XTTS v2 model
            logger.info("Loading XTTS v2 model...")
            self._model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
            
            # Move to detected device (GPU/MPS/CPU)
            if self.device in ["cuda", "mps"]:
                try:
                    self._model.to(self.device)
                    logger.info(f"Model moved to {self.device.upper()}")
                except Exception as e:
                    logger.warning(f"Failed to move model to {self.device}, falling back to CPU: {e}")
                    self.device = "cpu"
            
            self._use_xtts = True
            self._initialized = True
            logger.info(f"XTTS v2 model loaded successfully on {self.device.upper()}")

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

    async def _ensure_voice_format(self, audio_path: str) -> str:
        """
        Ensure voice sample is in proper format for XTTS (24kHz mono WAV).
        Converts from other formats (M4A, MP3, etc.) if needed.
        """
        import subprocess
        
        audio_path_obj = Path(audio_path)
        
        # Check if already converted
        converted_path = audio_path_obj.parent / f"{audio_path_obj.stem}_converted.wav"
        if converted_path.exists():
            return str(converted_path)
        
        # Try to detect if conversion is needed using ffprobe
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "a:0",
                 "-show_entries", "stream=sample_rate,codec_name",
                 "-of", "csv=p=0", str(audio_path)],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(",")
                codec = parts[0] if len(parts) > 0 else ""
                sample_rate = int(parts[1]) if len(parts) > 1 else 0
                
                # If already 24kHz PCM WAV, use as-is
                if codec == "pcm_s16le" and sample_rate == 24000:
                    logger.info("Voice sample already in correct format", path=str(audio_path))
                    return str(audio_path)
            
            # Convert to 24kHz mono WAV for optimal XTTS quality
            logger.info("Converting voice sample to XTTS format", 
                       source=str(audio_path), target=str(converted_path))
            
            convert_result = subprocess.run([
                "ffmpeg", "-y", "-i", str(audio_path),
                "-ar", "24000",  # 24kHz sample rate (XTTS native)
                "-ac", "1",      # Mono
                "-c:a", "pcm_s16le",  # 16-bit PCM
                str(converted_path)
            ], capture_output=True, timeout=60)
            
            if convert_result.returncode == 0 and converted_path.exists():
                logger.info("Voice sample converted successfully", path=str(converted_path))
                return str(converted_path)
            else:
                logger.warning("Voice conversion failed, using original", 
                             error=convert_result.stderr.decode()[:200])
                
        except Exception as e:
            logger.warning("Voice format check failed, using original", error=str(e))
        
        return str(audio_path)

    async def synthesize(
        self,
        text: str,
        voice_sample: Optional[str] = None,
        language: str = "en",
        speed: float = 1.3, # 1.3x is closer to natural human conversational pace in XTTS v2
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
            try:
                result = await self._synthesize_xtts(text, voice_sample, language, speed)
                
                # Apply mastering if enabled
                if self.use_mastering:
                    result.audio_data, new_duration = await self._post_process_audio(result.audio_data)
                    if new_duration:
                        result.duration = new_duration
                
                return result
            except Exception as e:
                logger.error("XTTS synthesis failed, falling back", error=str(e))
                return await self._synthesize_fallback(text, speed)
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
        
        # Map builtin IDs to internal XTTS speaker embeddings (high quality)
        BUILTIN_SPEAKER_MAPPING = {
            "alex": "Damien Black",
            "sarah": "Claribel Dervla",
            "james": "Baldur Sanjin",
            "emma": "Alison Dietlinde",
            "david": "Viktor Eka",
            "default": "Andrew Chipper",
        }
        
        # Get or create voice sample path (for cloned voices)
        speaker_wav = voice_sample
        internal_speaker = None
        
        # If no path provided, check if it's a builtin ID
        voice_id_lower = str(voice_sample).lower().replace(" ", "_") if voice_sample else "default"
        
        # Check if this is a builtin voice (use internal speaker)
        if voice_id_lower in BUILTIN_SPEAKER_MAPPING:
            internal_speaker = BUILTIN_SPEAKER_MAPPING[voice_id_lower]
            speaker_wav = None  # Don't use cloning for builtins
        else:
            # Try to find cloned voice by name
            cloned_voice_paths = [
                Path(self.model_path).parent / "voices" / f"{voice_id_lower}.wav",
                Path(self.model_path) / "voices" / f"{voice_id_lower}.wav",
            ]
            
            found = False
            for candidate_path in cloned_voice_paths:
                if candidate_path.exists():
                    speaker_wav = str(candidate_path)
                    found = True
                    logger.info("Found cloned voice", voice_id=voice_id_lower, path=speaker_wav)
                    break
            
            if not found:
                # Fallback to default voice
                default_voice = Path(self.model_path) / "default_voice.wav"
                if default_voice.exists():
                    speaker_wav = str(default_voice)
                else:
                    speaker_wav = self._create_default_voice(voice_id_lower)
        
        # Convert audio to proper format for XTTS if needed (24kHz WAV)
        if speaker_wav and Path(speaker_wav).exists():
            speaker_wav = await self._ensure_voice_format(speaker_wav)
        
        for sentence in sentences:
            if not sentence.strip():
                continue
            
            # Generate audio with XTTS
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
            
            try:
                # Run synthesis - use internal speaker for builtins, cloning for custom
                if internal_speaker:
                    self._model.tts_to_file(
                        text=sentence,
                        file_path=tmp_path,
                        speaker=internal_speaker,
                        language=language,
                        split_sentences=False,
                        speed=speed,
                    )
                else:
                    self._model.tts_to_file(
                        text=sentence,
                        file_path=tmp_path,
                        speaker_wav=speaker_wav,
                        language=language,
                        split_sentences=False,
                        speed=speed,
                    )
                
                # Read the generated audio
                with wave.open(tmp_path, 'rb') as wav:
                    frames = wav.readframes(wav.getnframes())
                    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                    sample_rate = wav.getframerate()
                
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
        """Fallback synthesizer generating audible speech-like tones."""
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
        
        # Generate audible audio with speech-like patterns
        num_samples = int(duration * sample_rate)
        audio = np.zeros(num_samples, dtype=np.float32)
        
        # Base frequencies for speech-like sounds
        base_freq = 150  # Male-ish fundamental
        
        for i, timing in enumerate(word_timings):
            start_sample = int(timing.start_time * sample_rate)
            end_sample = int(timing.end_time * sample_rate)
            word_samples = end_sample - start_sample
            
            if word_samples <= 0:
                continue
            
            # Time array for this word
            t = np.linspace(0, timing.end_time - timing.start_time, word_samples)
            
            # Vary frequency slightly per word for natural variation
            word_freq = base_freq + (i % 5) * 20 + len(timing.word) * 5
            
            # Create harmonic-rich tone (fundamental + harmonics = speech-like)
            word_audio = np.sin(2 * np.pi * word_freq * t) * 0.3
            word_audio += np.sin(2 * np.pi * word_freq * 2 * t) * 0.15  # 2nd harmonic
            word_audio += np.sin(2 * np.pi * word_freq * 3 * t) * 0.08  # 3rd harmonic
            
            # Add envelope (attack, sustain, release) for natural sound
            envelope = np.ones(word_samples)
            attack = min(int(0.05 * sample_rate), word_samples // 4)
            release = min(int(0.08 * sample_rate), word_samples // 4)
            
            if attack > 0:
                envelope[:attack] = np.linspace(0, 1, attack)
            if release > 0:
                envelope[-release:] = np.linspace(1, 0, release)
            
            word_audio *= envelope
            
            # Add small gap between words
            gap_samples = int(0.02 * sample_rate)
            if word_samples > gap_samples * 2:
                word_audio[-gap_samples:] = 0
            
            # Add to main audio
            audio[start_sample:end_sample] = word_audio
        
        # Normalize to prevent clipping
        max_val = np.max(np.abs(audio))
        if max_val > 0:
            audio = audio / max_val * 0.7
        
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
        speed: float = 1.0,
        pitch: float = 1.0,
        chunk_size: int = 4096,
    ) -> AsyncGenerator[Tuple[bytes, List[WordTiming]], None]:
        """
        Stream synthesized speech in chunks with full quality parity.
        """
        if not self._initialized:
            await self.initialize()

        # For streaming, we use the full synthesis logic (including speed and mastering)
        # then stream the resulting bytes in chunks.
        result = await self.synthesize(text, voice_sample, language, speed, pitch)
        
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

    def _create_default_voice(self, voice_id: str = "default") -> str:
        """Create a default voice sample for XTTS if the real one is missing."""
        # Generate broadband noise with speech-like envelope
        # This works much better than a sine wave for XTTS conditioning
        sample_rate = 22050
        duration = 3.0
        num_samples = int(sample_rate * duration)
        
        # Pink-ish noise
        noise = np.random.normal(0, 0.5, num_samples)
        
        # Apply speech-like envelope (rough syllables)
        envelope = np.ones(num_samples)
        for i in range(10):  # 10 rough syllables
            start = np.random.randint(0, num_samples - 2000)
            length = np.random.randint(4410, 8820)
            envelope[start:start+length] *= np.random.uniform(1.5, 3.0)
            
        audio = noise * envelope
        
        # Save to temp file
        voices_dir = Path(self.model_path) / "builtin_fallbacks"
        voices_dir.mkdir(parents=True, exist_ok=True)
        voice_path = voices_dir / f"{voice_id}_fallback.wav"
        
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

    async def _post_process_audio(self, audio_bytes: bytes) -> Tuple[bytes, Optional[float]]:
        """Apply FFmpeg mastering filters to audio bytes using temp files for header integrity."""
        temp_in = None
        temp_out = None
        try:
            # Create temp files
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f_in:
                f_in.write(audio_bytes)
                temp_in = f_in.name
            
            temp_out = temp_in + ".mastered.wav"

            # Filters:
            # 1. highpass: Remove extreme low frequency rumble
            # 2. loudnorm: EBU R128 loudness normalization
            # 3. compand: Soft dynamic range compression for "fuller" sound
            # 4. treble: Subtle boost for clarity
            filters = (
                "highpass=f=80, "
                "loudnorm=I=-16:TP=-1.5:LRA=11, "
                "compand=attacks=0:points=-30/-90|-20/-20|0/0, "
                "treble=g=1.5:f=6000" # Adjusted for better clarity
            )

            cmd = [
                "ffmpeg", "-y",
                "-i", temp_in,
                "-af", filters,
                "-ar", "24000",
                temp_out
            ]

            process = subprocess.run(
                cmd,
                capture_output=True,
                check=True
            )

            # Read back
            with open(temp_out, 'rb') as f_out:
                mastered_bytes = f_out.read()

            # Get new duration using ffprobe
            duration = None
            try:
                probe_cmd = [
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", temp_out
                ]
                probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
                if probe_result.returncode == 0:
                    duration = float(probe_result.stdout.strip())
            except:
                pass

            return mastered_bytes, duration
        except Exception as e:
            logger.error("Post-processing encountered an error", error=str(e))
            return audio_bytes, None
        finally:
            # Cleanup
            for p in [temp_in, temp_out]:
                if p and os.path.exists(p):
                    try: os.unlink(p)
                    except: pass

    def get_available_voices(self) -> List[Dict]:
        """Get list of available voice profiles."""
        # Built-in default voices using XTTS speaker embeddings
        voices = [
            {
                "id": "default",
                "name": "Default Voice",
                "language": "en",
                "type": "builtin",
                "gender": "neutral",
                "description": "Standard XTTS default voice",
            },
            {
                "id": "alex",
                "name": "Alex",
                "language": "en",
                "type": "builtin",
                "gender": "male",
                "description": "Conversational business male voice",
            },
            {
                "id": "sarah",
                "name": "Sarah",
                "language": "en",
                "type": "builtin",
                "gender": "female",
                "description": "Friendly, tutorial-style female voice",
            },
            {
                "id": "james",
                "name": "James",
                "language": "en",
                "type": "builtin",
                "gender": "male",
                "description": "Authoritative, deep male voice",
            },
            {
                "id": "emma",
                "name": "Emma",
                "language": "en",
                "type": "builtin",
                "gender": "female",
                "description": "Energetic marketing female voice",
            },
            {
                "id": "david",
                "name": "David",
                "language": "en",
                "type": "builtin",
                "gender": "male",
                "description": "Calm wellness male voice",
            },
        ]
        
        # List cloned voices from the voices directory
        voices_dir = Path(self.model_path) / "voices"
        if voices_dir.exists():
            for voice_file in voices_dir.glob("*.wav"):
                voices.append({
                    "id": voice_file.stem,
                    "name": voice_file.stem.replace("_", " ").title(),
                    "language": "en",
                    "type": "cloned",
                    "gender": "unknown",
                    "description": f"Cloned voice from {voice_file.name}",
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
