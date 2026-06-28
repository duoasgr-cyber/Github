# Tasks

- [x] Task 1: 实现 ffmpeg 硬件解码自动检测方法
  - [x] SubTask 1.1: 在 `screen_capture.py` 中新增 `_detect_hw_accel()` 方法，依次检测 CUDA、DXVA2、QSV 可用性
  - [x] SubTask 1.2: 检测逻辑：执行 `ffmpeg -hwaccels` 解析输出，再通过试启动验证实际可用性
  - [x] SubTask 1.3: 返回检测到的最优 hwaccel 方案名称（`cuda`/`dxva2`/`qsv`/`None`），缓存结果避免重复检测

- [x] Task 2: 改造 `_start_ffmpeg()` 使用硬件解码 + 低延迟参数
  - [x] SubTask 2.1: 调用 `_detect_hw_accel()` 获取可用方案
  - [x] SubTask 2.2: 根据 hwaccel 方案构建不同的 ffmpeg 命令参数（CUDA 用 `-hwaccel cuda -c:v h264_cuvid`，DXVA2 用 `-hwaccel dxva2`，QSV 用 `-hwaccel qsv`，None 不加 hwaccel 参数）
  - [x] SubTask 2.3: 在所有方案中统一加入低延迟参数：`-fflags nobuffer -flags low_delay -probesize 32 -analyzeduration 0`
  - [x] SubTask 2.4: 硬件解码时 ffmpeg 输出仍为 rawvideo rgb24（硬件解码后自动回传 CPU 内存），保持下游逻辑不变

- [x] Task 3: 实现跳过过期帧逻辑
  - [x] SubTask 3.1: 在 `_scrcpy_read_loop()` 中，读取到新帧后先检查是否有更多帧可读（Windows 用 PeekNamedPipe，其他平台用 select）
  - [x] SubTask 3.2: 如果有堆积帧，循环读取并丢弃，只保留最后一帧
  - [x] SubTask 3.3: 对最后一帧调用 `set_current_frame()` 传递给 UI

- [x] Task 4: 优化 scrcpy server 启动参数
  - [x] SubTask 4.1: 在 `_start_server_process()` 的命令参数中增加 `video_bit_rate=8000000`

- [x] Task 5: 优化 `MirrorGraphicsView.update_frame()` 渲染路径
  - [x] SubTask 5.1: ffmpeg 输出 pix_fmt 改为 `rgb24`，移除 `rgbSwapped()` 调用
  - [x] SubTask 5.2: 更新相关注释和文档字符串

- [ ] Task 6: 集成测试与验证
  - [ ] SubTask 6.1: 连接 Android 设备，启动投屏，观察日志确认硬件解码是否生效
  - [ ] SubTask 6.2: 对比优化前后 CPU 占用和帧率表现
  - [ ] SubTask 6.3: 验证无硬件加速时回退到软解码正常工作

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 3] independent
- [Task 4] independent
- [Task 5] independent
- [Task 6] depends on [Task 1, Task 2, Task 3, Task 4, Task 5]
