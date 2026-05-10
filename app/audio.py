import time
import wave
import threading
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1


class AudioRecorder:
    def __init__(self, recordings_dir: Path, device: Optional[str] = None):
        self.recordings_dir = recordings_dir
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.device = device or None
        self._recording = False
        self._frames: list[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._start_time: float = 0.0
        self._lock = threading.Lock()

    def _find_device_id(self) -> Optional[int]:
        if not self.device:
            return None
        needle = self.device.lower()
        for i, d in enumerate(sd.query_devices()):
            if needle in d["name"].lower() and d["max_input_channels"] > 0:
                return i
        raise ValueError(
            f"Audio device '{self.device}' not found. "
            "Run '.venv/bin/python -m app.devices' to list available devices."
        )

    def start(self) -> float:
        if self._recording:
            raise RuntimeError("Already recording")

        self._frames = []
        self._start_time = time.time()
        self._recording = True
        device_id = self._find_device_id()

        def callback(indata, frames, time_info, status):
            if self._recording:
                with self._lock:
                    self._frames.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            callback=callback,
            device=device_id,
            blocksize=1024,
        )
        self._stream.start()
        return self._start_time

    def stop(self) -> tuple[Path, float]:
        if not self._recording:
            raise RuntimeError("Not currently recording")

        self._recording = False
        duration = time.time() - self._start_time

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            frames = list(self._frames)

        timestamp = int(self._start_time)
        wav_path = self.recordings_dir / f"meeting_{timestamp}.wav"

        if frames:
            audio_data = np.concatenate(frames, axis=0)
            audio_int16 = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)
            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(audio_int16.tobytes())
        else:
            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)

        return wav_path, duration

    @property
    def is_recording(self) -> bool:
        return self._recording

    def elapsed(self) -> float:
        if not self._recording:
            return 0.0
        return time.time() - self._start_time

    @staticmethod
    def list_devices() -> list[dict]:
        all_devices = []
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                all_devices.append({
                    "id": i,
                    "name": d["name"],
                    "channels": d["max_input_channels"],
                    "is_blackhole": "blackhole" in d["name"].lower(),
                    "active": False,
                })
        return all_devices

    @staticmethod
    def blackhole_installed() -> bool:
        return any(
            "blackhole" in d["name"].lower()
            for d in sd.query_devices()
            if d["max_input_channels"] > 0
        )
