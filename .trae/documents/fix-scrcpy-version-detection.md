# 修复 scrcpy 4.0 无法正常启动的问题

> **日期**: 2026-06-21
> **问题**: scrcpy 启动失败，回退到 screncap 模式，日志报版本不匹配错误

***

## 一、根因分析

### 错误链路（来自实际日志）

```
从 JAR 检测到 scrcpy server 版本: 9.1.31          ← ❌ 错误！检测到的是内部库版本
scrcpy 版本差距过大: client=3.3.4, server=9.1.31   ← ⚠️ client 也是错的
启动 scrcpy server (version=9.1.31, major=9)         ← 把 "9.1.31" 传给了 server
server ERROR: The server version (4.0) does not match the client (9.1.31)  ← server 拒绝！
```

### 两个 Bug

| Bug       | 位置                             | 现象                       | 根因                                                                                                                                |
| --------- | ------------------------------ | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| **Bug A** | `_detect_server_jar_version()` | 返回 `"9.1.31"` 而非 `"4.0"` | 正则 `\d+\.\d+\.\d+` 在 .dex 中匹配到了 AndroidX/Gradle 插件等第三方库版本号（如 `androidx.core:core:1.9.0` 中的数字），而非 scrcpy 自身版本                      |
| **Bug B** | `_detect_scrcpy_version()`     | 返回 `"3.3.4"` 而非 `"4.0"`  | `scrcpy --version` 命令命中了系统 PATH 上的旧版 `C:\ProgramData\chocolatey\bin\scrcpy.exe`（3.3.4），而非项目自带的 `lib/scrcpy-win64\scrcpy.exe`（4.0） |

### 关键约束（官方要求）

> **The first argument is the client scrcpy version. The server fails if the client and the server do not have the exact same version.**
>
> — [develop.md](https://github.com/Genymobile/scrcpy/blob/master/doc/develop.md)

Server JAR 实际是 **4.0**，但我们传了 `"9.1.31"` → 直接被拒绝。

***

## 二、修复方案

### 核心思路

**不再依赖不可靠的自动检测，改为基于已知部署版本的确定性策略。**

我们明确知道部署的 JAR 是 4.0 → 直接传 `"4.0"` 给 server。

### 修改文件：[screen\_capture.py](file:///d:/Github/PY/core/screen_capture.py)

#### 修改 1：修复 `_detect_server_jar_version()` — 增加 4.0 特定检测逻辑

**位置**: L90-L140

**改动**：

* 在 .dex 搜索中增加优先匹配 `"4.0"` 的逻辑

* 过滤掉明显不是 scrcpy 版本的号（如 > 5.0 的主版本或过于常见的库版本）

* 如果检测到不合理版本（如 "9.1.31"），返回 None 让调用方使用兜底值

```python
def _detect_server_jar_version(jar_path: str) -> Optional[str]:
    # ... 现有逻辑 ...

    # 新增：.dex 搜索时优先找 "4.x" 格式的短版本号（scrcpy 风格）
    # 并过滤掉明显是库版本的号（主版本 > 5 或常见库模式）
    _KNOWN_LIB_VERSION_PREFIXES = ("1.", "2.", "3.", "8.", "9.", "10.", "27.", "28.")
    for name in namelist:
        if name.endswith(".dex"):
            content = zf.read(name).decode("utf-8", errors="replace")
            matches = re.findall(r"\b(\d\.\d(?:\.\d)?)\b", content)
            for version in matches:
                major = int(version.split(".")[0])
                # scrcpy 版本特征：主版本 2-5，且格式简洁
                if 2 <= major <= 5:
                    logger.debug("从 dex 文件 %s 检测到可能的 scrcpy 版本: %s", name, version)
                    return version
    return None
```

#### 修改 2：修复 `_detect_scrcpy_version()` — 优先使用捆绑的 scrcpy 客户端

**位置**: L59-L87

**改动**：

* 先尝试项目自带的 `lib/scrcpy-win64/scrcpy.exe --version`

* 再尝试系统 PATH 的 `scrcpy --version`

* 兜底仍为 `"4.0"`

```python
def _detect_scrcpy_version() -> str:
    # 按优先级尝试多个 scrcpy 客户端路径
    candidates = [
        os.path.join(_PROJECT_ROOT, "lib", "scrcpy-win64", "scrcpy.exe"),  # 项目自带（首选）
        "scrcpy",  # 系统 PATH
    ]
    for exe_path in candidates:
        try:
            result = subprocess.run(
                [exe_path, "--version"],
                capture_output=True, text=True, timeout=5,
                creationflags=_NO_WINDOW, startupinfo=_STARTUPINFO,
            )
            if result.returncode == 0 and result.stdout:
                ver = result.stdout.split()[1]
                if ver[0].isdigit():
                    logger.debug("检测到 scrcpy 客户端版本 (%s): %s", exe_path, ver)
                    return ver
        except Exception:
            continue
    return "4.0"
```

#### 修改 3（关键）：在 `_try_start_scrcpy()` 中增加版本合理性校验

**位置**: \~L376-L387

**改动**：当 JAR 检测到的版本不合理时（major > 5），强制使用客户端版本或硬编码兜底。

```python
# 0. 检测 server 版本
server_version = _detect_server_jar_version(self._server_jar)
if server_version:
    major = _parse_major_version(server_version)
    # 合理性校验：scrcpy 主版本应在 2-5 范围内
    # 若超出则说明检测到的是库版本而非 scrcpy 版本
    if major > 5:
        logger.warning(
            "JAR 版本检测结果异常 (%s, major=%d)，可能是库版本号，将忽略",
            server_version, major,
        )
        server_version = None  # 强制走 fallback

if server_version:
    logger.info("从 JAR 检测到 scrcpy server 版本: %s", server_version)
else:
    # 兜底：使用客户端版本（因为我们部署的就是同版本）
    server_version = _get_scrcpy_version()
    logger.info("JAR 版本检测未果，使用客户端版本作为 server 版本: %s", server_version)
```

***

## 三、验证方法

### 单元测试

```bash
cd d:/Github/PY
python -m pytest tests/test_screen_capture.py tests/test_performance_benchmark.py -v --tb=short
```

预期：45 测试全部通过

### 功能验证（连接设备）

预期日志变化：

```
# 修复前（错误）❌
从 JAR 检测到 scrcpy server 版本: 9.1.31
client=3.3.4 (major=3), server=9.1.31 (major=9)
启动 scrcpy server (version=9.1.31, major=9)
ERROR: server version (4.0) does not match the client (9.1.31)
→ 回退 screncap

# 修复后（正确）✅
从 JAR 检测到 scrcpy server 版本: 4.0       ← 或使用客户端版本 4.0
启动 scrcpy server (version=4.0, major=4)
scrcpy 4.x 协议: 设备=xxx, codec=0x68323634, 分辨率=xxx
→ 正常投屏 🎉
```

***

## 四、涉及文件

| 文件                                                                     | 改动量   | 说明                   |
| ---------------------------------------------------------------------- | ----- | -------------------- |
| [core/screen\_capture.py](file:///d:/Github/PY/core/screen_capture.py) | 3 处修改 | Bug A + Bug B + 校验逻辑 |
| 无需新增文件                                                                 | -     | -                    |
| 无需替换资源                                                                 | -     | JAR 已是 4.0，无需再换      |

