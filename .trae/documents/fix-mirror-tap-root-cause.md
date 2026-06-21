# 修复投屏点击无响应 — 根因修复计划

## Summary
上一轮修改增强了 `_send_tap_async` 的日志和 fallback 机制，但用户反馈**仍然没有任何日志输出**。经深入排查事件链路，发现真正的根因在更上游：**`EmbeddedMirrorView.mousePressEvent` 中的 `if self._device_width > 0:` 守卫条件导致点击事件从未被发射**。

## Current State Analysis

### 完整点击事件链路
```
用户点击 → EmbeddedMirrorView.mousePressEvent
         → _view_to_device() 转换坐标
         → if self._device_width > 0:   ← 🔴 断点在这里
         → point_clicked.emit()
         → ScreenshotPicker._on_point_clicked()
         → _send_tap_async()             ← 上一轮修改的位置（从未到达）
```

### 根因定位

**`_device_width` 初始值为 0，且设置路径存在缺陷：**

| 设置路径 | 代码位置 | 状态 |
|---------|---------|------|
| 初始值 | `embedded_mirror_widget.py` L96 | **0** |
| 异步 ADB 检测 | `screenshot_picker.py` L238-281 | 依赖 `wm size` 命令 |
| `update_frame()` 回调 | `embedded_mirror_widget.py` L99-117 | **只设 `_frame_width`，不设 `_device_width`** |

**关键缺陷**：`EmbeddedMirrorView.update_frame()` 接收帧数据时只更新了 `_frame_width/_frame_height`（用于渲染），但**从未同步设置 `_device_width/_device_height`**（用于坐标映射）。而 `_device_width` 仅靠异步的 `adb shell wm size` 命令设置——该命令可能延迟或失败。

### 为什么"没有任何日志"
- `mousePressEvent` 中 `if self._device_width > 0:` 为 False → 直接跳过，不 emit 信号
- `_send_tap_async` 根本不会被调用 → 上一轮添加的所有日志都不会触发

## Proposed Changes

### Change 1: `EmbeddedMirrorView.update_frame()` 自动初始化设备分辨率

**文件**: [embedded_mirror_widget.py](PY/ui/components/embedded_mirror_widget.py) L99-117

**What**: 在 `update_frame()` 中，当 `_device_width == 0` 时，自动用帧尺寸初始化设备分辨率。

**Why**: 帧尺寸来自 scrcpy 协议解析的可靠数据，无需额外等待异步 ADB 命令。这是最直接的修复——让投屏画面一有帧就能响应点击。

**How**: 在 `update_frame()` 末尾添加：
```python
# 首次收到帧时，自动初始化设备分辨率（用于坐标映射）
if self._device_width == 0 and w > 0 and h > 0:
    self._device_width = w
    self._device_height = h
```

### Change 2: `mousePressEvent` 添加防御性日志

**文件**: [embedded_mirror_widget.py](PY/ui/components/embedded_mirror_widget.py) L302-322

**What**: 在 `if self._device_width > 0:` 的 else 分支添加 DEBUG 日志。

**Why**: 方便未来排查类似问题，明确告知点击被丢弃的原因。

**How**:
```python
if self._device_width > 0:
    # ... 现有逻辑
else:
    logger.debug("点击被忽略: _device_width=0 (分辨率尚未设置)")
```

### Change 3 (可选增强): `ScreenshotPicker._on_frame_captured` 同步传递分辨率

**文件**: [screenshot_picker.py](PY/ui/components/screenshot_picker.py) L157-160

**What**: 在接收到帧时，同步更新 ScreenshotPicker 自身的 `_device_width/_device_height`。

**Why**: 保持 ScreenshotPicker 和 EmbeddedMirrorView 的分辨率状态一致，避免旋转检测等逻辑使用过时值。

**How**:
```python
def _on_frame_captured(self, frame: np.ndarray):
    if frame is not None and frame.size > 0:
        self._view.update_frame(frame)
        # 同步分辨率信息（确保与 view 一致）
        h, w = frame.shape[:2]
        if self._device_width == 0 and w > 0:
            self._device_width = w
            self._device_height = h
```

## Assumptions & Decisions
1. scrcpy 协议解析的帧尺寸 (`_frame_width x _frame_height`) 与设备物理分辨率一致（对于 Phigros 场景成立）
2. 后续 `wm size` 异步检测结果会覆盖初始值（实现更精确的分辨率），这是安全的
3. 不修改 `MirrorWindow`（独立投屏窗口）的逻辑，它有自己的分辨率获取流程

## Verification Steps
1. 启动程序，连接设备，打开投屏
2. 投屏画面出现后**立即点击**（不等分辨率检测完成）
3. 观察日志应出现 `tap 请求:` 或 `tap 成功` 的输出
4. 手机屏幕应有触摸响应
5. 如果仍有问题，日志中应有明确的断点提示（而非完全静默）
