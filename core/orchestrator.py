"""
core/orchestrator.py
====================
DictationOrchestrator — the application's central state machine.

States
------
IDLE        → waiting for the user to press the hotkey
RECORDING   → audio is being streamed into the buffer
PROCESSING  → audio is being transcribed and formatted
INJECTING   → text is being typed into the active window
ERROR       → a recoverable error occurred; resets to IDLE after logging

The orchestrator owns ZERO OS-specific code.  It only talks to the four
port interfaces defined in core/interfaces.py.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from typing import Optional

from core.audio_buffer import AudioBuffer
from core.interfaces import (
    IAudioCapture,
    IInferenceEngine,
    ITextInjector,
    IUIIndicator,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State enum
# ---------------------------------------------------------------------------

class State(enum.Enum):
    IDLE = "IDLE"
    RECORDING = "RECORDING"
    PROCESSING = "PROCESSING"
    INJECTING = "INJECTING"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class DictationOrchestrator:
    """
    Coordinates audio capture → transcription → injection via the port
    interfaces.  All state transitions are logged and thread-safe.

    Parameters
    ----------
    audio_capture:
        Adapter implementing IAudioCapture.
    inference_engine:
        Adapter implementing IInferenceEngine.
    text_injector:
        Adapter implementing ITextInjector.
    ui_indicator:
        Adapter implementing IUIIndicator.
    """

    def __init__(
        self,
        audio_capture: IAudioCapture,
        inference_engine: IInferenceEngine,
        text_injector: ITextInjector,
        ui_indicator: IUIIndicator,
    ) -> None:
        self._audio = audio_capture
        self._engine = inference_engine
        self._injector = text_injector
        self._ui = ui_indicator

        self._buffer = AudioBuffer()
        self._state = State.IDLE
        self._state_lock = threading.Lock()

        # Patch the audio adapter to push frames into our buffer
        self._audio_push_target: Optional[AudioBuffer] = None

    # ------------------------------------------------------------------
    # Public API — called from the hotkey listener thread
    # ------------------------------------------------------------------

    def toggle(self) -> None:
        """
        Toggle recording on / off.

        - If IDLE    → start recording
        - If RECORDING → stop recording, kick off processing in a background thread
        - Any other state (PROCESSING / INJECTING) → ignore the press
        """
        with self._state_lock:
            current = self._state

        if current == State.IDLE:
            self._transition_to_recording()
        elif current == State.RECORDING:
            self._transition_to_processing()
        else:
            logger.debug("toggle() ignored — current state is %s", current.value)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _transition_to_recording(self) -> None:
        with self._state_lock:
            self._state = State.RECORDING

        # Inject buffer reference into audio adapter via monkey-patch
        # This keeps IAudioCapture minimal while still being decoupled.
        self._buffer.drain()  # flush any stale data
        self._audio._buffer_ref = self._buffer  # type: ignore[attr-defined]

        self._audio.start()
        self._ui.show_recording()
        logger.info("▶ State → RECORDING")

    def _transition_to_processing(self) -> None:
        with self._state_lock:
            self._state = State.PROCESSING

        self._audio.stop()
        self._ui.show_processing()
        logger.info("⏳ State → PROCESSING")

        # Run the heavy work off the main / hotkey thread
        threading.Thread(
            target=self._process_and_inject,
            daemon=True,
            name="bol-process",
        ).start()

    def _transition_to_injecting(self, text: str) -> None:
        with self._state_lock:
            self._state = State.INJECTING

        self._ui.show_injecting()
        logger.info("⌨️  State → INJECTING (%d chars)", len(text))

        self._injector.inject(text + " ")

        self._transition_to_idle()

    def _transition_to_idle(self) -> None:
        with self._state_lock:
            self._state = State.IDLE

        self._ui.show_idle()
        logger.info("🟢 State → IDLE")

    def _transition_to_error(self, reason: str) -> None:
        with self._state_lock:
            self._state = State.ERROR

        logger.error("💥 State → ERROR: %s", reason)
        self._transition_to_idle()

    # ------------------------------------------------------------------
    # Processing pipeline (runs on background thread)
    # ------------------------------------------------------------------

    def _process_and_inject(self) -> None:
        t_start = time.perf_counter()

        # 1. Drain the buffer
        wav_bytes = self._buffer.drain_as_pcm16(self._audio.sample_rate)
        if not wav_bytes:
            logger.warning("⚠️  No audio captured (buffer empty or silent).")
            self._transition_to_idle()
            return

        # 2. Transcribe
        try:
            t_stt = time.perf_counter()
            raw_text = self._engine.transcribe(wav_bytes, self._audio.sample_rate)
            stt_ms = (time.perf_counter() - t_stt) * 1000
            logger.info("🗣️  STT (%.0fms): %r", stt_ms, raw_text)
        except Exception as exc:  # noqa: BLE001
            self._transition_to_error(f"Transcription failed: {exc}")
            return

        if not raw_text.strip():
            logger.info("⚠️  Whisper returned empty text — skipping.")
            self._transition_to_idle()
            return

        # 3. LLM post-processing / formatting
        try:
            t_llm = time.perf_counter()
            formatted_text = self._engine.format_text(raw_text)
            llm_ms = (time.perf_counter() - t_llm) * 1000
            logger.info("✨ LLM  (%.0fms): %r", llm_ms, formatted_text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("⚠️  LLM formatting failed (%s) — using raw text.", exc)
            formatted_text = raw_text

        total_ms = (time.perf_counter() - t_start) * 1000
        logger.info("⏱️  Total pipeline: %.0fms", total_ms)

        # 4. Inject
        self._transition_to_injecting(formatted_text)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def state(self) -> State:
        with self._state_lock:
            return self._state
