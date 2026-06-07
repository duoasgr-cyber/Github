# 投屏（屏幕捕获）验收标准（针对当前仓库实现）

当前仓库的“投屏”实现在 `core/screen_capture.py` 中，本质是通过 **scrcpy + ffmpeg** 获取设备画面，并在 scrcpy 不可用时回退到 **adb exec-out screencap**。以下验收标准用于验证主链路：**发现设备 -> 启动投屏 -> 持续取帧 -> 断连感知 -> 自动恢复**。

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
- ffmpeg 可用性：系统 PATH 内存在 ffmpeg；缺失时应有明确报错。
- 多设备：使用 `adb -s {serial}` 指定设备，避免串台。

## 四、测试建议（可自动化）

- 单元测试（mock）：`_start_scrcpy` 失败 -> 进入回退；`stop()` 清理资源；`get_current_frame` 返回拷贝。
- 集成测试：绑定设备后执行一次 start/stop 循环；校验日志中出现“screencap回退模式启动/结束”或“自动重连成功”等关键字。
