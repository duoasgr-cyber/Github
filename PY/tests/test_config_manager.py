"""Unit tests for core/config_manager.py"""
import json
import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.config_manager import ConfigManager


class TestConfigManagerUnit(unittest.TestCase):

    def setUp(self):
        ConfigManager._instance = None
        ConfigManager._init_flag = False
        self.temp_dir = tempfile.mkdtemp()
        config_dir = os.path.join(self.temp_dir, "config")
        os.makedirs(config_dir, exist_ok=True)
        with open(os.path.join(config_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump(ConfigManager.DEFAULT_CONFIG, f)
        with open(os.path.join(config_dir, "workflows.json"), "w", encoding="utf-8") as f:
            json.dump({"workflows": {}}, f)
        self.cm = ConfigManager(self.temp_dir)

    def tearDown(self):
        ConfigManager._instance = None
        ConfigManager._init_flag = False
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_nested_config(self):
        val = self.cm.get_config("buy_params.user_price")
        self.assertEqual(val, ConfigManager.DEFAULT_CONFIG["buy_params"]["user_price"])

    def test_get_missing_key_returns_default(self):
        val = self.cm.get_config("nonexistent.key", default="fallback")
        self.assertEqual(val, "fallback")

    def test_set_and_get_config(self):
        self.cm.set_config("buy_params.user_price", 999)
        val = self.cm.get_config("buy_params.user_price")
        self.assertEqual(val, 999)

    def test_set_config_persists_to_disk(self):
        self.cm.set_config("buy_params.user_price", 42)
        self.cm.save_config()
        ConfigManager._instance = None
        ConfigManager._init_flag = False
        cm2 = ConfigManager(self.temp_dir)
        val = cm2.get_config("buy_params.user_price")
        self.assertEqual(val, 42)

    def test_missing_config_file_recovers_default(self):
        config_path = os.path.join(self.temp_dir, "config", "config.json")
        os.remove(config_path)
        ConfigManager._instance = None
        ConfigManager._init_flag = False
        cm2 = ConfigManager(self.temp_dir)
        val = cm2.get_config("buy_params.user_price")
        self.assertEqual(val, ConfigManager.DEFAULT_CONFIG["buy_params"]["user_price"])

    def test_corrupted_json_recovers_default(self):
        config_path = os.path.join(self.temp_dir, "config", "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("{invalid json!!!")
        ConfigManager._instance = None
        ConfigManager._init_flag = False
        cm2 = ConfigManager(self.temp_dir)
        val = cm2.get_config("buy_params.user_price")
        self.assertEqual(val, ConfigManager.DEFAULT_CONFIG["buy_params"]["user_price"])

    def test_set_and_get_workflow(self):
        wf = {"description": "test", "steps": [{"type": "wait", "seconds": 1}]}
        self.cm.set_workflow("test_wf", wf)
        result = self.cm.get_workflow("test_wf")
        self.assertEqual(result["description"], "test")
        self.assertEqual(len(result["steps"]), 1)

    def test_get_nonexistent_workflow_returns_empty(self):
        result = self.cm.get_workflow("does_not_exist")
        self.assertEqual(result, {})

    def test_delete_workflow(self):
        wf = {"steps": []}
        self.cm.set_workflow("to_delete", wf)
        self.cm.delete_workflow("to_delete")
        result = self.cm.get_workflow("to_delete")
        self.assertEqual(result, {})

    def test_get_all_workflows(self):
        self.cm.set_workflow("wf1", {"steps": []})
        self.cm.set_workflow("wf2", {"steps": []})
        all_wfs = self.cm.get_all_workflows()
        self.assertIn("wf1", all_wfs)
        self.assertIn("wf2", all_wfs)

    def test_reload_from_disk(self):
        config_path = os.path.join(self.temp_dir, "config", "config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        cfg["buy_params"]["user_price"] = 777
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
        self.cm.reload()
        val = self.cm.get_config("buy_params.user_price")
        self.assertEqual(val, 777)

    def test_atomic_write_no_corruption(self):
        for i in range(20):
            self.cm.set_config("buy_params.user_price", i)
        val = self.cm.get_config("buy_params.user_price")
        self.assertEqual(val, 19)

    def test_singleton_behavior(self):
        cm2 = ConfigManager(self.temp_dir)
        self.assertIs(self.cm, cm2)

    def test_default_config_has_required_keys(self):
        dc = ConfigManager.DEFAULT_CONFIG
        required = ["buy_params", "mail_params", "schedule", "recognition",
                     "ocr_regions", "device", "timing", "logging", "ui",
                     "execution", "coordinate"]
        for key in required:
            self.assertIn(key, dc, f"DEFAULT_CONFIG missing key: {key}")


if __name__ == "__main__":
    unittest.main()
