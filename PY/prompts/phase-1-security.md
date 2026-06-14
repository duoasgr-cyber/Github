# 第一阶段：安全加固 — 实现提示词

> 执行环境：项目根目录 `PY/`，Python 3.10+，所有路径相对于 `PY/`。

## 目标

消除 ADB 命令注入漏洞，将所有 `shell=True` 调用改为参数列表形式（`shell=False`），并扩展注入防护到所有 step handler。

---

## 任务 1：重构 `core/adb_core.py` — 消除 shell 注入

### 背景

`AdbCore.execute()`（第 25-54 行）当前使用 f-string 拼接命令字符串 + `shell=True`：

```python
full_cmd = f"adb -s {serial} {command}"
result = subprocess.run(full_cmd, ..., shell=True)
```

所有公开方法（`tap`, `swipe`, `keyevent`, `input_text`, `screenshot`, `pull_file`, `push_file`, `delete_file`, `shell`, `force_stop`, `launch`, `get_device_list`, `get_device_resolution`）都通过 `self.execute(f"shell ...")` 调用，参数直接注入 shell。

### 要求

**1.1 改造 `execute()` 方法签名**

```python
def execute(self, args: list[str], timeout: float = 30.0, device: str = None) -> subprocess.CompletedProcess:
    """args 为 ADB 子命令列表，如 ["shell", "input", "tap", "100", "200"]"""
    serial = device or self._device
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(args)
    
    logger.debug("执行命令: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False  # 关键：禁止 shell 解释
        )
        # ... 保持原有的 returncode 检查和异常处理逻辑不变 ...
```

**1.2 逐个改造所有公开方法**，将 f-string 调用改为列表参数：

| 方法 | 当前调用 | 改为 |
|------|---------|------|
| `tap(x, y)` | `f"shell input tap {x} {y}"` | `["shell", "input", "tap", str(x), str(y)]` |
| `long_press(x, y, duration)` | `f"shell input swipe {x} {y} {x} {y} {int(duration)}"` | `["shell", "input", "swipe", str(x), str(y), str(x), str(y), str(int(duration))]` |
| `swipe(x1, y1, x2, y2, duration)` | `f"shell input swipe ..."` | `["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(int(duration))]` |
| `keyevent(key)` | `f"shell input keyevent {key}"` | `["shell", "input", "keyevent", str(key)]` |
| `input_text(text)` | `f"shell input text {text}"` | `["shell", "input", "text", str(text)]` |
| `screenshot(path)` | `f"shell screencap -p {path}"` | `["shell", "screencap", "-p", str(path)]` |
| `pull_file(remote, local)` | `f"pull {remote} {local}"` | `["pull", str(remote), str(local)]` |
| `push_file(local, remote)` | `f"push {local} {remote}"` | `["push", str(local), str(remote)]` |
| `delete_file(path)` | `f"shell rm {path}"` | `["shell", "rm", str(path)]` |
| `shell(cmd)` | `f"shell {cmd}"` | ⚠️ **见下方特殊处理** |
| `force_stop(package)` | `f"shell am force-stop {package}"` | `["shell", "am", "force-stop", str(package)]` |
| `launch(package)` | `f"shell monkey -p {package} ..."` | `["shell", "monkey", "-p", str(package), "-c", "android.intent.category.LAUNCHER", "1"]` |
| `get_device_list()` | `"devices"` | `["devices"]` |
| `get_device_resolution()` | `"shell wm size"` | `["shell", "wm", "size"]` |

**1.3 特殊处理 `shell()` 方法**

`shell()` 方法接收用户传入的原始 shell 命令字符串，需要拆分但不能用 shell 解释器：

```python
def shell(self, cmd: str, device: str = None, timeout: float = 30.0) -> str:
    """执行 shell 命令。cmd 会被 shlex.split() 拆分为参数列表。"""
    import shlex
    try:
        args = ["shell"] + shlex.split(cmd)
        result = self.execute(args, timeout=timeout, device=device)
        return result.stdout.strip()
    except ValueError as e:
        logger.error("Shell命令解析失败: %s - %s", cmd, e)
        return ""
    except AdbError:
        logger.error("Shell命令失败: %s", cmd)
        return ""
```

**1.4 添加输入验证工具函数**（文件顶部，import 区域之后）

