"""Wallpaper-only subtitle display mode.

This module deliberately controls only the Wallpaper/Lively subtitle surface.
It does not change chat history, chat bubbles, TTS language, or the legacy
floating subtitle window.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from server import presentation_runtime


@dataclass
class _SubtitleState:
    japanese_text: str = ""
    chinese_text: str = ""
    sentence_id: str = ""


_state = _SubtitleState()
_render_fn: Callable[[str], None] | None = None


def get_mode() -> str:
    """Compatibility view for callers that still use zh/ja/bilingual/off."""

    return presentation_runtime.legacy_caption_setting()


def get_config() -> dict[str, str]:
    return presentation_runtime.get_config()


def set_mode(value: object, *, render_current: bool = True) -> str:
    presentation_runtime.set_legacy_caption_setting(
        value,
        render_current=render_current,
    )
    if render_current:
        _render()
    return get_mode()


def needs_translation() -> bool:
    return presentation_runtime.get_caption_mode() in {"translated", "bilingual"}


def set_renderer(render_fn: Callable[[str], None] | None) -> None:
    global _render_fn
    _render_fn = render_fn
    _render()


def begin(sentence_id: str, japanese_text: str = "") -> str:
    """Start or switch the caption slot to a newly playing sentence."""

    sentence_id = str(sentence_id or "")
    if not sentence_id:
        return current_text()
    if _state.sentence_id == sentence_id:
        # A streaming sentence can call the physical chunk hook repeatedly.
        # Do not erase a translation that already arrived for this same ID.
        if japanese_text and not _state.japanese_text:
            _state.japanese_text = str(japanese_text)
        return _render()
    _state.sentence_id = sentence_id
    _state.japanese_text = str(japanese_text or "")
    _state.chinese_text = ""
    return _render()


def update(
    japanese_text: str,
    chinese_text: str = "",
    sentence_id: str | None = None,
) -> str:
    """Update the active sentence, rejecting late updates from older sentences."""

    incoming_id = str(sentence_id or "")
    if incoming_id:
        if _state.sentence_id and incoming_id != _state.sentence_id:
            return current_text()
        _state.sentence_id = incoming_id
    _state.japanese_text = str(japanese_text or "")
    _state.chinese_text = str(chinese_text or "")
    return _render()


def clear(sentence_id: str | None = None) -> str:
    """Clear only the requested sentence, preserving a newer active sentence."""

    incoming_id = str(sentence_id or "")
    if incoming_id and _state.sentence_id and incoming_id != _state.sentence_id:
        return current_text()
    _state.japanese_text = ""
    _state.chinese_text = ""
    _state.sentence_id = ""
    return _render()


def sentence_id() -> str:
    return _state.sentence_id


def current_text() -> str:
    ja = _state.japanese_text
    zh = _state.chinese_text
    mode = presentation_runtime.get_caption_mode()
    if mode == "off":
        return ""
    if mode == "source":
        return ja
    if mode == "bilingual":
        if zh and ja and zh != ja:
            return f"{zh}\n{ja}"
        return zh or ja
    # Translation mode is strict: the Japanese source is never exposed as a
    # temporary fallback while the Chinese translation is still pending.
    return zh


def refresh() -> str:
    return _render()


def _render() -> str:
    text = current_text()
    if _render_fn is not None:
        _render_fn(text)
    return text
