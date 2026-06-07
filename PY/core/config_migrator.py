"""Configuration schema validation and migration manager.

Validates config.json and workflows.json against schemas, and migrates
older config versions forward automatically with backup.
"""
import json
import os
import shutil
import logging
import tempfile
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

CURRENT_CONFIG_VERSION = 2


def _load_json(file_path: str) -> Optional[dict]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load %s: %s", file_path, e)
        return None


def _save_json(file_path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(file_path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.move(tmp, file_path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _backup_file(file_path: str) -> Optional[str]:
    """Create a timestamped backup of a file. Returns backup path."""
    if not os.path.exists(file_path):
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{file_path}.bak.{ts}"
    shutil.copy2(file_path, backup_path)
    logger.info("Backed up %s -> %s", file_path, backup_path)
    return backup_path


# --- Validation helpers ---

REQUIRED_CONFIG_KEYS = [
    "buy_params", "mail_params", "recognition", "device", "timing", "logging"
]

REQUIRED_WORKFLOW_KEYS = ["workflows"]


def validate_config(config: dict) -> Tuple[bool, list]:
    """Validate a config dict. Returns (is_valid, list_of_issues)."""
    issues = []
    for key in REQUIRED_CONFIG_KEYS:
        if key not in config:
            issues.append(f"Missing required key: {key}")

    bp = config.get("buy_params", {})
    if "user_price" in bp and not isinstance(bp["user_price"], (int, float)):
        issues.append("buy_params.user_price must be a number")
    if "max_mail_count" in bp and not isinstance(bp["max_mail_count"], int):
        issues.append("buy_params.max_mail_count must be an integer")

    device = config.get("device", {})
    res = device.get("base_resolution", {})
    if res:
        w, h = res.get("width", 0), res.get("height", 0)
        if w <= 0 or h <= 0:
            issues.append("device.base_resolution must have positive width/height")

    return (len(issues) == 0, issues)


def validate_workflow(name: str, workflow: dict) -> Tuple[bool, list]:
    """Validate a single workflow dict."""
    issues = []
    if "steps" not in workflow:
        issues.append(f"Workflow '{name}' missing 'steps'")
        return (False, issues)

    steps = workflow.get("steps", [])
    if not isinstance(steps, list):
        issues.append(f"Workflow '{name}' steps must be a list")
        return (False, issues)

    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            issues.append(f"Workflow '{name}' step {i} must be a dict")
            continue
        if "type" not in step:
            issues.append(f"Workflow '{name}' step {i} missing 'type'")

    dev_res = workflow.get("device_resolution", {})
    if dev_res:
        w, h = dev_res.get("width", 0), dev_res.get("height", 0)
        if w <= 0 or h <= 0:
            issues.append(f"Workflow '{name}' device_resolution must be positive")

    return (len(issues) == 0, issues)


def validate_workflows(workflows: dict) -> Tuple[bool, list]:
    """Validate the top-level workflows dict."""
    all_issues = []
    if "workflows" not in workflows:
        return (False, ["Missing required key: workflows"])

    wf_dict = workflows.get("workflows", {})
    if not isinstance(wf_dict, dict):
        return (False, ["'workflows' must be a dict"])

    for name, wf in wf_dict.items():
        valid, issues = validate_workflow(name, wf)
        if not valid:
            all_issues.extend(issues)

    return (len(all_issues) == 0, all_issues)


# --- Migration ---

def _migrate_v1_to_v2(config: dict) -> dict:
    """Migrate config from version 1 to version 2.

    v2 adds:
      - config_version field
      - execution.policy section
    """
    config["config_version"] = 2
    if "execution" not in config:
        config["execution"] = {
            "policy": {
                "default_policy": "fail",
                "max_retries": 3,
                "retry_delay": 0.5,
                "backoff_base": 1.0,
                "backoff_max": 10.0,
                "category_overrides": {}
            }
        }
    if "coordinate" not in config:
        config["coordinate"] = {
            "auto_scale": False,
            "warn_on_mismatch": True
        }
    return config


MIGRATIONS = {
    1: _migrate_v1_to_v2,
}


def migrate_config(config: dict, backup_path: Optional[str] = None) -> Tuple[dict, bool]:
    """Migrate config forward through all pending migrations.

    Returns (migrated_config, was_migrated).
    """
    current_version = config.get("config_version", 1)
    migrated = False

    while current_version < CURRENT_CONFIG_VERSION:
        migration_fn = MIGRATIONS.get(current_version)
        if migration_fn is None:
            logger.warning("No migration from version %d, skipping", current_version)
            break
        logger.info("Migrating config from v%d to v%d", current_version, current_version + 1)
        config = migration_fn(config)
        current_version += 1
        migrated = True

    return config, migrated


def load_and_validate_config(config_path: str, default_config: dict) -> dict:
    """Load config with validation and automatic migration.

    Returns the config dict. On corruption, restores defaults and backs up the bad file.
    """
    config = _load_json(config_path)

    if config is None:
        logger.warning("Config missing or corrupt, creating from defaults")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        _save_json(config_path, default_config)
        return dict(default_config)

    # Backup before migration
    needs_migration = config.get("config_version", 1) < CURRENT_CONFIG_VERSION
    if needs_migration:
        _backup_file(config_path)

    config, migrated = migrate_config(config)

    valid, issues = validate_config(config)
    if not valid:
        logger.warning("Config validation issues: %s", issues)
        _backup_file(config_path)
        logger.info("Restoring config from defaults after validation failure")
        _save_json(config_path, default_config)
        return dict(default_config)

    if migrated:
        _save_json(config_path, config)
        logger.info("Config migrated to version %d and saved", CURRENT_CONFIG_VERSION)

    return config


def load_and_validate_workflows(workflows_path: str, default_workflows: dict) -> dict:
    """Load workflows with validation. On corruption, restores defaults."""
    workflows = _load_json(workflows_path)

    if workflows is None:
        logger.warning("Workflows missing or corrupt, creating from defaults")
        os.makedirs(os.path.dirname(workflows_path), exist_ok=True)
        _save_json(workflows_path, default_workflows)
        return dict(default_workflows)

    valid, issues = validate_workflows(workflows)
    if not valid:
        logger.warning("Workflow validation issues: %s", issues)
        _backup_file(workflows_path)
        logger.info("Restoring workflows from defaults after validation failure")
        _save_json(workflows_path, default_workflows)
        return dict(default_workflows)

    return workflows
