import logging
import json
import os
import sys
import traceback

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QStackedWidget,
    QStatusBar, QLabel, QSystemTrayIcon,
    QMenu, QAction, QSizePolicy, QApplication, QSplitter,
    QDialog, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QThread
from PyQt5.QtGui import QIcon, QFont

from core.config_manager import ConfigManager
from core.adb_core import AdbCore, _adb
from core.device_manager import DeviceManager
from core.screen_capture import ScrcpyCapture
from core.ocr_engine import OcrEngine
from core.step_executor import StepExecutor
from core.logger import setup_logging
from ui.panels.log_panel import LogPanel, QtLogHandler
from ui.panels.workflow_panel import WorkflowPanel
from ui.panels.config_panel import ConfigPanel
from ui.panels.device_panel import DevicePanel
from ui.panels.status_panel import StatusPanel
from ui.panels.test_panel import TestPanel
import os
import sys
import traceback

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QStackedWidget,
    QStatusBar, QLabel, QSystemTrayIcon,
    QMenu, QAction, QSizePolicy, QApplication, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QThread
from PyQt5.QtGui import QIcon, QFont

from core.config_manager import ConfigManager
from core.adb_core import AdbCore, _adb
from core.device_manager import DeviceManager
from core.screen_capture import ScrcpyCapture
from core.ocr_engine import OcrEngine
from core.step_executor import StepExecutor
from core.script_runner import ScriptRunner
from core.logger import setup_logging
from ui.panels.log_panel import LogPanel, QtLogHandler
from ui.panels.workflow_panel import WorkflowPanel
from ui.panels.config_panel import ConfigPanel
from ui.panels.device_panel import DevicePanel
from ui.panels.status_panel import StatusPanel
from ui.panels.test_panel import TestPanel
from ui.components.step_list_widget import StepListWidget
from ui.components.float_widget import FloatingWidget
from ui.components.task_tab_bar import TaskTabBar
from ui.components.sidebar_widget import SidebarWidget
from ui.components.screenshot_picker import ScreenshotPicker
from ui.components.empty_state_widget import LoadingOverlay
from ui.components.toast_notification import ToastManager
from ui.dialogs.workflow_manager_dialog import WorkflowManagerDialog
from core.task_state_manager import TaskStateManager


class _WorkflowWorker(QThread):
    finished_signal = pyqtSignal()

    def __init__(self, step_executor, workflow_name, parent=None):
        super().__init__(parent)
        self._step_executor = step_executor
        self._workflow_name = workflow_name

    def run(self):
        self._step_executor.execute_workflow(self._workflow_name, 0)
        self.finished_signal.emit()


