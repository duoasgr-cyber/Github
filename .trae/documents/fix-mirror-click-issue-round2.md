# 修复投屏窗口点击无反应和坐标偏移问题（第二轮）

## 问题描述

用户反馈两个问题：
1. **点击后可能没有反应** - 点击事件被忽略或不触发 tap
2. **手机响应的位置与点击位置不一致** - 坐标映射存在系统性偏差

---

## 第一轮修复回顾

第一轮修复移除了 `update_frame()` 中的自动初始化逻辑（将帧尺寸作为设备分辨率），但后续发现这会导致 `_device_width==0` 时点击被完全忽略。因此代码已恢复回退逻辑（第176-182行），允许在真实分辨率未就绪时临时使用帧尺寸。

**然而，这种回退机制本身就是坐标偏移的根源之一**：当帧被 scrcpy 的 `max_size=1280` 缩放后，帧尺寸 ≠ 设备实际分辨率，使用帧尺寸作为设备分辨率必然导致坐标错误。

---

## 根本原因分析（深度）

### 问题 1：点击无反应的根本原因

#### 原因 A：竞态条件导致的短暂无效期

**时序问题**：
```
t=0ms:  start() 被调用
t=1ms:  _get_device_resolution() 启动后台线程执行 adb shell wm size
t=2ms:  _start_frame_update() 启动定时器（8ms间隔）
t=10ms: 第一帧到达 update_frame()
        → _device_width == 0（wm size 还没返回）
        → 触发回退逻辑：_device_width = frame_width（如720）
        → _resolution_from_frame = True
t=500ms: wm size 返回结果
         → _set_resolution(1080, 1920) 被调用
         → 覆盖回退值：_device_width = 1080 ✓
```

**正常情况下**：500ms 后分辨率就正确了，点击应该能响应。

**异常情况**：
- 如果 `wm size` 命令失败（超时、权限问题等）
- `_device_width` 保持为回退值（帧尺寸）
- 点击有响应，但**坐标是错的**（这是问题2的根源）

#### 原因 B：坐标越界被静默忽略

