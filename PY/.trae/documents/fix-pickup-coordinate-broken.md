# 修复"从投屏获取坐标"功能

## 摘要

"从投屏获取坐标"功能完全失效——用户在步骤编辑器中点击"📍 从投屏获取坐标"按钮后，在投屏画面上点击无法获取坐标。

## 根因分析

**核心缺陷**：`ScreenshotPicker._poll_latest_frame()` 设置了自身的 `_device_width` 但未调用 `self._view.set_device_resolution()`，导致 `EmbeddedMirrorView._device_width` 始终为 0。

`EmbeddedMirrorView.mousePressEvent()` 中有 `if self._device_width > 0` 检查，`_device_width == 0` 时所有点击被静默忽略，输出日志 "点击被忽略: _device_width=0"。

**信号链追踪**：
```
StepEditor.pickup_requested
  → MainWindow._on_pickup_requested()
    → ScreenshotPicker.enter_pickup_mode()
      → EmbeddedMirrorView.set_pickup_mode(True)  ✅ 正确设置 _pickup_mode

EmbeddedMirrorView.mousePressEvent()
  → if self._device_width > 0:  ← ❌ 此处为 False，点击被忽略
    → if self._pickup_mode:
      → pickup_completed.emit(dev_x, dev_y)
        → ScreenshotPicker._on_pickup_completed()
          → pickup_completed.emit(dev_x, dev_y)
            → MainWindow._on_pickup_completed()
              → StepEditor.update_coord_fields(x, y)
```

## 当前状态

前一次会话已应用以下 4 项修复，代码均已就位：

### 修复 1：`screenshot_picker.py` — 同步设备分辨率到 View

**文件**：[screenshot_picker.py](file:///d:/Github/PY/ui/components/screenshot_picker.py#L188-L208)

`_poll_latest_frame()` 中补充了 `self._view.set_device_resolution(w, h)` 调用，确保 View 的 `_device_width` 不再为 0。

```python
if self._device_width == 0 and w > 0:
    self._device_width = w
    self._device_height = h
    # 关键修复：同步设置 view 的设备分辨率
    self._view.set_device_resolution(w, h)
```

### 修复 2：`embedded_mirror_widget.py` — 帧尺寸变化检测

**文件**：[embedded_mirror_widget.py](file:///d:/Github/PY/ui/components/embedded_mirror_widget.py#L159-L174)

`update_frame()` 中在赋值前保存旧值，使帧尺寸变化检测生效。

```python
old_w, old_h = self._frame_width, self._frame_height  # 赋值前保存
self._frame_width = w
self._frame_height = h
if old_w > 0 and old_h > 0 and (w != old_w or h != old_h):
    self._update_pickup_border()
```

### 修复 3：`embedded_mirror_widget.py` — pickup 模式视觉反馈

**文件**：[embedded_mirror_widget.py](file:///d:/Github/PY/ui/components/embedded_mirror_widget.py#L245-L260)

新增 `_update_pickup_border()` 方法，使用独立 `QGraphicsRectItem` 作为蓝色边框 overlay，避免每帧重绘。

### 修复 4：`embedded_mirror_widget.py` — set_pickup_mode 优化

**文件**：[embedded_mirror_widget.py](file:///d:/Github/PY/ui/components/embedded_mirror_widget.py#L237-L243)

`set_pickup_mode()` 仅在有标记/校准时调用 `_update_display()`，避免不必要的场景重建和闪烁。

## 已确认的代码正确性

- [x] 信号链完整：`pickup_requested` → `pickup_completed` 全链路连接正确
- [x] `_device_width` 同步：`_poll_latest_frame()` 和 `_apply_resolution()` 均调用 `set_device_resolution()`
- [x] View 自身回退：`update_frame()` 中当 `_device_width == 0` 时用帧尺寸回退
- [x] pickup 边框 overlay：`_scene.clear()` 后正确重建
- [x] 坐标映射：`dev_x = int(px * device_width / frame_width)` 正确处理 scrcpy 缩放

## 验证步骤

1. 启动应用，连接设备，确认投屏画面正常显示
2. 在工作流编辑器中选择一个 tap/long_press/tap_point 类型的步骤
3. 点击"📍 从投屏获取坐标"按钮
4. 确认投屏画面出现蓝色边框（视觉反馈）
5. 在投屏画面上点击目标位置
6. 确认坐标值正确填入步骤编辑器的 X/Y 字段
7. 对 swipe 类型步骤，验证两次点击分别填入起始和结束坐标
8. 按 Esc 键确认能退出选点模式
