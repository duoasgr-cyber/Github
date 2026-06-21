# 投屏延迟优化 Spec

## Why
当前投屏端到端延迟明显，动作不跟手。根本原因是 PyAV H.264 解码器未启用低延迟模式、scrcpy server 启动参数把采集帧率上限锁在 30fps，且 UI 轮询间隔为 16ms，导致解码缓冲、编码帧率限制和显示轮询三层延迟叠加。

## What Changes
- 在 `core/screen_capture.py` 的 PyAV `CodecContext` 上启用 `LOW_DELAY` 标志（参考 scrcpy 官方客户端的 `AV_CODEC_FLAG_LOW_DELAY`）
- scrcpy server 启动参数从 `max_fps=30` 提升到 `max_fps=60`，并显式传入 `video_codec_options=latency=1,priority=0`
- `ui/components/embedded_mirror_widget.py` 的帧轮询定时器从 16ms 缩短到 8ms
- 保持现有 screencap 回退、版本自适应头部读取、资源清理逻辑不变
- **BREAKING**: 无破坏性变更；如设备硬件不支持 `latency=1` 的编码器选项，server 可能忽略或报错，需保留回退能力

## Impact
- Affected code: `PY/core/screen_capture.py`、`PY/ui/components/embedded_mirror_widget.py`
- Affected behavior: 投屏端到端延迟预期降低 30~50%，高刷新率设备上流畅度明显提升
- Affected dependencies: 无新增依赖，仍依赖现有 PyAV + scrcpy-server.jar

## ADDED Requirements

### Requirement: PyAV 解码器低延迟模式
系统 SHALL 在创建 H.264 解码器时启用 `LOW_DELAY` 标志，减少 FFmpeg 内部为帧重排序而引入的缓冲延迟。

#### Scenario: scrcpy 模式启动
- **WHEN** `_scrcpy_read_loop()` 创建 `CodecContext`
- **THEN** `codec.flags` 包含 `av.codec.Flags.LOW_DELAY`

#### Scenario: 解码器仍正常出帧
- **WHEN** 启用低延迟标志后收到 H.264 流
- **THEN** 解码器正常输出 RGB 帧，不出现大面积解码错误或花屏

### Requirement: scrcpy server 低延迟编码参数
系统 SHALL 在启动 scrcpy server 时传入更高帧率上限和显式低延迟编码选项，让设备端编码器以实时优先级工作。

#### Scenario: server 启动参数
- **WHEN** `_start_server_process()` 构建启动命令
- **THEN** 命令包含 `max_fps=60` 和 `video_codec_options=latency=1,priority=0`

#### Scenario: 旧版本 server 兼容
- **WHEN** 当前 `scrcpy-server.jar` 版本较旧、不支持 `video_codec_options`
- **THEN** 系统应能正常回退或忽略未知选项，不导致启动崩溃（依赖现有重试/回退机制）

### Requirement: UI 帧轮询加速
系统 SHALL 缩短 UI 层拉取新帧的间隔，降低显示层延迟。

#### Scenario: 投屏启动
- **WHEN** `EmbeddedMirrorWidget.start()` 启动帧更新定时器
- **THEN** 定时器间隔为 8ms（约 120fps 轮询）

## MODIFIED Requirements

### Requirement: scrcpy server 启动参数
原参数 `max_fps=30` 调整为 `max_fps=60`，并新增 `video_codec_options=latency=1,priority=0` 以显式请求设备端低延迟编码。

## REMOVED Requirements
无移除项。
