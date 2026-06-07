import json
import os
import threading
import tempfile
import shutil
import logging

logger = logging.getLogger(__name__)


class TaskStateManager:
    """管理多任务状态的持久化存储。

    每个任务拥有独立的 id、标题、绑定设备、当前方案和步骤索引。
    所有读写使用"写临时文件 -> 移动替换"原子模式。
    """

    _DEFAULT_SNAPSHOT = {"active_task_id": "", "tasks": []}

    def __init__(self, base_dir: str):
        self._path = os.path.join(base_dir, "config", "tasks.json")
        self._lock = threading.Lock()
        self._tasks: dict = {}          # task_id -> state dict
        self._counter: int = 0
        self._snapshot: dict = dict(self._DEFAULT_SNAPSHOT)

    # ---------- 公开接口 ----------

    def load_snapshot(self) -> dict:
        """从磁盘加载快照并同步到内存。返回快照字典。"""
        with self._lock:
            data = self._read_json()
            self._snapshot = data
            self._tasks.clear()
            for t in data.get("tasks", []):
                tid = t.get("id", "")
                self._tasks[tid] = dict(t)
            self._counter = len(self._tasks)
            return data

    def save_snapshot(self, snapshot: dict) -> None:
        """将完整快照写入磁盘并同步内存。"""
        with self._lock:
            self._snapshot = snapshot
            self._tasks.clear()
            for t in snapshot.get("tasks", []):
                tid = t.get("id", "")
                self._tasks[tid] = dict(t)
            self._counter = max(self._counter, len(self._tasks))
            self._write_json(snapshot)

    def get_task(self, task_id: str) -> dict:
        with self._lock:
            return dict(self._tasks.get(task_id, {}))

    def update_task(self, task_id: str, **kwargs) -> None:
        with self._lock:
            if task_id not in self._tasks:
                self._tasks[task_id] = {"id": task_id, "title": "", "workflow": "", "bound_device": "", "bound_device_label": "", "selected_step_index": 0}
            self._tasks[task_id].update(kwargs)

    def remove_task(self, task_id: str) -> None:
        with self._lock:
            self._tasks.pop(task_id, None)
            snapshot_tasks = self._snapshot.get("tasks", [])
            self._snapshot["tasks"] = [t for t in snapshot_tasks if t.get("id") != task_id]
            if self._snapshot.get("active_task_id") == task_id:
                remaining = self._snapshot["tasks"]
                self._snapshot["active_task_id"] = remaining[0]["id"] if remaining else ""
            self._write_json(self._snapshot)

    def next_task_id(self) -> str:
        with self._lock:
            self._counter += 1
            return f"task_{self._counter}"

    def next_task_title(self) -> str:
        with self._lock:
            return f"任务{self._counter}"

    # ---------- 内部 ----------

    def _read_json(self) -> dict:
        if not os.path.exists(self._path):
            return dict(self._DEFAULT_SNAPSHOT)
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("读取任务状态失败: %s", e)
            return dict(self._DEFAULT_SNAPSHOT)

    def _write_json(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self._path), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            shutil.move(tmp, self._path)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise