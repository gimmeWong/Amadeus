# Render / Wallpaper 状态同步问题

> 这是一份用于向上游项目作者提交 Issue 的中文草稿。文中区分了已观察到的现象、技术分析、候选修复和仍需上游确认的设计问题。

## 建议标题

`Render 与 Wallpaper 在界面重启后丢失实时人物状态`

## 问题摘要

当 Render 和 Wallpaper 同时启用时，理论上两者应该消费同一套人物表现信号，包括字幕、说话状态、嘴部振幅、表情和 SpriteForge 动作/姿势。

在当前 Windows 环境中，程序第一次启动时通常正常，但关闭并重新打开 Wallpaper，或者在语音播放过程中重启 Render 后，新打开的界面可能无法继续接收实时状态。

具体表现包括：

- Wallpaper 的静态背景仍然存在，但字幕不再更新。
- Wallpaper 中的人物不再接收说话动画、嘴部动作或表情变化。
- 从 Render 切换回 Wallpaper 后，人物可能保持静止，即使后端仍然在发送事件。
- 语音播放期间关闭并重新打开 Render 后，字幕有时能够恢复，但说话状态、表情或姿势没有恢复。
- 之前的一次修改还曾导致切换界面后 Wallpaper 变黑。这个问题属于界面生命周期/渲染表面回归，应与状态重放问题分开处理，修复同步逻辑时不能重新引入。

## 预期行为

Render 和 Wallpaper 是两个显示表面，不应该代表两套独立的对话状态。只要某个表面正在运行，它就应该能够接收到当前的规范化人物表现状态。

重新打开一个表面时，行为应该等价于一个新的客户端加入现有状态流：

1. 加载资源和渲染器配置。
2. 重放当前的模式、表情、说话状态、嘴部值、字幕和当前 SpriteForge 动作。
3. 按顺序接收后续实时事件。
4. 已结束的句子应重放为空字幕，并且 `speaking=false`。
5. 停止一个表面不能使另一个表面的桥接或资源地址失效。

## 复现步骤

### A. 重启 Wallpaper 后丢失状态

1. 启动 Amadeus，并启用 Wallpaper/Lively 表面。
2. 发送一条会产生 TTS 和人物反馈的消息。
3. 确认第一次启动时字幕正常显示，人物能够接收说话、嘴部和表情更新。
4. 只停止 Wallpaper/Lively。
5. 在同一个后端进程中重新启动 Wallpaper/Lively。
6. 再发送一条消息，或者在上一段人物状态仍处于活动状态时重启 Wallpaper。

实际观察到：新打开的 Wallpaper 页面能够显示静态背景，但字幕和/或人物动画不再更新。后端可能仍然在发送 Render 事件，而 Render 表面仍然能够工作。

### B. 语音播放期间重启 Render

1. 播放一段较长的 TTS 语音。
2. 在语音播放过程中关闭 Render。
3. 重新打开 Render。

实际观察到：字幕可能能够恢复，但说话动画、表情或嘴部状态可能缺失或停留在旧状态。结果取决于重启时机。

### C. 在两个表面之间切换

1. 启动 Wallpaper。
2. 启用 Render。
3. 关闭 Render，返回 Wallpaper。

实际观察到：Wallpaper 仍然可见但人物被冻结，或者不再收到新的字幕/人物事件。历史上还出现过切换后 Wallpaper 变黑的问题；修复状态同步时不应重新引入该回归。

## 技术链路

预期的事件链路如下：

```text
TTS / 对话状态
        |
        v
规范化人物表现状态 + Render Bridge
        |
        +--> Render iframe / SpriteForge renderer
        |
        +--> Wallpaper Bridge（SSE + 状态快照）--> Lively/WebView2 iframe
```

其中需要明确区分两个状态：

- `setMouth(value)` 控制当前嘴部开合幅度。`0` 表示当前嘴部闭合，但不会结束说话动画循环。
- `setSpeaking(false)` 结束说话状态，并停止说话帧循环。因此完整的 TTS 结束流程需要同时发送 `mouth=0` 和 `speaking=false`。

目前观察到的问题符合以下情况：新创建的 iframe 在 SSE 连接建立之前错过了已经发送的瞬时事件；或者 Lively/WebView2 重启后，旧的 EventSource 连接仍然存在，但已经不能继续传递事件。因此，除了实时事件流之外，还需要提供当前状态快照。

## 当前 fork 中的候选修复

本地分支 `fix/render-wallpaper-switch` 包含一套候选实现。它由几个相互独立的部分组成。

### 1. 保存并重放运行时状态

