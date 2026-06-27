# 彻底移除帧尺寸回退机制

## 问题

即使添加了同步获取方法，日志仍然显示：
```
⚠️ 设备分辨率未就绪，暂用帧尺寸回退: 576x1280
```

**根本原因**：`update_frame()` 中的回退逻辑仍在第一帧到达时触发。

## 解决方案：完全移除回退逻辑

### 核心思路

**如果分辨率未就绪，就不设置任何值，宁可点击无效也不使用错误坐标**

---

## 具体修改

### 修改 1: 移除 EmbeddedMirrorView.update_frame() 中的回退逻辑

**文件**: [embedded_mirror_widget.py#L191-202](d:\Github\PY\ui\components\embedded_mirror_widget.py#L191-L202)

**当前代码**:
```python
# 当外部尚未提供真实分辨率时，用帧尺寸作为临时回退，保证点击有响应。
if self._device_width == 0 and w > 0 and h > 0:
    self._device_width = w
    self._device_height = h
    self._resolution_from_frame = True
    logger.warning("⚠️ 设备分辨率未就绪，暂用帧尺寸回退: %dx%d ...", w, h)
```

**修改为**:
```python
# 不再使用帧尺寸作为回退值（会导致坐标不准确）
# 分辨率必须由外部通过 set_device_resolution() 设置正确的物理分辨率
# 如果 _device_width == 0，点击将被忽略（返回 (0,0)），这是预期行为
```

即：**删除这整个 if 块**

---

### 修改 2: 移除 MirrorGraphicsView.update_frame() 中的回退逻辑

**文件**: [mirror_window.py](d:\Github\PY\ui\mirror_window.py) （同样的位置）

同样删除回退逻辑。

---

### 修改 3: 确保 start() 中的同步获取是唯一设置分辨率的途径

**当前的 start() 已经正确**：
1. 先同步获取（阻塞 ≤3秒）
2. 成功 → 使用精确值
3. 失败 + 估算成功 → 使用估算值（标记为"估算"）
4. 失败 + 估算失败 → **不设置任何值，_device_width 保持为 0**
5. 然后才启动帧更新

此时 `update_frame()` 不会再覆盖为帧尺寸。

---

### 修改 4: 改进 _view_to_device() 当分辨率为0时的行为

当 `_device_width == 0` 时，当前返回 `(0,0)` 并静默忽略。

可以改进为输出一次提示日志（仅首次）：

```python
def _view_to_device(self, view_x, view_y):
    if self._pixmap_item is None or self._device_width == 0:
        # 分辨率未就绪时，输出一次提示（避免刷屏）
        if not hasattr(self, '_resolution_warned'):
            self._resolution_warned = True
            logger.warning(
                "⚠️ 点击被忽略: 设备分辨率尚未设置 "
                "(start() 中的同步获取可能失败)"
            )
        return (0, 0)
    # ... 正常映射逻辑
```

---

## 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| `ui/components/embedded_mirror_widget.py` | 删除 update_frame() 中的回退逻辑（6行） |
| `ui/components/embedded_mirror_widget.py` | 改进 _view_to_device() 的提示信息 |
| `ui/mirror_window.py` | 删除 MirrorGraphicsView.update_frame() 中的回退逻辑 |

---

## 预期效果

### 场景 1：同步获取成功（正常情况）
```
[INFO] 设备分辨率: 1080x1920 (来源: sync/wm size)
[启动帧更新]
[第一帧到达] → _device_width=1080 ✅ 不触发回退
[点击] → 坐标准确 ✅
```

### 场景 2：同步获取失败，估算成功
```
[WARNING] ⚠️ 同步获取超时...
[WARNING] ⚠️ 使用估算分辨率: 1080x1920
[启动帧更新]
[第一帧到达] → _device_width=1080 ✅ 不触发回退（已设置估算值）
[点击] → 坐标基本准确（误差取决于估算精度）
```

### 场景 3：完全失败（极端情况）
```
[ERROR] ❌ 无法获取也无法估算分辨率！
[启动帧更新]
[第一帧到达] → _device_width=0 ✅ 不设置回退值
[点击] → ⚠️ 点击被忽略: 设备分辨率尚未设置 (仅提示一次)
[后续] 异步重试可能成功后恢复
```

**关键改变**：不再有 "暂用帧尺寸回退: 576x1280" 的误导性日志！

---

## 风险说明

### 如果分辨率获取失败：
- **之前的行为**：使用错误的坐标（576x1280 而非 1080x1920），点击偏移约33%
- **之后的行为**：点击被完全忽略（返回 (0,0)），但至少不会误导用户

**权衡**：宁可不工作，也不给出错误的结果

---

## 验证步骤

1. 启动投屏
2. 观察日志：
   - 应该看到 `设备分辨率: 1080x1920 (来源: sync/...)`
   - **不应该**看到 `暂用帧尺寸回退`
3. 测试点击：应该准确或被明确告知不可用
