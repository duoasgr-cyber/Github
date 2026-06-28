import json
import os
import logging
import copy

logger = logging.getLogger(__name__)


def _deep_merge(default: dict, current: dict) -> dict:
    """Merge current into default, keeping default keys and adding new ones from current."""
    result = copy.deepcopy(default)
    for key, value in current.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_and_validate_config(config_path: str, default_config: dict) -> dict:
    """Load config file, validate against default, and merge missing keys."""
    if not os.path.exists(config_path):
        logger.info("Config not found: %s, creating from default", config_path)
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)
        return copy.deepcopy(default_config)

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load config (%s), using default", e)
        return copy.deepcopy(default_config)

    merged = _deep_merge(default_config, data)
    return merged


def load_and_validate_workflows(workflows_path: str, default_workflows: dict) -> dict:
    """Load workflows file, validate against default structure."""
    if not os.path.exists(workflows_path):
        logger.info("Workflows not found: %s, creating from default", workflows_path)
        os.makedirs(os.path.dirname(workflows_path), exist_ok=True)
        with open(workflows_path, "w", encoding="utf-8") as f:
            json.dump(default_workflows, f, ensure_ascii=False, indent=2)
        return copy.deepcopy(default_workflows)

    try:
        with open(workflows_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load workflows (%s), using default", e)
        return copy.deepcopy(default_workflows)

    if not isinstance(data, dict) or "workflows" not in data:
        logger.warning("Invalid workflows structure, using default")
        return copy.deepcopy(default_workflows)

    return data
