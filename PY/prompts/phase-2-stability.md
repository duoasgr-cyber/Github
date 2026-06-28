# 第二阶段：稳定性 — 实现提示词

> 执行环境：项目根目录 `PY/`，Python 3.10+，所有路径相对于 `PY/`。
> 前置条件：第一阶段（安全加固）已完成。

## 目标

1. 消除关键路径的 `silent except: pass`，改为带日志的异常处理
2. 统一工作流引擎（删除 `main_window.py` 中的重复 `_WorkflowWorker`）
3. 修复 `_shutdown()` 完整清理资源
4. 修复已知的代码缺陷

---

## 任务 1：消除 `screen_capture.py` 中的 silent except

### 背景

`core/screen_capture.py` 有 **12 处** `except: pass` 或 `except Exception: pass`，隐藏了 subprocess/socket/ffmpeg 的真实错误。

### 要求

**逐个检查并替换**以下位置的静默异常处理：

| 行号（约） | 上下文 | 处理方式 |
|------------|--------|---------|
| ~155 | `_start_scrcpy` 子进程启动 | `logger.debug("scrcpy 可选步骤失败: %s", e)` |
| ~168 | socket 连接 | `logger.warning("socket 连接失败: %s", e)` |
| ~198 | ffmpeg 进程 | `logger.debug("ffmpeg 未启动 (可选): %s", e)` |
| ~411 | 帧解码 | `logger.debug("帧解码跳过: %s", e)` |
| ~565 | 资源清理 - server | `logger.debug("scrcpy server 清理: %s", e)` |
| ~573 | 资源清理 - socket | `logger.debug("socket 清理: %s", e)` |
| ~581 | 资源清理 - ffmpeg | `logger.debug("ffmpeg 清理: %s", e)` |
| ~592 | 资源清理 - 线程 | `logger.debug("线程清理: %s", e)` |

**原则**：
- 资源清理中的 except 用 `logger.debug()`（正常关闭时异常可接受）
- 连接/初始化中的 except 用 `logger.warning()`（用户可能需要知道）
- 全部保留 `pass` 的控制流语义（不抛出），只增加日志

**替换模板**：

```python
# 当前
try:
    ...
except Exception:
    pass

# 改为
try:
    ...
except Exception as e:
    logger.debug("<上下文描述>: %s", e)
```

---

## 任务 2：消除 `main_window.py` 中的 silent except

### 要求

**2.1 UI 状态恢复**（第 189-190 行）

```python
# 当前
except Exception:
    pass

# 改为
except Exception as e:
    logging.warning("UI 状态恢复失败，使用默认值: %s", e)
```

**2.2 UI 状态保存**（第 212-213 行）

```python
except Exception as e:
    logging.warning("UI 状态保存失败: %s", e)
```

**2.3 修复异常钩子中的重复代码**（第 516-528 行）

当前代码将同一异常记录了两次。改为：

```python
def exception_hook(exc_type, exc_value, exc_tb):
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logging.critical("未处理的异常:\n%s", tb_text)
    try:
        self._log_panel._append_log(f"未处理的异常: {exc_value}", logging.ERROR)
    except Exception as e:
        # 日志面板不可用时写入 stderr 作为后备
        import sys
        print(f"[fallback] 异常日志写入失败: {e}", file=sys.stderr)
    original_excepthook(exc_type, exc_value, exc_tb)
```

---

## 任务 3：消除 `main.py` 中的 silent except

### 要求

**3.1 Setup wizard 失败**（约第 40-41 行）

```python
except Exception as e:
    logging.info("Setup wizard 跳过或失败: %s", e)
```

**3.2 崩溃遥测失败**（约第 63-64 行）

```python
except Exception as e:
    logging.debug("崩溃遥测发送失败: %s", e)
```

---

## 任务 4：消除 `core/telemetry.py` 和其他模块中的 silent except

### 要求

搜索所有 `except.*pass$` 模式：

