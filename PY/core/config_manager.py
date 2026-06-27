import json
import os
import threading
import logging
import shutil
import tempfile

from core.config_migrator import load_and_validate_config, load_and_validate_workflows

logger = logging.getLogger(__name__)


class ConfigManager:
    DEFAULT_CONFIG = {
        "config_version": 2,
        "buy_params": {
            "user_price": 0.5,
            "price_coefficient": 4560,
            "min_price": 300000,
            "max_mail_count": 190
        },
        "mail_params": {
            "mail_count_file": "you.txt",
            "auto_increment": True
        },
        "workflow_engine": {
            "refresh_workflow": "refresh_path",
            "max_mail_count_default": 190,
            "status_recovering": "恢复中...",
            "status_running": "运行中",
            "status_mail_full": "邮件已满"
        },
        "recognition": {
            "template_threshold": 0.85,
            "template_dir": "tp",
            "ocr_gpu": False
        },
        "ocr_regions": {
            "price_region": {
                "left": 1316,
                "top": 648,
                "right": 1590,
                "bottom": 703
            },
            "button_region": {
                "left": 1300,
                "top": 648,
                "right": 1580,
                "bottom": 705
            }
        },
        "wifi_control": {
            "enable_cmd": "svc wifi enable",
            "disable_cmd": "svc wifi disable"
        },
        "device": {
            "game_package": "com.tencent.tmgp.dfm",
            "base_resolution": {
                "width": 2400,
                "height": 1080
            },
            "scrcpy_server_path": "lib/scrcpy-server.jar"
        },
        "timing": {
            "default_wait": 1.5,
            "screenshot_wait": 2.0,
            "game_start_wait": 30,
            "match_wait": 15
        },
        "logging": {
            "log_file": "app.log",
            "log_level": "INFO",
            "max_log_size_mb": 10
        },
        "ui": {
            "theme": "dark",
            "floating_window_opacity": 0.85,
            "floating_window_bg": "#1a1a2e",
            "price_color": "#00ff88",
            "mail_color": "#ffaa00",
            "status_color": "#a0a0a0"
        },
        "execution": {
            "policy": {
                "default_policy": "fail",
                "max_retries": 3,
                "retry_delay": 0.5,
                "backoff_base": 1.0,
                "backoff_max": 10.0,
                "category_overrides": {}
            }
        },
        "coordinate": {
            "auto_scale": False,
            "warn_on_mismatch": True
        },
        "telemetry": {
            "enabled": False,
            "endpoint": ""
        }
    }

    DEFAULT_WORKFLOWS = {"workflows": {}}

    _instance = None
    _init_flag = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, base_dir: str) -> None:
        if ConfigManager._init_flag:
            return
        ConfigManager._init_flag = True
        self._base_dir = base_dir
        self._config_dir = os.path.join(base_dir, "config")
        self._config_path = os.path.join(self._config_dir, "config.json")
        self._workflows_path = os.path.join(self._config_dir, "workflows.json")
        self._config = None  # type: Optional[dict]
        self._workflows = None  # type: Optional[dict]
        self._lock = threading.Lock()

    def _load_json_file(self, file_path: str, default: dict) -> dict:
        if not os.path.exists(file_path):
            logger.warning("File not found: %s, restoring from default", file_path)
            return json.loads(json.dumps(default))
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info("Loaded file: %s", file_path)
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load %s (%s), restoring from default", file_path, e)
            return json.loads(json.dumps(default))

    def _ensure_config(self) -> dict:
        if self._config is None:
            self._config = load_and_validate_config(
                self._config_path, self.DEFAULT_CONFIG
            )
        return self._config

    def _ensure_workflows(self) -> dict:
        if self._workflows is None:
            self._workflows = load_and_validate_workflows(
                self._workflows_path, self.DEFAULT_WORKFLOWS
            )
        return self._workflows

    def _atomic_write(self, file_path: str, data: dict) -> None:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        dir_name = os.path.dirname(file_path)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            shutil.move(tmp_path, file_path)
            logger.info("Saved file: %s", file_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    @staticmethod
    def _resolve_get(data: dict, key_path: str, default=None):
        keys = key_path.split(".")
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    @staticmethod
    def _resolve_set(data: dict, key_path: str, value) -> None:
        keys = key_path.split(".")
        current = data
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

    def get_config(self, key_path: str, default=None):
        with self._lock:
            config = self._ensure_config()
            return self._resolve_get(config, key_path, default)

    def set_config(self, key_path: str, value) -> None:
        with self._lock:
            config = self._ensure_config()
            self._resolve_set(config, key_path, value)
            self._atomic_write(self._config_path, config)

    def get_workflow(self, name: str) -> dict:
        with self._lock:
            workflows = self._ensure_workflows()
            return workflows.get("workflows", {}).get(name, {})

    def set_workflow(self, name: str, workflow: dict) -> None:
        with self._lock:
            workflows = self._ensure_workflows()
            if "workflows" not in workflows:
                workflows["workflows"] = {}
            workflows["workflows"][name] = workflow
            self._atomic_write(self._workflows_path, workflows)

    def get_all_workflows(self) -> dict:
        with self._lock:
            workflows = self._ensure_workflows()
            return workflows.get("workflows", {})

    def delete_workflow(self, name: str) -> None:
        with self._lock:
            workflows = self._ensure_workflows()
            if "workflows" in workflows and name in workflows["workflows"]:
                del workflows["workflows"][name]
                self._atomic_write(self._workflows_path, workflows)

    def reload(self) -> None:
        with self._lock:
            self._config = load_and_validate_config(
                self._config_path, self.DEFAULT_CONFIG
            )
            self._workflows = load_and_validate_workflows(
                self._workflows_path, self.DEFAULT_WORKFLOWS
            )
            logger.info("Reloaded config and workflows from disk")

    def save_config(self) -> None:
        with self._lock:
            config = self._ensure_config()
            self._atomic_write(self._config_path, config)

    def save_workflows(self) -> None:
        with self._lock:
            workflows = self._ensure_workflows()
            self._atomic_write(self._workflows_path, workflows)
