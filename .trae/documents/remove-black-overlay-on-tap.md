# 移除点击后屏幕变黑遮罩的计划

## Summary
用户反馈点击右侧投屏窗口后，屏幕直接变黑。经代码分析，这是 `EmbeddedMirrorView._update_display()` 中 `_pickup_mode` 模式下绘制的半透明黑色遮罩导致的（颜色 `QColor(0, 0, 0, 100)`）。

用户要求**直接移除这个变黑设定**，即不再在选点模式下给投屏画面添加黑色遮罩。

## Current State Analysis

### 变黑代码位置
[embedded_mirror_widget.py](PY/ui/components/embedded_mirror_widget.py) L268-L287：

```python
# 坐标选择模式遮罩
if self._pickup_mode:
    painter.fillRect(
        draw_pixmap.rect(),
        QColor(0, 0, 0, 100)  # 半透明黑色遮罩
    )
    # 中央提示文字
    hint = "点击屏幕选择坐标"
    font = QFont("Microsoft YaHei", 16, QFont.Bold)
    painter.setFont(font)
    painter.setPen(QPen(QColor(255, 255, 255, 200)))
    ...
```

### 触发路径
1. 进入选点模式时：`main_window._on_pickup_requested()` → `screenshot_picker.enter_pickup_mode()` → `EmbeddedMirrorView.set_pickup_mode(True)`
2. 任何导致 `_update_display()` 被调用的事件（如添加标记、进入选点模式）都会重绘遮罩

## Proposed Changes

### Change 1: 移除黑色遮罩和提示文字

**文件**: [embedded_mirror_widget.py](PY/ui/components/embedded_mirror_widget.py) L268-L287

**What**: 删除 `_pickup_mode` 分支中的 `painter.fillRect()` 黑色遮罩和中央提示文字绘制。

**Why**: 直接响应用户要求——点击后屏幕不再变黑。

**How**: 将 `_pickup_mode` 分支的内容完全删除（或只保留最少必要的标记差异）。

### Change 2 (可选): 保留选点模式标记

如果希望用户在选点模式下仍有视觉反馈，可以改用不遮挡画面的方式（如边框高亮），但用户明确要求移除变黑，因此直接删除即可。

## Assumptions & Decisions
1. 用户只要求移除"变黑"效果，不是移除选点模式本身
2. `_pickup_mode` 的状态变量保留，仅移除视觉遮罩
3. 选点模式下点击仍正常发出 `pickup_completed` 信号

## Verification Steps
1. 启动程序，连接设备，打开投屏
2. 进入选点模式（或任何会触发 `_update_display()` 的场景）
3. 确认投屏画面不再变黑
4. 确认点击仍能正常选择坐标/发送 tap