`render/headless_bridge.py` 现在保存最新字幕和当前 SpriteForge 动作，并在新的 Render 客户端连接时，与模式、表情、说话状态和嘴部状态一起重放。

`wallpaper/wallpaper_engine_bridge.py` 现在为嘴部、字幕、说话状态、表情、模式和 SpriteForge 动作保存可重放状态。状态接口支持 `?replay=1`，只返回当前运行时状态，不返回一次性的资源初始化事件。

SpriteForge 的动作和释放操作共用一个重放槽位。这样可以避免重连时先应用过期的释放事件、覆盖较新的动作状态。

### 2. Wallpaper 重启后的状态恢复

`server/handlers/wallpaper_handler.py` 在新的 Wallpaper Bridge 和动画器注册完成后调用 Render Bridge 的 `replay_all()`，使新创建的 Wallpaper 主机立即获得规范化状态，而不是等待下一条实时事件。

`wallpaper/lively/index.html` 会轮询 `/wallpaper/bridge-info`。当桥接 token 发生变化时，它会重建内部 iframe，以便建立新的 WebView2/EventSource 连接。

`render/web/wallpaper_engine_bridge.js` 还会轮询 `/wallpaper/state?replay=1`，并按状态槽位只应用更新的重放事件。这个恢复轮询本身不会定时重载 iframe，只会重新应用运行时状态。

### 3. 字幕生命周期和过期句子保护

`server/wallpaper_subtitle_runtime.py` 记录当前 `sentence_id`，根据字幕模式管理日文原文和中文译文，拒绝旧句子的延迟翻译或完成事件，并在当前句子结束时发送空字幕。

`tts/playback.py` 在句子开始时调用独立的 `begin_subtitle_display` 钩子。`server/app.py` 在句子/整轮播放结束时清理字幕，并忽略过期句子的更新。

### 4. 表面生命周期和后端选择

`electron/src/renderer/App.tsx` 在 Render 启用时保持 Wallpaper 主机运行；只要任一表面仍然依赖 graph 表现流，就保持 graph 后端。只有当两个表面都不再需要 graph 后端时，才恢复到 VTS。

这一部分与状态重放机制分开，因为在打开 Render 时停止外部 Wallpaper 主机，可能会使 Lively 的资源地址失效并造成黑屏。

### 5. Pixi 纹理防御性处理

`render/web/wallpaper_scene.js` 将缺少有效 `baseTexture` 的 Pixi 纹理视为可恢复的资源加载竞争：保留原有背景或环境图层，而不是直接中止场景初始化。

同时，字幕图层顺序被明确调整，避免不透明的场景纹理异步更新后覆盖字幕。

## 回归测试

本地新增了以下针对性测试：

- `tests/test_render_wallpaper_switch.py`
- `tests/test_wallpaper_subtitle_runtime.py`
- `tests/test_wallpaper_asset_revision.py`

测试覆盖：

- Render/Wallpaper 切换时的后端选择；
- bridge token 变化时的 iframe 重建；
- 运行时状态快照；
- 不同状态槽位之间的重放顺序；
- 字幕句子 ID 保护；
- 句子完成后的字幕清理；
- 新客户端连接后字幕和 SpriteForge 动作的重放。

当前 Windows 工作区的运行环境没有安装 `pytest`，因此完整 pytest 命令暂时无法执行。字幕运行时测试文件可以直接使用项目虚拟环境运行，针对性检查已通过。上游项目应在 CI 中运行完整测试，并增加真实 SSE 客户端或 WebView2 主机的集成测试。

## 希望上游作者确认的问题

1. Render 和 Wallpaper 是否应该始终共享同一套规范化人物表现状态？还是允许某个表面在另一个表面活动时暂停说话/姿势更新？
2. 新连接的表面是否应该接收完整状态快照？或者协议是否应该定义明确的“订阅 + 重放”握手？
3. 当前支持的 Lively/WebView2 主机是否保证外层 Wallpaper 页面保持不变时，旧 EventSource 连接会被关闭？如果不能，是否应在 bridge 协议中增加 session token 或 connection id？
4. SpriteForge 中约 1 秒的说话结束后闭嘴保持是否是有意设计？候选修复将其视为正常行为，但 `speaking=false` 之后嘴部持续无限循环应视为 bug。
5. 上游更倾向于使用带序列号的统一事件日志，还是使用“最新值重放槽位 + 一次性动作独立通道”的设计？

## 范围和非目标

本方案不修改模型/provider 层、TTS 音色选择、Live2D 资源或 Lively 安装过程，只关注后端、Render、Wallpaper 以及浏览器客户端之间的人物表现状态传输和恢复。

