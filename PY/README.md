# 三角洲自动抢购工具 v2.0

> 🎮 基于 ADB + OCR 的 Android 游戏自动化工具

## ✨ 功能特性

- 📱 **ADB 设备管理** — 自动发现、连接、监控 Android 设备
- 📸 **双模式屏幕采集** — scrcpy 高速采集 + screencap 回退
- 🔍 **OCR 价格识别** — EasyOCR 中英文识别，自动价格比较
- 🔄 **工作流引擎** — JSON 配置的自动化步骤（18+ 步骤类型）
- 🖥️ **PyQt5 GUI** — 暗色主题、四区工作台、侧边栏导航
- 🛡️ **安全防护** — ADB 命令注入防护、安全表达式求值器
- 📊 **结构化日志** — 上下文感知的日志记录

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
│   ├── adb_core.py           # ADB 统一接口（shell=False 安全调用）
│   ├── config_manager.py     # JSON 配置管理
│   ├── device_manager.py     # 设备发现与监控
│   ├── error_policy.py       # 错误处理策略
│   ├── expression_eval.py    # 安全表达式求值器
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
├── tests/                    # 测试套件（238 测试）
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

MIT