```python
import shlex

# 允许的包名字符（Android 包名规范）
_PACKAGE_PATTERN = re.compile(r'^[a-zA-Z0-9._]+$')
# 允许的 ADB keyevent 名称/数字
_KEYEVENT_PATTERN = re.compile(r'^[a-zA-Z0-9_]+$')
# 文件路径中禁止的 shell 元字符
_SHELL_META_PATTERN = re.compile(r'[;&|$(){}!#`\\]')

def _validate_package(package: str) -> bool:
    """验证 Android 包名是否安全。"""
    if not package or not _PACKAGE_PATTERN.match(package):
        logger.error("非法包名: %s", package)
        return False
    return True

def _validate_keyevent(key: str) -> bool:
    """验证 keyevent 名称是否安全。"""
    if not key or not _KEYEVENT_PATTERN.match(key):
        logger.error("非法 keyevent: %s", key)
        return False
    return True

def _validate_path(path: str) -> bool:
    """验证路径中不包含 shell 元字符。"""
    if not path or _SHELL_META_PATTERN.search(path):
        logger.error("非法路径 (含 shell 元字符): %s", path)
        return False
    return True
```

**1.5 在各方法中添加验证**（在调用 `self.execute()` 之前）

- `force_stop`, `launch` → 调用 `_validate_package(package)`
- `keyevent` → 调用 `_validate_keyevent(key)`
- `screenshot`, `pull_file`, `push_file`, `delete_file` → 调用 `_validate_path()` 对路径参数

**1.6 兼容性：保留旧签名的过渡层**

由于 `step_executor.py` 和 `recorder.py` 中有大量 `self._adb_core.execute(f"shell ...")` 的调用，需要保留一个过渡方法：

```python
def execute_legacy(self, command: str, timeout: float = 30.0, device: str = None) -> subprocess.CompletedProcess:
    """旧接口兼容层，内部调用新 execute。将在第二阶段移除。"""
    import shlex
    logger.warning("execute_legacy() 已废弃，请迁移到 execute(list) 接口")
    args = shlex.split(command)
    return self.execute(args, timeout=timeout, device=device)
```

**1.7 更新 `push_and_start_scrcpy()` 方法**（第 194-231 行）

当前此方法已经使用了 `cmd_parts` 列表但仍在旧 execute 上构建。改为直接用参数列表调用 `execute()`。

**1.8 更新模块级便捷函数**（第 236-300 行）

所有 `def tap(...) -> _adb.tap(...)` 等模块级函数不需要改，因为它们只转发到实例方法。

---

## 任务 2：扩展注入防护到 `core/step_executor.py`

### 背景

当前 `_INJECTION_PATTERN`（第 19 行）只在 `_step_adb_command()`（第 679 行）检查，其他所有 step handler 绕过了检测。

### 要求

**2.1 在 `_step_input_text()` 中添加文本净化**

```python
def _step_input_text(self, step: dict) -> bool:
    text = step.get("text", "")
    # ADB input text 不支持部分特殊字符，用转义或拒绝
    if _INJECTION_PATTERN.search(text):
        logger.warning("input_text 包含潜在危险字符，进行转义: %s", text[:50])
        # 对 ADB shell 特殊字符进行转义
        text = text.replace("\\", "\\\\").replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
    return self._adb_core.input_text(text)
```

**2.2 在 `_step_force_stop()` 和 `_step_launch()` 中验证包名**

```python
def _step_force_stop(self, step: dict) -> bool:
    package = step["package"]
    if not re.match(r'^[a-zA-Z0-9._]+$', package):
        logger.error("非法包名: %s", package)
        return False
    # ... 原有逻辑 ...

def _step_launch(self, step: dict) -> bool:
    package = step["package"]
    if not re.match(r'^[a-zA-Z0-9._]+$', package):
        logger.error("非法包名: %s", package)
        return False
    # ... 原有逻辑 ...
```

**2.3 在 `_step_keyevent()` 中验证 keyevent**

```python
def _step_keyevent(self, step: dict) -> bool:
    key = step["key"]
    if not re.match(r'^[a-zA-Z0-9_]+$', str(key)):
        logger.error("非法 keyevent: %s", key)
        return False
    return self._adb_core.keyevent(key)
