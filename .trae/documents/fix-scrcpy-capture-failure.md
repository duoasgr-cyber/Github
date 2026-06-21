# 修复 scrcpy 模式启动失败问题

## 问题摘要

运行时出现 `读取 scrcpy 设备名失败` 错误，导致 scrcpy 模式无法启动，回退到 screencap 模式。

## 根因分析

错误发生在 `screen_capture.py:414`，`_read_exact(socket, 64)` 返回 `None`。完整链路：

1. `_try_start_scrcpy()` 推送 JAR → 设置端口转发 → 启动 server 进程 ✅
2. `_connect_socket()` 连接成功 ✅
3. 读取 dummy byte (1字节) ✅
4. **读取设备名 (64字节) 失败** ❌ — `sock.recv()` 返回空字节（server 关闭连接）

### 根本原因：scrcpy 版本/协议不匹配

代码存在两个关键缺陷：

**缺陷1：版本检测不可靠**（[screen_capture.py:74-97](file:///d:/Github/PY/core/screen_capture.py#L74-L97)）
- `_detect_scrcpy_version()` 依赖 `scrcpy --version` 命令
- 如果系统未安装 scrcpy 客户端，回退到硬编码 `"2.0"`
- 但实际 `lib/scrcpy-server.jar` 可能是 3.x 版本
- 版本字符串作为第一个参数传给 server：`app_process / com.genymobile.scrcpy.Server {version}`
- **版本不匹配时 server 可能拒绝连接或立即退出**

**缺陷2：协议解析只支持 3.x**（[screen_capture.py:401-448](file:///d:/Github/PY/core/screen_capture.py#L401-L448)）
- 代码注释明确写着"适配 scrcpy 3.x 协议"
- 协议格式：`[1 byte dummy] [64 bytes device name] [4 bytes codec] [4 bytes width] [4 bytes height]`
- scrcpy 2.x 协议格式不同：`[1 byte dummy] [64 bytes device name] [4 bytes width] [4 bytes height]`（无 codec 字段）
- 没有任何版本分支逻辑，2.x server 发来的数据会被错误解析

**缺陷3：握手阶段 socket 无超时保护**（[screen_capture.py:447](file:///d:/Github/PY/core/screen_capture.py#L447)）
- 连接成功后 `sock.settimeout(None)` 设为阻塞模式
- `_read_exact` 依赖 `self._running` 检查来退出，但如果 server 既不发送数据也不关闭连接，会无限阻塞

**缺陷4：错误诊断不足**
- `_read_exact` 返回 None 时不区分 EOF / timeout / stopped
- server 进程 stderr 未在握手失败时读取和记录

## 修复方案

### 修改文件：`d:\Github\PY\core\screen_capture.py`

### 改动1：从 JAR 文件检测 server 版本

替换 `_detect_scrcpy_version()` 函数，优先从 JAR 文件内部提取版本号，而非依赖 scrcpy 客户端：

```python
def _detect_server_jar_version(jar_path: str) -> Optional[str]:
    """从 scrcpy-server.jar 内部提取版本号。

    scrcpy server JAR 内含 META-INF/MANIFEST.MF 或
    res/version 文件，包含版本信息。
    使用 Python zipfile 模块读取，无需外部依赖。
    """
    try:
        import zipfile
        with zipfile.ZipFile(jar_path, 'r') as zf:
            # 尝试读取 MANIFEST.MF
            for name in zf.namelist():
                if name.endswith('MANIFEST.MF'):
                    content = zf.read(name).decode('utf-8', errors='replace')
                    for line in content.splitlines():
                        if 'Implementation-Version' in line or 'Bundle-Version' in line:
                            version = line.split(':')[-1].strip()
                            if version and version[0].isdigit():
                                return version
            # 尝试读取 version 资源文件
            for name in zf.namelist():
                if 'version' in name.lower() and not name.endswith('/'):
                    content = zf.read(name).decode('utf-8', errors='replace').strip()
                    if content and content[0].isdigit():
                        return content
    except Exception as e:
        logger.debug("从 JAR 检测版本失败: %s", e)
    return None
```

修改 `_try_start_scrcpy` 中的版本获取逻辑：
- 优先从 JAR 文件提取版本
- 其次尝试 `scrcpy --version`
- 最后回退到 `"2.0"`

### 改动2：自适应协议解析（兼容 2.x 和 3.x）

将协议头部解析改为自适应模式，根据版本号或数据特征判断协议版本：

```python
def _read_scrcpy_header(self, sock, server_version):
    """自适应读取 scrcpy 协议头部，兼容 2.x 和 3.x。"""

    # 1. 读取 dummy byte
    dummy = self._read_exact(sock, 1)
    if dummy is None:
        return False

    # 2. 读取 64 字节设备名
    device_name_bytes = self._read_exact(sock, 64)
    if device_name_bytes is None:
        return False

    # 3. 根据版本判断是否有 codec 字段
    major_version = self._parse_major_version(server_version)
    if major_version >= 3:
        # 3.x: [codec_id(4)] [width(4)] [height(4)]
        codec_id_bytes = self._read_exact(sock, 4)
        if codec_id_bytes is None:
            return False
        size_bytes = self._read_exact(sock, 8)
        if size_bytes is None:
            return False
        self._frame_width = struct.unpack('>I', size_bytes[0:4])[0]
        self._frame_height = struct.unpack('>I', size_bytes[4:8])[0]
    else:
        # 2.x: [width(4)] [height(4)]
        size_bytes = self._read_exact(sock, 8)
        if size_bytes is None:
            return False
        self._frame_width = struct.unpack('>I', size_bytes[0:4])[0]
        self._frame_height = struct.unpack('>I', size_bytes[4:8])[0]

    return True
```

### 改动3：握手阶段添加 socket 超时

在 `_connect_socket` 返回后、开始读取协议头部之前，设置合理的 socket 超时：

```python
# 连接成功后设置握手超时（而非无限阻塞）
sock.settimeout(_SCRCPY_SOCKET_TIMEOUT)  # 5秒
```

在 `_read_exact` 中增加超时后的重试或更详细的错误日志。

### 改动4：增强错误诊断

1. `_read_exact` 增加失败原因区分（EOF / timeout / stopped）
2. 握手失败时读取并记录 server 进程的 stderr
3. 日志中输出检测到的版本号和使用的协议模式

```python
def _read_exact(self, sock, n):
    buf = bytearray()
    while len(buf) < n:
        if not self._running:
            logger.debug("_read_exact: 采集已停止 (已读 %d/%d 字节)", len(buf), n)
            return None
        try:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                logger.debug("_read_exact: 连接已关闭 (已读 %d/%d 字节)", len(buf), n)
                return None
            buf.extend(chunk)
        except socket.timeout:
            logger.debug("_read_exact: 读取超时 (已读 %d/%d 字节)", len(buf), n)
            return None
        except OSError as e:
            logger.debug("_read_exact: socket 错误 %s (已读 %d/%d 字节)", e, len(buf), n)
            return None
    return bytes(buf)
```

### 改动5：server 启动后检查 stderr

在 `_start_server_process` 中，启动后增加 stderr 非阻塞读取，检测版本不匹配等错误：

```python
# 启动后短暂等待，检查是否有立即错误
time.sleep(0.5)
if self._server_process.poll() is not None:
    # server 已退出，读取 stderr
    ...
else:
    # server 仍在运行，尝试非阻塞读取 stderr 中的警告
    try:
        self._server_process.stderr.read1(4096)  # 非阻塞读取
    except Exception:
        pass
```

## 实施步骤

1. 修改 `_detect_scrcpy_version` → 增加 JAR 版本检测
2. 新增 `_parse_major_version` 辅助函数
3. 新增 `_read_scrcpy_header` 自适应协议解析方法
4. 修改 `_try_start_scrcpy` 使用新的版本检测和协议解析
5. 修改 `_connect_socket` 返回前设置握手超时
6. 增强 `_read_exact` 错误诊断日志
7. 在握手失败时读取 server stderr

## 验证步骤

1. 确认 `lib/scrcpy-server.jar` 存在且版本可被检测
2. 运行程序，观察日志中的版本检测和协议选择信息
3. 验证 scrcpy 模式能正常启动并取帧
4. 模拟版本不匹配场景，确认自适应协议解析能正确回退
5. 运行现有单元测试确保无回归
