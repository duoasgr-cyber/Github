# 第四阶段：工程化 — 实现提示词

> 执行环境：项目根目录 `PY/`，Python 3.10+，所有路径相对于 `PY/`。
> 前置条件：第一、二、三阶段已完成。

## 目标

1. 清理根目录临时脚本 + legacy 归档
2. 添加 README.md 和 CHANGELOG.md
3. 修复 `.gitignore` 排除 `.github/` 的问题
4. 添加 pre-commit hooks
5. 完善 requirements（锁版本 + dev 依赖）

---

## 任务 1：清理根目录临时脚本

### 背景

项目根目录（`PY/` 的上一级或 `PY/` 内）存在 22+ 个 `_patch_*.py`、`fix_*.py` 临时脚本，约 35KB，是迭代修复过程中产生的但已不再需要。

### 要求

**1.1 识别临时脚本**

```powershell
# 列出所有疑似临时脚本
Get-ChildItem -Path "PY" -Filter "*.py" -File | Where-Object {
    $_.Name -match '^(_patch_|fix_|temp_|tmp_)'
} | Select-Object Name, Length, LastWriteTime
```

**1.2 确认是否仍被引用**

对每个临时脚本，检查其是否被任何其他文件 import 或引用：

```powershell
foreach ($file in $tempFiles) {
    $name = $file.BaseName
    $refs = Select-String -Path "PY\*.py","PY\**\*.py" -Pattern $name -Exclude "$($file.Name)"
    if ($refs.Count -eq 0) {
        Write-Host "无引用: $($file.Name)"
    }
}
```

**1.3 删除无引用的临时脚本**

将确认无引用的脚本移至 `PY/legacy/patches/` 子目录（保留历史可追溯）：

```powershell
New-Item -ItemType Directory -Path "PY\legacy\patches" -Force
# 移动文件
Move-Item -Path "PY\_patch_*.py" -Destination "PY\legacy\patches\"
Move-Item -Path "PY\fix_*.py" -Destination "PY\legacy\patches\"
```

**1.4 更新 `.gitignore`**

在 `.gitignore` 中添加（如果想彻底忽略 legacy）：

```gitignore
# Legacy code preserved for reference only
PY/legacy/
```

---

## 任务 2：整理 legacy 目录

### 背景

`PY/legacy/` 包含 40+ 个旧版脚本（v1.0 代码）。它们不应被删除（保留历史参考），但应明确标记为非活跃代码。

### 要求

**2.1 在 legacy 目录添加 README**

创建 `PY/legacy/README.md`：

```markdown
# ⚠️ Legacy Code — 非活跃代码

此目录包含 **v1.0** 版本的原始代码，在 v2.0 重构后已不再使用。

## 目录说明

- `*.py` — v1.0 的独立脚本
- `patches/` — v2.0 开发过程中的临时修复脚本

## ⚠️ 重要

- **不要修改此目录中的文件**
- **不要从此目录导入代码**
- 新功能请在 `core/` 和 `ui/` 中实现

此目录仅作历史参考用途。
```

**2.2 确认 `legacy/` 未被 import**

```powershell
Select-String -Path "PY\core\*.py","PY\ui\**\*.py","PY\main.py" -Pattern "from.*legacy|import.*legacy"
```

应返回零结果。如有引用，迁移到 `core/` 后移除。

---

## 任务 3：添加 README.md

### 要求

在项目根目录创建 `README.md`：

