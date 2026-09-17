"""
adapters/windows/hotkey_listener.py
=====================================
Global hotkey listener for Windows using pynput.

Wraps pynput.keyboard.GlobalHotKeys so that the orchestrator remains
completely decoupled from pynput's API.
"""

from __future__ import annotations

import logging
from typing import Callable

from pynput import keyboard

logger = logging.getLogger(__name__)

# Default hotkey combinations (user can override via config.py)
DEFAULT_HOTKEYS = [
    "<ctrl>+<shift>+<space>",
    "<ctrl>+<alt>+<space>",
]


class WindowsHotkeyListener:
    """
    Listens for one or more global hotkey combinations and calls *callback*
    each time any of them is pressed.

    Parameters
    ----------
    callback:
        A zero-argument callable invoked on every hotkey press.
        Will be called from pynput's listener thread.
    hotkeys:
        List of pynput-format hotkey strings.  Defaults to Ctrl+Shift+Space
        and Ctrl+Alt+Space.
    """

    def __init__(
        self,
        callback: Callable[[], None],
        hotkeys: list[str] | None = None,
    ) -> None:
        self._callback = callback
        self._hotkeys = hotkeys or DEFAULT_HOTKEYS
        self._listener: keyboard.GlobalHotKeys | None = None

    def start(self) -> None:
        """Begin listening.  Non-blocking — spawns pynput's internal thread."""
        hotkey_map = {hk: self._callback for hk in self._hotkeys}
        self._listener = keyboard.GlobalHotKeys(hotkey_map)
        self._listener.start()
        logger.info(
            "🎹 Hotkey listener active: %s",
            " | ".join(self._hotkeys),
        )

    def stop(self) -> None:
        """Stop listening and clean up."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            logger.info("Hotkey listener stopped.")

    def join(self) -> None:
        """Block the calling thread until the listener exits."""
        if self._listener is not None:
            self._listener.join()
