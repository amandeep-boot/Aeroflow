import io
import os
import sys
import time
import wave
import threading
import ctypes
from ctypes import wintypes
import numpy as np
from prompts import DICTATION_SYSTEM_PROMPT

try:
    import sounddevice as sd
except ImportError:
    print("❌ 'sounddevice' not installed.")
    sys.exit(1)

try:
    from groq import Groq
except ImportError:
    print("❌ 'groq' not installed.")
    sys.exit(1)

try:
    from pynput import keyboard
except ImportError:
    print("❌ 'pynput' not installed.")
    sys.exit(1)

# ---- Win32 SendInput Setup ----
INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_SPACE = 0x20


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTunion(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_input", _INPUTunion),
    ]


SendInput = ctypes.windll.user32.SendInput
SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
SendInput.restype = wintypes.UINT
GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState


def wait_for_modifiers_released():
    """Wait until user has released Ctrl, Shift, Alt, and Space keys."""
    keys_to_check = [VK_CONTROL, VK_SHIFT, VK_MENU, VK_SPACE]
    deadline = time.time() + 1.0  # Max 1 second timeout
    while time.time() < deadline:
        if not any(GetAsyncKeyState(k) & 0x8000 for k in keys_to_check):
            break
        time.sleep(0.01)
    time.sleep(0.05)  # Tiny settling window


def type_text(text: str, char_delay: float = 0.002):
    """Types text atomically using Win32 SendInput array."""
    wait_for_modifiers_released()

    for char in text:
        utf16_bytes = char.encode("utf-16-le")
        for i in range(0, len(utf16_bytes), 2):
            code_unit = int.from_bytes(utf16_bytes[i:i + 2], byteorder="little")
            
            # Pack both DOWN and UP into a single atomic call so key repeat never fires
            inp_array = (INPUT * 2)(
                INPUT(
                    type=INPUT_KEYBOARD,
                    ki=KEYBDINPUT(wVk=0, wScan=code_unit, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=0),
                ),
                INPUT(
                    type=INPUT_KEYBOARD,
                    ki=KEYBDINPUT(wVk=0, wScan=code_unit, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=0),
                ),
            )
            SendInput(2, inp_array, ctypes.sizeof(INPUT))
            if char_delay:
                time.sleep(char_delay)


def get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key and os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("GROQ_API_KEY="):
                    api_key = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not api_key:
        api_key = input("Enter Groq API Key: ").strip()
    return Groq(api_key=api_key)


def find_preferred_device():
    devices = sd.query_devices()
    default_dev = sd.default.device[0]
    for idx, dev in enumerate(devices):
        if dev["max_input_channels"] > 0 and "airdopes" in dev["name"].lower():
            return idx
    return default_dev


class DictationEngine:
    def __init__(self):
        self.client = get_groq_client()
        self.device_idx = find_preferred_device()
        self.sample_rate = 16000
        self.is_recording = False
        self.recorded_chunks = []
        self.stream = None
        self.lock = threading.Lock()
        dev_name = sd.query_devices(self.device_idx)["name"]
        print(f"🎤 Audio Device: [{self.device_idx}] {dev_name}")

    def _audio_callback(self, indata, frames, time_info, status):
        if self.is_recording:
            self.recorded_chunks.append(indata.copy())

    def toggle(self):
        with self.lock:
            if not self.is_recording:
                self.start_recording()
            else:
                self.stop_and_process()

    def start_recording(self):
        self.recorded_chunks = []
        self.is_recording = True
        self.stream = sd.InputStream(
            device=self.device_idx,
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._audio_callback,
        )
        self.stream.start()
        print("\n🔴 [RECORDING...] Speak now! (Press hotkey again to finish)")

    def stop_and_process(self):
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        print("⏳ [PROCESSING...] Transcribing audio via Groq...")
        threading.Thread(target=self._process_worker, args=(list(self.recorded_chunks),)).start()

    def _process_worker(self, chunks):
        if not chunks:
            print("⚠️  No audio captured.")
            return

        full_audio = np.concatenate(chunks, axis=0)
        max_peak = np.max(np.abs(full_audio))
        if max_peak < 0.02:
            print("⚠️  Audio was silent / no speech detected.")
            return

        audio_int16 = (full_audio * 32767).astype(np.int16)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_int16.tobytes())
        buffer.seek(0)

        t0 = time.perf_counter()
        try:
            transcription = self.client.audio.transcriptions.create(
                file=("dictation.wav", buffer.read()),
                model="whisper-large-v3-turbo",
                temperature=0.0,
            )
            raw_text = transcription.text.strip()
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            return

        stt_ms = (time.perf_counter() - t0) * 1000

        if not raw_text:
            print("⚠️  Whisper returned empty text.")
            return

        print(f"🗣️  Raw ({stt_ms:.0f}ms): \"{raw_text}\"")
        print("✨ Formatting via LLM...")

        # Step 2: LLM post-processing for intelligent formatting
        t1 = time.perf_counter()
        try:
            chat = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": DICTATION_SYSTEM_PROMPT},
                    {"role": "user", "content": raw_text},
                ],
                temperature=0.0,
                max_tokens=1024,
            )
            text = chat.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️  LLM formatting failed, using raw text. Error: {e}")
            text = raw_text

        llm_ms = (time.perf_counter() - t1) * 1000
        total_ms = (time.perf_counter() - t0) * 1000
        print(f"📝 Formatted ({llm_ms:.0f}ms): \"{text}\"")
        print(f"⏱️  Total: {total_ms:.0f}ms (STT: {stt_ms:.0f}ms + LLM: {llm_ms:.0f}ms)")
        print("⌨️  Typing into active window...")
        type_text(text + " ")
        print("✅ Injected cleanly! Ready for next dictation.")


def main():
    print("=" * 60)
    print("🎙️  Bol Radha Bol - Global Hotkey Test v2")
    print("=" * 60)
    print("Active Hotkey: <ctrl>+<shift>+<space>")
    print("Fallback Hotkey: <ctrl>+<alt>+<space>")
    print("Press once to START recording.")
    print("Press again to STOP recording and auto-type.")
    print("Press Ctrl+C in this terminal to exit.")
    print("=" * 60)

    engine = DictationEngine()

    # Support both Ctrl+Shift+Space and Ctrl+Alt+Space
    hotkeys = keyboard.GlobalHotKeys({
        "<ctrl>+<shift>+<space>": engine.toggle,
        "<ctrl>+<alt>+<space>": engine.toggle,
    })

    hotkeys.start()
    print("\n🟢 Listening for global hotkey! Switch to Notepad and try either:")
    print("   👉 Ctrl + Shift + Space  (Recommended)")
    print("   👉 Ctrl + Alt + Space")

    try:
        hotkeys.join()
    except KeyboardInterrupt:
        print("\nExiting...")
        hotkeys.stop()


if __name__ == "__main__":
    main()