```markdown
# 三角洲自动抢购工具 v2.0

> 🎮 基于 ADB + OCR 的 Android 游戏自动化工具

[![CI](https://github.com/<user>/<repo>/actions/workflows/ci.yml/badge.svg)](https://github.com/<user>/<repo>/actions/workflows/ci.yml)

## ✨ 功能特性

- 📱 ADB 设备管理 — 自动发现、连接、监控 Android 设备
- 📸 双模式屏幕采集 — scrcpy 高速采集 + screencap 回退
- 🔍 OCR 价格识别 — EasyOCR 中英文识别，自动价格比较
- 🔄 工作流引擎 — JSON 配置的自动化步骤（18+ 步骤类型）
- 🖥️ PyQt5 GUI — 暗色主题、四区工作台、侧边栏导航
- 🛡️ 安全防护 — ADB 命令注入防护、安全表达式求值器
- 📊 结构化日志 — 上下文感知的日志记录

## 🚀 快速开始

### 环境要求

- Python 3.10+
- ADB（Android Debug Bridge）已安装并在 PATH 中
- Android 设备已开启 USB 调试
- [可选] GPU + CUDA（加速 OCR）
- [可选] ffmpeg（屏幕录制功能）

### 安装

```bash
cd PY
pip install -r requirements.txt
```

### 运行

```bash
python main.py
```

### 打包

```bash
pyinstaller app.spec
```

## 📁 项目结构

```
PY/
├── core/                     # 核心引擎
│   ├── adb_core.py           # ADB 统一接口
│   ├── config_manager.py     # JSON 配置管理
│   ├── device_manager.py     # 设备发现与监控
│   ├── error_policy.py       # 错误处理策略
│   ├── expression_eval.py    # 安全表达式求值
│   ├── ocr_engine.py         # OCR 识别引擎
│   ├── recorder.py           # 操作录制器
│   ├── screen_capture.py     # 屏幕采集（scrcpy/screencap）
│   ├── step_executor.py      # 步骤执行器（18+ 类型）
│   ├── task_state_manager.py # 多任务状态持久化
│   ├── telemetry.py          # 可选遥测
│   └── workflow_engine.py    # 工作流引擎
├── ui/                       # PyQt5 GUI
│   ├── main_window.py        # 主窗口
│   ├── panels/               # 功能面板
│   ├── components/           # UI 组件
│   ├── dialogs/              # 对话框
│   └── style.qss             # 暗色主题
├── config/                   # JSON 配置文件
├── tests/                    # 测试套件
├── prompts/                  # AI 辅助开发提示词
├── legacy/                   # v1.0 历史代码（仅供参考）
├── main.py                   # 应用入口
└── requirements.txt          # 依赖清单
```

## 🧪 测试

```bash
# 运行全部测试
cd PY && python -m pytest tests/ -v

# 只运行单元测试
python -m pytest tests/test_*.py -v

# 运行 UI 冒烟测试
python -m pytest tests/ui_smoke/ -v
```

## 🔧 配置

- `config/config.json` — 全局配置（ADB 参数、OCR 参数、错误策略等）
- `config/workflows.json` — 工作流定义（步骤序列）
- `config/coordinates.json` — 坐标配置
- `config/tasks.json` — 多任务状态（自动生成）

## 📄 License

[选择你的许可证]
```

---

## 任务 4：添加 CHANGELOG.md

### 要求

创建 `CHANGELOG.md`：

```markdown
# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/) 格式。

## [2.1.0] - Unreleased

### 安全
- 修复 ADB 命令注入漏洞：`execute()` 改为 `shell=False` + 参数列表
- 扩展注入防护到所有 step handler（input_text、force_stop、launch 等）
- 添加输入验证函数（包名、keyevent、文件路径）

### 稳定性
- 消除 `screen_capture.py` 中 12 处 silent except: pass
- 统一工作流引擎，删除 main_window 中重复的 _WorkflowWorker
- 修复 `_shutdown()` 完整清理资源（6 个组件）
- 修复异常钩子中的重复日志

### 测试
- 新增 `test_adb_core.py` — ADB 核心模块单元测试
- 新增 `test_step_executor.py` — 步骤执行器测试（15+ 类型）
- 新增 `test_ocr_engine.py` — OCR 引擎测试

### 工程化
- 清理 22+ 临时脚本到 legacy/patches/
- 添加 README.md、CHANGELOG.md
- 修复 `.gitignore` 排除 `.github/` 的问题
- 添加 pre-commit hooks（格式化 + 类型检查 + 测试）
- 完善 requirements（分离 dev 依赖、锁定版本范围）

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
```

---

## 任务 5：修复 `.gitignore`

### 背景

当前 `.gitignore` 排除了 `.github/`，导致 CI 配置文件可能未被版本控制。

### 要求

**5.1 检查当前 `.gitignore`**

```powershell
Select-String -Path ".gitignore" -Pattern "\.github"
```

