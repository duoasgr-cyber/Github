# 投屏窗口鼠标坐标悬浮显示 Spec

## Why
当前鼠标悬停坐标仅显示在顶部工具栏的 `_coord_label` 中，距离投屏画面较远，用户在精确定位时需要来回视线移动。需要在投屏视图区域右下角直接叠加显示坐标，方便实时观察鼠标对应的设备坐标位置。

## What Changes
- 在 `MirrorGraphicsView` 视图右下角叠加半透明坐标显示层（QLabel / QGraphicsTextItem），跟随鼠标实时更新
- 坐标格式：`(x, y)`，x 和 y 为相对于手机屏幕的设备坐标
- 样式：半透明深色背景 + 亮色文字，不遮挡画面主要内容
- 仅在鼠标进入投屏视图且设备分辨率已获取时显示

## Impact
- Affected code: `PY/ui/mirror_window.py`（主要改动：MirrorGraphicsView 类）
- Affected behavior: 鼠标悬停投屏画面时，右下角实时显示设备坐标

## ADDED Requirements

### Requirement: 投屏视图右下角坐标悬浮显示
系统 SHALL 在 MirrorGraphicsView 的右下角区域叠加显示一个半透明坐标标签，当鼠标在视图内移动时实时更新显示当前鼠标位置对应的设备坐标（x, y）。

#### Scenario: 鼠标在投屏视图内移动
- **WHEN** 用户将鼠标移入投屏视图区域且设备分辨率已设置
- **THEN** 视图右下角显示半透明坐标标签，内容为 `(dev_x, dev_y)` 格式的设备坐标，随鼠标移动实时更新

#### Scenario: 鼠标离开投屏视图
- **WHEN** 用户将鼠标移出投屏视图区域
- **THEN** 坐标标签隐藏或显示为占位文本

#### Scenario: 设备分辨率未获取
- **WHEN** 设备分辨率尚未获取（_device_width == 0）
- **THEN** 坐标标签不显示或显示 `(-, -)`

#### Scenario: 坐标标签样式
- **WHEN** 坐标标签可见
- **THEN** 标签使用半透明深色背景（如 rgba(0,0,0,180)）、亮色文字（#58a6ff）、Consolas 等宽字体、适当内边距、圆角边框，位于视图右下角并保持一定边距

## MODIFIED Requirements
无。

## REMOVED Requirements
无。
