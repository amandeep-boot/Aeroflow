"""
adapters/ui/indicator.py
=========================
Floating status overlay — a non-focus-stealing status pill.

Implements: core.interfaces.IUIIndicator

Uses tkinter (ships with Python, zero extra dependencies) to create a tiny
always-on-top window anchored to the bottom-right of the primary screen.
The window is overrideredirect (no title bar / border) and click-through.

State → Visual mapping
-----------------------
IDLE        → hidden (window withdrawn)
RECORDING   → 🔴 Recording...     (red bg)
PROCESSING  → ⏳ Transcribing...  (amber bg)
INJECTING   → ⌨️  Typing...       (blue bg)
"""

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from typing import Optional

from core.interfaces import IUIIndicator

logger = logging.getLogger(__name__)

# Colour palette
_COLOURS = {
    "recording":  ("#FF3B3B", "#FFFFFF"),   # bg, fg
    "processing": ("#F5A623", "#1A1A1A"),
    "injecting":  ("#2C7BE5", "#FFFFFF"),
    "idle":       ("#2A2A2A", "#FFFFFF"),    # used briefly before hide
}

_LABELS = {
    "recording":  "🔴  Recording…",
    "processing": "⏳  Transcribing…",
    "injecting":  "⌨️   Typing…",
    "idle":       "🟢  Ready",
}


class FloatingIndicator(IUIIndicator):
    """
    Runs a tkinter event loop on a dedicated daemon thread so it never
    blocks or steals focus from the main application thread.

    All state changes are marshalled onto that thread via a queue.
    """

    def __init__(self, margin: int = 18, opacity: float = 0.88) -> None:
        self._margin = margin
        self._opacity = opacity
        self._queue: queue.Queue = queue.Queue()
        self._root: Optional[tk.Tk] = None
        self._label_widget: Optional[tk.Label] = None
        self._thread = threading.Thread(
            target=self._run_tk_loop,
            daemon=True,
            name="bol-overlay",
        )
        self._thread.start()

    # ------------------------------------------------------------------
    # IUIIndicator interface — called from any thread
    # ------------------------------------------------------------------

    def show_recording(self) -> None:
        self._enqueue(("show", "recording"))

    def show_processing(self) -> None:
        self._enqueue(("show", "processing"))

    def show_injecting(self) -> None:
        self._enqueue(("show", "injecting"))

    def show_idle(self) -> None:
        self._enqueue(("hide",))

    def hide(self) -> None:
        self._enqueue(("destroy",))

    # ------------------------------------------------------------------
    # Internal — all methods below run ONLY on the tkinter thread
    # ------------------------------------------------------------------

    def _enqueue(self, command: tuple) -> None:
        self._queue.put(command)

    def _run_tk_loop(self) -> None:
        """Main tkinter event loop (runs on the daemon thread)."""
        self._root = tk.Tk()
        root = self._root

        # Borderless, always-on-top, semi-transparent
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", self._opacity)
        root.configure(bg="#2A2A2A")
        root.withdraw()  # Start hidden

        self._label_widget = tk.Label(
            root,
            text="",
            font=("Segoe UI", 11, "bold"),
            padx=14,
            pady=7,
            borderwidth=0,
        )
        self._label_widget.pack()

        # Poll the command queue every 50 ms
        root.after(50, self._process_queue)
        root.mainloop()

    def _process_queue(self) -> None:
        try:
            while True:
                cmd = self._queue.get_nowait()
                if cmd[0] == "show":
                    self._do_show(cmd[1])
                elif cmd[0] == "hide":
                    self._do_hide()
                elif cmd[0] == "destroy":
                    self._do_destroy()
                    return
        except queue.Empty:
            pass
        if self._root:
            self._root.after(50, self._process_queue)

    def _do_show(self, state: str) -> None:
        root = self._root
        lbl = self._label_widget
        if root is None or lbl is None:
            return

        bg, fg = _COLOURS.get(state, ("#2A2A2A", "#FFFFFF"))
        text = _LABELS.get(state, state)
        lbl.config(text=text, bg=bg, fg=fg)
        root.configure(bg=bg)

        # Position: bottom-right corner, above the taskbar
        root.update_idletasks()
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        win_w = lbl.winfo_reqwidth() + 28
        win_h = lbl.winfo_reqheight() + 14
        x = screen_w - win_w - self._margin
        y = screen_h - win_h - self._margin - 48  # 48 ≈ taskbar height
        root.geometry(f"{win_w}x{win_h}+{x}+{y}")
        root.deiconify()

    def _do_hide(self) -> None:
        if self._root:
            self._root.withdraw()

    def _do_destroy(self) -> None:
        if self._root:
            self._root.destroy()
            self._root = None
