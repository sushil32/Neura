
from aiortc import MediaStreamTrack
import io
import wave
import time
import asyncio
from av import AudioFrame
import numpy as np

class TTSStreamTrack(MediaStreamTrack):
    """
    A MediaStreamTrack that yields audio frames from a queue of WAV data.
    """
    kind = "audio"

    def __init__(self):
        super().__init__()
        self.queue = asyncio.Queue()
        self.current_chunk = None
        self.chunk_pos = 0
        self.start_time = None
        self._timestamp = 0
        self.sample_rate = 24000  # Default for Neura TTS (check this!) or 48000
        self.pts = 0

    async def add_audio(self, wav_bytes):
        """Add a WAV byte chunk to the queue."""
        # Simple parsing of WAV header to get data
        # In production, use a more robust wav parser or raw PCM
        try:
             with io.BytesIO(wav_bytes) as bio:
                with wave.open(bio, 'rb') as wf:
                    self.sample_rate = wf.getframerate()
                    # frames = wf.readframes(wf.getnframes())
                    # self.queue.put_nowait(frames)
                    
                    # Read 20ms chunks (standard ptime)
                    # 24000 Hz * 0.02s = 480 samples
                    # 2 bytes/sample * 1 channel = 2 bytes/frame (mono 16-bit)
                    # chunk size = 480 * 2 = 960 bytes
                    
                    samples_per_20ms = int(self.sample_rate * 0.02)
                    while True:
                        data = wf.readframes(samples_per_20ms)
                        if not data:
                            break
                        await self.queue.put(data)
                        
        except Exception as e:
            print(f"Error parsing WAV: {e}")

    async def recv(self):
        """
        Yields an AudioFrame. 
        Aiortc calls this method to get the next frame.
        """
        if self.start_time is None:
            self.start_time = time.time()

        # Get data from queue or silence
        try:
            # Non-blocking check?
            if self.queue.empty():
                # Provide silence if no audio
                # return self._create_silence()
                # Wait for data? or just silence?
                # If we block, we freeze stream?
                # Aiortc expects frames at regular intervals.
                data = await self._get_silence_or_data()
            else:
                data = await self.queue.get()
        except:
             data = await self._get_silence()

        frame = self._create_audio_frame(data)
        
        # Increment timestamp
        samples = len(data) // 2 # 16-bit mono
        self.pts += samples
        frame.pts = self.pts
        frame.time_base = 1 / self.sample_rate
        return frame

    async def _get_silence_or_data(self):
         # Try to get data with a tiny timeout, else return silence
         try:
             return await asyncio.wait_for(self.queue.get(), timeout=0.01)
         except asyncio.TimeoutError:
             return self._get_silence()

    def _get_silence(self):
        # 20ms of silence
        samples = int(self.sample_rate * 0.02)
        return b'\x00' * (samples * 2)

    def _create_audio_frame(self, data):
        # Create AudioFrame from raw bytes (int16 PCM)
        # Note: PyAV AudioFrame construction is complex, usually easier to use ndarray
        
        # numpy approach
        audio_array = np.frombuffer(data, dtype=np.int16)
        # reshape to (channels, samples) -> (1, N)
        audio_array = audio_array.reshape(1, -1)
        
        frame = AudioFrame.from_ndarray(audio_array, format='s16', layout='mono')
        frame.sample_rate = self.sample_rate
        return frame
