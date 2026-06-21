# 投屏帧率优化 Spec

## Why
当前投屏使用 ffmpeg CPU 软解码 H.264 → rawvideo BGR24 → numpy → QImage 软渲染管线，1080p 下 CPU 占用高、解码跟不上编码速度导致丢帧，实际帧率远低于 scrcpy server 设定的 60fps。需要通过硬件解码、低延迟参数、跳帧策略和渲染优化来大幅提升投屏流畅度。

## What Changes
- ffmpeg 解码从 CPU 软解改为 GPU 硬件解码（DXVA2/CUDA 自动检测，回退软解）
- ffmpeg 命令增加低延迟参数（`-fflags nobuffer`、`-flags low_delay`、`-probesize 32`）
- scrcpy server 启动参数增加 `video_bit_rate` 和 `send_device_meta`
- 帧读取循环增加跳过过期帧逻辑（当帧堆积时丢弃旧帧只保留最新帧）
- `MirrorGraphicsView.update_frame()` 减少 QImage 内存拷贝（避免 `rgbSwapped()`，直接使用 BGR 格式）
- 新增 ffmpeg 硬件解码能力自动检测方法

## Impact
- Affected code: `PY/core/screen_capture.py`（主要改动）、`PY/ui/mirror_window.py`（渲染优化）
- Affected dependencies: 无新增依赖，依赖系统已安装的 ffmpeg GPU 加速支持
- Affected behavior: 投屏帧率预期从当前 ~15-25fps 提升至 40-60fps，延迟降低 30-50%

## ADDED Requirements

### Requirement: ffmpeg 硬件解码自动检测与启用
系统 SHALL 在启动 ffmpeg 解码前自动检测可用的硬件加速方案（优先级：CUDA > DXVA2 > QSV > 软解），并使用检测到的最优方案启动 ffmpeg 解码进程。

#### Scenario: 检测到 NVIDIA GPU
- **WHEN** 系统检测到 ffmpeg 支持 CUDA 硬件加速且 GPU 可用
- **THEN** 使用 `-hwaccel cuda -c:v h264_cuvid` 启动 ffmpeg 解码

#### Scenario: 检测到 DXVA2 支持（Windows 通用）
- **WHEN** 系统未检测到 CUDA 但 ffmpeg 支持 DXVA2
- **THEN** 使用 `-hwaccel dxva2` 启动 ffmpeg 解码

#### Scenario: 无硬件加速可用
- **WHEN** 系统未检测到任何 GPU 加速方案
- **THEN** 回退到当前软解码模式，并记录日志

### Requirement: ffmpeg 低延迟参数
系统 SHALL 在 ffmpeg 命令中启用低延迟参数，减少解码缓冲带来的帧延迟。

#### Scenario: 启动 ffmpeg 解码
- **WHEN** 系统启动 ffmpeg 解码进程
- **THEN** 命令包含 `-fflags nobuffer -flags low_delay -probesize 32 -analyzeduration 0` 参数

### Requirement: 跳过过期帧
系统 SHALL 在帧读取循环中实现跳帧逻辑，当帧堆积时只保留最新帧，避免延迟累积。

#### Scenario: 帧堆积时跳过旧帧
- **WHEN** ffmpeg stdout 中有多帧待读取且当前帧尚未被 UI 消费
- **THEN** 丢弃旧帧，只将最新帧传递给 UI

#### Scenario: 正常帧率无堆积
- **WHEN** 帧读取速度跟得上解码速度
- **THEN** 每帧正常传递给 UI，不丢弃

### Requirement: 渲染路径优化
系统 SHALL 优化 QImage 构建路径，减少每帧的内存拷贝操作。

#### Scenario: BGR 帧渲染
- **WHEN** 收到 BGR 格式的 numpy 帧
- **THEN** 直接使用 `QImage.Format_BGR30` 或 `Format_RGBX8888` 构建 QImage，避免 `rgbSwapped()` 额外拷贝

## MODIFIED Requirements

### Requirement: scrcpy server 启动参数
原参数 `max_fps=60` 保持不变，新增 `video_bit_rate=8000000`（8Mbps）以提升画质流畅度，减少编码端马赛克和帧率波动。

## REMOVED Requirements
无移除项。
