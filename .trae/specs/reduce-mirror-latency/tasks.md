# Tasks

- [x] Task 1: 启用 PyAV 解码器低延迟标志
  - [x] SubTask 1.1: 在 `_scrcpy_read_loop()` 中 `CodecContext.create("h264", "r")` 之后设置 `codec.flags |= av.codec.Flags.LOW_DELAY`
  - [x] SubTask 1.2: 可选追加 `codec.flags2 |= av.codec.Flags2.FAST` 与 `codec.skip_loop_filter = "ALL"` 以降低 CPU 占用
  - [x] SubTask 1.3: 运行 `tests/test_screen_capture.py` 确认解码仍正常

- [x] Task 2: 调整 scrcpy server 启动参数
  - [x] SubTask 2.1: 将 `_start_server_process()` 中的 `max_fps=30` 改为 `max_fps=60`
  - [x] SubTask 2.2: 在 server 命令中追加 `video_codec_options=latency=1,priority=0`
  - [x] SubTask 2.3: 确认版本检测与 3.x 协议头部读取逻辑不受影响

- [x] Task 3: 缩短 UI 帧轮询间隔
  - [x] SubTask 3.1: 在 `EmbeddedMirrorWidget._start_frame_update()` 中将 `self._frame_timer.start(16)` 改为 `start(8)`

- [x] Task 4: 回归测试与验证
  - [x] SubTask 4.1: 运行 `pytest tests/test_screen_capture.py -v`
  - [x] SubTask 4.2: 检查 `tests/test_workflow_engine.py` 等可能调用 screen_capture 的测试是否通过
  - [x] SubTask 4.3: 手动验证 scrcpy 不可用时能正常回退到 screencap 模式

# Task Dependencies
- [Task 2] 与 [Task 3] 互相独立
- [Task 4] depends on [Task 1, Task 2, Task 3]
