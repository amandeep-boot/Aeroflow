"""
main.py
=======
Bol Radha Bol — bootstrap & dependency injection entry point.

This module:
  1. Validates configuration (API key present, correct OS, etc.)
  2. Instantiates the platform-specific adapters
  3. Wires them into the DictationOrchestrator (dependency injection)
  4. Starts the hotkey listener and blocks until the user exits
"""

from __future__ import annotations

import logging
import platform
import sys

import config  # noqa: F401 — loads .env as a side effect

# Configure logging before any other imports
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Platform guard
# ---------------------------------------------------------------------------

def _check_platform() -> None:
    system = platform.system()
    if system != "Windows":
        logger.error(
            "Bol Radha Bol currently only supports Windows. "
            "Detected OS: %s. Linux support is planned for Phase 4.",
            system,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_config() -> None:
    if not config.GROQ_API_KEY:
        logger.error(
            "GROQ_API_KEY is not set.\n"
            "  → Add it to your .env file:  GROQ_API_KEY=gsk_...\n"
            "  → Or set the environment variable before running."
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("🎙️   Bol Radha Bol — System-Wide Dictation Engine")
    print("=" * 60)

    _check_platform()
    _validate_config()

    # --- Import adapters (platform-specific) ----------------------------
    from adapters.windows.audio_capture import WindowsAudioCapture
    from adapters.windows.text_injector import WindowsTextInjector
    from adapters.windows.hotkey_listener import WindowsHotkeyListener
    from adapters.ai.cloud_engine import GroqCloudEngine
    from adapters.ui.indicator import FloatingIndicator
    from core.orchestrator import DictationOrchestrator

    # --- Instantiate adapters -------------------------------------------
    audio_capture = WindowsAudioCapture(
        device_index=config.AUDIO_DEVICE_INDEX,
    )
    inference_engine = GroqCloudEngine(
        api_key=config.GROQ_API_KEY,
        stt_model=config.STT_MODEL,
        llm_model=config.LLM_MODEL,
        llm_enabled=config.LLM_ENABLED,
    )
    text_injector = WindowsTextInjector(
        char_delay=config.CHAR_DELAY,
    )
    ui_indicator = FloatingIndicator(
        margin=config.OVERLAY_MARGIN,
        opacity=config.OVERLAY_OPACITY,
    )

    # --- Wire into orchestrator (dependency injection) ------------------
    orchestrator = DictationOrchestrator(
        audio_capture=audio_capture,
        inference_engine=inference_engine,
        text_injector=text_injector,
        ui_indicator=ui_indicator,
    )

    # --- Hotkey listener ------------------------------------------------
    hotkey_listener = WindowsHotkeyListener(
        callback=orchestrator.toggle,
        hotkeys=config.HOTKEYS,
    )

    # --- Start ----------------------------------------------------------
    print(f"\n🟢 Listening for global hotkey: {' | '.join(config.HOTKEYS)}")
    print("   Press once → START recording")
    print("   Press again → STOP & auto-type")
    print("   Ctrl+C in this terminal → EXIT\n")

    ui_indicator.show_idle()
    hotkey_listener.start()

    try:
        hotkey_listener.join()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    finally:
        hotkey_listener.stop()
        audio_capture.stop()
        ui_indicator.hide()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()