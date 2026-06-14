# 第三阶段：测试补全 — 实现提示词

> 执行环境：项目根目录 `PY/`，Python 3.10+，所有路径相对于 `PY/`。
> 前置条件：第一、二阶段已完成。
> 运行测试：`cd PY && python -m pytest tests/ -v`

## 目标

为以下零覆盖的核心模块补充单元测试：
1. `step_executor.py` — 覆盖 18+ 步骤类型（最复杂模块，819 行）
2. `adb_core.py` — mock ADB 调用测试
3. `ocr_engine.py` — mock EasyOCR 测试

---

## 通用测试规范

### Mock 策略

本项目所有测试都在无真实设备环境下运行：
- ADB 调用 → `unittest.mock.patch("subprocess.run")`
- 屏幕采集 → `unittest.mock.patch` 返回预制 numpy 数组
- OCR 引擎 → `unittest.mock.patch("easyocr.Reader")`
- PyQt5 → 使用 `QT_QPA_PLATFORM=offscreen`（CI 已配置）
- 图片模板 → 使用 `numpy` 生成纯色/渐变测试图片，不依赖磁盘文件

### 测试文件位置

```
PY/tests/
├── test_adb_core.py          ← 新建
├── test_step_executor.py     ← 新建
├── test_ocr_engine.py        ← 新建
├── test_config_manager.py    （已有）
├── test_integration.py       （已有）
├── test_screen_capture.py    （已有）
├── test_telemetry_report.py  （已有）
├── test_workflow_engine.py   （已有）
└── ... 其他已有测试 ...
```

### 命名规范

```python
class Test<ModuleName>:
    def test_<行为描述>(self):
        """中文 docstring 描述预期行为。"""
```

---

## 任务 1：`test_adb_core.py` — ADB 核心模块测试

### 背景

`core/adb_core.py` 提供 `AdbCore` 类和模块级便捷函数。第一阶段已将 `execute()` 改为 `shell=False` + 参数列表。

### 要求的测试用例

