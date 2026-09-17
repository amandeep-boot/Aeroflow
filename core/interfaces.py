"""
core/interfaces.py
==================
Port definitions for the Bol Radha Bol hexagonal architecture.

Every concrete adapter (Windows audio, Groq cloud, Win32 injector, etc.)
MUST implement exactly one of these ABCs.  The orchestrator and the rest of
the core are only allowed to import from this module – never from adapters.
"""

from __future__ import annotations

import abc
from typing import Generator


# ---------------------------------------------------------------------------
# Port 1: Audio Capture
# ---------------------------------------------------------------------------

class IAudioCapture(abc.ABC):
    """Represents any device that can stream raw PCM audio frames."""

    @abc.abstractmethod
    def start(self) -> None:
        """Begin streaming audio.  Must be non-blocking."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop streaming and release hardware resources."""

    @property
    @abc.abstractmethod
    def sample_rate(self) -> int:
        """PCM sample rate in Hz (typically 16 000)."""

    @property
    @abc.abstractmethod
    def channels(self) -> int:
        """Number of audio channels (1 = mono)."""


# ---------------------------------------------------------------------------
# Port 2: Inference Engine (STT + optional LLM post-processing)
# ---------------------------------------------------------------------------

class IInferenceEngine(abc.ABC):
    """
    Converts a raw PCM buffer into a finished, formatted string.

    Implementations may choose to:
      - call a cloud API (Groq whisper → llama),
      - run a local faster-whisper model,
      - or any combination.
    """

    @abc.abstractmethod
    def transcribe(self, audio_bytes: bytes, sample_rate: int) -> str:
        """
        Parameters
        ----------
        audio_bytes:
            Raw signed 16-bit mono PCM data (little-endian).
        sample_rate:
            PCM sample rate in Hz.

        Returns
        -------
        str
            The *raw* transcription text.  May be empty string if no speech.
        """

    @abc.abstractmethod
    def format_text(self, raw_text: str) -> str:
        """
        Apply post-processing / LLM formatting to *raw_text*.

        Returns the finished string ready to be injected into the active
        window.  Must return raw_text unchanged if formatting fails, rather
        than raising.
        """


# ---------------------------------------------------------------------------
# Port 3: Text Injector
# ---------------------------------------------------------------------------

class ITextInjector(abc.ABC):
    """Sends a string of characters to the currently focused UI element."""

    @abc.abstractmethod
    def inject(self, text: str) -> None:
        """
        Type *text* into the active window.

        Must be focus-safe: it must NOT steal window focus or touch the
        clipboard.  It must wait until any trigger modifier keys (Ctrl, Shift,
        Alt, etc.) have been released before typing.
        """


# ---------------------------------------------------------------------------
# Port 4: UI Indicator
# ---------------------------------------------------------------------------

class IUIIndicator(abc.ABC):
    """Non-focus-stealing floating status overlay."""

    @abc.abstractmethod
    def show_idle(self) -> None:
        """Display the IDLE / ready state."""

    @abc.abstractmethod
    def show_recording(self) -> None:
        """Display the RECORDING state (e.g. red dot)."""

    @abc.abstractmethod
    def show_processing(self) -> None:
        """Display the PROCESSING / transcribing state."""

    @abc.abstractmethod
    def show_injecting(self) -> None:
        """Display the INJECTING / typing state."""

    @abc.abstractmethod
    def hide(self) -> None:
        """Destroy / hide the overlay window."""
