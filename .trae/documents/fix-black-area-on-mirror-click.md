# 修复嵌入式投屏点击后出现黑色区域的计划

## Summary

用户反馈在嵌入式截图选择器（带工具栏的投屏区域）的普通模式下，点击投屏画面右侧后会出现一块黑色矩形区域。经代码分析，该黑色区域是 `EmbeddedMirrorView._update_display()` 中绘制坐标标记文本背景时，`text_rect` 计算错误导致的。

具体而言，代码使用 `painter.window().adjusted(mx + 8, my - th, mx + 8 + tw, my)` 计算文本背景矩形。`painter.window()` 返回的是整张画面的 `QRect(0, 0, W, H)`，`adjusted()` 会把该矩形的四条边分别加上传入的偏移量，从而将矩形错误地放大到画面右下角。当用户在画面右侧点击时，生成的黑色文本背景会覆盖右侧大片区域，形成用户看到的“黑色框选框”。

本计划将修正 `text_rect` 的计算方式，并在必要时对文本位置做越界保护，确保点击后只在标记旁边显示一个小文本背景，不再出现大面积黑色区域。

## Current State Analysis

### 问题代码位置

[PY/ui/components/embedded_mirror_widget.py](PY/ui/components/embedded_mirror_widget.py) L293-L304：

```python
# 坐标文本
dev_x, dev_y = self._view_to_device(mx, my)
text = f"({dev_x}, {dev_y})"
painter.setPen(QPen(QColor(255, 255, 255, 200)))
font = QFont("Consolas", 9)
painter.setFont(font)
fm = painter.fontMetrics()
tw = fm.horizontalAdvance(text) + 8
th = fm.height() + 4
text_rect = painter.window().adjusted(mx + 8, my - th, mx + 8 + tw, my)  # 错误：矩形被放大
painter.fillRect(text_rect, QColor(0, 0, 0, 160))
painter.drawText(text_rect, Qt.AlignCenter, text)
```

### 触发路径

1. 用户在嵌入式截图选择器（`ScreenshotPicker`）中点击投屏画面。
2. `EmbeddedMirrorView.mousePressEvent()` 判断当前不是 `_pickup_mode`，于是在点击位置添加一个标记。
3. `add_marker()` 调用 `_update_display()` 重绘画面。
4. `_update_display()` 遍历所有标记，为每个标记绘制十字、圆圈和坐标文本。
5. 坐标文本背景的 `text_rect` 计算错误，当标记靠近画面右侧时，`fillRect` 会涂黑从标记到画面右下角的整个区域。

### 相关文件

- [PY/ui/components/embedded_mirror_widget.py](PY/ui/components/embedded_mirror_widget.py)：包含 `EmbeddedMirrorView` 和 `_update_display()` 的实现。
- [PY/ui/components/screenshot_picker.py](PY/ui/components/screenshot_picker.py)：使用 `EmbeddedMirrorView` 的截图选择器组件。

## Proposed Changes

### Change 1: 修正坐标文本背景矩形计算

**文件**: [PY/ui/components/embedded_mirror_widget.py](PY/ui/components/embedded_mirror_widget.py) L302-L304

**What**: 将 `text_rect = painter.window().adjusted(mx + 8, my - th, mx + 8 + tw, my)` 改为使用 `QRect` 直接构造正确的文本背景矩形。

**Why**: `painter.window().adjusted(dx1, dy1, dx2, dy2)` 是对整张画面矩形做“边框内缩/外扩”，而不是在指定位置创建一个矩形。改为 `QRect(mx + 8, my - th, tw, th)` 后，文本背景将严格限制在标记右上方的小范围内，不会再覆盖大片区域。

**How**: 替换为如下代码：

```python
text_rect = QRect(mx + 8, my - th, tw, th)
painter.fillRect(text_rect, QColor(0, 0, 0, 160))
painter.drawText(text_rect, Qt.AlignCenter, text)
```

### Change 2: 文本背景越界保护（可选但推荐）

**文件**: [PY/ui/components/embedded_mirror_widget.py](PY/ui/components/embedded_mirror_widget.py) L302 附近

**What**: 当标记靠近画面右边缘或上边缘时，自动将文本背景调整到画面内（例如向左或向下偏移）。

**Why**: 避免文本背景被画面边缘截断，提升可读性。

**How**: 在构造 `text_rect` 前，根据 `draw_pixmap.width()` 和 `draw_pixmap.height()` 判断是否需要调整 `text_x` 和 `text_y`：

```python
text_x = mx + 8
if text_x + tw > draw_pixmap.width():
    text_x = mx - tw - 8
text_y = my - th
if text_y < 0:
    text_y = my + 8
text_rect = QRect(text_x, text_y, tw, th)
```

> 注：Change 2 是对 Change 1 的增强，确保文本背景始终完整可见。若希望改动最小，可只实施 Change 1。

## Assumptions & Decisions

1. 用户所描述的“黑色区域框选框”即为标记坐标文本背景被错误放大后形成的大面积黑色矩形。
2. 保留坐标标记和坐标文本功能，仅修复其背景矩形的绘制范围。
3. `_pickup_mode` 选点模式下不添加标记，因此不会触发该绘制逻辑；本修复主要针对普通点击模式。
4. 优先采用最小改动方案（Change 1），Change 2 作为可读性增强可选实施。

## Verification Steps

1. 启动程序并连接设备，打开嵌入式截图选择器。
2. 在投屏画面右侧点击，添加一个坐标标记。
3. 确认画面右侧不再出现大面积黑色区域。
4. 确认标记旁边仍然正常显示白色坐标文本（如 `(1842, 306)`）。
5. 在不同位置（左上角、右下角、边缘）点击，确认文本背景显示正常、无越界。
6. 进入“从投屏获取坐标”选点模式，确认选点模式下点击不会添加标记，也不会出现黑色区域。
