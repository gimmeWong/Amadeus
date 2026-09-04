"""Regression coverage for the wallpaper-only subtitle surface."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import presentation_runtime, wallpaper_subtitle_runtime
from tts.playback import PlaybackManager
from wallpaper.wallpaper_engine_bridge import _BridgeState


def test_translated_caption_waits_for_translation() -> None:
    """Translated mode must not temporarily expose the Japanese source."""

    original_config = presentation_runtime.get_config()
    rendered: list[str] = []
    try:
        presentation_runtime.set_config(
            {"wallpaper_caption_mode": "translated"},
            render_current=False,
        )
        wallpaper_subtitle_runtime.set_renderer(rendered.append)

        wallpaper_subtitle_runtime.update(
            "Japanese source",
            "",
            sentence_id="sentence-1",
        )

        assert wallpaper_subtitle_runtime.current_text() == ""
        assert rendered[-1] == ""

        wallpaper_subtitle_runtime.update(
            "Japanese source",
            "Chinese translation",
            sentence_id="sentence-1",
        )

        wallpaper_subtitle_runtime.begin("sentence-1", "Japanese source")

        assert wallpaper_subtitle_runtime.current_text() == "Chinese translation"
        assert rendered[-1] == "Chinese translation"
    finally:
        wallpaper_subtitle_runtime.clear()
        wallpaper_subtitle_runtime.set_renderer(None)
        presentation_runtime.set_config(original_config, render_current=False)


def test_stale_completion_and_translation_cannot_replace_the_current_sentence() -> None:
    original_config = presentation_runtime.get_config()
    rendered: list[str] = []
    try:
        presentation_runtime.set_config(
            {"wallpaper_caption_mode": "translated"},
            render_current=False,
        )
        wallpaper_subtitle_runtime.set_renderer(rendered.append)

        wallpaper_subtitle_runtime.begin("old", "old")
        wallpaper_subtitle_runtime.update("old", "old translated", sentence_id="old")
        wallpaper_subtitle_runtime.begin("new", "new")

        assert wallpaper_subtitle_runtime.clear("old") == ""
        assert wallpaper_subtitle_runtime.sentence_id() == "new"
        rendered_before_stale_update = list(rendered)
        assert wallpaper_subtitle_runtime.update(
            "old",
            "late old translation",
            sentence_id="old",
        ) == ""
        assert wallpaper_subtitle_runtime.sentence_id() == "new"
        assert rendered == rendered_before_stale_update

        wallpaper_subtitle_runtime.update("new", "new translated", sentence_id="new")
        assert wallpaper_subtitle_runtime.current_text() == "new translated"
        assert rendered[-1] == "new translated"
    finally:
        wallpaper_subtitle_runtime.clear()
        wallpaper_subtitle_runtime.set_renderer(None)
        presentation_runtime.set_config(original_config, render_current=False)


def test_finished_caption_replays_as_empty_after_wallpaper_reconnect() -> None:
    original_config = presentation_runtime.get_config()
    state = _BridgeState()

    def render(text: str) -> None:
        state.publish(
            {"method": "setSubtitle", "args": [text], "t": 1.0},
            replay="subtitle",
        )

    try:
        presentation_runtime.set_config(
            {"wallpaper_caption_mode": "translated"},
            render_current=False,
        )
        wallpaper_subtitle_runtime.set_renderer(render)
        wallpaper_subtitle_runtime.update(
            "Japanese source",
            "Chinese translation",
            sentence_id="sentence-1",
        )
        wallpaper_subtitle_runtime.clear("sentence-1")

        replay = state.snapshot(replay_only=True)["calls"]
        assert replay[-1]["method"] == "setSubtitle"
        assert replay[-1]["args"] == [""]
    finally:
        wallpaper_subtitle_runtime.clear()
        wallpaper_subtitle_runtime.set_renderer(None)
        presentation_runtime.set_config(original_config, render_current=False)


def test_playback_manager_drops_completed_sentence_from_current_state() -> None:
    manager = PlaybackManager(object())
    manager.current_playing_id = "sentence-1"
    manager._current_playing_segment_ids = {"sentence-1"}
    manager._turn_sentence_texts["sentence-1"] = "source"

    manager._mark_sentence_complete("sentence-1")

    assert manager.current_playing_id is None
    assert manager.is_current_playback_sentence("sentence-1") is False


def test_playback_manager_clears_primary_after_the_last_merged_segment() -> None:
    manager = PlaybackManager(object())
    manager.current_playing_id = "sentence-1"
    manager._current_playing_segment_ids = {
        "sentence-1",
        "sentence-2",
    }
    manager._turn_sentence_texts.update(
        {"sentence-1": "first", "sentence-2": "second"}
    )

    manager._mark_sentence_complete("sentence-1")
    assert manager.current_playing_id == "sentence-1"
    manager._mark_sentence_complete("sentence-2")

    assert manager.current_playing_id is None
    assert manager.is_current_playback_sentence("sentence-1") is False
    assert manager.is_current_playback_sentence("sentence-2") is False


def _main() -> None:
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok: {name}")


if __name__ == "__main__":
    _main()
