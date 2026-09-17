"""
adapters/ai/cloud_engine.py
============================
Cloud-based inference engine adapter: Groq Whisper + Compound.

Implements: core.interfaces.IInferenceEngine

Pipeline
--------
1. ``transcribe(wav_bytes)``  →  Groq Whisper large-v3-turbo  →  raw text
2. ``format_text(raw_text)``  →  Groq compound →  formatted text

The LLM model and prompt are configurable via config.py.
"""

from __future__ import annotations

import io
import logging
import wave

from groq import Groq

from core.interfaces import IInferenceEngine
from prompts import DICTATION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class GroqCloudEngine(IInferenceEngine):
    """
    Uses the Groq cloud API for:
      - Speech-to-text  (whisper-large-v3-turbo)
    - LLM formatting  (groq/compound)

    Parameters
    ----------
    api_key:
        Groq API key.  Loaded from config.py / .env by the bootstrap.
    stt_model:
        Groq-hosted Whisper model to use for transcription.
    llm_model:
        Groq-hosted LLM model to use for post-processing.
    llm_enabled:
        Set to False to skip LLM formatting (returns raw STT output).
    """

    def __init__(
        self,
        api_key: str,
        stt_model: str = "whisper-large-v3-turbo",
        llm_model: str = "groq/compound",
        llm_enabled: bool = True,
    ) -> None:
        self._client = Groq(api_key=api_key)
        self._stt_model = stt_model
        self._llm_model = llm_model
        self._llm_enabled = llm_enabled
        logger.info(
            "GroqCloudEngine ready | STT: %s | LLM: %s (%s)",
            stt_model,
            llm_model,
            "enabled" if llm_enabled else "disabled",
        )

    # ------------------------------------------------------------------
    # IInferenceEngine interface
    # ------------------------------------------------------------------

    def transcribe(self, audio_bytes: bytes, sample_rate: int) -> str:
        """
        Send WAV bytes to Groq Whisper and return the raw transcription.

        Parameters
        ----------
        audio_bytes:
            Full WAV file bytes (as produced by AudioBuffer.drain_as_pcm16).
        sample_rate:
            Sample rate (informational only — the WAV header already encodes it).

        Returns
        -------
        str
            Raw transcription text, or '' if empty.
        """
        buf = io.BytesIO(audio_bytes)
        buf.name = "dictation.wav"

        result = self._client.audio.transcriptions.create(
            file=("dictation.wav", buf.read()),
            model=self._stt_model,
            temperature=0.0,
        )
        raw = result.text.strip()
        logger.debug("Whisper raw: %r", raw)
        return raw

    def format_text(self, raw_text: str) -> str:
        """
        Send *raw_text* through the LLM formatting pass.

        Falls back to *raw_text* if the LLM is disabled or if the API call
        fails, so the injection step can always proceed.
        """
        if not self._llm_enabled:
            return raw_text

        try:
            response = self._client.chat.completions.create(
                model=self._llm_model,
                messages=[
                    {"role": "system", "content": DICTATION_SYSTEM_PROMPT},
                    {"role": "user", "content": raw_text},
                ],
                temperature=0.0,
                max_tokens=1024,
            )
            formatted = response.choices[0].message.content.strip()
            logger.debug("LLM formatted: %r", formatted)
            return formatted
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM formatting failed (%s) — returning raw text.", exc)
            return raw_text