```python
"""ADB 核心模块单元测试。"""
import pytest
from unittest.mock import patch, MagicMock, call
import subprocess
from core.adb_core import AdbCore, AdbError


class TestAdbCoreExecute:
    """execute() 基础行为。"""

    @patch("subprocess.run")
    def test_execute_builds_command_list(self, mock_run):
        """execute() 应构建参数列表而非字符串。"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        adb = AdbCore()
        adb.set_device("emulator-5554")
        adb.execute(["shell", "input", "tap", "100", "200"])

        cmd = mock_run.call_args[0][0]
        assert isinstance(cmd, list)
        assert cmd == ["adb", "-s", "emulator-5554", "shell", "input", "tap", "100", "200"]

    @patch("subprocess.run")
    def test_execute_no_device(self, mock_run):
        """未设置设备时不应包含 -s 参数。"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        adb = AdbCore()
        adb.execute(["devices"])
        cmd = mock_run.call_args[0][0]
        assert cmd == ["adb", "devices"]

    @patch("subprocess.run")
    def test_execute_shell_false(self, mock_run):
        """execute() 必须使用 shell=False。"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        adb = AdbCore()
        adb.execute(["shell", "echo", "test"])
        assert mock_run.call_args[1].get("shell") is False

    @patch("subprocess.run")
    def test_execute_nonzero_raises_adb_error(self, mock_run):
        """非零返回码应抛出 AdbError。"""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        adb = AdbCore()
        with pytest.raises(AdbError):
            adb.execute(["shell", "ls"])

    @patch("subprocess.run")
    def test_execute_timeout_raises_adb_error(self, mock_run):
        """超时应抛出 AdbError。"""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="adb", timeout=30)
        adb = AdbCore()
        with pytest.raises(AdbError, match="超时"):
            adb.execute(["shell", "ls"])


class TestAdbCoreActions:
    """各操作方法测试。"""

    @patch("subprocess.run")
    def test_tap_calls_correct_args(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        adb = AdbCore()
        adb.set_device("dev1")
        assert adb.tap(100, 200) is True
        cmd = mock_run.call_args[0][0]
        assert "tap" in cmd
        assert "100" in cmd
        assert "200" in cmd

    @patch("subprocess.run")
    def test_swipe_calls_correct_args(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        adb = AdbCore()
        adb.set_device("dev1")
        assert adb.swipe(10, 20, 30, 40, 500) is True
        cmd = mock_run.call_args[0][0]
        assert "swipe" in cmd
        assert "10" in cmd
        assert "500" in cmd

    @patch("subprocess.run")
    def test_input_text_calls_correct_args(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        adb = AdbCore()
        adb.set_device("dev1")
        assert adb.input_text("hello") is True
        cmd = mock_run.call_args[0][0]
        assert cmd[-1] == "hello"

    @patch("subprocess.run")
    def test_force_stop_validates_package(self, mock_run):
        """合法包名应成功。"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        adb = AdbCore()
        adb.set_device("dev1")
        assert adb.force_stop("com.tencent.tmgp.dfm") is True

    @patch("subprocess.run")
    def test_force_stop_rejects_injection(self, mock_run):
        """含注入字符的包名应被拒绝。"""
        adb = AdbCore()
        adb.set_device("dev1")
        # 根据第一阶段实现，可能返回 False 或抛异常
        result = adb.force_stop("com.test;rm -rf /")
        assert result is False

    @patch("subprocess.run")
    def test_get_device_list_parses_output(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="List of devices attached\nemulator-5554\tdevice\n192.168.1.100:5555\tdevice\n",
            stderr=""
        )
        adb = AdbCore()
        devices = adb.get_device_list()
        assert devices == ["emulator-5554", "192.168.1.100:5555"]

    @patch("subprocess.run")
    def test_get_device_list_empty(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="List of devices attached\n\n",
            stderr=""
        )
        adb = AdbCore()
        assert adb.get_device_list() == []

    @patch("subprocess.run")
    def test_get_device_resolution_parses(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Physical size: 1080x1920\n",
            stderr=""
        )
        adb = AdbCore()
        adb.set_device("dev1")
        w, h = adb.get_device_resolution()
        assert w == 1080
        assert h == 1920


class TestModuleLevelFunctions:
    """模块级便捷函数转发测试。"""

    @patch.object(AdbCore, "tap", return_value=True)
    def test_module_tap(self, mock_tap):
        from core.adb_core import tap
        tap(10, 20, device="dev1")
        mock_tap.assert_called_once_with(10, 20, device="dev1")
```

---

## 任务 2：`test_step_executor.py` — 步骤执行器测试

### 背景

`core/step_executor.py` 有 18 种步骤类型。需要 mock 所有依赖（adb_core, screen_capture, ocr_engine, device_manager, config_manager）。

### 要求的测试用例

