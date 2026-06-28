import logging
import time
import os
import threading
import cv2
import numpy as np
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal, QThread

from core.config_manager import ConfigManager
from core.step_executor import StepExecutor
from core.ocr_engine import OcrEngine
from core.device_manager import DeviceManager

logger = logging.getLogger(__name__)


class _WorkflowWorker(QObject):
    price_updated = pyqtSignal(int)
    mail_count_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str, str)
    cycle_completed = pyqtSignal(int)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, config_manager: ConfigManager, step_executor: StepExecutor,
                 ocr_engine: OcrEngine, device_manager: DeviceManager, parent=None):
        super().__init__(parent)
        self._config_manager = config_manager
        self._step_executor = step_executor
        self._ocr_engine = ocr_engine
        self._device_manager = device_manager
        self._stop_requested: bool = False
        self._paused: bool = False
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._current_price: int = 0
        self._mail_count: int = 0
        self._cycle_count: int = 0
        self._template_cache: dict = {}

    def request_reset_mail_count(self) -> None:
        """线程安全地重置邮件计数（由 WorkflowEngine 调用）。"""
        self._mail_count = 0
        self._save_mail_count()
        self.mail_count_updated.emit(0)

    def _cfg_refresh_workflow(self) -> str:
        return self._config_manager.get_config("workflow_engine.refresh_workflow", "refresh_path")

    def _cfg_status_running(self) -> str:
        return self._config_manager.get_config("workflow_engine.status_running", "运行中")

    def _cfg_status_recovering(self) -> str:
        return self._config_manager.get_config("workflow_engine.status_recovering", "恢复中...")

    def _cfg_status_mail_full(self) -> str:
        return self._config_manager.get_config("workflow_engine.status_mail_full", "邮件已满")

    def run(self) -> None:
        self._stop_requested = False
        self._paused = False
        self._pause_event.set()
        self._load_mail_count()
        self.status_updated.emit(self._cfg_status_running(), "#4caf50")

        while not self._stop_requested:
            if not self._check_pause():
                break
            try:
                self._run_cycle()
            except Exception as e:
                logger.error("工作流循环异常: %s", e)
                self.error_occurred.emit(str(e))
                self._interruptible_sleep(1.0)

        self.status_updated.emit("已停止", "#a0a0a0")
        self.finished.emit()

    def request_stop(self) -> None:
        self._stop_requested = True
        self._step_executor.stop()
        self._pause_event.set()

    def request_pause(self) -> None:
        self._paused = True
        self._step_executor.pause()
        self.status_updated.emit("已暂停", "#ffaa00")

    def request_resume(self) -> None:
        self._paused = False
        self._step_executor.resume()
        self._pause_event.set()
        self.status_updated.emit(self._cfg_status_running(), "#4caf50")

    def get_current_price(self) -> int:
        return self._current_price

    def get_mail_count(self) -> int:
        return self._mail_count

    def _check_pause(self) -> bool:
        while self._paused and not self._stop_requested:
            self._pause_event.clear()
            self._pause_event.wait()
        return not self._stop_requested

    def _interruptible_sleep(self, seconds: float) -> None:
        elapsed = 0.0
        while elapsed < seconds:
            if self._stop_requested:
                return
            if self._paused:
                if not self._check_pause():
                    return
            sleep_time = min(0.1, seconds - elapsed)
            time.sleep(sleep_time)
            elapsed += sleep_time

    def _load_mail_count(self) -> None:
        mail_count_file = self._config_manager.get_config("mail_params.mail_count_file", "you.txt")
        try:
            if os.path.exists(mail_count_file):
                with open(mail_count_file, "r", encoding="utf-8") as f:
                    self._mail_count = int(f.read().strip())
            else:
                self._mail_count = 0
        except (ValueError, OSError) as e:
            logger.warning("读取邮件数量失败: %s", e)
            self._mail_count = 0
        self.mail_count_updated.emit(self._mail_count)

    def _save_mail_count(self) -> None:
        mail_count_file = self._config_manager.get_config("mail_params.mail_count_file", "you.txt")
        try:
            with open(mail_count_file, "w", encoding="utf-8") as f:
                f.write(str(self._mail_count))
        except OSError as e:
            logger.error("写入邮件数量失败: %s", e)

    def _increment_mail_count(self) -> None:
        self._mail_count += 1
        self._save_mail_count()
        self.mail_count_updated.emit(self._mail_count)
        logger.info("邮件数量: %d", self._mail_count)

    def _check_mail_limit(self) -> bool:
        default_max = self._config_manager.get_config("workflow_engine.max_mail_count_default", 190)
        max_mail_count = self._config_manager.get_config("buy_params.max_mail_count", default_max)
        if self._mail_count >= max_mail_count:
            logger.warning("邮件数量已达上限: %d/%d，跳过购买", self._mail_count, max_mail_count)
            self.status_updated.emit(self._cfg_status_mail_full(), "#ff6b6b")
            return False
        return True

    def _get_current_frame(self) -> Optional[np.ndarray]:
        return self._step_executor.get_current_frame()

    def _check_template(self, frame: np.ndarray, template_name: str,
                        threshold: float = 0.85) -> bool:
        template_dir = self._config_manager.get_config("recognition.template_dir", "tp")
        template_path = os.path.join(template_dir, template_name)

        # 模板缓存：避免循环中重复读取磁盘
        cache_key = template_path
        if cache_key not in self._template_cache:
            template = cv2.imread(template_path, cv2.IMREAD_COLOR)
            if template is None:
                logger.error("加载模板图片失败: %s", template_path)
                return False
            self._template_cache[cache_key] = template
        template = self._template_cache[cache_key]

        if template.shape[0] > frame.shape[0] or template.shape[1] > frame.shape[1]:
            return False
        result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return max_val >= threshold

    def _get_user_scheme_workflow(self) -> str:
        user_scheme = self._config_manager.get_config("buy_params.user_scheme", 1)
        return f"programme_choose_{user_scheme}"

    def _refresh_price(self) -> None:
        self._step_executor.execute_workflow(self._cfg_refresh_workflow())
        if self._stop_requested:
            return
        self._step_executor.execute_workflow("programme_choose_0")
        if self._stop_requested:
            return
        self._step_executor.execute_workflow(self._get_user_scheme_workflow())

    def _run_cycle(self) -> None:
        if not self._check_pause():
            return

        self._refresh_price()
        if self._stop_requested:
            return

        self._interruptible_sleep(1.0)
        if self._stop_requested:
            return

        frame = self._get_current_frame()
        if frame is None:
            self.error_occurred.emit("获取屏幕帧失败")
            return

        button_region = self._config_manager.get_config("ocr_regions.button_region", None)
        content_type, result_text = self._ocr_engine.recognize_button(frame, button_region)
        logger.info("按钮识别: type=%s, text=%s", content_type, result_text)

        if content_type == "chinese":
            cleaned_text = result_text.replace(" ", "")
            if "方" in cleaned_text:
                self.status_updated.emit("确认购买界面", "#4caf50")
                self._handle_confirm_buy()
            else:
                self.status_updated.emit(self._cfg_status_recovering(), "#ff6b6b")
                self._recover_game()
        elif content_type == "number":
            self._handle_price_check()
        else:
            self.status_updated.emit(self._cfg_status_recovering(), "#ff6b6b")
            self._recover_game()

    def _handle_confirm_buy(self) -> None:
        if not self._check_mail_limit():
            return

        self._step_executor.execute_workflow("e_adb_buy")
        if self._stop_requested:
            return

        self._interruptible_sleep(2.0)
        if self._stop_requested:
            return

        self._execute_card_mail()

    def _handle_price_check(self) -> None:
        self.status_updated.emit("购买界面", "#4caf50")

        while not self._stop_requested:
            if not self._check_pause():
                return

            self._refresh_price()
            if self._stop_requested:
                return

            self._interruptible_sleep(0.2)
            if self._stop_requested:
                return

            frame = self._get_current_frame()
            if frame is None:
                self.error_occurred.emit("获取屏幕帧失败")
                return

            price_region = self._config_manager.get_config("ocr_regions.price_region", None)
            game_price = self._ocr_engine.recognize_price(frame, price_region)

            self._current_price = game_price
            self.price_updated.emit(game_price)
            logger.info("当前价格: %d", game_price)

            if game_price > 1000000000:
                logger.warning("价格异常: %d", game_price)
                break

            user_price = self._config_manager.get_config("buy_params.user_price", 0.5)
            price_coefficient = self._config_manager.get_config("buy_params.price_coefficient", 4560)
            min_price = self._config_manager.get_config("buy_params.min_price", 300000)

            if game_price <= min_price:
                logger.info("价格过小: %d <= %d", game_price, min_price)
                break

            target_price = int(user_price * price_coefficient)
            if target_price >= game_price:
                logger.info("价格合适: 目标%d >= 游戏%d", target_price, game_price)
                if not self._check_mail_limit():
                    break
                self.status_updated.emit("购买中...", "#4caf50")
                self._step_executor.execute_workflow("e_adb_buy")
                if self._stop_requested:
                    return
                self._interruptible_sleep(2.0)
                if self._stop_requested:
                    return
                self._execute_card_mail()
                break
            else:
                logger.info("价格不合适: 目标%d < 游戏%d", target_price, game_price)

    def _execute_card_mail(self) -> None:
        self._step_executor.execute_workflow("after_buy")
        if self._stop_requested:
            return

        self._step_executor.execute_workflow("begin")
        if self._stop_requested:
            return

        frame = self._get_current_frame()
        if frame is None:
            self.error_occurred.emit("获取屏幕帧失败，卡邮件流程中断")
            return

        is_ru = self._check_template(frame, "kai_1.jpg")
        is_kai = self._check_template(frame, "kai_2.jpg")
        scheme_workflow = self._get_user_scheme_workflow()

        if is_ru:
            self._step_executor.execute_workflow("ru_run_1")
            if self._stop_requested:
                return

            self._step_executor.execute_workflow(scheme_workflow)
            if self._stop_requested:
                return

            result = self._step_executor.execute_workflow("ru_run_2")
            if self._stop_requested:
                return

            if result:
                self._increment_mail_count()

            self._step_executor.execute_workflow("fin")
            if self._stop_requested:
                return

            self._step_executor.execute_workflow(scheme_workflow)

        elif is_kai:
            self._step_executor.execute_workflow("kaishi")
            if self._stop_requested:
                return

            self._step_executor.execute_workflow(scheme_workflow)

        self._cycle_count += 1
        self.cycle_completed.emit(self._cycle_count)

    def _recover_game(self) -> None:
        self._step_executor.execute_workflow("restart")
        if self._stop_requested:
            return

        max_attempts: int = 30
        for _ in range(max_attempts):
            if self._stop_requested:
                return
            self._interruptible_sleep(1.0)
            if self._stop_requested:
                return

            frame = self._get_current_frame()
            if frame is None:
                continue

            is_dl = self._check_template(frame, "dl.jpg")
            is_ru = self._check_template(frame, "kai_1.jpg")
            is_kai = self._check_template(frame, "kai_2.jpg")

            if is_dl or is_ru or is_kai:
                if is_ru:
                    self._step_executor.execute_workflow("ru_run")
                elif is_kai:
                    self._step_executor.execute_workflow("kai_run")
                elif is_dl:
                    self._interruptible_sleep(1.0)
                    frame2 = self._get_current_frame()
                    if frame2 is not None and self._check_template(frame2, "dl.jpg"):
                        self._step_executor.execute_workflow("dl_run")
                return

        logger.warning("恢复游戏超时")
        self.error_occurred.emit("恢复游戏超时")


