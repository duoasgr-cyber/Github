# 修复右侧投屏窗口点击手机完全无响应

## Summary

用户在右侧嵌入式投屏窗口（ScreenshotPicker / EmbeddedMirrorView）中点击画面，手机完全没有任何反应，且右下角坐标悬浮标签也不显示。根因是 `EmbeddedMirrorView` 在 `_device_width == 0` 时直接静默丢弃了所有点击和移动事件，而当前代码又取消了 `update_frame()` 中的自动分辨率初始化，导致若 `adb shell wm size` 异步检测失败或未及时返回，点击就会永久无响应。

## Current State Analysis

### 相关文件

- [PY/ui/components/embedded_mirror_widget.py](file:///d:/Github/PY/ui/components/embedded_mirror_widget.py) — `EmbeddedMirrorView` 实现
- [PY/ui/mirror_window.py](file:///d:/Github/PY/ui/mirror_window.py) — 独立投屏窗口 `MirrorGraphicsView`
- [PY/ui/components/screenshot_picker.py](file:///d:/Github/PY/ui/components/screenshot_picker.py) — 右侧截图选择器，使用 `EmbeddedMirrorView`
- [PY/core/screen_capture.py](file:///d:/Github/PY/core/screen_capture.py) — scrcpy server 启动参数 `control=false`，未占用输入设备

### 问题根因链

```
用户点击 / 移动鼠标
    ↓
EmbeddedMirrorView.mousePressEvent / mouseMoveEvent
    ↓
_view_to_device() 因 _device_width == 0 直接返回 (0, 0)
    ↓
if self._device_width > 0: 为 False
    ↓
不 emit point_clicked / mouse_moved，也不更新坐标标签
    ↓
ScreenshotPicker._on_point_clicked 从未被调用
    ↓
手机无任何反应，坐标标签也不显示
```

### 关键代码现状

1. `EmbeddedMirrorView.update_frame()`（embedded_mirror_widget.py L148-162）：
   - 只设置 `_frame_width/_frame_height`
   - **不再**自动初始化 `_device_width/_device_height`
   - 注释说明“等待外部通过 set_device_resolution() 设置正确的物理分辨率”

2. `EmbeddedMirrorView._view_to_device()`（L239-275）：
   - 开头即判断 `if self._pixmap_item is None or self._device_width == 0: return (0, 0)`
   - 只要 `_device_width == 0`，无论点哪里都返回 `(0, 0)`

3. `EmbeddedMirrorView.mousePressEvent()`（L369-402）：
   - `if self._device_width > 0:` 才 emit 信号
   - else 仅记录 debug 日志“点击被忽略”

4. `EmbeddedMirrorView.mouseMoveEvent()`（L404-419）：
   - 同样 `if self._device_width > 0:` 才 emit `mouse_moved` 和更新坐标标签

### 为什么 `wm size` 可能未及时设置 `_device_width`

- `ScreenshotPicker.start()` 异步调用 `_detect_device_resolution()`，通过 `adb shell wm size` 获取
- 如果命令失败、超时、设备未授权、或线程尚未完成，`_device_width` 一直为 0
- 画面已经可以正常显示（scrcpy 帧流正常），但点击被硬阻断

## Proposed Changes

### Change 1: EmbeddedMirrorView — 当无外部分辨率时回退到帧尺寸

**文件**: [PY/ui/components/embedded_mirror_widget.py](file:///d:/Github/PY/ui/components/embedded_mirror_widget.py)

**What**: 在 `update_frame()` 中，若 `_device_width == 0` 且帧尺寸有效，临时用帧尺寸初始化设备分辨率，并标记为“来自帧回退”。

**Why**: 保证投屏画面出现后点击立即有响应，而不是无限期等待 `wm size`。

**How**:

```python
# 在 update_frame() 末尾添加
if self._device_width == 0 and w > 0 and h > 0:
    self._device_width = w
    self._device_height = h
    self._resolution_from_frame = True
    logger.debug("设备分辨率未就绪，暂用帧尺寸回退: %dx%d", w, h)
```

并在 `__init__` 中初始化：

```python
self._resolution_from_frame: bool = False
```

### Change 2: EmbeddedMirrorView — set_device_resolution 覆盖回退值

**What**: 外部传入真实分辨率时，覆盖回退值并清除标记。

**Why**: 一旦 `wm size` 返回真实分辨率，立即纠正坐标映射，避免长期使用被 max_size 缩放过的帧尺寸。

**How**: 修改 `set_device_resolution()`:

```python
def set_device_resolution(self, width: int, height: int):
    self._device_width = width
    self._device_height = height
    self._resolution_from_frame = False
    logger.debug("设置真实设备分辨率: %dx%d", width, height)
```

### Change 3: EmbeddedMirrorView — 移除 mousePressEvent 中的硬阻断

**What**: 将 `if self._device_width > 0:` 改为仅在外部未提供真实分辨率时发出 warning，但仍然 emit 信号。

**Why**: 即使当前只有帧尺寸回退，也应让手机响应点击，而不是完全无反应。坐标偏差问题通过 Change 2 在真实分辨率到达后自动修正。

**How**:

```python
if event.button() == Qt.LeftButton:
    dev_x, dev_y = self._view_to_device(event.pos().x(), event.pos().y())
    if self._device_width > 0:
        if self._resolution_from_frame:
            logger.debug("使用帧尺寸回退发送点击: device=(%d,%d)", dev_x, dev_y)
        if self._pickup_mode:
            self.pickup_completed.emit(dev_x, dev_y)
        elif self._calibration_mode:
            scene_pos = self.mapToScene(event.pos())
            self.add_marker(int(scene_pos.x()), int(scene_pos.y()))
            self.point_clicked.emit(dev_x, dev_y)
        else:
            self.point_clicked.emit(dev_x, dev_y)
    else:
        logger.warning("点击被忽略: _device_width=0 (分辨率尚未设置)")
    event.accept()
    return
```

### Change 4: EmbeddedMirrorView — mouseMoveEvent 同步处理

**What**: 移动鼠标时，若 `_device_width == 0` 但帧尺寸有效，同样允许更新坐标标签。

**Why**: 让用户在真实分辨率到达前也能看到坐标反馈，便于判断投屏是否正常工作。

**How**: 移除 `if self._device_width > 0:` 对 `_update_coord_overlay` 的包裹，仅对 `mouse_moved.emit` 保留判断（避免发送无效坐标信号）。

### Change 5: MirrorGraphicsView（独立投屏窗口）同步修复

**文件**: [PY/ui/mirror_window.py](file:///d:/Github/PY/ui/mirror_window.py)

**What**: 对独立投屏窗口应用相同的回退逻辑：
- `update_frame()` 中自动用帧尺寸回退 `_device_width/_device_height`
- `set_device_resolution()` 覆盖回退值
- 移除 `mousePressEvent` 中的硬阻断

**Why**: 独立窗口与嵌入式窗口逻辑同源，避免同样的问题在独立窗口复现。

### Change 6: ScreenshotPicker — 加速真实分辨率获取后的同步

**文件**: [PY/ui/components/screenshot_picker.py](file:///d:/Github/PY/ui/components/screenshot_picker.py)

**What**: 在 `_poll_latest_frame()` 中，除了帧尺寸同步外，如果自身 `_device_width == 0` 而 view 已有分辨率，也同步一次。

**Why**: 保持 ScreenshotPicker 与 EmbeddedMirrorView 状态一致，避免 tap 发送时使用错误坐标。

**How**:

```python
# 在 _poll_latest_frame() 中 frame 有效后添加
if self._device_width == 0 and self._view.get_device_resolution() != (0, 0):
    self._device_width, self._device_height = self._view.get_device_resolution()
```

> 需要为 EmbeddedMirrorView 添加 `get_device_resolution()` 公开方法。

## Assumptions & Decisions

- **“完全无反应”的根因是 `_device_width == 0` 导致事件被静默丢弃**，而非 ADB 命令或 scrcpy 控制通道问题（scrcpy 已 `control=false`）。
- 用帧尺寸作为临时回退，可能会因 scrcpy `max_size=1280` 缩放导致坐标轻微偏差，但比完全无反应更可接受。
- 一旦 `wm size` 返回真实分辨率，立即覆盖回退值，恢复精确映射。
- 保持现有 `set_device_resolution()` 接口不变，仅增加内部标记和回退逻辑。

## Verification Steps

1. 启动应用，连接设备，打开右侧投屏。
2. 在画面出现后立即点击，手机应有触摸响应。
3. 移动鼠标，右下角坐标标签应显示坐标数字。
4. 查看日志，确认有 `tap 请求:` 或 `点击被忽略` 等明确输出，不再完全静默。
5. 等待几秒后再次点击，确认 `wm size` 返回真实分辨率后坐标更精确。
6. 测试独立投屏窗口，确认同样恢复正常。
7. 测试选点模式、校准模式、滚轮缩放、中键平移等不受影响。
