from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock
import asyncio

from vts.expression_controller import ExpressionController
from render.headless_bridge import HeadlessRenderBridge
from server.protocol import Method
from wallpaper.wallpaper_engine_bridge import WallpaperEngineBridgeHost


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "electron" / "src" / "renderer" / "App.tsx"
LIVELY_WRAPPER = ROOT / "wallpaper" / "lively" / "index.html"
WALLPAPER_SCENE = ROOT / "render" / "web" / "wallpaper_scene.js"


def test_wallpaper_switch_keeps_the_graph_expression_backend() -> None:
    source = APP.read_text(encoding="utf-8")
    wallpaper_branch = source.split("const handleToggleWallpaper", 1)[1].split(
        "// listen for render mode", 1
    )[0]
    start_branch = wallpaper_branch.split("if (next) {", 1)[1].split(
        "} else {", 1
    )[0]

    assert "send('expression.set_backend', { backend: 'graph' })" in start_branch
    assert "send('expression.set_backend', { backend: 'vts' })" not in start_branch


def test_stopping_wallpaper_restores_the_normal_vts_backend() -> None:
    source = APP.read_text(encoding="utf-8")
    wallpaper_branch = source.split("const handleToggleWallpaper", 1)[1].split(
        "// listen for render mode", 1
    )[0]

    stop_branch = wallpaper_branch.split("} else {", 1)[1]
    assert "send('wallpaper.stop', {})" in stop_branch
    assert "send('expression.set_backend', { backend: renderActive ? 'graph' : 'vts' })" in stop_branch


def test_render_switch_keeps_wallpaper_host_alive_for_lively() -> None:
    source = APP.read_text(encoding="utf-8")
    render_branch = source.split("const handleToggleRender", 1)[1].split(
        "// Toggle the Electron Slice wallpaper projection", 1
    )[0]
    start_branch = render_branch.split("if (next) {", 1)[1].split("} else {", 1)[0]

    assert "send('wallpaper.stop', {})" not in start_branch
    assert "setWallpaperActive(false)" not in start_branch


def test_render_toggle_tracks_wallpaper_state_for_backend_restore() -> None:
    source = APP.read_text(encoding="utf-8")
    render_callback = source.split("const handleToggleRender", 1)[1].split(
        "// Toggle the Electron Slice wallpaper projection", 1
    )[0]

    # The callback reads wallpaperActive when Render is disabled, so it must
    # be recreated with the current surface state instead of retaining an old
    # closure value.
    assert "}, [send, renderActive, wallpaperActive])" in render_callback


def test_graph_backend_forwards_speaking_to_the_spriteforge_animator() -> None:
    controller = ExpressionController()
    animator = Mock()
    controller.set_animator(animator, backend="graph")

    controller.on_sentence_start("sentence-1")

    animator.on_speaking.assert_called_once_with(True)


def test_lively_wrapper_reloads_its_iframe_after_the_bridge_is_recreated() -> None:
    source = LIVELY_WRAPPER.read_text(encoding="utf-8")

    # Lively keeps this outer page alive while Wallpaper mode is toggled.  A
    # restarted host has a fresh bridge token, so the old inner iframe must be
    # recreated instead of remaining attached to its disconnected event stream.
    assert "function applyBridgeInfo(info)" in source
    assert "bridgeToken" in source
    assert "frame.src = frameUrl" in source
    assert "window.setInterval(pollBridgeInfo, 1000)" in source


def test_lively_wrapper_does_not_rebuild_the_inner_frame_on_a_timer() -> None:
    source = LIVELY_WRAPPER.read_text(encoding="utf-8")
    bridge = ROOT / "render" / "web" / "wallpaper_engine_bridge.js"
    bridge_source = bridge.read_text(encoding="utf-8")

    # Recovery is driven by the bridge state poll. The wrapper must not
    # destroy and recreate the WebGL iframe merely because a child heartbeat
    # was delayed, which can replay stale terminal subtitles.
    assert 'type: "amadeus-wallpaper-heartbeat"' not in bridge_source
    assert 'event.data.type === "amadeus-wallpaper-heartbeat"' not in source
    assert "lastFrameHeartbeat" not in source
    assert 'loadFrame("heartbeat_timeout")' not in source


def test_wallpaper_scene_does_not_abort_when_a_texture_has_no_base_texture() -> None:
    source = WALLPAPER_SCENE.read_text(encoding="utf-8")

    # Pixi can briefly return a texture shell while the asset cache is being
    # recreated. A transient race must not abort initDesktopScene.
    assert "PIXI.Texture.from returned no baseTexture" in source
    assert "if (!texture || !texture.baseTexture)" in source
    assert "if (!tex || !tex.baseTexture)" in source


def test_wallpaper_subtitle_stays_above_the_foreground_scenario() -> None:
    source = WALLPAPER_SCENE.read_text(encoding="utf-8")
    layer_order = source.split("_syncLayerOrder() {", 1)[1].split("noteActivity()", 1)[0]

    # Scenario frames are opaque. Its container must be restored first and
    # the subtitle must be added afterward, otherwise a late texture callback
    # can obscure subtitles while Lively's ticker is suspended.
    assert "stage.addChildAt(this.container" in layer_order
    assert "stage.addChild(subtitleLayer);" in layer_order
    assert layer_order.index("stage.addChildAt(this.container") < layer_order.index(
        "stage.addChild(subtitleLayer);"
    )


def test_headless_bridge_replays_live_subtitle_and_spriteforge_intent() -> None:
    bridge = HeadlessRenderBridge(project_root=ROOT)
    emitted: list[tuple[str, dict]] = []

    async def capture(method: str, params: dict) -> None:
        emitted.append((method, params))

    bridge._emit_async = capture  # type: ignore[method-assign]
    bridge.set_subtitle("正在处理")
    bridge.trigger_spriteforge_intent("thinking")
    asyncio.run(bridge.replay_all())

    assert (Method.RENDER_SUBTITLE, {"text": "正在处理"}) in emitted
    assert any(
        method == Method.RENDER_SPRITEFORGE_INTENT and params.get("label")
        for method, params in emitted
    )


def test_wallpaper_state_snapshot_replays_mouth_and_latest_pose_order() -> None:
    host = WallpaperEngineBridgeHost()
    host.set_mouth_value(0.7)
    host.trigger_spriteforge_intent("thinking")
    host.release_spriteforge()
    host.trigger_spriteforge_intent("smile")

    calls = host._state.snapshot()["calls"]
    methods = [call["method"] for call in calls]
    assert "setMouth" in methods
    pose_calls = [call for call in calls if call["method"] in {
        "triggerSpriteForgeIntent", "releaseSpriteForge"
    }]
    assert [call["method"] for call in pose_calls] == ["triggerSpriteForgeIntent"]
    assert pose_calls[0]["args"][0] == "smile"
