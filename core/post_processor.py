"""
core/post_processor.py
=======================
Lightweight in-process text formatter.

This module is intentionally kept separate from the inference engine so that
it can be re-used, tested, or swapped independently.  The actual LLM call
lives in the adapters layer (cloud_engine.py); this module only exposes
helper utilities for deterministic, offline transformations.
"""

from __future__ import annotations

import re


def strip_trailing_whitespace(text: str) -> str:
    """Remove trailing whitespace / newlines from each line."""
    return "\n".join(line.rstrip() for line in text.splitlines())


def ensure_sentence_end(text: str) -> str:
    """
    If the text is a single paragraph with no terminal punctuation,
    append a period.
    """
    stripped = text.strip()
    if not stripped:
        return text
    # Only touch single-line prose — leave lists/emails as-is
    if "\n" in stripped:
        return text
    if stripped[-1] not in ".!?,;:…":
        stripped += "."
    return stripped


def sanitize_for_injection(text: str) -> str:
    """
    Final safety pass before the text is sent to the OS injector.

    - Normalise unicode dashes to ASCII hyphen where appropriate
    - Remove non-printable control characters (except \\n and \\t)
    """
    # Strip C0 control chars but preserve newline (0x0a) and tab (0x09)
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)
    return text


def post_process(text: str, *, add_trailing_space: bool = False) -> str:
    """
    Run all deterministic post-processing steps in order.

    Parameters
    ----------
    text:
        Raw or LLM-formatted text.
    add_trailing_space:
        If True, append a single trailing space so the cursor lands
        after the injected text (useful in most text fields).
    """
    text = strip_trailing_whitespace(text)
    text = sanitize_for_injection(text)
    if add_trailing_space and text:
        text += " "
    return text
