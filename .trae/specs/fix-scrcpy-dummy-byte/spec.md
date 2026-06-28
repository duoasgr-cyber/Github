# 修复 scrcpy 启动失败回退 screencap 导致投屏卡顿 Spec

## Why
scrcpy 模式启动时读取 dummy byte 失败，导致回退到 screencap 截图模式（最多 5fps），投屏严重卡顿。根本原因是 JAR 版本检测失败后使用了不匹配的版本号传给 server，以及 dummy byte 读取失败时缺少足够的诊断信息，无法定位具体原因。

## What Changes
- 改进 JAR 版本检测：从 JAR 内的 `classes.dex` 中提取版本号（当前 MANIFEST.MF 和资源文件方式对 scrcpy server JAR 无效）
- dummy byte 读取失败时自动记录 server stderr 输出
- 增加 server 启动后的就绪等待机制（当前仅等 0.5s，server 可能尚未就绪）
- 增加 adb forward 端口清理（启动前先移除旧转发，避免端口冲突）
- 在 screencap 回退模式下增加帧率提示日志，告知用户当前为低帧率模式

## Impact
- Affected code: `PY/core/screen_capture.py`
- Affected behavior: scrcpy 启动成功率提升，减少不必要的 screencap 回退；回退时用户能从日志中了解原因

## ADDED Requirements

### Requirement: JAR 版本号可靠检测
系统 SHALL 能够从 scrcpy-server.jar 中可靠提取版本号。当 MANIFEST.MF 和资源文件方式均失败时，SHALL 尝试从 JAR 内 `classes.dex` 的字符串常量中搜索版本号模式。

#### Scenario: MANIFEST.MF 无版本信息
- **WHEN** JAR 的 MANIFEST.MF 中不包含 Implementation-Version 或 Bundle-Version
- **THEN** 系统尝试从 `classes.dex` 中搜索语义化版本号模式（如 `3.3.4`）

#### Scenario: 所有检测方式均失败
- **WHEN** 无法从 JAR 中提取任何版本号
- **THEN** 使用 scrcpy 客户端版本号，并记录 WARNING 日志提示版本可能不匹配

### Requirement: dummy byte 读取失败时记录 server stderr
系统 SHALL 在 `_read_scrcpy_header()` 读取 dummy byte 失败时，自动调用 `_log_server_stderr()` 记录 server 进程的错误输出，便于诊断。

#### Scenario: dummy byte 读取失败
- **WHEN** `_read_exact(sock, 1)` 返回 None
- **THEN** 在记录错误日志之前，先调用 `_log_server_stderr()` 输出 server 的 stderr

### Requirement: server 启动就绪等待优化
系统 SHALL 在启动 server 进程后，等待 server 就绪再尝试 socket 连接。当前固定 0.5s 等待不够可靠，SHALL 改为在 socket 连接阶段使用重试机制（已有 `_connect_socket` 的 3s 超时重试），并适当增加 server 进程启动后的初始等待时间。

#### Scenario: server 启动较慢
- **WHEN** server 进程启动后需要超过 0.5s 才就绪
- **THEN** `_connect_socket()` 的重试机制能在 3s 超时内成功连接

### Requirement: adb forward 端口清理
系统 SHALL 在设置新的 adb forward 之前，先移除设备上旧的 scrcpy 端口转发，避免残留转发导致连接异常。

#### Scenario: 存在旧的端口转发
- **WHEN** 系统启动 scrcpy 并设置端口转发
- **THEN** 先执行 `adb forward --remove tcp:<port>` 清理旧转发，再设置新转发

### Requirement: screencap 回退模式帧率提示
系统 SHALL 在进入 screencap 回退模式时，记录 WARNING 日志明确告知当前为低帧率模式及原因，帮助用户理解卡顿原因。

#### Scenario: 回退到 screencap 模式
- **WHEN** scrcpy 启动失败，系统回退到 screencap 模式
- **THEN** 记录 WARNING 日志，包含"当前为低帧率截图模式（约 5fps），投屏可能卡顿"的提示

## MODIFIED Requirements

### Requirement: `_detect_server_jar_version` 版本检测
原实现仅从 MANIFEST.MF 和资源文件中提取版本号，对 scrcpy-server.jar 无效。修改为增加 `classes.dex` 字符串搜索作为第三级回退。

## REMOVED Requirements
无移除项。
