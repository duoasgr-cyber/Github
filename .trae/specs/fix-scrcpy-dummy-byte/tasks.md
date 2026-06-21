# Tasks

- [x] Task 1: 改进 JAR 版本检测，增加 classes.dex 字符串搜索
  - [x] SubTask 1.1: 在 `_detect_server_jar_version()` 中增加第三级回退：从 JAR 内 `classes.dex` 的二进制数据中搜索语义化版本号模式（`\d+\.\d+\.\d+`）
  - [x] SubTask 1.2: 搜索策略：遍历 JAR 内所有 `.dex` 文件，读取其二进制内容，用正则搜索版本号字符串
  - [x] SubTask 1.3: 版本号验证：匹配到的版本号应为主版本 >= 2，取最后一个匹配结果（通常为实际版本）

- [x] Task 2: dummy byte 读取失败时记录 server stderr
  - [x] SubTask 2.1: 在 `_read_scrcpy_header()` 中 dummy byte 读取失败时，先调用 `self._log_server_stderr()` 再返回 False

- [x] Task 3: adb forward 端口清理
  - [x] SubTask 3.1: 在 `_setup_adb_forward()` 开头增加 `adb forward --remove tcp:<port>` 清理旧转发
  - [x] SubTask 3.2: 清理失败不阻断流程（仅记录 debug 日志），继续设置新转发

- [x] Task 4: screencap 回退模式帧率提示
  - [x] SubTask 4.1: 在 `_capture_loop()` 中进入 screencap 回退时，增加 WARNING 日志提示当前为低帧率模式

- [x] Task 5: JAR 版本检测失败时增加 WARNING 日志
  - [x] SubTask 5.1: 当所有版本检测方式均失败、回退到使用客户端版本时，将日志级别从 INFO 改为 WARNING，并提示版本可能不匹配

# Task Dependencies
- [Task 2] independent
- [Task 3] independent
- [Task 4] independent
- [Task 5] depends on [Task 1]
