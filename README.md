# Bol Radha Bol 🎙️

A cross-platform, system-wide dictation engine for Windows (Linux planned).

Dictate text into **any** application — IDEs, terminals, browsers, Slack — without touching the clipboard or breaking your flow.

## How it works

1. Press **`Ctrl+Shift+Space`** anywhere in the OS
2. Speak naturally
3. Press the hotkey again
4. Formatted text is typed directly into your active window

## Quick start

```bash
# 1. Clone & create virtual env
python -m venv .venv
.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your Groq API key in .env
echo GROQ_API_KEY=gsk_... > .env

# 4. Run
python main.py
```

## Architecture

Hexagonal (Ports & Adapters) architecture — the core has zero OS or cloud coupling.

```
core/               ← OS-agnostic brain
  interfaces.py     ← Port contracts (IAudioCapture, IInferenceEngine, ...)
  audio_buffer.py   ← Thread-safe audio queue
  orchestrator.py   ← State machine (IDLE → RECORDING → PROCESSING → INJECTING)
  post_processor.py ← Deterministic text cleanup

adapters/
  ai/
    cloud_engine.py     ← Groq Whisper (STT) + Llama (LLM formatting)
  windows/
    audio_capture.py    ← sounddevice / WASAPI
    text_injector.py    ← Win32 SendInput (KEYEVENTF_UNICODE)
    hotkey_listener.py  ← pynput GlobalHotKeys
  ui/
    indicator.py        ← Floating status pill (tkinter)

config.py   ← All user settings (hotkeys, models, device, etc.)
main.py     ← Bootstrap & dependency injection
prompts.py  ← LLM system prompt for intelligent text formatting
```

## Configuration

Edit [`config.py`](config.py) to change:
- **Hotkeys** (`HOTKEYS`)
- **Audio device** (`AUDIO_DEVICE_INDEX`)
- **STT/LLM models** (`STT_MODEL`, `LLM_MODEL`)
- **Disable LLM formatting** (`LLM_ENABLED = False`)

## Roadmap

- [x] Phase 1: Core Framework (interfaces, buffer, orchestrator, post-processor)
- [x] Phase 2: Windows Adapters (audio, text injection, hotkey, Groq cloud engine)
- [x] Phase 3: Floating UI Overlay
- [ ] Phase 4: Linux Support (ydotool / xdotool) + PyInstaller packaging
