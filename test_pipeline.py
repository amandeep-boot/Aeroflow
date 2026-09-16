import io
import os
import sys
import time
import wave
import ctypes
from ctypes import wintypes
import numpy as np

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

# ---- Win32 SendInput Setup ----
INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002


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


def type_text(text: str, delay: float = 0.005):
    """Types text directly into the focused window using SendInput."""
    for char in text:
        utf16_bytes = char.encode("utf-16-le")
        for i in range(0, len(utf16_bytes), 2):
            code_unit = int.from_bytes(utf16_bytes[i:i + 2], byteorder="little")
            inp_down = INPUT(
                type=INPUT_KEYBOARD,
                ki=KEYBDINPUT(wVk=0, wScan=code_unit, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=0),
            )
            inp_up = INPUT(
                type=INPUT_KEYBOARD,
                ki=KEYBDINPUT(wVk=0, wScan=code_unit, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=0),
            )
            SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))
            SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))
            if delay:
                time.sleep(delay)


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
    # Look for headset/airdropes first, else default
    for idx, dev in enumerate(devices):
        if dev["max_input_channels"] > 0 and "airdopes" in dev["name"].lower():
            return idx
    return default_dev


def record_audio_in_memory(device_idx, duration_sec=4, sample_rate=16000):
    """Records audio directly into an in-memory WAV buffer."""
    print(f"🎙️  [RECORDING] for {duration_sec}s... Speak now!")
    audio_data = sd.rec(
        int(duration_sec * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        device=device_idx,
    )
    sd.wait()
    print("⏹️  [RECORDING DONE] Processing...")

    # Convert to 16-bit PCM in RAM
    audio_int16 = (audio_data * 32767).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())
    buffer.seek(0)
    buffer.name = "audio.wav"
    return buffer


def main():
    print("=" * 55)
    print("🚀 Bol Radha Bol - Minimal End-to-End Pipeline Test")
    print("=" * 55)

    client = get_groq_client()
    device_idx = find_preferred_device()
    dev_name = sd.query_devices(device_idx)["name"]
    print(f"Using Audio Input: [{device_idx}] {dev_name}\n")

    while True:
        print("-------------------------------------------------------")
        choice = input("Press [Enter] to dictate (or 'q' to quit): ").strip().lower()
        if choice == "q":
            print("Exiting...")
            break

        print("\n⏳ Focus on your target window (Notepad, browser, etc.)!")
        print("   Recording begins in 2 seconds...")
        time.sleep(2)

        # 1. Record audio in memory
        t0 = time.perf_counter()
        audio_buffer = record_audio_in_memory(device_idx=device_idx, duration_sec=4)

        # 2. Transcribe via Groq API
        t1 = time.perf_counter()
        try:
            transcription = client.audio.transcriptions.create(
                file=("dictation.wav", audio_buffer.read()),
                model="whisper-large-v3-turbo",
                temperature=0.0,
            )
            text = transcription.text.strip()
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            continue

        t2 = time.perf_counter()

        if not text:
            print("⚠️  No speech detected. Nothing to type.")
            continue

        print(f"📝 Heard: \"{text}\"")
        print(f"⚡ STT Latency: {(t2 - t1)*1000:.0f}ms")

        # 3. Inject directly into the active window
        print("⌨️  Injecting text into active window...")
        type_text(text + " ")
        t3 = time.perf_counter()

        print(f"✅ Typed in {(t3 - t2)*1000:.0f}ms! Total Pipeline: {(t3 - t0):.2f}s\n")


if __name__ == "__main__":
    main()