```

**2.4 在文件路径相关步骤中验证路径**

对 `_step_screenshot`（save_path）、`_step_pull_file`（remote, local）、`_step_delete_file`（path）检查 `_SHELL_META_PATTERN`。

---

## 任务 3：修复 `core/recorder.py` 中的 shell 注入

### 背景

`recorder.py` 第 136-138 行使用 `subprocess.Popen(cmd, shell=True, ...)`。

### 要求

找到 `subprocess.Popen` 调用，改为参数列表：

```python
# 当前（推测结构）
cmd = f"adb -s {serial} shell getevent -lt"
proc = subprocess.Popen(cmd, shell=True, ...)

# 改为
proc = subprocess.Popen(
    ["adb", "-s", serial, "shell", "getevent", "-lt"],
    shell=False,
    ...
)
```

---

## 任务 4：添加安全测试

### 要求

创建 `PY/tests/test_adb_security.py`：

```python
"""ADB 命令注入防护测试。"""
import pytest
from unittest.mock import patch, MagicMock
from core.adb_core import AdbCore, _validate_package, _validate_keyevent, _validate_path


class TestInputValidation:
    """验证输入校验函数。"""

    def test_validate_package_valid(self):
        assert _validate_package("com.tencent.tmgp.dfm") is True

    def test_validate_package_injection(self):
        assert _validate_package("com.test;rm -rf /") is False

    def test_validate_package_empty(self):
        assert _validate_package("") is False

    def test_validate_keyevent_valid(self):
        assert _validate_keyevent("KEYCODE_HOME") is True
        assert _validate_keyevent("3") is True

    def test_validate_keyevent_injection(self):
        assert _validate_keyevent("3;ls") is False

    def test_validate_path_valid(self):
        assert _validate_path("/data/local/tmp/screenshot.png") is True

    def test_validate_path_injection(self):
        assert _validate_path("/tmp/test;rm -rf /") is False


class TestAdbCoreShellFalse:
    """验证 execute() 使用 shell=False。"""

    @patch("subprocess.run")
    def test_execute_uses_shell_false(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        adb = AdbCore()
        adb.set_device("emulator-5554")
        adb.tap(100, 200)
        
        args, kwargs = mock_run.call_args
        assert kwargs.get("shell") is False or args[0] == ["adb", "-s", "emulator-5554", "shell", "input", "tap", "100", "200"]

    @patch("subprocess.run")
    def test_execute_builds_list_args(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        adb = AdbCore()
        adb.set_device("emulator-5554")
        adb.tap(100, 200)
        
        cmd = mock_run.call_args[0][0]
        assert isinstance(cmd, list)
        assert cmd[0] == "adb"
        assert "-s" in cmd
        assert "shell" in cmd
        assert "input" in cmd
        assert "tap" in cmd
        assert "100" in cmd
        assert "200" in cmd


class TestStepExecutorInjection:
    """验证 step_executor 中的注入防护。"""

    def test_input_text_rejects_injection(self):
        """包含 shell 元字符的文本应被转义或拒绝。"""
        from core.step_executor import StepExecutor, _INJECTION_PATTERN
        assert _INJECTION_PATTERN.search("hello; rm -rf /") is True

    def test_package_name_validation(self):
        """非法包名应被拒绝。"""
        import re
        pattern = re.compile(r'^[a-zA-Z0-9._]+$')
        assert pattern.match("com.tencent.tmgp.dfm") is not None
        assert pattern.match("com.test;ls") is None
```

---

## 验收标准

1. ✅ `grep -r "shell=True" PY/core/adb_core.py` 返回零结果
2. ✅ `grep -r "shell=True" PY/core/recorder.py` 返回零结果
3. ✅ `execute()` 方法签名接收 `list[str]` 而非 `str`
4. ✅ 所有通过 `f-string` 构建的命令调用改为列表形式
5. ✅ 输入验证函数在关键路径上被调用
6. ✅ `PY/tests/test_adb_security.py` 全部通过
7. ✅ 现有测试 `PY/tests/` 全部仍然通过（`cd PY && python -m pytest tests/ -v`）
8. ✅ 对 `input_text("hello; rm -rf /")` 不再执行 `rm -rf /`

## 注意事项

- 不要改变任何方法的外部返回值语义（`bool`、`str`、`CompletedProcess`）
- `execute_legacy()` 只作为过渡层，不需要测试覆盖
- `shell()` 方法用 `shlex.split()` 拆分，但要处理 `ValueError`（畸形引号）
- 保持 logger 调用中的中文信息不变
- `push_and_start_scrcpy()` 方法中硬编码的 `"1.25"` 版本号暂不处理（第二阶段）
