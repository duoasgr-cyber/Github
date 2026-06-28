# 修复高清投屏不显示画面 Spec

## Why
用户反馈使用手机进行高清投屏时，虽然 scrcpy 连接成功建立、设备分辨率正常检测（576x1280）、日志显示"屏幕采集连接已建立"，但投屏窗口中**完全不显示任何画面**。

从截图日志分析：
- scrcpy server 启动成功（version=3.3.4）
- socket 连接成功（127.0.0.1:27183）
- 协议头部解析成功（3.x 协议，codec=h264，分辨率=576x1280）
- 连接状态设置为已建立

**关键问题**：连接建立后，H.264 视频流数据虽然通过 socket 接收，但可能未成功解码为可显示的 RGB 帧，或解码后的帧未正确传递到 UI 层渲染。

## What Changes
- **诊断并修复 PyAV H.264 解码链路**：增加详细的解码过程日志，定位帧数据在哪个环节丢失
- **验证帧传递完整性**：确保从 socket 接收 → PyAV 解码 → numpy 帧 → UI 渲染的完整链路无断裂
- **优化错误处理和日志**：当前代码中多处使用 `except Exception: pass` 或仅记录 debug 级别日志，可能导致关键错误被忽略
- **检查 PyAV 解码器配置兼容性**：确认 LOW_DELAY、FAST 等 flag 在不同 PyAV/FFmpeg 版本下的行为

## Impact
- Affected code: `PY/core/screen_capture.py`（主要改动点：`_scrcpy_read_loop()` 方法）
- Affected behavior: 修复后高清投屏应能正常显示手机画面
- Affected testing: 需要实际连接 Android 设备验证

## ADDED Requirements

### Requirement: H.264 解码过程详细诊断日志
系统 SHALL 在 `_scrcpy_read_loop()` 的每个关键步骤增加 INFO 级别日志，便于定位画面不显示的根本原因。

#### Scenario: Socket 数据接收
- **WHEN** 从 socket 接收到 H.264 原始数据
- **THEN** 记录日志：接收到的数据大小（首次接收时记录，后续每 N 帧记录一次避免刷屏）

#### Scenario: PyAV parse 操作
- **WHEN** 调用 `codec.parse(raw_h264)` 解析 NAL 单元
- **THEN** 如果解析出 packets，记录 packet 数量；如果抛出 InvalidDataError 以外的异常，记录 WARNING 日志包含异常详情

#### Scenario: PyAV decode 操作
- **WHEN** 调用 `codec.decode(packet)` 解码为视频帧
- **THEN** 如果解码出 frames，记录帧数量；如果解码失败且不是 InvalidDataError，记录 WARNING 日志

#### Scenario: 帧格式转换
- **WHEN** 调用 `latest_frame.reformat(format="rgb24").to_ndarray()`
- **THEN** 记录首帧的 shape 和 dtype 信息（仅记录一次）

#### Scenario: 帧缓存更新
- **WHEN** 调用 `self.set_current_frame(rgb_frame)`
- **THEN** 记录首帧缓存成功的日志（仅记录一次）

### Requirement: PyAV 解码器健壮性增强
系统 SHALL 增强 PyAV H.264 解码器的错误处理能力，确保在各种异常情况下不会静默失败。

#### Scenario: 解码器初始化失败
- **WHEN** `CodecContext.create("h264", "r")` 抛出异常
- **THEN** 记录 ERROR 日志并返回，不再继续读取循环

#### Scenario: 解码参数设置失败
- **WHEN** 设置 `thread_type`、`flags`、`flags2` 等属性时抛出异常
- **THEN** 捕获异常并记录 WARNING 日志，但不阻断解码流程（降级运行）

#### Scenario: reformat 操作失败
- **WHEN** `frame.reformat(format="rgb24")` 失败
- **THEN** 记录 ERROR 日志包含原始帧格式信息，跳过该帧继续处理下一帧

### Requirement: 帧数据完整性验证
系统 SHALL 在关键节点增加帧数据有效性检查，尽早发现数据异常。

#### Scenario: 接收到空数据
- **WHEN** `sock.recv()` 返回空字节串（非 b""，而是长度为 0）
- **THEN** 记录 DEBUG 日志并 continue（当前行为已是如此，需确认逻辑正确）

#### Scenario: 解析出的 packet 为空
- **WHEN** `codec.parse()` 返回的 packets 迭代器为空
- **THEN** 不记录日志（正常现象），直接 continue

#### Scenario: 解码出的 frame 为 None 或无效
- **WHEN** `codec.decode()` 返回的 frames 中包含 None 元素
- **THEN** 过滤掉 None 帧不处理

### Requirement: 连接建立后的首帧超时告警
系统 SHALL 在连接建立后的一定时间内检测是否收到首帧，如果超时未收到则发出警告。

#### Scenario: 连接建立后 5 秒内未收到首帧
- **WHEN** `_scrcpy_read_loop()` 进入主循环后 5 秒内 `set_current_frame()` 未被调用
- **THEN** 记录 WARNING 日志："已连接超过 5 秒但未收到任何视频帧，请检查 H.264 解码链路"

## MODIFIED Requirements

### Requirement: `_scrcpy_read_loop()` 主循环逻辑
原实现中异常处理过于宽泛，部分关键错误被静默吞掉。修改为：
- 将 `except InvalidDataError` 保持不变（解码器尚未收到完整帧时的正常现象）
- 将 `except Exception as e` 从 DEBUG 改为 WARNING，并增加更详细的上下文信息（如当前缓冲区大小、最近一次成功解码时间等）
- 增加 try-except 包裹 `set_current_frame()` 调用，防止帧缓存操作异常导致整个循环退出

### Requirement: PyAV 解码器配置
原实现设置了一些高级优化参数（LOW_DELAY、FAST、skip_loop_filter），可能在某些 FFmpeg/PyAV 版本组合下不兼容或产生副作用。修改为：
- 保留 `thread_type = "AUTO"` 和 `thread_count = 0`
- 保留 `flags |= LOW_DELAY`
- 将 `flags2 |= FAST` 和 `skip_loop_filter = "ALL"` 改为可选配置，失败时不影响核心功能
- 增加解码器创建后的状态验证日志

## REMOVED Requirements
无移除项。
