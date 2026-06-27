import logging
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
from ui.components.empty_state_widget import EmptyStateWidget, LoadingOverlay
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
        self._task_state = TaskStateManager(base_dir)
        self._floating_widget = FloatingWidget()
        self._floating_widget.hide()

        self._init_ui()
        self._init_logging()
        self._init_tray()
        self._connect_signals()
        self._setup_exception_handler()

        self._panels["workflow_editor"].load_workflows()
        self._panels["test"].load_workflows()
        self._restore_tasks()

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
        self._ss_empty.setParent(self._screenshot_picker)
        self._ss_empty.hide()

        # loading overlay
        self._loading_overlay = LoadingOverlay(parent=self)

        # Center split: stacked editors (left) + screenshot picker (right)
        center_splitter = QSplitter(Qt.Horizontal)
        center_splitter.addWidget(self._stacked)
        center_splitter.addWidget(self._screenshot_picker)
        center_splitter.setStretchFactor(0, 3)
        center_splitter.setStretchFactor(1, 2)
        center_splitter.setChildrenCollapsible(False)
        self._center_splitter = center_splitter

        # Auto-hide screenshot when current step has no coordinates
        if hasattr(self, '_update_screenshot_empty_state'):
            self._update_screenshot_empty_state()

        self._log_panel = LogPanel()

        # Main split: center area (top) + log panel (bottom)
        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.addWidget(center_splitter)
        main_splitter.addWidget(self._log_panel)
        main_splitter.setStretchFactor(0, 5)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([620, 180])
        main_splitter.setChildrenCollapsible(False)
        self._main_splitter = main_splitter

        body_layout.addWidget(self._sidebar)
        body_layout.addWidget(main_splitter, stretch=1)

        outer.addWidget(body, stretch=1)

        # Restore persisted UI state (sidebar & splitters) if available
        try:
            if os.path.exists(ui_state_path):
                with open(ui_state_path, "r", encoding="utf-8") as f:
                    ui_state = __import__("json").load(f)
                self._center_splitter.setSizes(ui_state.get("center_splitter_sizes", self._center_splitter.sizes()))
                self._main_splitter.setSizes(ui_state.get("main_splitter_sizes", self._main_splitter.sizes()))
        except Exception:
            pass

        self._init_status_bar()

    def _save_ui_state(self):
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ui_state_path = os.path.join(base_dir, "config", "ui_state.json")
            data = {}
            if os.path.exists(ui_state_path):
                with open(ui_state_path, "r", encoding="utf-8") as f:
                    data = __import__("json").load(f)
            data.update({
                "sidebar_collapsed": bool(getattr(self._sidebar, "is_collapsed", lambda: False)()),
                "center_splitter_sizes": self._center_splitter.sizes(),
                "main_splitter_sizes": self._main_splitter.sizes(),
            })
            os.makedirs(os.path.dirname(ui_state_path), exist_ok=True)
            tmp = ui_state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                __import__("json").dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, ui_state_path)
        except Exception:
            pass

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
        dialog = WorkflowManagerDialog(self._config_manager, self)
        dialog.exec_()
        self._workflow_switcher.refresh()
        self._panels["workflow_editor"].load_workflows()
        self._panels["test"].load_workflows()
        self._refresh_preview()

    def _on_workflow_switched(self, name: str):
        self._task_state.update_task(self._task_bar.current_task_id(), workflow=name)
        self._refresh_preview()
        self._save_task_snapshot()

    def _on_device_selected(self, serial: str, label: str):
        self._task_state.update_task(self._task_bar.current_task_id(), bound_device=serial)
        self._save_task_snapshot()

    def _on_device_rename_requested(self, serial: str, label: str):
        self._task_state.update_task(self._task_bar.current_task_id(), bound_device_label=label)
        self._save_task_snapshot()

    def _on_step_selected(self, row: int):
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
        wf = self._panels["workflow_editor"]
        if not hasattr(wf, "_current_workflow_name") or not wf._current_workflow_name:
            return
        workflow = self._config_manager.get_workflow(wf._current_workflow_name)
        if not workflow:
            return
        steps = workflow.get("steps", [])
        if index >= len(steps):
            return
        steps[index]["enabled"] = not steps[index].get("enabled", True)
        workflow["steps"] = steps
        self._config_manager.set_workflow(wf._current_workflow_name, workflow)
        wf.refresh_step_list()
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

    def keyPressEvent(self, event):
        from PyQt5.QtCore import Qt
        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key_B and mods == Qt.ControlModifier:
            self._sidebar.toggle()
        elif key == Qt.Key_L and mods == (Qt.ControlModifier | Qt.ShiftModifier):
            self._toggle_log_panel()
        else:
            super().keyPressEvent(event)

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
        self._workflow_switcher.blockSignals(True)
        self._workflow_switcher.set_current_workflow(state.get("workflow", ""))
        self._workflow_switcher.blockSignals(False)
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
        self._screenshot_picker.point_selected.connect(self._on_screenshot_point_selected)
        self._sidebar.step_preview.step_copy_requested.connect(self._on_step_copy)
        self._sidebar.step_preview.step_delete_requested.connect(self._on_step_delete)
        self._sidebar.step_preview.step_toggle_enabled.connect(self._on_step_toggle_enabled)
        self._panels["workflow_editor"].workflow_saved.connect(self._on_external_workflow_saved)

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
        if hasattr(self, '_ss_empty') and self._screenshot_picker:
            self._ss_empty.resize(self._screenshot_picker.size())
        if hasattr(self, '_loading_overlay'):
            self._loading_overlay.resize(self.size())

    def closeEvent(self, event):
        self._save_task_snapshot()
        if self._quitting:
            event.accept()
            return
        event.ignore()
        self.hide()

    def _shutdown(self):
        try:
            self._step_executor.stop()
        except Exception:
            pass


