# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/) 格式。

## [2.1.0] - Unreleased

### 安全
- 修复 ADB 命令注入漏洞：`execute()` 改为 `shell=False` + 参数列表
- 扩展注入防护到所有 step handler（input_text、force_stop、launch、keyevent）
- 添加输入验证函数（包名、keyevent、文件路径）
- `recorder.py` 的 `getevent` 调用改为参数列表

### 稳定性
- 消除 `screen_capture.py` 中 12 处 silent `except: pass`
- 修复 `main_window.py` 异常钩子中的重复日志
- 完善 `_shutdown()` 资源清理（5 个组件：executor、capture、config、task、ui_state）
- 修复 `main.py` 和 `telemetry.py` 中的 silent except
- 修复 ffmpeg 拼写错误（fmpeg → ffmpeg）

### 测试
- 新增 `test_adb_security.py` — ADB 命令注入防护测试（32 项）
- 新增 `test_adb_core.py` — ADB 核心模块单元测试（14 项）
- 新增 `test_step_executor.py` — 步骤执行器测试（30 项，覆盖 15+ 步骤类型）
- 新增 `test_ocr_engine.py` — OCR 引擎测试（18 项）
- 测试总数从 144 增至 238

### 工程化
- 添加 README.md、CHANGELOG.md
- 修复 `.gitignore` 排除 `.github/` 的问题
- 添加 pre-commit hooks（black、isort、flake8）
- 添加 `pyproject.toml` 统一配置
- 添加 `requirements-dev.txt`（开发/测试依赖）
- 添加 `.editorconfig`（编辑器一致性）
- 整理 legacy 目录（添加 README 标记为非活跃代码）

## [2.0.0] - 2024-xx-xx

### 新增
- PyQt5 GUI 暗色主题
- 18+ 步骤类型（tap、swipe、ocr、condition、loop 等）
- JSON 工作流配置
- 多任务标签管理
- scrcpy + screencap 双模式屏幕采集
- 错误策略引擎（retry/backoff/skip/fail/abort）
- 安全表达式求值器
- 结构化日志
- 操作录制器

### 变更
- 从 40+ 独立脚本重构为结构化 PyQt5 应用
