# Checklist

- [x] `_scrcpy_read_loop()` 方法在 socket 接收、parse、decode、reformat、set_current_frame 各环节均有诊断日志
- [x] PyAV 解码器创建失败时有 ERROR 日志并正确返回
- [x] PyAV 解码器高级参数设置失败时不阻断核心解码功能
- [x] reformat 操作失败时记录 ERROR 日志并跳过该帧而非退出循环
- [x] 连接建立后 5 秒内未收到首帧时有 WARNING 告警日志
- [x] 异常处理日志级别从 DEBUG 提升到 WARNING，包含足够上下文信息
- [x] set_current_frame() 调用有异常保护，不会导致读取循环意外退出
- [x] scrcpy server 启动参数添加 `send_frame_meta=false`，禁用 12 字节帧头，使 socket 直接输出裸 H.264 流
- [ ] 实际设备测试确认高清投屏画面正常显示
