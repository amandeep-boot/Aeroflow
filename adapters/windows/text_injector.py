"""
adapters/windows/text_injector.py
===================================
Windows text injection adapter using Win32 SendInput (KEYEVENTF_UNICODE).

Implements: core.interfaces.ITextInjector

Why SendInput over clipboard paste?
- Works in every application including command prompts, Electron apps,
  browser address bars, and most games.
- Does NOT touch the clipboard — user's copy-paste workflow is never broken.
- Sends events at the hardware level; impossible for apps to block via normal
  focus checks.
"""

from __future__ import annotations

import ctypes
import logging
import time
from ctypes import wintypes

from core.interfaces import ITextInjector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Win32 structures
# ---------------------------------------------------------------------------

INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002

# Virtual key codes for the modifier-release wait
_VK_SHIFT = 0x10
_VK_CONTROL = 0x11
_VK_MENU = 0x12   # Alt
_VK_SPACE = 0x20


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTunion(ctypes.Union):
    _fields_ = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT),
    ]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("_input",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("_input", _INPUTunion),
    ]


_SendInput = ctypes.windll.user32.SendInput
_SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
_SendInput.restype = wintypes.UINT

_GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState


# ---------------------------------------------------------------------------
# Adapter class
# ---------------------------------------------------------------------------

class WindowsTextInjector(ITextInjector):
    """
    Types a string into the currently focused window using the Win32
    SendInput API (KEYEVENTF_UNICODE).

    Parameters
    ----------
    char_delay:
        Per-character sleep in seconds.  0.002 (2 ms) is imperceptible to
        humans but prevents dropped characters in some apps with slow message
        queues (e.g. older Electron builds).
    modifier_timeout:
        Max seconds to wait for the trigger hotkey modifiers to be released
        before typing.  Prevents the first character from being eaten.
    """

    def __init__(
        self,
        char_delay: float = 0.002,
        modifier_timeout: float = 1.0,
    ) -> None:
        self._char_delay = char_delay
        self._modifier_timeout = modifier_timeout

    # ------------------------------------------------------------------
    # ITextInjector interface
    # ------------------------------------------------------------------

    def inject(self, text: str) -> None:
        """Type *text* into the active window, character by character."""
        self._wait_for_modifiers_released()
        self._type_text(text)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _wait_for_modifiers_released(self) -> None:
        """Block until Ctrl / Shift / Alt / Space are all released."""
        modifier_keys = [_VK_CONTROL, _VK_SHIFT, _VK_MENU, _VK_SPACE]
        deadline = time.monotonic() + self._modifier_timeout
        while time.monotonic() < deadline:
            if not any(_GetAsyncKeyState(k) & 0x8000 for k in modifier_keys):
                break
            time.sleep(0.01)
        # Tiny settling window so the OS finishes processing the key-up events
        time.sleep(0.05)

    def _type_text(self, text: str) -> None:
        for char in text:
            # Encode as UTF-16LE to safely handle ASCII, BMP chars, and emoji
            utf16_bytes = char.encode("utf-16-le")
            for i in range(0, len(utf16_bytes), 2):
                code_unit = int.from_bytes(utf16_bytes[i : i + 2], byteorder="little")

                # Send DOWN and UP as a single atomic SendInput call (array of 2)
                # to prevent key-repeat from firing if the user holds a key.
                inp_array = (_INPUT * 2)(
                    _INPUT(
                        type=INPUT_KEYBOARD,
                        ki=_KEYBDINPUT(
                            wVk=0,
                            wScan=code_unit,
                            dwFlags=KEYEVENTF_UNICODE,
                            time=0,
                            dwExtraInfo=0,
                        ),
                    ),
                    _INPUT(
                        type=INPUT_KEYBOARD,
                        ki=_KEYBDINPUT(
                            wVk=0,
                            wScan=code_unit,
                            dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
                            time=0,
                            dwExtraInfo=0,
                        ),
                    ),
                )
                _SendInput(2, inp_array, ctypes.sizeof(_INPUT))

            if self._char_delay:
                time.sleep(self._char_delay)