**5.2 移除 `.github/` 排除规则**

如果存在 `.github/` 排除行，删除或注释掉：

```gitignore
# 以下行已移除（CI 配置需要被版本控制）
# .github/
```

**5.3 确认 CI 配置已追踪**

```powershell
git add .github/
git status
```

---

## 任务 6：添加 pre-commit hooks

### 要求

**6.1 创建 `requirements-dev.txt`**

```txt
# 测试
pytest>=7.0,<9.0
pytest-cov>=4.0,<6.0
pytest-timeout>=2.0,<3.0

# 代码格式化
black>=23.0,<25.0
isort>=5.0,<7.0

# 类型检查
mypy>=1.0,<2.0

# Lint
flake8>=6.0,<8.0
flake8-bugbear>=23.0

# Pre-commit
pre-commit>=3.0,<5.0
```

**6.2 创建 `.pre-commit-config.yaml`**（项目根目录）

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb=500']

  - repo: https://github.com/psf/black
    rev: 24.3.0
    hooks:
      - id: black
        language_version: python3
        args: ['--line-length=120']

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: ['--profile=black', '--line-length=120']

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: ['--max-line-length=120', '--extend-ignore=E203,W503']
        additional_dependencies:
          - flake8-bugbear
```

**6.3 创建 `pyproject.toml`**（统一配置格式化/测试/类型检查）

```toml
[tool.black]
line-length = 120
target-version = ["py310"]

[tool.isort]
profile = "black"
line_length = 120

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
addopts = "-v --tb=short"
timeout = 30

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"
```

**6.4 安装 hooks**

```bash
pip install pre-commit
pre-commit install
```

---

## 任务 7：完善 requirements.txt

### 要求

**7.1 更新 `requirements.txt`**，添加版本范围约束：

```txt
PyQt5>=5.15,<5.16
opencv-python>=4.8,<5.0
numpy>=1.24,<2.0
easyocr>=1.7,<2.0
Pillow>=10.0,<11.0
```

> 注意：`numpy>=1.24,<2.0` 避免 numpy 2.0 的 breaking changes。PyQt5 限定 5.15.x 因为 6.x 不兼容。

**7.2 验证依赖可安装**

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

---

## 任务 8：添加 `.editorconfig`

### 要求

创建 `.editorconfig` 确保编辑器一致性：

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[*.py]
indent_style = space
indent_size = 4

[*.json]
indent_style = space
indent_size = 2

[*.md]
indent_style = space
indent_size = 2
trim_trailing_whitespace = false

[*.yml]
indent_style = space
indent_size = 2

[*.qss]
indent_style = space
indent_size = 4
```

---

## 验收标准

1. ✅ 根目录无 `_patch_*.py` / `fix_*.py` 临时脚本
2. ✅ `PY/legacy/README.md` 存在且说明清晰
3. ✅ 项目根目录有 `README.md`（包含功能说明、快速开始、项目结构）
4. ✅ 项目根目录有 `CHANGELOG.md`（记录 v2.0 和 v2.1.0 变更）
5. ✅ `.gitignore` 不再排除 `.github/`
6. ✅ `.pre-commit-config.yaml` 存在且可安装
7. ✅ `pyproject.toml` 统一配置 black/isort/pytest/mypy
8. ✅ `requirements.txt` 有版本范围约束
9. ✅ `requirements-dev.txt` 存在且包含测试/格式化依赖
10. ✅ `.editorconfig` 存在
11. ✅ `pip install -r requirements.txt && pip install -r requirements-dev.txt` 成功
12. ✅ 现有测试仍然全部通过

## 注意事项

- 临时脚本只移不删（移到 `legacy/patches/`），保留 git 历史可追溯
- README 使用中文（与项目文档语言一致）
- pre-commit hooks 首次安装后运行 `pre-commit run --all-files` 可能格式化大量代码，可以先只安装 hooks 不做全量格式化，后续逐步规范化
- `pyproject.toml` 不要与 `setup.py` 冲突（如果项目没有 `setup.py` 就直接用 `pyproject.toml`）
- CHANGELOG 中 v2.0.0 的日期用 `2024-xx-xx` 占位，由用户补充实际日期
