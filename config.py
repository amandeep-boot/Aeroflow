"""
config.py
=========
Central configuration for Bol Radha Bol.

All user-tunable settings live here.  Environment variables and a .env file
in the project root are supported for secrets (API keys).  Everything else
can be edited directly in this file.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# .env loader (simple, no external dependencies)
# ---------------------------------------------------------------------------

def _load_env(path: str = ".env") -> None:
    """Parse a .env file and inject values into os.environ if not already set."""
    env_path = Path(path)
    if not env_path.exists():
        return
    with env_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_env()


# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------

GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")

# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------

# Set to None for auto-select (prefers "airdopes" headset, then system default)
AUDIO_DEVICE_INDEX: int | None = None

SAMPLE_RATE: int = 16_000  # Hz — Whisper models expect 16 kHz

# ---------------------------------------------------------------------------
# Hotkeys (pynput format)
# ---------------------------------------------------------------------------

HOTKEYS: list[str] = [
    "<ctrl>+<shift>+<space>",  # Primary
    "<ctrl>+<alt>+<space>",    # Fallback
]

# ---------------------------------------------------------------------------
# Inference (Groq Cloud)
# ---------------------------------------------------------------------------

STT_MODEL: str = "whisper-large-v3-turbo"
LLM_MODEL: str = "groq/compound"

# Set to False to skip LLM formatting and use raw STT output
LLM_ENABLED: bool = True

# ---------------------------------------------------------------------------
# Text Injector
# ---------------------------------------------------------------------------

# Delay between each character injection (seconds).
# 0.002 is imperceptible to humans but prevents dropped chars in slow apps.
CHAR_DELAY: float = 0.002

# ---------------------------------------------------------------------------
# UI Overlay
# ---------------------------------------------------------------------------

# Distance from the screen edge in pixels
OVERLAY_MARGIN: int = 18

# Window opacity (0.0 = fully transparent, 1.0 = fully opaque)
OVERLAY_OPACITY: float = 0.88

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL: str = "INFO"   # DEBUG | INFO | WARNING | ERROR
