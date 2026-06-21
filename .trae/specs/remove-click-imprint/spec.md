# 移除投屏窗口点击印记效果 Spec

## Why
投屏窗口（EmbeddedMirrorView）中点击后，之前点击过的位置会在下次点击瞬间出现十字标记和坐标文本的"印记"。原因是 `mousePressEvent` 在普通模式下会调用 `add_marker()` 将点击位置加入 `_markers` 列表，每次点击触发 `_update_display()` 重绘所有历史标记。虽然下一帧更新会覆盖标记，但点击瞬间所有累积标记会短暂闪现。

## What Changes
- 移除普通点击模式下的 `add_marker()` 调用，点击只发送 tap 事件，不添加视觉标记
- 标记功能仅在 `calibration_mode` 和 `pickup_mode` 下保留

## Impact
- Affected code:
  - [embedded_mirror_widget.py](PY/ui/components/embedded_mirror_widget.py) — `EmbeddedMirrorView.mousePressEvent` 移除非选点模式下的 `add_marker()` 调用

## ADDED Requirements

### Requirement: 普通点击不产生视觉标记

`EmbeddedMirrorView` 在普通模式下（非校准模式、非选点模式）点击时 SHALL NOT 添加视觉标记（十字线、坐标文本等）。

#### Scenario: 普通模式点击
- **WHEN** 用户在投屏画面上左键单击
- **AND** `_pickup_mode` 为 False 且 `_calibration_mode` 为 False
- **THEN** 系统 SHALL 仅发射 `point_clicked` 信号
- **AND** SHALL NOT 调用 `add_marker()` 或触发 `_update_display()`
- **AND** 画面上 SHALL NOT 出现任何点击印记

#### Scenario: 校准模式点击仍添加标记
- **WHEN** 用户在投屏画面上左键单击
- **AND** `_calibration_mode` 为 True
- **THEN** 系统 SHALL 调用 `add_marker()` 添加标记并重绘

#### Scenario: 选点模式点击不添加标记
- **WHEN** 用户在投屏画面上左键单击
- **AND** `_pickup_mode` 为 True
- **THEN** 系统 SHALL 仅发射 `pickup_completed` 信号
- **AND** SHALL NOT 调用 `add_marker()`
