from PyQt5.QtWidgets import QWidget, QHBoxLayout, QTabBar, QPushButton, QLabel, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal


class TaskTabBar(QWidget):
    """顶部任务标签栏：左侧设置按钮 + 中间 QTabBar + 右侧新建按钮。"""

    task_switched = pyqtSignal(int)
    task_close_requested = pyqtSignal(int)
    task_create_requested = pyqtSignal()
    settings_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("taskTabBar")
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(6)

        self._btn_settings = QPushButton("⚙ 设置")
        self._btn_settings.setFixedHeight(30)
        self._btn_settings.setProperty("class", "primary")
        self._btn_settings.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self._btn_settings)

        self._tabs = QTabBar()
        self._tabs.setTabsClosable(True)
        self._tabs.setExpanding(False)
        self._tabs.setMovable(False)
        self._tabs.currentChanged.connect(self.task_switched.emit)
        self._tabs.tabCloseRequested.connect(self.task_close_requested.emit)
        layout.addWidget(self._tabs, stretch=1)

        self._btn_add = QPushButton("+")
        self._btn_add.setFixedSize(30, 30)
        self._btn_add.setToolTip("新建任务")
        self._btn_add.clicked.connect(self.task_create_requested.emit)
        layout.addWidget(self._btn_add)

    # ---------- 公开接口 ----------

    def add_task(self, task_id: str, title: str) -> int:
        idx = self._tabs.addTab(title)
        self._tabs.setTabData(idx, task_id)
        self._tabs.setCurrentIndex(idx)
        return idx

    def remove_task(self, index: int) -> None:
        if 0 <= index < self._tabs.count():
            self._tabs.removeTab(index)

    def set_active_task(self, task_id: str) -> bool:
        for i in range(self._tabs.count()):
            if self._tabs.tabData(i) == task_id:
                self._tabs.setCurrentIndex(i)
                return True
        return False

    def current_task_id(self) -> str:
        idx = self._tabs.currentIndex()
        if idx < 0:
            return ""
        return self._tabs.tabData(idx) or ""

    def task_at(self, index: int):
        """返回 (task_id, title)。"""
        if 0 <= index < self._tabs.count():
            return self._tabs.tabData(index), self._tabs.tabText(index)
        return "", ""

    def count(self) -> int:
        return self._tabs.count()

    def iter_tasks(self):
        for i in range(self._tabs.count()):
            yield self._tabs.tabData(i), self._tabs.tabText(i)