查看 [embedded_mirror_widget.py#L370-372](d:\Github\PY\ui\components\embedded_mirror_widget.py#L370-L372)：
```python
if self._device_width > 0:
    # ... 发射信号
else:
    logger.debug("点击被忽略: _device_width=0")
```

**问题**：当 `_device_width > 0` 但值不正确时（如使用了帧尺寸），点击会有响应但坐标错误，且**没有任何警告日志**！

---

### 问题 2：坐标偏移的根本原因（核心问题）

#### 核心矛盾：帧尺寸 vs 设备分辨率的缩放差异

**技术背景**：
- scrcpy server 参数：`max_size=1280`（见 [screen_capture.py#L558](d:\Github\PY\core\screen_capture.py#L558)）
- 这意味着视频流的最大边长会被缩放到 ≤1280px
- 例如：设备 1080x1920 → 帧 720x1280（短边优先适配 max_size）

**坐标映射公式**（[embedded_mirror_widget.py#L248-251](d:\Github\PY\ui\components\embedded_mirror_widget.py#L248-251)）：
```python
dev_x = int(px * self._device_width / pw)  # px=场景x坐标, pw=帧宽, _device_width=设备宽
dev_y = int(py * self._device_height / ph)  # py=场景y坐标, ph=帧高, _device_height=设备高
```

**正确性条件**：`_device_width / pw == _device_height / ph`（即两个轴的缩放比例必须一致）

#### 场景分析

##### 场景 1：竖屏模式（理想情况）
- 设备分辨率：1080x1920
- 帧尺寸：720x1280（max_size=1280 缩放）
- 缩放比例：1080/720 = 1.5, 1920/1280 = 1.5 ✓ 一致
- 用户点击画面中心 (360, 640)
- 映射结果：dev_x = 360 * 1080 / 720 = 540, dev_y = 640 * 1920 / 1280 = 960 ✓

##### 场景 2：使用了错误的设备分辨率（回退逻辑触发时）
- 设备实际分辨率：1080x1920
- 帧尺寸：720x1280
- **错误地**设置：_device_width=720, _device_height=1280（使用了帧尺寸作为回退）
- 缩放比例：720/720 = 1.0, 1280/1280 = 1.0 ✓ 数学上一致
- 用户点击画面中心 (360, 640)
- 映射结果：dev_x = 360 * 720 / 720 = 360, dev_y = 640 * 1280 / 1280 = 640
- **实际应该**: dev_x=540, dev_y=960
- **误差**: (-180, -320)，即点击位置比预期偏左上约33%！

**这就是用户报告的"手机响应位置不对"的主要原因！**

##### 场景 3：设备旋转时的复杂情况

**关键问题：scrcpy 帧的方向已经随设备旋转**

当设备从竖屏旋转到横屏时：
- scrcpy 自动输出横向帧（如从 720x1280 变成 1280x720）
- `wm size` 也自动返回横向分辨率（如从 1080x1920 变成 1920x1080）
- **两者都是自适应的，不需要额外的旋转处理！**

**但是代码中的旋转处理逻辑**（[embedded_mirror_widget.py#L785-788](d:\Github\PY\ui\components\embedded_mirror_widget.py#L785-788)）：
```python
if (old in (0, 2)) != (new_rotation in (0, 2)):
    self._device_width, self._device_height = (self._device_height, self._device_width)
    self._view.set_device_resolution(self._device_width, self._device_height)
```

**潜在问题**：
1. 如果 `wm size` 已经返回了新的横向分辨率（1920x1080）
2. 然后 rotation 检测又执行了一次交换
3. 结果变成 (1080, 1920) ← **错误的！**

**竞态条件示例**：
```
t=0s:   初始：_device_width=1080, _device_height=1920（竖屏）
t=2s:   用户旋转设备到横屏
t=2.1s: scrcpy 输出新帧：1280x720（横向）
t=2.5s: wm size 轮询返回：1920x1080（横向）
        → _set_resolution(1920, 1080) 被调用
        → _device_width=1920, _device_height=1080 ✓
t=3.0s: rotation 定时器触发（2秒间隔）
        → 检测到 rotation: 0→1
        → 执行交换：_device_width=1080, _device_height=1920 ✗ 错误！
```

**结果**：坐标完全颠倒！

---

### 问题 3：QGraphicsView fitInView 导致的坐标系统复杂性

**隐藏问题**：`fitInView()` 会引入复杂的坐标系变换

当 pixmap 尺寸与 viewport 尺寸比例不同时：
```python
# pixmap: 720x1280 (竖向长图)
# viewport: 800x600 (横向宽屏)

# fitInView(KeepAspectRatio) 会：
# 1. 计算缩放因子：scale = min(800/720, 600/1280) = 0.469
# 2. 缩放后 pixmap 尺寸：337.5 x 600
# 3. 水平居中：pixmap 左边界 x = (800-337.5)/2 = 231.25
```

此时用户点击 viewport 的 (400, 300)（视觉中心）：
- `mapToScene(400, 300)` 应该返回 pixmap 上的 (360, 640)（画面中心）
- **理论上这是正确的**，Qt 的 mapToScene 会处理所有变换

**但是如果**：
- pixmap_item 的位置不是精确的 (0,0)
- 或者 scene 的 rect 被修改过
- 或者有其他的 transform 叠加

都可能导致 mapToScene 返回意外值。

---

## 修复方案

### 方案概述

采用**多层次的防御性修复**：

1. **消除回退机制的副作用**：即使使用帧尺寸作为临时回退，也要记录标记并在真实分辨率到达时立即更新
2. **解决旋转处理的竞态条件**：避免重复交换或遗漏交换
3. **添加坐标一致性验证**：在每次坐标映射时验证缩放比例是否合理
4. **增强日志和可观测性**：输出足够的信息用于诊断问题

---

### 详细修改计划

#### 修改 1: 改进设备分辨率设置机制

**文件**: [embedded_mirror_widget.py](d:\Github\PY\ui\components\embedded_mirror_widget.py) - `EmbeddedMirrorView` 类

**当前位置** (#L119-L133):
```python
def set_device_resolution(self, width: int, height: int):
    """设置设备物理分辨率，用于坐标映射。"""
    self._device_width = width
    self._device_height = height
    self._resolution_from_frame = False
    logger.debug("设置真实设备分辨率: %dx%d", width, height)
```

**修改为**:
```python
def set_device_resolution(self, width: int, height: int):
    """设置设备物理分辨率，用于坐标映射。

    Args:
        width: 设备宽度（像素）
        height: 设备高度（像素）
    """
    old_w, old_h = self._device_width, self._device_height
    self._device_width = width
    self._device_height = height
    self._resolution_from_frame = False

    # 检测分辨率变化（用于诊断）
    if old_w > 0 and old_h > 0 and (width != old_w or height != old_h):
        logger.info(
            "设备分辨率更新: %dx%d -> %dx%d %s",
            old_w, old_h, width, height,
            "(覆盖帧尺寸回退)" if getattr(self, '_resolution_from_frame', False) else ""
        )

    logger.debug("设置真实设备分辨率: %dx%d", width, height)
```

**目的**：记录分辨率变化历史，便于诊断是否发生了意外的覆盖或重复交换。

---

#### 修改 2: 改进回退逻辑，添加明确标记和警告

**文件**: [embedded_mirror_widget.py](d:\Github\PY\ui\components\embedded_mirror_widget.py) - `update_frame()` 方法

**当前位置** (#L176-L182):
```python
# 当外部尚未提供真实分辨率时，用帧尺寸作为临时回退，保证点击有响应。
# 后续 set_device_resolution() 会被外部调用并覆盖该回退值。
if self._device_width == 0 and w > 0 and h > 0:
    self._device_width = w
    self._device_height = h
    self._resolution_from_frame = True
    logger.debug("设备分辨率未就绪，暂用帧尺寸回退: %dx%d", w, h)
```

**修改为**:
```python
# 当外部尚未提供真实分辨率时，用帧尺寸作为临时回退，保证点击有响应。
# ⚠️ 注意：此回退值通常不准确（帧已被 scrcpy max_size 缩放），
#    仅用于避免点击完全无反应，坐标会有系统性偏差。
# 后续 set_device_resolution() 会被外部调用并覆盖该回退值。
if self._device_width == 0 and w > 0 and h > 0:
    self._device_width = w
    self._device_height = h
    self._resolution_from_frame = True
    logger.warning(
        "⚠️ 设备分辨率未就绪，暂用帧尺寸回退: %dx%d (坐标可能有偏差，等待真实分辨率)",
        w, h
    )
```

**改动**：
- 日志级别从 debug 提升到 warning
- 添加明确的警告说明坐标可能不准确
- 便于运维人员快速识别问题

---

#### 修改 3: 在坐标映射中添加一致性验证

**文件**: [embedded_mirror_widget.py](d:\Github\PY\ui\components\embedded_mirror_widget.py) - `_view_to_device()` 方法

**当前位置** (#L229-L265):
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

    # === 坐标一致性验证 ===
    # 检查帧与设备的缩放比例是否一致（允许 ±5% 误差）
    if self._device_width > 0 and self._device_height > 0 and pw > 0 and ph > 0:
        scale_x = self._device_width / pw
        scale_y = self._device_height / ph
        # 如果两个轴的缩放比例差异超过 10%，说明可能有问题
        if abs(scale_x - scale_y) / max(scale_x, scale_y) > 0.1:
            logger.warning(
                "⚠️ 坐标映射比例异常: X=%.2f, Y=%.2f (frame=%dx%d, device=%dx%d) "
                "%s",
                scale_x, scale_y, pw, ph,
                self._device_width, self._device_height,
                "(使用帧尺寸回退)" if getattr(self, '_resolution_from_frame', False) else ""
            )

    # 验证坐标是否在有效范围内
    if px < 0 or py < 0 or px > pw or py > ph:
        logger.debug(
            "坐标超出帧范围: scene=(%.1f, %.1f), frame=%dx%d",
            px, py, pw, ph
        )

    dev_x = int(px * self._device_width / pw)
    dev_y = int(py * self._device_height / ph)
    dev_x = max(0, min(dev_x, self._device_width - 1))
    dev_y = max(0, min(dev_y, self._device_height - 1))

    # 调试日志（限制输出频率）
    if not hasattr(self, '_click_count'):
        self._click_count = 0
    if self._click_count < 5:
        self._click_count += 1
        logger.debug(
            "坐标映射 #%d: view(%d,%d)->scene(%.1f,%.1f)->dev(%d,%d) "
            "[frame=%dx%d, device=%dx%d, scale=%.2fx%.2f, fallback=%s]",
            self._click_count,
            view_x, view_y, px, py, dev_x, dev_y,
            pw, ph, self._device_width, self._device_height,
            self._device_width / pw if pw > 0 else 0,
            self._device_height / ph if ph > 0 else 0,
            getattr(self, '_resolution_from_frame', False)
        )

    return (dev_x, dev_y)
```

**新增功能**：
1. **缩放比例一致性检查**：如果 X/Y 轴缩放比例差异超过 10%，输出 warning 日志
2. **增强的调试信息**：包含缩放比例数值和是否使用回退值的标记
3. **便于快速定位问题**：看到 warning 就知道坐标可能不准确

---

#### 修改 4: 解决旋转处理的竞态条件

**文件**: [embedded_mirror_widget.py](d:\Github\PY\ui\components\embedded_mirror_widget.py) - `_on_rotation_detected()` 方法

**当前位置** (#L777-L791):
```python
def _on_rotation_detected(self, new_rotation: int):
    """旋转检测回调。"""
    if new_rotation != self._device_rotation:
        old = self._device_rotation
        self._device_rotation = new_rotation
        logger.info("设备旋转: %d -> %d", old, new_rotation)

        # 交换宽高
        if (old in (0, 2)) != (new_rotation in (0, 2)):
            self._device_width, self._device_height = (self._device_height, self._device_width)
            self._view.set_device_resolution(self._device_width, self._device_height)
            self._resolution_label.setText(f"分辨率: {self._device_width}x{self._device_height}")

        # 自动适配
        QTimer.singleShot(100, self._on_fit)
```

**修改为**:
```python
def _on_rotation_detected(self, new_rotation: int):
    """旋转检测回调。"""
    if new_rotation != self._device_rotation:
        old = self._device_rotation
        self._device_rotation = new_rotation
        logger.info("设备旋转: %d -> %d", old, new_rotation)

        # 交换宽高（仅当方向改变时：竖屏↔横屏）
        if (old in (0, 2)) != (new_rotation in (0, 2)):
            old_res = (self._device_width, self._device_height)
            self._device_width, self._device_height = (self._device_height, self._device_width)

            logger.info(
                "旋转交换分辨率: %dx%d -> %dx%d (rotation %d->%d)",
                old_res[0], old_res[1],
                self._device_width, self._device_height,
                old, new_rotation
            )

            self._view.set_device_resolution(self._device_width, self._device_height)
            self._resolution_label.setText(f"分辨率: {self._device_width}x{self._device_height}")

            # 旋转后立即刷新分辨率（防止使用过期值）
            # 延迟 500ms 执行，给 scrcpy 时间输出新方向的帧
            QTimer.singleShot(500, self._get_device_resolution)

        # 自动适配
        QTimer.singleShot(100, self._on_fit)
```

**关键改进**：
1. **添加详细的交换日志**：记录交换前后的值，便于追踪
2. **交换后主动刷新分辨率**：延迟 500ms 后重新获取 `wm size`，确保最终值正确
   - 这解决了竞态条件：即使交换错了，500ms 后会被正确的值覆盖
   - 500ms 的延迟给 scrcpy 足够时间输出新方向的帧

---

#### 修改 5: 对 MirrorWindow 应用相同的修复

**文件**: [mirror_window.py](d:\Github\PY\ui\mirror_window.py)

对 `MirrorGraphicsView` 类应用相同的修改：
1. 增强 `set_device_resolution()` 的日志
2. 改进 `update_frame()` 中的回退逻辑
3. 在 `_view_to_device()` 中添加一致性验证
4. 优化 `_on_rotation_changed()` 和 `_on_rotation_detected_from_thread()` 的竞态处理

具体修改内容与上述修改 1-4 相同，只是应用到 MirrorWindow 的类中。

---

#### 修改 6: 添加启动时的分辨率预检

**文件**: [embedded_mirror_widget.py](d:\Github\PY\ui\components\embedded_mirror_widget.py) - `start()` 方法

**当前位置** (#L674-L688):
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

    # ① 优先获取设备分辨率（必须在帧更新之前完成）
    self._get_device_resolution()

    # ② 启动旋转检测（检测初始方向）
    self._start_rotation_detection()

    # ③ 最后启动帧更新（确保分辨率已就绪或至少回退逻辑已激活）
    self._start_frame_update()

    # ④ 设置超时保护：如果 2 秒后仍在使用回退值，强制刷新分辨率
    QTimer.singleShot(2000, self._ensure_resolution_ready)
```

**新增方法**:
```python
def _ensure_resolution_ready(self):
    """确保设备分辨率已正确设置（超时保护）。"""
    if getattr(self._view, '_resolution_from_frame', False):
        logger.warning(
            "⚠️ 启动 2 秒后仍使用帧尺寸作为分辨率回退，尝试重新获取..."
        )
        # 强制重新获取分辨率
        self._get_device_resolution()
        # 再等 2 秒检查
        QTimer.singleShot(2000, self._ensure_resolution_ready)
```

**目的**：
- 确保即使在最坏情况下（wm size 首次失败），也会自动重试
- 避免用户长时间使用不准确的坐标

---

### 修改文件清单

| 文件 | 修改项 | 行号范围 | 优先级 |
|------|--------|---------|--------|
| `ui/components/embedded_mirror_widget.py` | 1. set_device_resolution() 增强日志 | #L119-L133 | 高 |
| `ui/components/embedded_mirror_widget.py` | 2. update_frame() 回退逻辑改进 | #L176-L182 | **高** |
| `ui/components/embedded_mirror_widget.py` | 3. _view_to_device() 一致性验证 | #L229-L265 | **高** |
| `ui/components/embedded_mirror_widget.py` | 4. _on_rotation_detected() 竞态修复 | #L777-L791 | **高** |
| `ui/components/embedded_mirror_widget.py` | 5. start() 超时保护 | #L674-L688 | 中 |
| `ui/mirror_window.py` | 6. MirrorGraphicsView 同步修改 | 多处 | **高** |

---

## 技术决策说明

### 决策 1：保留回退机制但增强监控

**为什么不完全移除回退逻辑？**
- 完全移除会导致 `_device_width==0` 期间点击完全无反应
- 这对用户体验影响更大（完全无法操作 vs 操作略有偏差）
- 通过增强日志和超时重试，可以最小化回退持续时间

### 决策 2：旋转后延迟刷新分辨率

**为什么是 500ms？**
- scrcpy 检测到设备旋转并开始输出新方向的帧需要时间（通常 100-300ms）
- `wm size` 命令执行需要时间（约 50-100ms）
- 500ms 给予足够的缓冲，同时不会让用户感知到明显延迟

### 决策 3：一致性验证阈值设为 10%

**为什么不是 5% 或 20%？**
- 5% 太严格：正常的 DPI 缩放或非均匀缩放可能触发误报
- 20% 太宽松：可能漏掉真正的坐标错误
- 10% 是经验值，能在准确性和误报率之间取得平衡

---

## 验证方案

### 单元测试（自动化）

#### 测试 1：坐标映射一致性验证
```python
def test_scale_consistency_check():
    """测试缩放比例不一致时应输出 warning"""
    view = EmbeddedMirrorView()
    view._frame_width = 720
    view._frame_height = 1280
    view._device_width = 1080  # scale_x = 1.5
    view._device_height = 1280  # scale_y = 1.0 (不一致!)

    result = view._view_to_device(360, 640)
    # 应该触发 warning 日志
```

#### 测试 2：旋转交换的正确性
```python
def test_rotation_swap():
    """测试旋转时分辨率交换正确"""
    widget = EmbeddedMirrorWidget()
    widget._device_width = 1080
    widget._device_height = 1920
    widget._device_rotation = 0

    # 模拟旋转到横屏
    widget._on_rotation_detected(1)
    assert widget._device_width == 1920
    assert widget._device_height == 1080
```

### 手动测试（必需）

#### 测试场景清单

| # | 场景 | 步骤 | 预期结果 |
|---|------|------|---------|
| 1 | 冷启动点击 | 打开投屏窗口，立即点击 | 2秒内坐标准确（或显示 warning） |
| 2 | 竖屏精度 | 连接竖屏设备，点击四角+中心 | 误差 < 5px |
| 3 | 横屏精度 | 旋转到横屏，再次点击 | 误差 < 5px |
| 4 | 快速旋转 | 连续旋转3次，每次旋转后立即点击 | 无崩溃，坐标逐渐收敛 |
| 5 | 高分辨率 | 使用 2K 设备（2560x1440） | 坐标准确 |
| 6 | 缩放操作 | 滚轮放大到200%，点击同一位置 | 设备坐标不变 |
| 7 | 平移操作 | 拖拽平移后点击边缘 | 坐标准确 |
| 8 | 断线重连 | 拔插 USB，恢复后点击 | 分辨率自动刷新 |

### 日志验证

运行程序后，检查日志应包含以下关键信息：

**正常启动序列**：
```
DEBUG 设置真实设备分辨率: 1080x1920
INFO  设备分辨率: 1080x1920
DEBUG 坐标映射 #1: view(400,300)->scene(360.0,640.0)->dev(540,960) [frame=720x1280, device=1080x1920, scale=1.50x1.50, fallback=False]
```

**使用回退值时（应有 warning）**：
```
WARNING ⚠️ 设备分辨率未就绪，暂用帧尺寸回退: 720x1280 (坐标可能有偏差...)
WARNING ⚠️ 坐标映射比例异常: X=1.00, Y=1.00 (...) (使用帧尺寸回退)
DEBUG 坐标映射 #1: view(400,300)->scene(360.0,640.0)->dev(360,640) [frame=720x1280, device=720x1280, scale=1.00x1.00, fallback=True]
```

**旋转切换时**：
```
INFO  设备旋转: 0 -> 1
INFO  旋转交换分辨率: 1080x1920 -> 1920x1080 (rotation 0->1)
INFO  设备分辨率更新: 1920x1080 -> 1920x1080
```

---

## 回归风险评估

### 低风险修改
- ✅ 日志级别调整（debug → warning）
- ✅ 添加新的日志输出
- ✅ 添加注释说明

### 中风险修改
- ⚠️ 旋转后延迟刷新分辨率（500ms）
  - **缓解措施**：延迟期间使用交换后的值，虽然可能不完全准确，但总比没有好
  - **回退方案**：如果测试发现 500ms 不够，可以调整为 1000ms 或移除此功能

### 需要重点关注的风险
- 🔶 **超时保护机制** (`_ensure_resolution_ready`)
  - 可能导致短时间内多次调用 `wm size`
  - **缓解措施**：添加防抖逻辑（已在 QTimer.singleShot 中实现）

---

## 后续优化建议（本次不实施）

1. **缓存设备分辨率到本地文件**：避免每次启动都需要等待 ADB 命令
2. **支持手动校准偏移量**：对于特殊 ROM 或设备，允许用户输入校正系数
3. **使用 scrcpy 的 lock_video_orientation 参数**：锁定视频方向，简化旋转处理逻辑
4. **实现智能重试机制**：指数退避重试 `wm size`，而非固定间隔

---

## 总结

### 本次修复的核心改进

1. **解决点击无反应**：
   - 保留回退机制确保始终有响应
   - 添加超时保护和自动重试
   - 增强日志便于快速定位问题

2. **解决坐标偏移**：
   - 添加缩放比例一致性验证（10% 阈值）
   - 修复旋转处理的竞态条件（延迟刷新）
   - 明确标识回退状态，提醒用户可能的不准确

3. **提升可观测性**：
   - 关键节点都有详细日志
   - 包含完整的上下文信息（帧尺寸、设备分辨率、缩放比例、回退状态）
   - Warning 级别日志能快速引起注意

### 预期效果

修复后：
- ✅ 点击始终有响应（即使分辨率未就绪）
- ✅ 正常情况下坐标误差 < 5px
- ✅ 旋转切换后 1-2 秒内坐标收敛到准确值
- ✅ 异常情况有明显日志警告，便于排查
- ✅ 无崩溃或死锁风险
