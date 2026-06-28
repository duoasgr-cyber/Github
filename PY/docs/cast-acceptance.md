# 投屏（屏幕捕获）验收标准（针对当前仓库实现）

当前仓库的"投屏"实现在 `core/screen_capture.py` 中，本质是通过 **scrcpy + PyAV** 获取设备画面，并在 scrcpy 不可用时回退到 **adb exec-out screencap**。以下验收标准用于验证主链路：**发现设备 -> 启动投屏 -> 持续取帧 -> 断连感知 -> 自动恢复**。

> **scrcpy 版本支持**: 2.x / 3.x / 4.0（自适应检测，默认兼容 4.0）
>
> **迁移状态**: 已完成 scrcpy 4.0 迁移（2026-06-21），详见 [`.trae/documents/scrcpy4-migration-plan.md`](../.trae/documents/scrcpy4-migration-plan.md)

## 一、功能主链路

1. **设备绑定可见**
- UI 能选择/绑定设备（`bound_device`），未绑定时禁止启动并给出提示。

2. **启动投屏**
- 调用 `ScrcpyCapture.start(device_serial, server_jar_path, max_retries)` 成功后可取到帧。
- 若 scrcpy 启动失败，应自动进入 screencap 回退，且 `is_connected()` 为 true。

3. **稳定取帧**
- `get_current_frame()` 在连接态可返回非空 `numpy.ndarray`；返回值是拷贝，外部修改不影响内部缓存。

4. **断连感知**
- socket/ffmpeg 管线异常时应 `emit connection_lost`；能通过日志看到断连原因。

5. **自动恢复**
- 能自动重连（最多 `max_retries` 次），恢复后 `emit connection_restored`；超过阈值后切回 screencap。

## 二、性能与质量指标（可分阶段）

- **首帧可用时间**：`start()` 返回后首次 `get_current_frame()` 可返回非空帧（建议不超过 2s，受设备/USB影响）。
- **卡顿**：UI 不因取帧线程阻塞；可记录丢帧/降频日志（screencap 模式下尤其明显）。
- **资源回收**：`stop()` 后 socket/ffmpeg/server_process 应释放，端口 forward 被清理。

## 三、兼容性与环境

- Windows：`subprocess` 需使用 `CREATE_NO_WINDOW`，避免弹窗（当前代码已处理）。
- PyAV 可用性：系统需安装 PyAV 库（`pip install av`），用于 H.264/H.265/AV1 解码；缺失时应有明确报错。
- scrcpy 版本：支持 **2.x / 3.x / 4.0** 自适应检测；默认兜底版本为 **4.0**。
- 多设备：使用 `adb -s {serial}` 指定设备，避免串台。
- Android 版本：scrcpy 4.0 要求 Android ≥ 7.0（推荐 ≥ 10）。

## 四、测试建议（可自动化）

- 单元测试（mock）：`_start_scrcpy` 失败 -> 进入回退；`stop()` 清理资源；`get_current_frame` 返回拷贝。
- 集成测试：绑定设备后执行一次 start/stop 循环；校验日志中出现"screencap回退模式启动/结束"或"自动重连成功"等关键字。

## 五、嵌入式投屏功能（v2.0 新增）

### 功能说明

从 v2.0 版本开始，投屏功能已集成到主界面的右侧区域（原"截图选择器"位置），无需再打开独立的投屏窗口。

### 主要特性

1. **实时投屏**
   - 设备选择后自动启动屏幕采集和投屏
   - 支持高清渲染（QGraphicsView）
   - 自动适配窗口大小

2. **坐标选择**
   - 左键点击添加坐标标记
   - 右键点击删除最后一个标记
   - 支持校准模式（显示网格）

3. **缩放控制**
   - 适配窗口：自动适配窗口大小
   - 1:1：原始分辨率显示
   - 重置：重置视图
   - 鼠标滚轮缩放

4. **设备旋转检测**
   - 自动检测设备旋转状态
   - 旋转时自动调整分辨率和视图

5. **连接状态显示**
   - 实时显示连接状态
   - 断开时显示红色提示
   - 连接时显示绿色提示

### 使用方法

1. 在侧边栏选择设备
2. 系统自动启动屏幕采集和投屏
3. 在投屏区域进行坐标选择
4. 坐标选择结果会自动同步到工作流编辑器

### 文件结构

```
ui/components/
├── embedded_mirror_widget.py  # 嵌入式投屏组件
├── screenshot_picker.py       # 截图选择器（已重构）
└── ...

ui/
├── main_window.py             # 主窗口（已修改）
└── mirror_window.py           # 独立投屏窗口（保留兼容性）
```

### 技术实现

- 使用 `QGraphicsView` 实现高清渲染
- 复用 `ScrcpyCapture` 的帧流
- 通过信号槽机制连接设备状态
- 使用定时器检测设备旋转