class WorkflowEngine(QObject):
    price_updated = pyqtSignal(int)
    mail_count_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str, str)
    cycle_completed = pyqtSignal(int)
    error_occurred = pyqtSignal(str)

    def __init__(self, config_manager: ConfigManager, step_executor: StepExecutor,
                 ocr_engine: OcrEngine, device_manager: DeviceManager, parent=None):
        super().__init__(parent)
        self._config_manager = config_manager
        self._step_executor = step_executor
        self._ocr_engine = ocr_engine
        self._device_manager = device_manager
        self._thread: Optional[QThread] = None
        self._worker: Optional[_WorkflowWorker] = None
        self._current_price: int = 0
        self._mail_count: int = 0

    def start(self) -> None:
        if self.is_running():
            return

        self._thread = QThread()
        self._worker = _WorkflowWorker(
            self._config_manager, self._step_executor,
            self._ocr_engine, self._device_manager
        )
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._worker.price_updated.connect(self.price_updated.emit)
        self._worker.mail_count_updated.connect(self.mail_count_updated.emit)
        self._worker.status_updated.connect(self.status_updated.emit)
        self._worker.cycle_completed.connect(self.cycle_completed.emit)
        self._worker.error_occurred.connect(self.error_occurred.emit)

        self._worker.price_updated.connect(self._on_price_updated)
        self._worker.mail_count_updated.connect(self._on_mail_count_updated)

        self._thread.start()

    def stop(self) -> None:
        if self._worker is not None:
            self._worker.request_stop()
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(5000)
        self._worker = None
        self._thread = None

    def pause(self) -> None:
        if self._worker is not None:
            self._worker.request_pause()

    def resume(self) -> None:
        if self._worker is not None:
            self._worker.request_resume()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def get_current_price(self) -> int:
        return self._current_price

    def get_mail_count(self) -> int:
        return self._mail_count

    def reset_mail_count(self) -> None:
        self._mail_count = 0
        if self._worker is not None:
            self._worker.request_reset_mail_count()
        else:
            mail_count_file = self._config_manager.get_config("mail_params.mail_count_file", "you.txt")
            try:
                with open(mail_count_file, "w", encoding="utf-8") as f:
                    f.write("0")
            except OSError as e:
                logger.error("重置邮件数量失败: %s", e)
        self.mail_count_updated.emit(0)

    def _on_price_updated(self, price: int) -> None:
        self._current_price = price

    def _on_mail_count_updated(self, count: int) -> None:
        self._mail_count = count
