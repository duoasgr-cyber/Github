# Tasks

- [x] Task 1: 在 `_scrcpy_read_loop()` 中增加详细的诊断日志
  - [x] SubTask 1.1: 在 socket 数据接收处增加日志（记录接收数据大小，首次和每 100 帧记录一次）
  - [x] SubTask 1.2: 在 `codec.parse()` 调用后增加日志（记录解析出的 packet 数量）
  - [x] SubTask 1.3: 在 `codec.decode()` 调用后增加日志（记录解码出的帧数量）
  - [x] SubTask 1.4: 在 `reformat().to_ndarray()` 处增加首帧 shape/dtype 日志
  - [x] SubTask 1.5: 在 `set_current_frame()` 处增加首帧成功缓存日志

- [x] Task 2: 增强 PyAV 解码器错误处理健壮性
  - [x] SubTask 2.1: 在 `CodecContext.create()` 外层增加 try-except，失败时记录 ERROR 并返回
  - [x] SubTask 2.2: 将解码器参数设置（flags、flags2、skip_loop_filter）分别包裹 try-except，失败时 WARNING 但不阻断
  - [x] SubTask 2.3: 在 `reformat()` 操作外层增加 try-except，失败时记录 ERROR 并跳过该帧

- [x] Task 3: 实现连接建立后的首帧超时告警机制
  - [x] SubTask 3.1: 在 `_scrcpy_read_loop()` 入口记录开始时间
  - [x] SubTask 3.2: 在主循环中检查距离开始时间是否超过 5 秒且未收到首帧
  - [x] SubTask 3.3: 如果超时未收到首帧，记录 WARNING 日志提示检查解码链路

- [x] Task 4: 改进异常处理日志级别和上下文信息
  - [x] SubTask 4.1: 将 `_scrcpy_read_loop` 中 `except Exception as e` 的日志级别从 DEBUG 改为 WARNING
  - [x] SubTask 4.2: 在异常日志中增加上下文信息：接收次数、解码帧数、运行时长等
  - [x] SubTask 4.3: 在 `set_current_frame()` 调用处增加 try-except，防止帧缓存异常导致循环退出

- [ ] Task 5: 实际设备测试验证
  - [ ] SubTask 5.1: 连接 Android 设备启动高清投屏
  - [ ] SubTask 5.2: 观察新增的诊断日志输出，定位问题环节
  - [ ] SubTask 5.3: 根据日志定位结果进行针对性修复（可能需要额外任务）
  - [ ] SubTask 5.4: 验证修复后画面正常显示

# Task Dependencies
- [Task 2] independent
- [Task 3] independent
- [Task 4] independent
- [Task 5] depends on [Task 1, Task 2, Task 3, Task 4]