class MainWindow(QMainWindow):
    nav_changed = pyqtSignal(int)

    NAV_ITEMS = [
        ("工作流编辑", "workflow_editor"),
        ("配置", "configuration"),
        ("设备管理", "device_management"),
        ("运行监控", "status_monitor"),
        ("测试", "test"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tray_icon = None
        self._workflow_worker = None
        self._quitting = False
        self._in_pickup_mode = False

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._config_manager = ConfigManager(base_dir)
        self._adb_core = _adb
        self._device_manager = DeviceManager(parent=self)
        self._screen_capture = ScrcpyCapture(parent=self)
        self._screen_capture.connection_lost.connect(lambda: self.set_connection_status(False))
        self._screen_capture.connection_restored.connect(lambda: self.set_connection_status(True))
        self._screen_capture.error_occurred.connect(lambda msg: logging.error("投屏错误: %s", msg))
        self._ocr_engine = OcrEngine()
        self._step_executor = StepExecutor(
            self._config_manager, self._adb_core,
            self._screen_capture, self._ocr_engine,
            self._device_manager, parent=self
        )
        self._script_runner = ScriptRunner(self._step_executor, parent=self)
        self._task_state = TaskStateManager(base_dir)
        self._floating_widget = FloatingWidget()
        self._floating_widget.hide()
        self._toast = ToastManager(parent=self)

        self._init_ui()
        self._init_logging()
        self._init_tray()
        self._connect_signals()
        self._setup_shortcuts()
        self._setup_accessibility()
        self._setup_exception_handler()

        self._panels["workflow_editor"].load_workflows()
        self._panels["test"].load_workflows()
        self._restore_tasks()
        # 在初始化完成后连接面板→侧边栏同步，避免 load_workflows 触发误保存
        self._panels["workflow_editor"].workflow_selected.connect(self._on_panel_workflow_selected)
        self._panels["workflow_editor"].step_deleted.connect(lambda _: self._refresh_preview())

    def _init_ui(self):
        self.setWindowTitle("三角洲自动抢购工具 v2.0")
        self.setMinimumSize(1200, 800)

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ui_state_path = os.path.join(base_dir, "config", "ui_state.json")

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._task_bar = TaskTabBar()
        outer.addWidget(self._task_bar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # -- collapsible sidebar
        self._sidebar = SidebarWidget(
            self._device_manager, self._adb_core,
            self._config_manager, ui_state_path=ui_state_path
        )
        self._sidebar.setFixedWidth(260)
        self._device_bind = self._sidebar.device_bind
        self._workflow_switcher = self._sidebar.workflow_switcher
        self._step_preview = self._sidebar.step_preview

        self._stacked = QStackedWidget()
        self._panels = {
            "workflow_editor": WorkflowPanel(self._config_manager, self._screen_capture, device_manager=self._device_manager),
            "configuration": ConfigPanel(self._config_manager),
            "device_management": DevicePanel(self._device_manager, self._adb_core),
            "status_monitor": StatusPanel(),
            "test": TestPanel(self._step_executor, self._config_manager),
        }
        for _, key in self.NAV_ITEMS:
            self._stacked.addWidget(self._panels[key])

        self._screenshot_picker = ScreenshotPicker(
            screen_capture=self._screen_capture,
            device_manager=self._device_manager,
            config_manager=self._config_manager,
        )

        # empty state for screenshot area
        self._ss_empty = EmptyStateWidget(
            icon="📷",
            message="暂无截图",
            hint="选择坐标步骤后自动截图"
        )
        self._screenshot_picker.setMinimumWidth(400)


        # loading overlay
        self._loading_overlay = LoadingOverlay(parent=self)

        # Center split: stacked editors (left) + screenshot picker (right)
        center_splitter = QSplitter(Qt.Horizontal)
        center_splitter.addWidget(self._stacked)
        center_splitter.addWidget(self._screenshot_picker)
        center_splitter.setStretchFactor(0, 5)
        center_splitter.setStretchFactor(1, 3)
        center_splitter.setChildrenCollapsible(False)
        self._center_splitter = center_splitter


        self._log_panel = LogPanel()

        # Main split: stacked panels (top) + log panel (bottom)
        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.addWidget(self._stacked)
        main_splitter.addWidget(self._log_panel)
        main_splitter.setStretchFactor(0, 5)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([720, 160])
        main_splitter.setChildrenCollapsible(False)
        self._main_splitter = main_splitter

        body_layout.addWidget(self._sidebar)
        body_layout.addWidget(main_splitter, stretch=1)

        outer.addWidget(body, stretch=1)

        # Restore persisted UI state if available
        try:
            if os.path.exists(ui_state_path):
                with open(ui_state_path, "r", encoding="utf-8") as f:
                    ui_state = json.load(f)
                self._center_splitter.setSizes(ui_state.get("center_splitter_sizes", self._center_splitter.sizes()))
                self._main_splitter.setSizes(ui_state.get("main_splitter_sizes", self._main_splitter.sizes()))
                self._panels["workflow_editor"].set_right_splitter_sizes(
                    ui_state.get("right_splitter_sizes", [])
                )
                self._panels["workflow_editor"].set_splitter_sizes(
                    ui_state.get("wf_splitter_sizes", [])
                )
        except Exception as e:
            logging.warning("UI 状态恢复失败，使用默认值: %s", e)

        self._init_status_bar()

    def _save_ui_state(self):
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ui_state_path = os.path.join(base_dir, "config", "ui_state.json")
            data = {}
            if os.path.exists(ui_state_path):
                with open(ui_state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data.update({
                "sidebar_collapsed": bool(getattr(self._sidebar, "is_collapsed", lambda: False)()),
                "main_splitter_sizes": self._main_splitter.sizes(),
                "right_splitter_sizes": self._panels["workflow_editor"].get_right_splitter_sizes(),
                "wf_splitter_sizes": self._panels["workflow_editor"].get_splitter_sizes(),
            })
            os.makedirs(os.path.dirname(ui_state_path), exist_ok=True)
            tmp = ui_state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, ui_state_path)
        except Exception as e:
            logging.warning("UI 状态保存失败: %s", e)

    def _restore_tasks(self):
        snapshot = self._task_state.load_snapshot()
        if not snapshot:
            self._create_task()
            return

        tasks = snapshot.get("tasks", [])
        active_id = snapshot.get("active_task_id")
        if not tasks:
            self._create_task()
            return

        for task in tasks:
            task_id = task.get("id", "")
            title = task.get("title", "")
            self._task_bar.add_task(task_id, title)
            self._task_state.update_task(task_id, title=title, workflow=task.get("workflow", ""), bound_device=task.get("bound_device", ""), selected_step_index=task.get("selected_step_index", 0))

        if active_id and self._task_bar.set_active_task(active_id):
            self._apply_active_task()
        else:
            self._task_bar.setCurrentIndex(0)
            self._apply_active_task()
        self._save_task_snapshot()

    def _create_task(self):
        task_id = self._task_state.next_task_id()
        title = self._task_state.next_task_title()
        self._task_state.update_task(task_id, title=title)
        self._task_bar.add_task(task_id, title)
        self._task_bar.set_active_task(task_id)
        self._apply_active_task()
        self._save_task_snapshot()

    def _on_settings(self):
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("设置")
        dlg.setMinimumSize(800, 600)
        layout = QVBoxLayout(dlg)
        tabs = QTabWidget()
        tabs.addTab(self._panels["configuration"], "配置")
        tabs.addTab(self._panels["device_management"], "设备管理")
        layout.addWidget(tabs)
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.accepted.connect(dlg.accept)
        layout.addWidget(btn_box)
        dlg.exec_()
        # 把面板从 QTabWidget 取出并重新挂回 stacked，避免随对话框一起被销毁
        # （addTab 会把 widget 重新 parent 到 QTabWidget，对话框关闭时会被一并销毁）
        tabs.removeTab(tabs.indexOf(self._panels["configuration"]))
        tabs.removeTab(tabs.indexOf(self._panels["device_management"]))
        if self._stacked.indexOf(self._panels["configuration"]) < 0:
            self._stacked.insertWidget(1, self._panels["configuration"])
        if self._stacked.indexOf(self._panels["device_management"]) < 0:
            self._stacked.insertWidget(2, self._panels["device_management"])

    def _on_switch_task(self, index: int):
        self._apply_active_task()
        self._save_task_snapshot()

    def _on_close_task(self, index: int):
        task_id, title = self._task_bar.task_at(index)
        if self._task_bar.count() <= 1:
            QApplication.beep()
            return
        from PyQt5.QtWidgets import QMessageBox
        if QMessageBox.question(self, "关闭任务", f"确定关闭任务《{title}》吗？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self._task_state.remove_task(task_id)
        self._task_bar.remove_task(index)
        self._apply_active_task()
        self._save_task_snapshot()

    def _on_manage_workflows(self):
        current_wf = self._workflow_switcher.current_workflow()
        dialog = WorkflowManagerDialog(self._config_manager, current_wf, self)
        dialog.exec_()
        self._workflow_switcher.refresh()
        self._panels["workflow_editor"].load_workflows()
        self._panels["test"].load_workflows()
        self._refresh_preview()

    def _sync_workflow_panel(self, name: str):
        """将工作流面板的方案选择与给定名称同步（屏蔽信号避免回环）。"""
        wf_panel = self._panels["workflow_editor"]
        if hasattr(wf_panel, "_workflow_combo"):
            wf_panel._workflow_combo.blockSignals(True)
            idx = wf_panel._workflow_combo.findText(name)
            if idx >= 0:
                wf_panel._workflow_combo.setCurrentIndex(idx)
            wf_panel._workflow_combo.blockSignals(False)
            wf_panel._current_workflow_name = name
            wf_panel.refresh_step_list()
            if hasattr(wf_panel, "_step_editor"):
                wf_panel._step_editor.clear_step()

    def _on_workflow_switched(self, name: str):
        self._task_state.update_task(self._task_bar.current_task_id(), workflow=name)
        self._sync_workflow_panel(name)
        self._refresh_preview()
        self._save_task_snapshot()

    def _on_panel_workflow_selected(self, name: str):
        """工作流面板切换方案时，同步侧边栏方案选择器。"""
        self._workflow_switcher.blockSignals(True)
        self._workflow_switcher.set_current_workflow(name)
        self._workflow_switcher.blockSignals(False)
        self._task_state.update_task(self._task_bar.current_task_id(), workflow=name)
        self._refresh_preview()
        self._save_task_snapshot()

    def _on_device_selected(self, serial: str, label: str):
        self._task_state.update_task(self._task_bar.current_task_id(), bound_device=serial)
        self._save_task_snapshot()

        # 自动启动屏幕采集和投屏
        if serial:
            self._start_screen_capture(serial)

    def _on_device_rename_requested(self, serial: str, label: str):
        self._task_state.update_task(self._task_bar.current_task_id(), bound_device_label=label)
        self._save_task_snapshot()

    def _start_screen_capture(self, serial: str):
        """启动屏幕采集和投屏。"""
        if not serial:
            return

        # 读取 scrcpy_server_path 配置
        server_jar = self._config_manager.get_config("device.scrcpy_server_path", "")
        if not server_jar:
            server_jar = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "lib", "scrcpy-server.jar"
            )

        # 启动屏幕采集（如果尚未运行）
        if not self._screen_capture.is_running():
            self._screen_capture.start(
                serial=serial, server_jar_path=server_jar
            )
            logging.info("屏幕采集已启动: %s", serial)

        # 启动投屏组件
        self._screenshot_picker.start(serial)
        self._notify_mirror_state(True)

    def _stop_screen_capture(self):
        """停止屏幕采集和投屏。"""
        try:
            self._screenshot_picker.stop()
        except Exception as e:
            logging.warning("投屏组件停止失败: %s", e)
        try:
            self._screen_capture.stop()
        except Exception as e:
            logging.warning("屏幕采集停止失败: %s", e)
        self._notify_mirror_state(False)

    def _notify_mirror_state(self, active: bool):
        """通知侧边栏投屏状态变化。"""
        self._sidebar.set_mirror_active(active)

    def _on_open_mirror(self, serial: str):
        """切换高清投屏（投屏中则停止，否则启动）。"""
        if not serial:
            self._toast.warning("未选择设备，无法打开投屏")
            return

        if self._screen_capture.is_running():
            self._stop_screen_capture()
            logging.info("高清投屏已停止: %s", serial)
        else:
            self._start_screen_capture(serial)
            logging.info("高清投屏已启动: %s", serial)

    def _on_step_selected(self, row: int):
        self._exit_pickup_mode()
        self._task_state.update_task(self._task_bar.current_task_id(), selected_step_index=max(0, row))
        self._save_task_snapshot()

    def _on_step_copy(self, index: int):
        wf = self._panels["workflow_editor"]
        if hasattr(wf, "_step_list"):
            wf._step_list.setCurrentRow(index)
            wf.copy_step()

    def _on_step_delete(self, index: int):
        wf = self._panels["workflow_editor"]
        if hasattr(wf, "_step_list"):
            wf._step_list.setCurrentRow(index)
            wf.delete_step()

    def _on_step_toggle_enabled(self, index: int):
        self._panels["workflow_editor"].toggle_step_enabled(index)
        self._refresh_preview()

    def _update_screenshot_empty_state(self):
        wf = self._panels["workflow_editor"]
        if not hasattr(wf, "_step_list"):
            return
        row = wf._step_list.currentRow()
        if row < 0:
            self._ss_empty.show()
            return
        steps = []
        if hasattr(wf, "_current_workflow_name") and wf._current_workflow_name:
            data = self._config_manager.get_workflow(wf._current_workflow_name)
            if data:
                steps = data.get("steps", [])
        if row < len(steps):
            step = steps[row]
            coord_types = {"tap", "long_press", "swipe", "tap_point"}
            if step.get("type", "") in coord_types:
                self._ss_empty.hide()
            else:
                self._ss_empty.set_state(
                    icon="⚠",
                    message="当前步骤无坐标",
                    hint="选择点击/滑动类型步骤"
                )
                self._ss_empty.show()
        else:
            self._ss_empty.show()

    def _on_screenshot_point_selected(self, x: int, y: int):
        wf_panel = self._panels["workflow_editor"]
        if hasattr(wf_panel, "_step_editor"):
            wf_panel._step_editor.update_coord_fields(x, y)

    def _on_pickup_requested(self, sync_tap: bool):
        """StepEditor 请求进入坐标选择模式。"""
        self._in_pickup_mode = True
        self._screenshot_picker.enter_pickup_mode()

    def _on_pickup_completed(self, x: int, y: int):
        """坐标选择模式完成 — 写入坐标并可选执行 tap。"""
        # 写入坐标到 StepEditor
        wf_panel = self._panels["workflow_editor"]
        if hasattr(wf_panel, "_step_editor"):
            wf_panel._step_editor.update_coord_fields(x, y)

        # 如果勾选了同步 tap，通过 ADB 在手机上执行
        if hasattr(wf_panel, "_step_editor") and wf_panel._step_editor.is_sync_tap_checked():
            try:
                self._adb_core.tap(x, y)
                logging.info("坐标选择模式: 同步执行 tap(%d, %d)", x, y)
            except Exception as e:
                logging.error("坐标选择模式: 同步 tap 失败: %s", e)

        # 退出选点模式
        self._exit_pickup_mode()

    def _exit_pickup_mode(self):
        """退出坐标选择模式。"""
        if not self._in_pickup_mode:
            return
        self._in_pickup_mode = False
        self._screenshot_picker.exit_pickup_mode()
        wf_panel = self._panels["workflow_editor"]
        if hasattr(wf_panel, "_step_editor"):
            wf_panel._step_editor.exit_pickup_mode()

    def _setup_shortcuts(self):
        """设置全局快捷键。"""
        from PyQt5.QtGui import QKeySequence

        # Ctrl+1~5 切换面板
        for i, (_, key) in enumerate(self.NAV_ITEMS, 1):
            shortcut = QAction(self)
            shortcut.setShortcut(QKeySequence(f"Ctrl+{i}"))
            shortcut.triggered.connect(lambda checked, k=key: self._switch_panel(k))
            self.addAction(shortcut)

        # Ctrl+N 新建任务
        act_new_task = QAction(self)
        act_new_task.setShortcut(QKeySequence("Ctrl+N"))
        act_new_task.triggered.connect(self._create_task)
        self.addAction(act_new_task)

        # Ctrl+S 保存
        act_save = QAction(self)
        act_save.setShortcut(QKeySequence("Ctrl+S"))
        act_save.triggered.connect(self._save_all)
        self.addAction(act_save)

        # Ctrl+Z 撤销（转发到工作流面板）
        act_undo = QAction(self)
        act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        act_undo.triggered.connect(lambda: self._panels["workflow_editor"]._undo())
        self.addAction(act_undo)

        # Ctrl+Y 重做
        act_redo = QAction(self)
        act_redo.setShortcut(QKeySequence("Ctrl+Y"))
        act_redo.triggered.connect(lambda: self._panels["workflow_editor"]._redo())
        self.addAction(act_redo)

        # Ctrl+D 复制步骤
        act_copy = QAction(self)
        act_copy.setShortcut(QKeySequence("Ctrl+D"))
        act_copy.triggered.connect(lambda: self._panels["workflow_editor"].copy_step())
        self.addAction(act_copy)

        # Delete 删除步骤
        act_delete = QAction(self)
        act_delete.setShortcut(QKeySequence("Delete"))
        act_delete.triggered.connect(lambda: self._panels["workflow_editor"].delete_step())
        self.addAction(act_delete)

        # Space 切换步骤启用/禁用
        act_toggle = QAction(self)
        act_toggle.setShortcut(QKeySequence("Space"))
        act_toggle.triggered.connect(self._toggle_step_enabled)
        self.addAction(act_toggle)

        # F1 显示快捷键帮助
        act_help = QAction(self)
        act_help.setShortcut(QKeySequence("F1"))
        act_help.triggered.connect(self._show_shortcut_help)
        self.addAction(act_help)

        # Esc 退出坐标选择模式
        act_esc = QAction(self)
        act_esc.setShortcut(QKeySequence("Escape"))
        act_esc.triggered.connect(self._exit_pickup_mode)
        self.addAction(act_esc)

    def _switch_panel(self, panel_key: str):
        """切换到指定面板（带淡入淡出过渡）。"""
        for i, (_, key) in enumerate(self.NAV_ITEMS):
            if key == panel_key:
                if self._stacked.currentIndex() == i:
                    return
                # 淡出当前面板
                from PyQt5.QtWidgets import QGraphicsOpacityEffect
                current_widget = self._stacked.currentWidget()
                if current_widget:
                    effect = QGraphicsOpacityEffect(current_widget)
                    current_widget.setGraphicsEffect(effect)
                    fade_out = QPropertyAnimation(effect, b"opacity")
                    fade_out.setDuration(150)
                    fade_out.setStartValue(1.0)
                    fade_out.setEndValue(0.0)
                    fade_out.setEasingCurve(QEasingCurve.InOutCubic)

                    def do_switch():
                        self._stacked.setCurrentIndex(i)
                        new_widget = self._stacked.currentWidget()
                        if new_widget:
                            new_effect = QGraphicsOpacityEffect(new_widget)
                            new_widget.setGraphicsEffect(new_effect)
                            fade_in = QPropertyAnimation(new_effect, b"opacity")
                            fade_in.setDuration(200)
                            fade_in.setStartValue(0.0)
                            fade_in.setEndValue(1.0)
                            fade_in.setEasingCurve(QEasingCurve.InOutCubic)
                            fade_in.start()
                            # 保持引用防止 GC
                            self._fade_in_anim = fade_in
                            self._fade_in_effect = new_effect

                    fade_out.finished.connect(do_switch)
                    fade_out.start()
                    # 保持引用
                    self._fade_out_anim = fade_out
                    self._fade_out_effect = effect
                else:
                    self._stacked.setCurrentIndex(i)
                return

    def _save_all(self):
        """保存所有配置。"""
        try:
            self._config_manager.save_config()
            self._save_task_snapshot()
            self._save_ui_state()
            self._panels["workflow_editor"]._clear_undo_redo()
            self._toast.success("所有配置已保存")
        except Exception as e:
            self._toast.error(f"保存失败: {e}")

    def _toggle_step_enabled(self):
        """切换当前步骤的启用/禁用状态。"""
        wf = self._panels["workflow_editor"]
        row = wf.get_current_step_index()
        if row >= 0:
            self._on_step_toggle_enabled(row)

    def _show_shortcut_help(self):
        """显示快捷键帮助面板。"""
        dlg = QDialog(self)
        dlg.setWindowTitle("快捷键帮助")
        dlg.setMinimumSize(450, 500)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("键盘快捷键")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title.setStyleSheet("color: #58a6ff;")
        layout.addWidget(title)

        shortcuts = [
            ("面板切换", ""),
            ("  Ctrl+1", "切换到工作流编辑"),
            ("  Ctrl+2", "切换到配置"),
            ("  Ctrl+3", "切换到设备管理"),
            ("  Ctrl+4", "切换到运行监控"),
            ("  Ctrl+5", "切换到测试"),
            ("", ""),
            ("任务管理", ""),
            ("  Ctrl+N", "新建任务"),
            ("  Ctrl+S", "保存所有配置"),
            ("", ""),
            ("步骤编辑", ""),
            ("  Ctrl+D", "复制选中步骤"),
            ("  Delete", "删除选中步骤"),
            ("  Space", "切换步骤启用/禁用"),
            ("  Ctrl+Z", "撤销"),
            ("  Ctrl+Y", "重做"),
            ("", ""),
            ("界面控制", ""),
            ("  Ctrl+B", "折叠/展开侧边栏"),
            ("  Ctrl+Shift+L", "显示/隐藏日志面板"),
            ("  F1", "显示本帮助"),
        ]

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet(
            "QTextEdit { background-color: #0d1117; color: #e6edf3; "
            "font-family: Consolas, 'Microsoft YaHei'; font-size: 12px; "
            "border: 1px solid #30363d; border-radius: 4px; }"
        )
        help_text = ""
        for key, desc in shortcuts:
            if not key and not desc:
                help_text += "\n"
            elif not desc:
                help_text += f"\n<b>{key}</b>\n"
            else:
                help_text += f"  <span style='color: #58a6ff;'>{key:<20}</span> {desc}\n"
        text_edit.setHtml(help_text)
        layout.addWidget(text_edit, stretch=1)

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close)

        dlg.exec_()

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key_B and mods == Qt.ControlModifier:
            self._sidebar.toggle()
        elif key == Qt.Key_L and mods == (Qt.ControlModifier | Qt.ShiftModifier):
            self._toggle_log_panel()
        else:
            super().keyPressEvent(event)

    def _switch_panel(self, panel_key: str):
        """切换 _stacked 显示的面板，并更新导航栏选中状态。"""
        panel = self._panels.get(panel_key)
        if panel is None:
            return
        self._stacked.setCurrentWidget(panel)
        for key, btn in self._nav_buttons.items():
            btn.setChecked(key == panel_key)
        self.nav_changed.emit(self._stacked.currentIndex())
        # 主流程面板切换时刷新数据
        if panel_key == "main_flow" and hasattr(panel, "load_main_flow"):
            panel.load_main_flow()

    def _toggle_log_panel(self):
        sizes = self._main_splitter.sizes()
        if sizes[1] > 10:
            self._main_splitter.setSizes([sizes[0] + sizes[1], 0])
        else:
            self._main_splitter.setSizes([620, 180])
        self._save_ui_state()

    def _apply_active_task(self):
        task_id = self._task_bar.current_task_id()
        state = self._task_state.get_task(task_id)
        if not state:
            return
        workflow_name = state.get("workflow", "")
        self._workflow_switcher.blockSignals(True)
        self._workflow_switcher.set_current_workflow(workflow_name)
        self._workflow_switcher.blockSignals(False)
        self._sync_workflow_panel(workflow_name)
        self._device_bind.blockSignals(True)
        self._device_bind.set_bound_device(state.get("bound_device", ""), state.get("bound_device_label", ""))
        self._device_bind.blockSignals(False)
        self._refresh_preview()
        row = state.get("selected_step_index", 0)
        if 0 <= row < self._step_preview.count():
            self._step_preview.blockSignals(True)
            self._step_preview.setCurrentRow(row)
            self._step_preview.blockSignals(False)

    def _refresh_preview(self):
        workflow = self._workflow_switcher.current_workflow()
        if workflow:
            data = self._config_manager.get_workflow(workflow)
            self._step_preview.load_steps(data.get("steps", []))
        else:
            self._step_preview.load_steps([])

    def _save_task_snapshot(self):
        snapshot = {
            "active_task_id": self._task_bar.current_task_id(),
            "tasks": []
        }
        for task_id, title in self._task_bar.iter_tasks():
            state = self._task_state.get_task(task_id)
            snapshot["tasks"].append({
                "id": task_id,
                "title": title,
                "workflow": state.get("workflow", ""),
                "bound_device": state.get("bound_device", ""),
                "bound_device_label": state.get("bound_device_label", ""),
                "selected_step_index": state.get("selected_step_index", 0)
            })
        self._task_state.save_snapshot(snapshot)

    def _init_status_bar(self):
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        self._device_label = QLabel("设备: 未连接")
        self._connection_label = QLabel("连接: 断开")
        self._ocr_label = QLabel("OCR: 未加载")

        for label in (self._device_label, self._connection_label, self._ocr_label):
            label.setFont(QFont("Microsoft YaHei", 10))
            status_bar.addPermanentWidget(label)

    def _init_logging(self):
        handler = QtLogHandler(self)
        handler.log_signal.connect(self._log_panel._append_log)
        setup_logging(qt_handler=handler)

    def _init_tray(self):
        self._tray_icon = QSystemTrayIcon(self)
        self._tray_icon.setIcon(self.style().standardIcon(self.style().SP_ComputerIcon))
        self._tray_icon.setToolTip("三角洲自动抢购工具 v2.0")

        tray_menu = QMenu()

        show_action = QAction("显示主窗口", self)
        hide_action = QAction("隐藏主窗口", self)
        quit_action = QAction("退出", self)

        tray_menu.addAction(show_action)
        tray_menu.addAction(hide_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.show()

    def _connect_signals(self):
        self._task_bar.task_switched.connect(self._on_switch_task)
        self._task_bar.task_close_requested.connect(self._on_close_task)
        self._task_bar.task_create_requested.connect(self._create_task)
        self._task_bar.settings_requested.connect(self._on_settings)
        self._sidebar.workflow_changed.connect(self._on_workflow_switched)
        self._sidebar.manage_requested.connect(self._on_manage_workflows)
        self._sidebar.device_selected.connect(self._on_device_selected)
        self._sidebar.rename_requested.connect(self._on_device_rename_requested)
        self._sidebar.step_clicked.connect(self._on_step_selected)
        self._sidebar.step_order_changed.connect(self._refresh_preview)
        self._sidebar.open_mirror_requested.connect(self._on_open_mirror)
        self._screenshot_picker.point_selected.connect(self._on_screenshot_point_selected)
        self._screenshot_picker.pickup_completed.connect(self._on_pickup_completed)
        self._sidebar.step_preview.step_copy_requested.connect(self._on_step_copy)
        self._sidebar.step_preview.step_delete_requested.connect(self._on_step_delete)
        self._sidebar.step_preview.step_toggle_enabled.connect(self._on_step_toggle_enabled)
        self._panels["workflow_editor"].workflow_saved.connect(self._on_external_workflow_saved)
        # 坐标选择模式
        wf_editor = self._panels["workflow_editor"]
        if hasattr(wf_editor, "_step_editor"):
            wf_editor._step_editor.pickup_requested.connect(self._on_pickup_requested)
        wf_editor.step_selected.connect(lambda _: self._exit_pickup_mode())

        tray_menu = self._tray_icon.contextMenu()
        actions = tray_menu.actions()
        actions[0].triggered.connect(self._on_tray_show)
        actions[1].triggered.connect(self._on_tray_hide)
        actions[3].triggered.connect(self._on_tray_quit)

        self._tray_icon.activated.connect(self._on_tray_activated)
        self._floating_widget.pause_requested.connect(self._on_pause_monitoring)
        self._floating_widget.stop_requested.connect(self._on_stop_monitoring)

        self._device_manager.device_changed.connect(self._on_device_changed)
        self._device_manager.connection_status_changed.connect(self._on_connection_status_changed)

        status_panel = self._panels["status_monitor"]
        status_panel.start_monitoring.connect(self._on_start_monitoring)
        status_panel.stop_monitoring.connect(self._on_stop_monitoring)
        status_panel.pause_monitoring.connect(self._on_pause_monitoring)
        status_panel.resume_monitoring.connect(self._on_resume_monitoring)

        self._step_executor.step_started.connect(self._on_step_started)
        self._step_executor.workflow_completed.connect(self._on_workflow_completed)
        self._step_executor.workflow_failed.connect(self._on_workflow_failed)
        self._step_executor.workflow_stopped.connect(self._on_workflow_stopped)

        # LogPanel 脚本控制按钮
        self._log_panel.request_run_from.connect(self._on_log_run_from)
        self._log_panel.request_run_full.connect(self._on_log_run_full)
        self._log_panel.request_stop.connect(self._on_log_stop)
        self._script_runner.run_started.connect(self._on_script_run_started)
        self._script_runner.run_finished.connect(self._on_script_run_finished)
        self._script_runner.workflow_failed.connect(
            lambda name, err: logging.error("\u811a\u672c\u5931\u8d25 %s - %s", name, err)
        )
        self._script_runner.workflow_stopped.connect(
            lambda: logging.info("\u811a\u672c\u5df2\u505c\u6b62")
        )

    def _on_log_run_from(self):
        wf = self._workflow_switcher.current_workflow()
        if not wf:
            self._toast.warning("\u672a\u9009\u62e9\u5de5\u4f5c\u6d41")
            return
        idx = self._panels["workflow_editor"].get_current_step_index()
        if idx < 0:
            idx = 0
            logging.info("\u672a\u9009\u4e2d\u6b65\u9aa4\uff0c\u4ece\u7b2c 1 \u6b65\u542f\u52a8")
        self._script_runner.run_from(wf, idx)

    def _on_log_run_full(self):
        wf = self._workflow_switcher.current_workflow()
        if not wf:
            self._toast.warning("\u672a\u9009\u62e9\u5de5\u4f5c\u6d41")
            return
        self._script_runner.run_full(wf)

    def _on_log_stop(self):
        self._script_runner.stop()

    def _on_script_run_started(self, name: str, idx: int):
        self._log_panel.set_running(True)
        logging.info("\u811a\u672c\u542f\u52a8 workflow=%s, start_index=%d", name, idx)

    def _on_script_run_finished(self):
        self._log_panel.set_running(False)
        logging.info("\u811a\u672c\u6267\u884c\u7ed3\u675f")

    def _on_external_workflow_saved(self, workflow_name: str):
        self._workflow_switcher.refresh()
        self._refresh_preview()
        self._save_task_snapshot()
        self._save_ui_state()

    def _setup_exception_handler(self):
        original_excepthook = sys.excepthook

        def exception_hook(exc_type, exc_value, exc_tb):
            tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            logging.critical("未处理的异常:\n%s", tb_text)
            try:
                self._log_panel._append_log(f"未处理的异常: {exc_value}", logging.ERROR)
            except Exception:
                pass
            logging.critical("未处理的异常:\n%s", tb_text)
            try:
                self._log_panel._append_log(f"未处理的异常: {exc_value}", logging.ERROR)
            except Exception:
                pass
            original_excepthook(exc_type, exc_value, exc_tb)

        sys.excepthook = exception_hook

    def _on_tray_show(self):
        self.showNormal()
        self.activateWindow()

    def _on_tray_hide(self):
        self.hide()

    def _on_tray_quit(self):
        self._quitting = True
        self._shutdown()
        self._tray_icon.hide()
        QApplication.instance().quit()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._on_tray_show()

    def _on_device_changed(self, serial: str):
        self.set_device_status(serial)

    def _on_connection_status_changed(self, connected: bool):
        self.set_connection_status(connected)

    def _on_start_monitoring(self):
        bound_device = self._task_state.get_task(self._task_bar.current_task_id()).get("bound_device", "")
        if not bound_device:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "无法启动", "请先在侧边栏选择设备后再启动。")
            return
        workflow_name = self._workflow_switcher.current_workflow()
        if not workflow_name:
            logging.warning("未选择工作流，无法启动监控")
            return
        if self._workflow_worker is not None and self._workflow_worker.isRunning():
            logging.warning("工作流正在运行中")
            return
        self._panels["workflow_editor"]._clear_undo_redo()
        self._workflow_worker = _WorkflowWorker(self._step_executor, workflow_name, parent=self)
        self._workflow_worker.finished_signal.connect(self._on_workflow_worker_finished)
        self._workflow_worker.start()
        self._panels["status_monitor"].update_status("运行中", "#00ff88")
        self._panels["status_monitor"].update_current_workflow(workflow_name)
        self._floating_widget.update_status("运行中", "#00ff88")
        self._floating_widget.show()
        logging.info("启动监控: %s", workflow_name)

    def _on_stop_monitoring(self):
        self._step_executor.stop()
        self._panels["status_monitor"].update_status("停止中.", "#ffaa00")
        self._floating_widget.update_status("停止中.", "#ffaa00")

    def _on_pause_monitoring(self):
        self._step_executor.pause()
        self._panels["status_monitor"].update_status("已暂停", "#ffaa00")
        self._floating_widget.update_status("已暂停", "#ffaa00")

    def _on_resume_monitoring(self):
        self._step_executor.resume()
        self._panels["status_monitor"].update_status("运行中", "#00ff88")
        self._floating_widget.update_status("运行中", "#00ff88")

    def _on_workflow_worker_finished(self):
        self._panels["status_monitor"].update_status("已完成", "#a0a0a0")
        self._floating_widget.update_status("已完成", "#a0a0a0")

    def set_device_status(self, serial: str):
        if serial:
            self._device_label.setText(f"设备: {serial}")
        else:
            self._device_label.setText("设备: 未连接")


    def set_connection_status(self, connected: bool):
        self._connection_label.setText("连接: 已连接" if connected else "连接: 断开")

    def _on_step_started(self, index: int, step_type: str):
        logging.info("步骤 %d 开始: %s", index + 1, step_type)

    def _on_workflow_completed(self, name: str):
        logging.info("工作流完成: %s", name)

    def _on_workflow_failed(self, name: str, error: str):
        logging.error("工作流失败: %s - %s", name, error)

    def _on_workflow_stopped(self):
        logging.info("工作流已停止")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_loading_overlay'):
            self._loading_overlay.resize(self.size())
        # 响应式布局：窗口宽度 < 900px 时自动折叠侧边栏
        if hasattr(self, '_sidebar'):
            if event.size().width() < 900 and not self._sidebar.is_collapsed():
                self._sidebar.toggle()
            elif event.size().width() >= 1000 and self._sidebar.is_collapsed():
                # 只在宽度恢复时自动展开（如果之前是自动折叠的）
                pass

    def _setup_accessibility(self):
        """设置可访问性属性。"""
        # 主窗口
        self.setAccessibleName("三角洲自动抢购工具主窗口")
        self.setAccessibleDescription("ADB自动化工作流编辑和执行工具")

        # 侧边栏
        if hasattr(self, '_sidebar'):
            self._sidebar.setAccessibleName("侧边栏")
            self._sidebar.setAccessibleDescription("设备绑定、方案切换和步骤预览区域")

        # 面板
        panel_descriptions = {
            "workflow_editor": "工作流编辑面板 - 编辑和管理工作流步骤",
            "configuration": "配置面板 - 设置购买参数、识别参数、设备参数等",
            "device_management": "设备管理面板 - 管理已连接的安卓设备",
            "status_monitor": "运行监控面板 - 实时监控工作流执行状态",
            "test": "测试面板 - 单步测试和全量运行工作流",
        }
        for key, panel in self._panels.items():
            panel.setAccessibleName(self.NAV_ITEMS[[k for k, _ in enumerate(self.NAV_ITEMS) if _[1] == key][0]][0])
            panel.setAccessibleDescription(panel_descriptions.get(key, ""))

        # 日志面板
        if hasattr(self, '_log_panel'):
            self._log_panel.setAccessibleName("日志面板")
            self._log_panel.setAccessibleDescription("显示应用运行日志，支持按级别过滤")

        # 状态栏
        if hasattr(self, '_device_label'):
            self._device_label.setAccessibleName("设备状态")
        if hasattr(self, '_connection_label'):
            self._connection_label.setAccessibleName("连接状态")
        if hasattr(self, '_ocr_label'):
            self._ocr_label.setAccessibleName("OCR引擎状态")

        # 任务标签栏
        if hasattr(self, '_task_bar'):
            self._task_bar.setAccessibleName("任务标签栏")
            self._task_bar.setAccessibleDescription("管理多个任务标签页，切换不同任务")

        # 悬浮窗
        if hasattr(self, '_floating_widget'):
            self._floating_widget.setAccessibleName("悬浮监控窗")
            self._floating_widget.setAccessibleDescription("显示运行状态、价格和邮件数，可拖拽移动")

    def closeEvent(self, event):
        self._save_task_snapshot()
        if self._quitting:
            event.accept()
            return
        event.ignore()
        self.hide()

    def _shutdown(self):
        """清理所有资源，准备退出。"""
        errors = []

        # 0. 停止投屏组件
        try:
            self._screenshot_picker.stop()
        except Exception as e:
            errors.append(f"投屏组件停止失败: {e}")

        # 1. 停止 step executor
        try:
            self._step_executor.stop()
        except Exception as e:
            errors.append(f"步骤执行器停止失败: {e}")

        # 2. 停止屏幕采集
        try:
            self._screen_capture.stop()
        except Exception as e:
            errors.append(f"屏幕采集停止失败: {e}")

        # 3. 保存配置
        try:
            self._config_manager.save_config()
        except Exception as e:
            errors.append(f"配置保存失败: {e}")

        # 4. 保存任务快照
        try:
            self._save_task_snapshot()
        except Exception as e:
            errors.append(f"任务快照保存失败: {e}")

        # 5. 保存 UI 状态
        try:
            self._save_ui_state()
        except Exception as e:
            errors.append(f"UI 状态保存失败: {e}")

        if errors:
            for err in errors:
                logging.warning("关闭清理: %s", err)
        else:
            logging.info("所有资源已清理")


