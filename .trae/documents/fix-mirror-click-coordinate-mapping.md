# 修复投屏窗口点击坐标偏移问题

## 问题摘要

用户在投屏窗口中点击某个位置后，手机响应的实际位置与点击位置不一致（存在偏移）。这是一个坐标映射错误的问题。

## 当前状态分析

### 根本原因识别

通过代码分析，发现**三个关键问题**导致坐标映射不准确：

#### 问题 1：设备分辨率初始化错误（主要原因）

**文件**: [embedded_mirror_widget.py](d:\Github\PY\ui\components\embedded_mirror_widget.py#L152-L154)

```python
# 首次收到帧时，自动初始化设备分辨率（用于坐标映射）
if self._device_width == 0 and w > 0 and h > 0:
    self._device_width = w
    self._device_height = h
```

**问题描述**：
- scrcpy server 设置了 `max_size=1280`（见 [screen_capture.py#L526](d:\Github\PY\core\screen_capture.py#L526)），导致视频帧被缩放
- 例如：设备实际分辨率 1080x1920，但帧尺寸可能是 720x1280
- 上述代码会在首次收到帧时，**错误地将帧尺寸（720x1280）作为设备分辨率**
- 后续即使通过 `wm size` 获取到正确的物理分辨率（1080x1920），也可能因为时序问题导致坐标计算错误

**影响范围**：所有使用 `EmbeddedMirrorWidget` 的场景

---

#### 问题 2：设备旋转时的坐标映射不一致

**文件**:
- [mirror_window.py](d:\Github\PY\ui\mirror_window.py#L866-L873)
- [embedded_mirror_widget.py](d:\Github\PY\ui\components\embedded_mirror_widget.py#L711-L714)

```python
# 交换宽高
if (old in (0, 2)) != (new_rotation in (0, 2)):
    self._device_width, self._device_height = (self._device_height, self._device_width)
    self._view.set_device_resolution(self._device_width, self._device_height)
```

**问题描述**：
- 当设备旋转时（如从竖屏 0° 到横屏 90°），代码会交换 `_device_width` 和 `_device_height`
- 但是 **`_frame_width` 和 `_frame_height`（来自 scrcpy 视频流）也会随着设备旋转而改变**
- 在旋转过渡期间，可能出现以下情况：
  - 设备分辨率已交换（1920x1080）
  - 但视频帧还是旧的竖屏帧（720x1280）
  - 导致坐标映射比例错误

**示例**：
- 用户点击画面中心点
- 场景坐标：(360, 640) （假设帧是 720x1280）
- 错误映射：dev_x = 360 * 1920 / 720 = 960, dev_y = 640 * 1080 / 1280 = 540
- 正确应该是：dev_x = 540, dev_y = 960 （考虑旋转）

---

#### 问题 3：缺少帧与设备分辨率同步验证机制

**当前实现缺陷**：
- 没有验证 `_frame_width/frame_height` 与 `_device_width/device_height` 的比例关系是否合理
- 没有处理帧更新后分辨率可能变化的情况（如设备旋转、scrcpy 重连等）
- 坐标映射完全依赖开发者手动保持两者一致，容易出错

---

### 技术细节说明

#### scrcpy 的 max_size 参数影响

[screen_capture.py#L526](d:\Github\PY\core\screen_capture.py#L526):
```python
"max_size=1280",
```

这意味着：
- 设备分辨率 1920x1080 → 帧尺寸约 1280x720（或更小）
- 设备分辨率 1080x1920 → 帧尺寸约 720x1280（或更小）
- **帧尺寸 ≠ 设备实际分辨率**

#### 坐标映射流程

```
用户点击(view_x, view_y)
    ↓
mapToScene() → (scene_x, scene_y)  // 视图坐标转场景坐标
    ↓
_view_to_device():
    dev_x = scene_x * _device_width / _frame_width
    dev_y = scene_y * _device_height / _frame_height
    ↓
发送 tap(dev_x, dev_y) 到设备
```

**正确性条件**：`_device_width/_frame_width == _device_height/_frame_height`（即缩放比例一致）

---

## 修复方案

### 方案概述

修复核心思路：**确保坐标映射使用正确的参考系，并增加同步验证机制**

具体措施：
1. **移除错误的自动初始化逻辑**
2. **添加帧分辨率同步验证**
3. **优化旋转处理的时序**
4. **添加调试日志便于排查**

---

### 详细修改计划

#### 修改 1: 移除 EmbeddedMirrorView 的错误初始化

**文件**: [embedded_mirror_widget.py](d:\Github\PY\ui\components\embedded_mirror_widget.py#L150-L154)

**当前代码**:
```python
self._frame_width = w
self._frame_height = h

# 首次收到帧时，自动初始化设备分辨率（用于坐标映射）
if self._device_width == 0 and w > 0 and h > 0:
    self._device_width = w
    self._device_height = h
```

**修改为**:
```python
self._frame_width = w
self._frame_height = h

# 不再自动初始化设备分辨率，等待外部通过 set_device_resolution() 设置正确的物理分辨率
# 这样可以避免因 scrcpy max_size 缩放导致的帧尺寸与实际分辨率不匹配问题
```

**原因**：
- 帧尺寸可能被 max_size 缩放，不能代表真实设备分辨率
- 必须等待 `wm size` 命令返回正确的物理分辨率
- 外部调用者（EmbeddedMirrorWidget/MirrorWindow）负责在获取分辨率后调用 `set_device_resolution()`

---

#### 修改 2: 添加帧分辨率验证和日志

**文件**: [embedded_mirror_widget.py](d:\Github\PY\ui\components\embedded_mirror_widget.py#L231-L246)

**当前代码** (_view_to_device 方法):
```python
def _view_to_device(self, view_x: int, view_y: int) -> Tuple[int, int]:
    """视图坐标 -> 设备坐标。"""
    if self._pixmap_item is None or self._device_width == 0:
        return (0, 0)
    scene_pos = self.mapToScene(view_x, view_y)
    px = scene_pos.x()
    py = scene_pos.y()
    pw = self._frame_width
    ph = self._frame_height
    if pw == 0 or ph == 0:
        return (0, 0)
    dev_x = int(px * self._device_width / pw)
    dev_y = int(py * self._device_height / ph)
    dev_x = max(0, min(dev_x, self._device_width - 1))
    dev_y = max(0, min(dev_y, self._device_height - 1))
    return (dev_x, dev_y)
```

**修改为**:
```python
def _view_to_device(self, view_x: int, view_y: int) -> Tuple[int, int]:
    """视图坐标 -> 设备坐标。"""
    if self._pixmap_item is None or self._device_width == 0:
        return (0, 0)
    scene_pos = self.mapToScene(view_x, view_y)
    px = scene_pos.x()
    py = scene_pos.y()
    pw = self._frame_width
    ph = self._frame_height
    if pw == 0 or ph == 0:
        return (0, 0)

    # 验证坐标是否在有效范围内（防止缩放比例异常导致的坐标越界）
    if px < 0 or py < 0 or px > pw or py > ph:
        logger.debug(
            "坐标超出帧范围: scene=(%.1f, %.1f), frame=%dx%d",
            px, py, pw, ph
        )

    dev_x = int(px * self._device_width / pw)
    dev_y = int(py * self._device_height / ph)
    dev_x = max(0, min(dev_x, self._device_width - 1))
    dev_y = max(0, min(dev_y, self._device_height - 1))

    # 调试日志：输出坐标映射详情（仅在首几次点击时输出，避免日志过多）
    if not hasattr(self, '_click_count'):
        self._click_count = 0
    if self._click_count < 5:
        self._click_count += 1
        logger.debug(
            "坐标映射: view=(%d,%d) -> scene=(%.1f,%.1f) -> device=(%d,%d) "
            "[frame=%dx%d, device=%dx%d]",
            view_x, view_y, px, py, dev_x, dev_y,
            pw, ph, self._device_width, self._device_height
        )

    return (dev_x, dev_y)
```

**目的**：
- 添加边界检查和日志输出
- 便于后续调试和验证坐标映射是否正确
- 仅输出前 5 次点击日志，避免性能影响

---

#### 修改 3: 同样修改 MirrorWindow 中的 MirrorGraphicsView

**文件**: [mirror_window.py](d:\Github\PY\ui\mirror_window.py#L168-L183)

对 `MirrorGraphicsView._view_to_device()` 应用相同的修改（添加调试日志和边界检查）。

---

#### 修改 4: 确保设备分辨率优先于帧更新

**文件**: [embedded_mirror_widget.py](d:\Github\PY\ui\components\embedded_mirror_widget.py#L600-L614)

**当前代码** (start 方法):
```python
def start(self, serial: str):
    """启动投屏。"""
    self._device_serial = serial
    self._connected = True
    self._status_label.setText("已连接")
    self._status_label.setStyleSheet("color: #3fb950; font-size: 12px;")

    # 获取设备分辨率
    self._get_device_resolution()

    # 启动旋转检测
    self._start_rotation_detection()

    # 启动帧更新
    self._start_frame_update()
```

**修改为**:
```python
def start(self, serial: str):
    """启动投屏。"""
    self._device_serial = serial
    self._connected = True
    self._status_label.setText("已连接")
    self._status_label.setStyleSheet("color: #3fb950; font-size: 12px;")

    # 先获取设备分辨率（必须在帧更新之前完成）
    self._get_device_resolution()

    # 启动旋转检测
    self._start_rotation_detection()

    # 最后启动帧更新（确保分辨率已就绪）
    self._start_frame_update()
```

虽然代码顺序没有变化，但添加注释强调时序重要性。

---

#### 修改 5: 添加帧尺寸变化检测

**文件**: [embedded_mirror_widget.py](d:\Github\PY\ui\components\embedded_mirror_widget.py#L124-L149)

**当前代码** (update_frame 方法):
```python
def update_frame(self, frame: np.ndarray):
    """更新显示帧（RGB numpy array）。"""
    if frame is None or frame.size == 0:
        return
    h, w, ch = frame.shape
    bytes_per_line = ch * w
    # ...（省略）
    self._frame_width = w
    self._frame_height = h

    # 首次收到帧时，自动初始化设备分辨率（用于坐标映射）
    if self._device_width == 0 and w > 0 and h > 0:
        self._device_width = w
        self._device_height = h
```

**修改为**:
```python
def update_frame(self, frame: np.ndarray):
    """更新显示帧（RGB numpy array）。"""
    if frame is None or frame.size == 0:
        return
    h, w, ch = frame.shape
    bytes_per_line = ch * w
    # ...（省略中间代码）

    old_w, old_h = self._frame_width, self._frame_height
    self._frame_width = w
    self._frame_height = h

    # 检测帧尺寸变化（可能由设备旋转、scrcpy 重连等原因导致）
    if old_w > 0 and old_h > 0 and (w != old_w or h != old_h):
        logger.info(
            "帧尺寸变化: %dx%d -> %dx%d（可能设备旋转或重连）",
            old_w, old_h, w, h
        )
        # 注意：此处不自动更新设备分辨率，
        # 由外部的旋转检测逻辑负责同步更新
```

**目的**：
- 检测帧尺寸变化并记录日志
- 明确不在帧更新时自动修改设备分辨率（避免覆盖正确的物理分辨率）

---

#### 修改 6: 同样修改 MirrorWindow 的 MirrorGraphicsView.update_frame()

**文件**: [mirror_window.py](d:\Github\PY\ui\mirror_window.py#L122-L140)

应用相同的修改（移除可能的隐式初始化逻辑，添加帧尺寸变化检测）。

注意：查看当前代码，MirrorGraphicsView.update_frame() 并没有自动初始化设备分辨率的逻辑，所以只需添加帧尺寸变化检测即可。

---

### 修改文件清单

| 文件路径 | 修改内容 | 优先级 |
|---------|---------|--------|
| `ui/components/embedded_mirror_widget.py` | 1. 移除错误的自动初始化<br>2. 添加坐标映射日志<br>3. 添加帧尺寸变化检测 | **高** |
| `ui/mirror_window.py` | 1. 添加坐标映射日志<br>2. 添加帧尺寸变化检测 | **高** |

---

## 假设与决策

### 假设
1. 设备的物理分辨率通过 `wm size` 命令获取的是准确的
2. scrcpy 的 `max_size=1280` 会导致帧尺寸小于等于设备实际分辨率
3. 设备旋转时，帧尺寸和设备分辨率都会相应变化（宽高交换）
4. QGraphicsView 的 `mapToScene()` 在有缩放/平移变换时仍能正确工作

### 决策
1. **不修改 scrcpy 的 max_size 参数**：虽然增大 max_size 可以减少缩放差异，但会增加带宽和延迟
2. **不重构整个坐标系统**：当前的映射逻辑本身是正确的，只需要确保输入数据准确
3. **优先修复 EmbeddedMirrorWidget**：因为它包含错误的自动初始化逻辑，是主要问题源
4. **添加调试日志而非断言**：生产环境中不应因坐标问题崩溃，只记录日志便于排查

---

## 验证步骤

### 单元测试（可选）
1. 测试 `_view_to_device()` 在不同缩放比例下的正确性
2. 测试边界条件（负坐标、超大坐标等）

### 手动测试（必需）

#### 测试场景 1：正常竖屏模式
1. 连接设备（竖屏方向）
2. 打开投屏窗口
3. 点击画面的四个角和中心点
4. **预期**：手机响应位置与点击位置一致
5. **验证方法**：在手机上打开一个网格或标尺应用，对比点击位置

#### 测试场景 2：横屏模式
1. 将设备旋转到横屏
2. 等待投屏窗口自适应
3. 再次点击测试点
4. **预期**：坐标仍然准确

#### 测试场景 3：旋转切换
1. 在竖屏和横屏之间多次切换
2. 每次切换后立即点击
3. **预期**：即使在旋转过渡期间，坐标也不会严重偏离（允许短暂的不准确）

#### 测试场景 4：高分辨率设备
1. 使用 2K 或更高分辨率的设备（如 2560x1440）
2. 由于 max_size=1280，帧会被大幅缩放
3. **预期**：坐标映射仍然准确（这是关键的回归测试）

#### 测试场景 5：不同缩放级别
1. 在投屏窗口中使用滚轮缩放（放大/缩小）
2. 在不同缩放级别下点击同一位置
3. **预期**：无论缩放级别如何，点击位置都应映射到相同的设备坐标

### 日志验证
1. 运行程序后，查看日志输出中的"坐标映射"信息
2. 确认 `frame` 尺寸与 `device` 分辨率的比值是否合理
3. 如果比值接近 1.0（如 1280/1080≈1.19），说明帧确实被缩放了
4. 确认最终的设备坐标在合理范围内（0 到 device_width/height 之间）

---

## 回归风险

### 低风险
- 添加的日志输出不影响功能逻辑
- 帧尺寸变化检测只是记录日志

### 中等风险
- **移除自动初始化逻辑**：如果在某些极端情况下 `wm size` 命令失败或未及时返回，可能导致短暂的 `_device_width==0`，此时点击会被忽略
- **缓解措施**：现有的代码已经有处理 `_device_width==0` 的逻辑（返回 (0,0) 并忽略点击）

### 高风险
- 无

---

## 后续优化建议（本次不实施）

1. **考虑使用 scrcpy 的原始分辨率**：将 `max_size` 提高到设备实际分辨率（如 1920 或 2560），消除缩放差异
2. **添加坐标校准功能**：允许用户手动校准点击偏移（适用于特殊设备或定制 ROM）
3. **缓存设备分辨率**：避免每次启动都执行 ADB 命令
4. **支持多显示器 DPI 缩放**：在高 DPI 屏幕上可能需要额外的坐标转换

---

## 总结

**根本原因**：`EmbeddedMirrorView` 在首次收到视频帧时，错误地将被 scrcpy 缩放后的帧尺寸作为设备物理分辨率，导致坐标映射比例错误。

**修复策略**：
1. 移除错误的自动初始化逻辑
2. 依赖外部提供的正确设备分辨率（来自 `wm size` 命令）
3. 添加调试日志和变化检测，提高可观测性

**预期效果**：修复后，无论设备分辨率、旋转状态、缩放级别如何，投屏窗口的点击位置都能准确映射到手机的对应位置。
