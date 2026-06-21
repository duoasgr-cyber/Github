# 修复投屏窗口点击无响应 Spec

## Why
右侧投屏窗口（ScreenshotPicker/EmbeddedMirrorView）中点击后手机没有任何响应，用户无法通过投屏画面操控设备。经代码分析，存在多个潜在原因导致 tap 事件未能正确送达设备。

## What Changes
- **增强 `_send_tap_async` 的健壮性**：添加详细日志、移除静默返回、实现多方式 fallback（参考 MirrorWindow 已有的成熟实现）
- **修复坐标转换逻辑**：确保 `_view_to_device` 在各旋转模式下正确映射坐标
- **添加状态反馈**：tap 发送成功/失败时给用户可见的反馈

## Impact
- Affected code:
  - [screenshot_picker.py](PY/ui/components/screenshot_picker.py) — 主要修改目标，`_send_tap_async` 方法重写
  - [embedded_mirror_widget.py](PY/ui/components/embedded_mirror_widget.py) — `_view_to_device` 坐标转换验证
- Affected specs: 投屏交互功能

## ADDED Requirements

### Requirement: 健壮的 Tap 事件发送

`ScreenshotPicker._send_tap_async` SHALL 提供可靠的 tap 事件发送能力，功能对等于 `MirrorWindow._send_tap_async`。

#### Scenario: 点击投屏画面发送 tap 到设备
- **WHEN** 用户在投屏画面上左键单击
- **THEN** 系统 SHALL 通过 ADB 将触摸事件发送到设备对应坐标位置
- **AND** 发送过程 SHALL 在后台线程执行，不阻塞 UI
- **AND** SHALL 有日志记录发送结果（成功/失败 + 使用的方法名）

#### Scenario: 第一种方式失败自动回退
- **WHEN** 首选的 tap 发送方式失败（如 `input tap` 返回非 0）
- **THEN** 系统 SHALL 自动尝试下一种备选方式
- **AND** 备选方式包括：`input touchscreen tap`、`input tap`、`input motionevent DOWN/UP`

#### Scenario: 关键前置条件不满足
- **WHEN** `_device_serial` 为空或 `_adb_core` 为 None
- **THEN** SHALL 输出 WARNING 级别日志说明原因，而非静默返回

## MODIFIED Requirements

### Requirement: 坐标转换正确性

`EmbeddedMirrorView._view_to_device` SHALL 在所有旋转模式下正确将视图坐标映射为设备坐标。

#### Scenario: 横屏模式下的坐标映射
- **WHEN** 设备处于横屏模式（rotation 1 或 3）
- **AND** 用户点击投屏画面上的某个位置
- **THEN** 计算出的设备坐标 SHALL 正确对应手机屏幕上的实际位置
- **AND** 坐标 SHALL 在有效范围内 `[0, device_width) x [0, device_height)`

### Requirement: Tap 速率限制保持
- **WHEN** 用户快速连续点击
- **THEN** 两次 tap 之间的间隔 SHALL 不小于 `_TAP_MIN_INTERVAL`（当前 50ms）
- **AND** 超出频率的点击 SHALL 被丢弃并记录 DEBUG 日志