```powershell
# 在 PY/ 目录下执行
Select-String -Path "PY\core\*.py","PY\ui\*.py","PY\ui\**\*.py","PY\main.py" -Pattern "except.*:\s*$" -Context 0,1 | Select-String "pass"
```

逐个评估并添加适当的 logger 调用。分类标准：

| 场景 | 日志级别 |
|------|---------|
| 资源清理/关闭 | `logger.debug` |
| 可选功能回退 | `logger.info` |
| 数据损坏但可恢复 | `logger.warning` |
| 关键功能失败 | `logger.error` |

---

## 任务 5：统一工作流引擎 — 删除 `_WorkflowWorker`

### 背景

`main_window.py` 第 38-48 行定义了一个简化的 `_WorkflowWorker(QThread)`，它直接调用 `step_executor.execute_workflow()`，绕过了 `WorkflowEngine` 的暂停/恢复/循环管理。

而 `StatusPanel` 的 start/stop/pause/resume 信号（第 497-500 行）连接到 `_on_start_monitoring` 等方法，这些方法使用的是简化版 Worker。

### 要求

**5.1 删除 `_WorkflowWorker` 类**（第 38-48 行）

```python
# 删除以下代码
class _WorkflowWorker(QThread):
    finished_signal = pyqtSignal()
    ...
```

**5.2 在 `MainWindow.__init__` 中创建 `WorkflowEngine` 实例**

```python
from core.workflow_engine import WorkflowEngine

# 在 __init__ 中，step_executor 创建之后：
self._workflow_engine = WorkflowEngine(
    self._step_executor, self._config_manager, parent=self
)
```

**5.3 修改 `_on_start_monitoring()`**

```python
def _on_start_monitoring(self):
    bound_device = self._task_state.get_task(
        self._task_bar.current_task_id()
    ).get("bound_device", "")
    if not bound_device:
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.warning(self, "无法启动", "请先在侧边栏选择设备后再启动。")
        return
    workflow_name = self._workflow_switcher.current_workflow()
    if not workflow_name:
        logging.warning("未选择工作流，无法启动监控")
        return
    if self._workflow_engine.is_running():
        logging.warning("工作流已在运行中")
        return
    
    # 连接引擎信号到 UI 更新
    self._workflow_engine.workflow_completed.connect(self._on_workflow_completed)
    self._workflow_engine.workflow_failed.connect(self._on_workflow_failed)
    
    self._workflow_engine.start(workflow_name)
    self._panels["status_monitor"].update_status("运行中", "#00ff88")
    self._panels["status_monitor"].update_current_workflow(workflow_name)
    self._floating_widget.update_status("运行中", "#00ff88")
    self._floating_widget.show()
    logging.info("启动监控: %s", workflow_name)
```

**5.4 修改 `_on_stop_monitoring()` 和 `_on_pause_monitoring()`**

改为使用 `self._workflow_engine.stop()` / `.pause()` / `.resume()`。

**5.5 删除 `_on_workflow_worker_finished()` 方法**

改为通过 `WorkflowEngine` 的 `workflow_completed` 信号处理。

**5.6 移除 `self._workflow_worker` 属性**

从 `__init__` 中删除 `self._workflow_worker = None`。

> **注意**：先检查 `WorkflowEngine` 的实际接口。如果 `WorkflowEngine` 是一个 QObject 而不是 QThread，需要确认它内部如何处理线程。如果它依赖 `StepExecutor` 在调用线程中执行，可能需要在 QThread 中包装 `engine.start()`。查看 `PY/core/workflow_engine.py` 确认接口后再实施。

---

## 任务 6：修复 `_shutdown()` 完整清理资源

### 背景

当前 `_shutdown()`（第 633-638 行）只停止了 step_executor：

```python
def _shutdown(self):
    try:
        self._step_executor.stop()
    except Exception:
        pass
```

### 要求