```python
"""步骤执行器单元测试。"""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch, PropertyMock
from core.step_executor import StepExecutor


@pytest.fixture
def mock_deps():
    """构造 mock 依赖。"""
    config = MagicMock()
    config.get_config.return_value = {}
    config.get_workflow.return_value = {
        "steps": [],
        "device_resolution": {"width": 1080, "height": 1920}
    }

    adb = MagicMock()
    adb.tap.return_value = True
    adb.swipe.return_value = True
    adb.keyevent.return_value = True
    adb.input_text.return_value = True
    adb.force_stop.return_value = True
    adb.launch.return_value = True
    adb.wifi_enable.return_value = True
    adb.wifi_disable.return_value = True
    adb.pull_file.return_value = True
    adb.delete_file.return_value = True
    adb.shell.return_value = ""

    capture = MagicMock()
    capture.get_current_frame.return_value = np.zeros((1920, 1080, 3), dtype=np.uint8)

    ocr = MagicMock()
    ocr.recognize.return_value = ""
    ocr.recognize_price.return_value = 0

    device = MagicMock()
    device.get_device_resolution.return_value = (1080, 1920)
    device.get_current_device.return_value = "emulator-5554"

    return config, adb, capture, ocr, device


@pytest.fixture
def executor(mock_deps):
    config, adb, capture, ocr, device = mock_deps
    # 需要 QApplication 实例（QSignal 需要）
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    return StepExecutor(config, adb, capture, ocr, device)


class TestStepTap:
    def test_tap_calls_adb_with_scaled_coords(self, executor, mock_deps):
        """tap 步骤应调用 adb.tap() 并传入缩放后的坐标。"""
        _, adb, _, _, _ = mock_deps
        executor._scale_x = 1.0
        executor._scale_y = 1.0
        step = {"type": "tap", "x": 100, "y": 200}
        result = executor._step_tap(step)
        assert result is True
        adb.tap.assert_called_once_with(100, 200)

    def test_tap_with_scaling(self, executor, mock_deps):
        """坐标缩放应正确计算。"""
        _, adb, _, _, _ = mock_deps
        executor._scale_x = 2.0
        executor._scale_y = 1.5
        step = {"type": "tap", "x": 100, "y": 200}
        executor._step_tap(step)
        adb.tap.assert_called_once_with(200, 300)

    def test_tap_with_wait_after(self, executor):
        """wait_after 参数应导致可中断睡眠。"""
        step = {"type": "tap", "x": 100, "y": 200, "wait_after": 0.1}
        with patch.object(executor, '_interruptible_sleep') as mock_sleep:
            executor._step_tap(step)
            mock_sleep.assert_called_once_with(0.1)


class TestStepSwipe:
    def test_swipe_calls_adb(self, executor, mock_deps):
        _, adb, _, _, _ = mock_deps
        step = {"type": "swipe", "x1": 10, "y1": 20, "x2": 30, "y2": 40, "duration": 500}
        executor._step_swipe(step)
        adb.swipe.assert_called_once_with(10, 20, 30, 40, 500)


class TestStepKeyevent:
    def test_keyevent_calls_adb(self, executor, mock_deps):
        _, adb, _, _, _ = mock_deps
        step = {"type": "keyevent", "key": "KEYCODE_HOME"}
        executor._step_keyevent(step)
        adb.keyevent.assert_called_once_with("KEYCODE_HOME")


class TestStepWait:
    def test_wait_sleeps(self, executor):
        step = {"type": "wait", "seconds": 0.5}
        with patch.object(executor, '_interruptible_sleep') as mock_sleep:
            executor._step_wait(step)
            mock_sleep.assert_called_once_with(0.5)


class TestStepForceStop:
    def test_force_stop_calls_adb(self, executor, mock_deps):
        _, adb, _, _, _ = mock_deps
        step = {"type": "force_stop", "package": "com.tencent.tmgp.dfm"}
        executor._step_force_stop(step)
        adb.force_stop.assert_called_once_with("com.tencent.tmgp.dfm")


class TestStepLaunch:
    def test_launch_calls_adb(self, executor, mock_deps):
        _, adb, _, _, _ = mock_deps
        step = {"type": "launch", "package": "com.tencent.tmgp.dfm"}
        executor._step_launch(step)
        adb.launch.assert_called_once_with("com.tencent.tmgp.dfm")


class TestStepScreenshot:
    def test_screenshot_saves_frame(self, executor, mock_deps):
        _, _, capture, _, _ = mock_deps
        step = {"type": "screenshot", "save_path": "/tmp/test.png"}
        with patch("cv2.imwrite", return_value=True) as mock_write:
            result = executor._step_screenshot(step)
            assert result is True
            mock_write.assert_called_once()

    def test_screenshot_no_frame_fails(self, executor, mock_deps):
        _, _, capture, _, _ = mock_deps
        capture.get_current_frame.return_value = None
        step = {"type": "screenshot", "save_path": "/tmp/test.png"}
        assert executor._step_screenshot(step) is False


class TestStepCheckImage:
    def test_check_image_found(self, executor, mock_deps):
        """当模板匹配度 >= 阈值时返回 True。"""
        _, _, capture, _, _ = mock_deps
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[10:20, 10:20] = 255
        template = frame[10:20, 10:20].copy()
        capture.get_current_frame.return_value = frame

        with patch("core.step_executor._load_template_cached", return_value=template), \
             patch("cv2.matchTemplate") as mock_match, \
             patch("cv2.minMaxLoc", return_value=(0, 0.95, None, None)):
            mock_match.return_value = np.array([[0.95]])
            step = {"type": "check_image", "template": "test.png", "threshold": 0.85}
            executor._step_check_image(step)
            assert executor._last_check_result is True

    def test_check_image_not_found(self, executor, mock_deps):
        """当模板匹配度 < 阈值时返回 False。"""
        _, _, capture, _, _ = mock_deps
        capture.get_current_frame.return_value = np.zeros((100, 100, 3), dtype=np.uint8)

        with patch("core.step_executor._load_template_cached", return_value=np.zeros((10, 10, 3), dtype=np.uint8)), \
             patch("cv2.matchTemplate") as mock_match, \
             patch("cv2.minMaxLoc", return_value=(0, 0.3, None, None)):
            mock_match.return_value = np.array([[0.3]])
            step = {"type": "check_image", "template": "test.png", "threshold": 0.85}
            executor._step_check_image(step)
            assert executor._last_check_result is False


class TestStepOcrRegion:
    def test_ocr_recognizes_text(self, executor, mock_deps):
        _, _, _, ocr, _ = mock_deps
        ocr.recognize.return_value = "购买"
        step = {"type": "ocr_region"}
        executor._step_ocr_region(step)
        assert executor._last_ocr_result == "购买"

    def test_ocr_assigns_variable(self, executor, mock_deps):
        _, _, _, ocr, _ = mock_deps
        ocr.recognize.return_value = "12000"
        step = {"type": "ocr_region", "assign_variable": "price"}
        executor._step_ocr_region(step)
        assert executor._variables["price"] == "12000"


class TestStepVariable:
    def test_variable_string(self, executor):
        step = {"type": "variable", "var_name": "x", "var_type": "string", "var_value": "hello"}
        executor._step_variable(step)
        assert executor._variables["x"] == "hello"

    def test_variable_int(self, executor):
        step = {"type": "variable", "var_name": "n", "var_type": "int", "var_value": "42"}
        executor._step_variable(step)
        assert executor._variables["n"] == 42

    def test_variable_bool(self, executor):
        step = {"type": "variable", "var_name": "flag", "var_type": "bool", "var_value": "true"}
        executor._step_variable(step)
        assert executor._variables["flag"] is True


class TestStepCondition:
    def test_condition_then_branch(self, executor):
        """满足条件时执行 then_steps。"""
        with patch.object(executor, '_evaluate_condition', return_value=True):
            mock_step = {"type": "wait", "seconds": 0}
            step = {"type": "condition", "check": {}, "then_steps": [mock_step], "else_steps": []}
            with patch.object(executor, '_execute_single_step', return_value=True) as mock_exec:
                executor._step_condition(step)
                mock_exec.assert_called_once_with(mock_step)

    def test_condition_else_branch(self, executor):
        with patch.object(executor, '_evaluate_condition', return_value=False):
            mock_step = {"type": "wait", "seconds": 0}
            step = {"type": "condition", "check": {}, "then_steps": [], "else_steps": [mock_step]}
            with patch.object(executor, '_execute_single_step', return_value=True) as mock_exec:
                executor._step_condition(step)
                mock_exec.assert_called_once_with(mock_step)


class TestStepLoop:
    def test_loop_respects_max_count(self, executor):
        """循环应执行 max_count 次后停止。"""
        step = {"type": "loop", "max_count": 3, "steps": [{"type": "wait", "seconds": 0}]}
        call_count = 0
        def counting_exec(s):
            nonlocal call_count
            call_count += 1
            return True
        with patch.object(executor, '_execute_single_step', side_effect=counting_exec):
            executor._step_loop(step)
        assert call_count == 3

    def test_loop_respects_condition(self, executor):
        """条件不满足时循环应停止。"""
        call_count = 0
        def side_effect(check):
            nonlocal call_count
            call_count += 1
            return call_count <= 2
        step = {"type": "loop", "max_count": -1, "condition": {}, "steps": [{"type": "wait", "seconds": 0}]}
        with patch.object(executor, '_evaluate_condition', side_effect=side_effect), \
             patch.object(executor, '_execute_single_step', return_value=True):
            executor._step_loop(step)
        assert call_count == 3  # 第三次返回 False


class TestExecuteSingleStep:
    def test_unknown_step_type_fails(self, executor):
        step = {"type": "nonexistent_type"}
        assert executor._execute_single_step(step) is False

    def test_step_exception_returns_false(self, executor):
        """handler 抛异常时应返回 False。"""
        step = {"type": "tap", "x": 100, "y": 200}
        with patch.object(executor, '_step_tap', side_effect=RuntimeError("boom")):
            assert executor._execute_single_step(step) is False
```

