"""
core/audio_buffer.py
====================
Thread-safe, lock-protected audio chunk buffer.

The sounddevice callback (audio thread) pushes float32 numpy arrays here.
The orchestrator (main thread) drains and converts them when recording stops.
"""

from __future__ import annotations

import threading
from typing import List

import numpy as np


class AudioBuffer:
    """
    A thread-safe first-in, first-out buffer for raw audio chunks.

    Usage
    -----
    Push from the audio callback thread::

        buffer.push(indata.copy())

    Drain from the orchestrator / processing thread::

        pcm_bytes = buffer.drain_as_pcm16()
    """

    def __init__(self) -> None:
        self._chunks: List[np.ndarray] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Write side (audio thread)
    # ------------------------------------------------------------------

    def push(self, chunk: np.ndarray) -> None:
        """Append a float32 mono chunk to the buffer (thread-safe)."""
        with self._lock:
            self._chunks.append(chunk)

    # ------------------------------------------------------------------
    # Read side (orchestrator thread)
    # ------------------------------------------------------------------

    def drain(self) -> List[np.ndarray]:
        """
        Return all buffered chunks and reset the buffer atomically.

        Returns
        -------
        list of np.ndarray
            May be empty if nothing was captured.
        """
        with self._lock:
            chunks, self._chunks = self._chunks, []
        return chunks

    def drain_as_pcm16(self, sample_rate: int = 16_000) -> bytes:
        """
        Convenience wrapper: drain all chunks, concatenate, and return as
        signed 16-bit PCM bytes (little-endian) wrapped in a WAV container.

        Returns
        -------
        bytes
            Full WAV file bytes, or b'' if the buffer was empty / silent.
        """
        import io
        import wave

        chunks = self.drain()
        if not chunks:
            return b""

        full_audio = np.concatenate(chunks, axis=0)

        # Silence gate: peak amplitude below 2 % → discard
        if np.max(np.abs(full_audio)) < 0.02:
            return b""

        audio_int16 = (full_audio * 32_767).astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)          # 16-bit = 2 bytes
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int16.tobytes())
        buf.seek(0)
        return buf.read()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        with self._lock:
            return len(self._chunks)

    def is_empty(self) -> bool:
        with self._lock:
            return len(self._chunks) == 0