```python
def _shutdown(self):
    """清理所有资源，准备退出。"""
    errors = []
    
    # 1. 停止工作流引擎
    try:
        if hasattr(self, '_workflow_engine') and self._workflow_engine.is_running():
            self._workflow_engine.stop()
    except Exception as e:
        errors.append(f"工作流引擎停止失败: {e}")
    
    # 2. 停止屏幕采集
    try:
        self._screen_capture.stop()
    except Exception as e:
        errors.append(f"屏幕采集停止失败: {e}")
    
    # 3. 断开设备管理器
    try:
        if hasattr(self._device_manager, 'disconnect'):
            self._device_manager.disconnect()
    except Exception as e:
        errors.append(f"设备断开失败: {e}")
    
    # 4. 保存配置
    try:
        self._config_manager.save_config()
    except Exception as e:
        errors.append(f"配置保存失败: {e}")
    
    # 5. 保存任务快照
    try:
        self._save_task_snapshot()
    except Exception as e:
        errors.append(f"任务快照保存失败: {e}")
    
    # 6. 保存 UI 状态
    try:
        self._save_ui_state()
    except Exception as e:
        errors.append(f"UI 状态保存失败: {e}")
    
    if errors:
        for err in errors:
            logging.warning("关闭清理: %s", err)
    else:
        logging.info("所有资源已清理")
```

---

## 任务 7：修复其他已知缺陷

### 7.1 修复错别字

`core/screen_capture.py` 约第 342 行：

```python
# 当前
"请确保fmpeg已安装"
# 改为
"请确保ffmpeg已安装"
```

### 7.2 修复 `adb_core.py` 中 scrcpy 版本硬编码

`adb_core.py` 第 211 行 `"1.25"` 硬编码。与 `screen_capture.py` 的自动检测不一致。

方案：删除 `push_and_start_scrcpy()` 方法（第 194-231 行），因为 `screen_capture.py` 的 `_start_scrcpy()` 已经完整实现了推送+启动+版本检测逻辑。如果此方法仍被其他代码引用，标记为 `@deprecated` 并在调用处迁移到 `ScrcpyCapture.start()`。

### 7.3 修复 `app.spec` 入口

如果 `app.spec` 引用 `app.py` 但实际入口是 `main.py`，修正 entry point。

---

## 任务 8：添加稳定性测试

### 要求

创建 `PY/tests/test_shutdown.py`：

```python
"""验证资源清理逻辑。"""
import pytest
from unittest.mock import MagicMock, patch


class TestShutdown:
    def test_shutdown_stops_screen_capture(self):
        """_shutdown 应调用 screen_capture.stop()。"""
        # ... 用 mock 构造 MainWindow，调用 _shutdown，验证 stop 被调用

    def test_shutdown_saves_config(self):
        """_shutdown 应保存配置。"""
        # ...

    def test_shutdown_saves_task_snapshot(self):
        """_shutdown 应保存任务快照。"""
        # ...

    def test_shutdown_handles_errors_gracefully(self):
        """_shutdown 中某个组件失败不应阻止其他组件清理。"""
        # 让 screen_capture.stop() 抛异常，验证 config_manager.save_config() 仍被调用
```

---

## 验收标准

1. ✅ `screen_capture.py` 中不再有 bare `except: pass`（`except ... as e: logger.debug(...)` 代替）
2. ✅ `main_window.py` 异常钩子不再重复记录
3. ✅ `_shutdown()` 清理 6 个组件（engine、capture、device、config、task、ui_state）
4. ✅ `_WorkflowWorker` 已删除，所有工作流启动通过统一引擎
5. ✅ 错别字 `fmpeg` 已修复
6. ✅ 现有测试全部通过
7. ✅ 新测试覆盖 shutdown 和异常处理

## 注意事项

- 任务 5（统一引擎）是最复杂的改动，**务必先读 `core/workflow_engine.py` 确认接口**再动手
- 所有新增 `logger.xxx()` 调用保持中文信息风格
- 清理 except 时注意不要改变控制流（仍为 `pass` 语义，只是加了日志）