---

## 任务 3：`test_ocr_engine.py` — OCR 引擎测试

### 背景

`core/ocr_engine.py` 使用 EasyOCR，需要 mock `easyocr.Reader`。模块使用单例模式 + 线程锁。

### 要求的测试用例

```python
"""OCR 引擎单元测试。"""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from core.ocr_engine import OcrEngine


@pytest.fixture
def fresh_engine():
    """每次测试创建新的引擎实例（绕过单例）。"""
    engine = OcrEngine.__new__(OcrEngine)
    engine._reader = None
    engine._initialized = False
    return engine


class TestOcrInitialize:
    @patch("easyocr.Reader")
    def test_initialize_success(self, mock_reader_cls, fresh_engine):
        """正常初始化应返回 True。"""
        mock_reader_cls.return_value = MagicMock()
        result = fresh_engine.initialize(gpu=False)
        assert result is True
        assert fresh_engine.is_initialized() is True
        mock_reader_cls.assert_called_once_with(['ch_sim', 'en'], gpu=False)

    @patch("easyocr.Reader", side_effect=ImportError("no module"))
    def test_initialize_failure(self, mock_cls, fresh_engine):
        """初始化失败应返回 False 并进入降级模式。"""
        result = fresh_engine.initialize()
        assert result is False
        assert fresh_engine.is_initialized() is False

    @patch("easyocr.Reader")
    def test_initialize_idempotent(self, mock_cls, fresh_engine):
        """多次调用 initialize() 只初始化一次。"""
        mock_cls.return_value = MagicMock()
        fresh_engine.initialize()
        fresh_engine.initialize()
        mock_cls.assert_called_once()

    @patch("easyocr.Reader")
    def test_initialize_with_progress_callback(self, mock_cls, fresh_engine):
        """progress_callback 应被调用 0, 50, 100。"""
        mock_cls.return_value = MagicMock()
        cb = MagicMock()
        fresh_engine.initialize(progress_callback=cb)
        cb.assert_any_call(0)
        cb.assert_any_call(50)
        cb.assert_any_call(100)


class TestOcrRecognize:
    def test_recognize_not_initialized(self, fresh_engine):
        """未初始化时应返回空字符串。"""
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        assert fresh_engine.recognize(img) == ""

    def test_recognize_basic(self, fresh_engine):
        """应返回 OCR 识别文本。"""
        fresh_engine._initialized = True
        fresh_engine._reader = MagicMock()
        fresh_engine._reader.readtext.return_value = [
            (None, "购买", 0.9),
            (None, "按钮", 0.8),
        ]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = fresh_engine.recognize(img)
        assert "购买按钮" in result

    def test_recognize_with_region(self, fresh_engine):
        """region 参数应裁剪图片。"""
        fresh_engine._initialized = True
        fresh_engine._reader = MagicMock()
        fresh_engine._reader.readtext.return_value = [(None, "text", 0.9)]
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        region = {"left": 10, "top": 20, "right": 50, "bottom": 60}
        fresh_engine.recognize(img, region)
        # 验证 readtext 收到的图片尺寸是裁剪后的
        called_img = fresh_engine._reader.readtext.call_args[0][0]
        assert called_img.shape == (40, 40, 3)  # bottom-top, right-left

    def test_recognize_exception_returns_empty(self, fresh_engine):
        """OCR 异常应返回空字符串。"""
        fresh_engine._initialized = True
        fresh_engine._reader = MagicMock()
        fresh_engine._reader.readtext.side_effect = RuntimeError("GPU OOM")
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        assert fresh_engine.recognize(img) == ""


class TestOcrRecognizePrice:
    def test_recognize_price_valid(self, fresh_engine):
        """合法价格应正确解析。"""
        fresh_engine._initialized = True
        fresh_engine._reader = MagicMock()
        fresh_engine._reader.readtext.return_value = [(None, "120000", 0.9)]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        assert fresh_engine.recognize_price(img) == 120000

    def test_recognize_price_with_comma(self, fresh_engine):
        """带逗号的价格应正确解析。"""
        fresh_engine._initialized = True
        fresh_engine._reader = MagicMock()
        fresh_engine._reader.readtext.return_value = [(None, "1,200,000", 0.9)]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        assert fresh_engine.recognize_price(img) == 1200000

    def test_recognize_price_too_short_returns_sentinel(self, fresh_engine):
        """过短的数字应返回哨兵值。"""
        fresh_engine._initialized = True
        fresh_engine._reader = MagicMock()
        fresh_engine._reader.readtext.return_value = [(None, "12", 0.9)]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        assert fresh_engine.recognize_price(img) == 100_000_000_000_000

    def test_recognize_price_not_initialized(self, fresh_engine):
        """未初始化时应返回哨兵值。"""
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        assert fresh_engine.recognize_price(img) == 100_000_000_000_000

    def test_recognize_price_trailing_8_correction(self, fresh_engine):
        """末尾 '8' 应被修正为 '0'（游戏 OCR 特殊处理）。"""
        fresh_engine._initialized = True
        fresh_engine._reader = MagicMock()
        fresh_engine._reader.readtext.return_value = [(None, "120008", 0.9)]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        assert fresh_engine.recognize_price(img) == 120000


class TestOcrRecognizeButton:
    def test_recognize_button_chinese(self, fresh_engine):
        """检测到中文时返回 ("chinese", text)。"""
        fresh_engine._initialized = True
        fresh_engine._reader = MagicMock()
        fresh_engine._reader.readtext.return_value = [(None, "购买", 0.9)]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = fresh_engine.recognize_button(img)
        assert result == ("chinese", "购买")

    def test_recognize_button_number(self, fresh_engine):
        """检测到数字时返回 ("number", text)。"""
        fresh_engine._initialized = True
        fresh_engine._reader = MagicMock()
        fresh_engine._reader.readtext.return_value = [(None, "123456", 0.9)]
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = fresh_engine.recognize_button(img)
        assert result == ("number", "123456")


class TestCropRegion:
    def test_crop_no_region(self, fresh_engine):
        """无 region 时返回原图。"""
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        result = fresh_engine._crop_region(img, None)
        assert result.shape == (100, 200, 3)

    def test_crop_with_region(self, fresh_engine):
        """region 应正确裁剪。"""
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        region = {"left": 10, "top": 20, "right": 50, "bottom": 60}
        result = fresh_engine._crop_region(img, region)
        assert result.shape == (40, 40, 3)
```

---

## 验收标准

1. ✅ `PY/tests/test_adb_core.py` 创建并全部通过
2. ✅ `PY/tests/test_step_executor.py` 创建并全部通过
3. ✅ `PY/tests/test_ocr_engine.py` 创建并全部通过
4. ✅ 所有测试使用 mock，不依赖真实 ADB 设备或 GPU
5. ✅ 运行 `cd PY && python -m pytest tests/ -v` 全部通过
6. ✅ 测试覆盖 `step_executor.py` 的至少 15 种步骤类型
7. ✅ 测试覆盖 `adb_core.py` 的所有公开方法
8. ✅ 测试覆盖 `ocr_engine.py` 的所有公开方法

## 注意事项

- `StepExecutor` 是 `QObject`，构造时需要 `QApplication` 实例
- `OcrEngine` 是单例，测试 fixture 需要绕过单例（用 `__new__` 创建）
- `_load_template_cached` 用了 `@lru_cache`，需要 patch 模块级函数
- OCR 的 magic number `100_000_000_000_000` 在测试中应作为常量引用
- 所有 mock 的 `subprocess.run` 返回值需要包含 `returncode`、`stdout`、`stderr` 属性
