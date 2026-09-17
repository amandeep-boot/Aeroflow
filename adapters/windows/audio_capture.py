"""
adapters/windows/audio_capture.py
===================================
Windows audio capture adapter using sounddevice (WASAPI / WDM-KS).

Implements: core.interfaces.IAudioCapture
"""

from __future__ import annotations

import logging
from typing import Optional

import sounddevice as sd

from core.interfaces import IAudioCapture

logger = logging.getLogger(__name__)


def _find_preferred_device() -> int:
    """
    Auto-select the best available microphone.

    Priority:
      1. Any Bluetooth headset with "airdopes" in the name (personal preference)
      2. System default input device
    """
    default_dev: int = sd.default.device[0]  # type: ignore[index]
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0 and "airdopes" in dev["name"].lower():
            logger.info("Using preferred device [%d] %s", idx, dev["name"])
            return idx
    return default_dev


class WindowsAudioCapture(IAudioCapture):
    """
    Streams 16 kHz mono float32 audio from the microphone into a
    ``core.audio_buffer.AudioBuffer`` attached at runtime by the orchestrator.

    The orchestrator sets ``self._buffer_ref`` before calling ``start()``.
    """

    def __init__(self, device_index: Optional[int] = None) -> None:
        self._device_index = device_index if device_index is not None else _find_preferred_device()
        self._sample_rate = 16_000
        self._channels = 1
        self._stream: Optional[sd.InputStream] = None
        self._buffer_ref = None  # injected by DictationOrchestrator

        dev_name = sd.query_devices(self._device_index)["name"]
        logger.info("Audio device: [%d] %s", self._device_index, dev_name)

    # ------------------------------------------------------------------
    # IAudioCapture interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._stream is not None:
            logger.warning("start() called while stream is active — stopping first.")
            self.stop()

        self._stream = sd.InputStream(
            device=self._device_index,
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype="float32",
            callback=self._audio_callback,
        )
        self._stream.start()
        logger.debug("InputStream started.")

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
            logger.debug("InputStream stopped.")

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def channels(self) -> int:
        return self._channels

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _audio_callback(self, indata, frames, time_info, status) -> None:  # type: ignore[override]
        if status:
            logger.warning("sounddevice status: %s", status)
        if self._buffer_ref is not None:
            self._buffer_ref.push(indata.copy())
