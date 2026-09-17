import time
import sys
import ctypes
from ctypes import wintypes

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


def type_text(text: str, delay: float = 0.02):
    """Sends keystrokes to the active window using Windows SendInput API."""
    for char in text:
        # Encode as UTF-16LE to safely handle ASCII, symbols, and multi-byte emojis
        utf16_bytes = char.encode("utf-16-le")
        for i in range(0, len(utf16_bytes), 2):
            code_unit = int.from_bytes(utf16_bytes[i:i + 2], byteorder="little")

            inp_down = INPUT(
                type=INPUT_KEYBOARD,
                ki=KEYBDINPUT(
                    wVk=0,
                    wScan=code_unit,
                    dwFlags=KEYEVENTF_UNICODE,
                    time=0,
                    dwExtraInfo=0,
                ),
            )
            inp_up = INPUT(
                type=INPUT_KEYBOARD,
                ki=KEYBDINPUT(
                    wVk=0,
                    wScan=code_unit,
                    dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
                    time=0,
                    dwExtraInfo=0,
                ),
            )

            SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))
            SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))
            if delay:
                time.sleep(delay)


def main():
    print("=" * 40)
    print("🎙️  Bol Radha Bol - Dev Mode")
    print("=" * 40)
    print("Status: [IDLE] Ready.")
    print("Press Ctrl+C to quit.\n")

    try:
        while True:
            cmd = input("Press [Enter] to test text injection (or 'q' to quit): ")
            if cmd.strip().lower() == "q":
                print("Exiting...")
                break

            print("⏳ Switch to Notepad or any text field! Typing in 3 seconds...")
            for remaining in range(3, 0, -1):
                print(f"   {remaining}...")
                time.sleep(1)

            print("⌨️  Typing now...")
            type_text("Namaste! Bol Radha Bol is typing directly into your active window! 🚀\n")
            print("✅ Injected!\n")

    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    main()