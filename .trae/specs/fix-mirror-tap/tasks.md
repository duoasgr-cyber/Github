# Tasks

- [x] Task 1: 重写 `ScreenshotPicker._send_tap_async` 方法
  - [x] SubTask 1.1: 移除静默返回，在 `_device_serial` 或 `_adb_core` 为空时输出 WARNING 日志
  - [x] SubTask 1.2: 实现多方式 fallback 逻辑（参考 `MirrorWindow._try_input_tap`）：依次尝试 `input touchscreen tap` → `input tap` → `input motionevent DOWN/UP`
  - [x] SubTask 1.3: 使用 `self._adb_core.execute()` 执行命令（与现有代码风格一致），而非直接 subprocess
  - [x] SubTask 1.4: 添加 tap 结果日志（成功时 DEBUG + 方法名，失败时 WARNING + 原因）

- [x] Task 2: 验证并修复坐标转换逻辑
  - [x] SubTask 2.1: 审查 `EmbeddedMirrorView._view_to_device` 在各旋转模式（0°/90°/180°/270°）下的坐标映射正确性
  - [x] SubTask 2.2: 确认 `_on_rotation_detected` 中宽高交换后坐标转换仍然正确
  - [x] SubTask 2.3: 如有问题则修复坐标转换（经验证无需修复）

- [x] Task 3: 添加调试辅助 + 根因修复
  - [x] SubTask 3.1: 在 `_send_tap_async` 入口处添加 DEBUG 日志记录收到的原始坐标和当前设备信息
  - [x] SubTask 3.2: **根因修复**: `EmbeddedMirrorView.update_frame()` 首次收到帧时自动初始化 `_device_width/_device_height`
  - [x] SubTask 3.3: **根因修复**: `mousePressEvent` 添加防御性日志（点击被忽略时输出原因）
  - [x] SubTask 3.4: **根因修复**: `ScreenshotPicker._on_frame_captured()` 同步分辨率状态

# Task Dependencies
- [Task 2] independent — 可与 Task 1 并行
- [Task 3] independent — 可与 Task 1 并行
