# 三角洲自动抢购工具 v2.0 - Code Wiki

> 本文档为「三角洲自动抢购工具」项目的完整代码维基，涵盖项目架构、模块职责、关键类与函数、依赖关系及运行方式。

---

## 目录

1. [项目概述](#1-项目概述)
2. [整体架构](#2-整体架构)
3. [目录结构](#3-目录结构)
4. [核心模块详解](#4-核心模块详解)
5. [UI 模块详解](#5-ui-模块详解)
6. [配置系统](#6-配置系统)
7. [工作流系统](#7-工作流系统)
8. [依赖关系](#8-依赖关系)
9. [项目运行方式](#9-项目运行方式)
10. [数据模型](#10-数据模型)

---

## 1. 项目概述

### 1.1 项目简介

「三角洲自动抢购工具」是一款基于 **ADB + OCR + OpenCV** 的手机游戏自动化抢购脚本，通过 PyQt5 提供图形化界面。项目核心功能包括：

- 通过 ADB 连接 Android 手机，执行点击、滑动、截屏等操作
- 通过 OpenCV 模板匹配识别游戏界面状态
- 通过 EasyOCR 识别游戏中的价格数字和中文文字
- 自动监控价格，在合适时机购买道具
- 购买后执行「卡邮件」流程保留道具
- 自动售卖道具回收货币
- 悬浮窗实时显示价格和运行状态
- 可视化工作流编辑，支持拖拽排序

### 1.2 技术栈

| 类别 | 技术选型 | 说明 |
|------|----------|------|
| GUI 框架 | **PyQt5** | 原生美观、信号槽异步机制、QSS 样式表 |
| 配置管理 | **JSON** | 结构化、支持嵌套、可视化编辑 |
| OCR 引擎 | **EasyOCR** | 支持中英文识别，已有模型验证 |
| 图像匹配 | **OpenCV** | 模板匹配 `cv2.matchTemplate` |
| 截屏方案 | **scrcpy + screencap 双模式** | scrcpy 高效流传输，screencap 兜底 |
| 打包分发 | **PyInstaller** | 一键打包为 exe |
| 编程语言 | **Python 3.x** | 主开发语言 |

---

## 2. 整体架构

### 2.1 架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                        GUI 层 (PyQt5)                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ 工作流编辑│ │ 参数配置  │ │ 设备管理  │ │ 运行监控  │          │
│  │  面板    │ │  面板    │ │  面板    │ │  面板    │          │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘          │
│       │            │            │            │                  │
│       └────────────┴─────┬──────┴────────────┘                  │
│                          │                                       │
│              ┌───────────▼───────────┐                          │
│              │    配置管理器           │                          │
│              │  ConfigManager         │                          │
│              │  - config.json         │                          │
│              │  - workflows.json      │                          │
│              │  - ui_state.json       │                          │
│              └───────────┬───────────┘                          │
└──────────────────────────┼──────────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────────┐
│                     核心逻辑层 (Core)                           │
│                                                                 │
│  ┌─────────────────────┐  ┌─────────────────────┐              │
│  │   步骤执行引擎        │  │   工作流编排引擎      │              │
│  │   StepExecutor       │  │   WorkflowEngine     │              │
│  │  - 单步执行           │  │  - 主循环控制        │              │
│  │  - 错误策略           │  │  - 价格检查          │              │
│  │  - 变量系统           │  │  - 卡邮件流程        │              │
│  │  - 条件/循环          │  │  - 游戏恢复          │              │
│  └──────┬───────────────┘  └──────────┬──────────┘              │
│         │                              │                         │
│  ┌──────▼──────────────────────────────▼──────────┐             │
│  │            识别与设备层                           │             │
│  │  ┌─────────────┐  ┌─────────────┐             │             │
│  │  │  截屏模块    │  │  OCR 引擎   │             │             │
│  │  │ ScrcpyCapture│  │ OcrEngine   │             │             │
│  │  │ - scrcpy    │  │ - 价格识别   │             │             │
│  │  │ - screencap │  │ - 按钮识别   │             │             │
│  │  │ - 自动重连  │  │ - 区域识别   │             │             │
│  │  └──────┬──────┘  └─────────────┘             │             │
│  │         │                                      │             │
│  │  ┌──────▼──────────────────────────────┐      │             │
│  │  │           ADB 核心模块               │      │             │
│  │  │          AdbCore                     │      │             │
│  │  │  - tap/long_press/swipe             │      │             │
│  │  │  - keyevent/input_text              │      │             │
│  │  │  - screenshot/pull/push             │      │             │
│  │  │  - wifi_enable/force_stop/launch    │      │             │
│  │  │  - 设备列表/分辨率获取               │      │             │
│  │  └──────────────┬──────────────────────┘      │             │
│  │                 │                              │             │
│  │  ┌──────────────▼──────────────────────┐      │             │
│  │  │        设备管理器                    │      │             │
│  │  │       DeviceManager                 │      │             │
│  │  │  - 设备选择/切换                    │      │             │
│  │  │  - 连接状态监控                     │      │             │
│  │  │  - 分辨率获取                       │      │             │
│  │  └─────────────────────────────────────┘      │             │
│  └───────────────────────────────────────────────┘             │
└──────────────────────────────────┬──────────────────────────────┘
                                   │
                          ┌────────▼────────┐
                          │   ADB 进程      │
                          │  (手机通信)     │
                          └─────────────────┘
```

### 2.2 分层说明

| 层级 | 职责 | 关键模块 |
|------|------|----------|
| **GUI 层** | 用户交互、可视化配置、运行状态展示 | `ui/` 下所有模块 |
| **配置层** | 统一管理配置文件、工作流定义 | `ConfigManager`, `config/*.json` |
| **核心逻辑层** | 步骤执行、工作流编排、业务逻辑 | `StepExecutor`, `WorkflowEngine` |
| **识别与设备层** | 截屏、OCR 识别、ADB 操作、设备管理 | `ScrcpyCapture`, `OcrEngine`, `AdbCore`, `DeviceManager` |
| **硬件层** | Android 设备、ADB 通信 | 手机设备、ADB 工具 |

---

## 3. 目录结构

```
PY/
├── main.py                         # 程序入口
├── requirements.txt                # Python 依赖
├── app.spec                        # PyInstaller 打包配置
│
├── config/                         # 统一配置目录
│   ├── config.json                 # 全局参数配置
│   ├── coordinates.json            # 坐标点配置（历史遗留）
│   ├── workflows.json              # 工作流步骤序列定义
│   ├── tasks.json                  # 任务状态配置
│   ├── ui_state.json               # UI 状态持久化
│   └── schema/                     # JSON Schema 验证
│       ├── config.schema.json
│       └── workflows.schema.json
│
├── core/                           # 核心逻辑层
│   ├── __init__.py
│   ├── adb_core.py                 # ADB 命令统一执行器
│   ├── config_manager.py           # 配置管理器（单例）
│   ├── config_migrator.py          # 配置迁移与验证
│   ├── device_manager.py           # 设备管理器
│   ├── error_policy.py             # 错误策略与重试
│   ├── expression_eval.py          # 表达式安全求值
│   ├── logger.py                   # 日志系统
│   ├── ocr_engine.py               # OCR 识别引擎（单例）
│   ├── recorder.py                 # 操作录制
│   ├── screen_capture.py           # 截屏模块（scrcpy + screencap）
│   ├── step_executor.py            # 步骤执行引擎
│   ├── structured_log.py           # 结构化日志
│   ├── task_state_manager.py       # 任务状态管理
│   ├── telemetry.py                # 遥测数据
│   └── workflow_engine.py          # 工作流编排引擎
│
├── ui/                             # GUI 层
│   ├── __init__.py
│   ├── main_window.py              # 主窗口
│   ├── panels/                     # 功能面板
│   │   ├── __init__.py
│   │   ├── config_panel.py         # 参数配置面板
│   │   ├── device_panel.py         # 设备管理面板
│   │   ├── log_panel.py            # 运行日志面板
│   │   ├── status_panel.py         # 实时状态面板
│   │   ├── test_panel.py           # 测试面板
│   │   └── workflow_panel.py       # 工作流编辑面板
│   ├── components/                 # 通用组件
│   │   ├── __init__.py
│   │   ├── device_bind_widget.py   # 设备绑定组件
│   │   ├── empty_state_widget.py   # 空状态组件
│   │   ├── float_widget.py         # 悬浮窗组件
│   │   ├── screenshot_picker.py    # 截屏选点组件
│   │   ├── sidebar_widget.py       # 侧边栏组件
│   │   ├── step_editor.py          # 步骤编辑器
│   │   ├── step_list_widget.py     # 步骤列表（拖拽排序）
│   │   ├── task_tab_bar.py         # 任务标签栏
│   │   └── workflow_switcher.py    # 工作流切换器
│   ├── dialogs/                    # 对话框
│   │   ├── __init__.py
│   │   ├── setup_wizard.py         # 初始设置向导
│   │   ├── snippet_manager_dialog.py # 代码片段管理
│   │   └── workflow_manager_dialog.py # 工作流管理器
│   └── resources/                  # 资源文件
│       ├── style.qss               # QSS 样式表
│       └── icons/                  # 图标资源
│
├── tp/                             # 模板图片目录
│   ├── 1.jpg, 2.jpg, button.jpg   # 各种模板图
│   ├── kai_1.jpg, kai_2.jpg       # 界面状态模板
│   ├── dl.jpg, yji.jpg, kt.jpg    # 识别用模板
│   └── ...
│
├── lib/                            # 第三方库
│   └── scrcpy-server.jar           # scrcpy 服务端
│
├── minicap_files/                  # minicap 相关（备用）
│   ├── minicap
│   └── minicap.so
│
├── snippets/                       # 代码片段
│   └── snippets.json
│
├── tests/                          # 测试
│   ├── test_integration.py
│   ├── test_screen_capture.py
│   ├── ui_smoke/                   # UI 冒烟测试
│   ├── stability/                  # 稳定性测试
│   └── workflow_replay/            # 工作流回放测试
│
└── docs/                           # 文档
    └── cast-acceptance.md
```

---

## 4. 核心模块详解

### 4.1 ADB 核心模块 — `core/adb_core.py`

#### 模块职责

统一封装所有 ADB 操作，消除代码重复，提供类型安全的接口。

#### 关键类

**`AdbCore`**

- 位置: [adb_core.py](file:///workspace/PY/core/adb_core.py#L14-L232)
- 职责: ADB 命令执行器，封装所有底层 ADB 操作

| 方法 | 签名 | 说明 |
|------|------|------|
| `set_device` | `(serial: str) -> None` | 设置当前设备序列号 |
| `get_device` | `() -> Optional[str]` | 获取当前设备序列号 |
| `execute` | `(command, timeout=30.0, device=None) -> CompletedProcess` | 执行原始 ADB 命令 |
| `tap` | `(x, y, device=None) -> bool` | 点击屏幕坐标 |
| `long_press` | `(x, y, duration=1000, device=None) -> bool` | 长按（通过 swipe 实现） |
| `swipe` | `(x1, y1, x2, y2, duration=300, device=None) -> bool` | 滑动操作 |
| `keyevent` | `(key, device=None) -> bool` | 发送按键事件 |
| `input_text` | `(text, device=None) -> bool` | 输入文本 |
| `screenshot` | `(remote_path, device=None) -> bool` | 截屏到设备存储 |
| `pull_file` | `(remote, local, device=None) -> bool` | 从设备拉取文件 |
| `push_file` | `(local, remote, device=None) -> bool` | 推送文件到设备 |
| `delete_file` | `(path, device=None) -> bool` | 删除设备上的文件 |
| `shell` | `(cmd, device=None, timeout=30.0) -> str` | 执行 shell 命令并返回 stdout |
| `wifi_enable` | `(device=None) -> bool` | 启用 WiFi |
| `wifi_disable` | `(device=None) -> bool` | 禁用 WiFi |
| `force_stop` | `(package, device=None) -> bool` | 强制停止应用 |
| `launch` | `(package, device=None) -> bool` | 启动应用（通过 monkey） |
| `get_device_list` | `() -> List[str]` | 获取已连接设备列表 |
| `get_device_resolution` | `(device=None) -> Tuple[int, int]` | 获取设备分辨率 |
| `push_and_start_scrcpy` | `(server_path, device=None) -> Popen` | 推送并启动 scrcpy 服务 |

**`AdbError`**

- 位置: [adb_core.py](file:///workspace/PY/core/adb_core.py#L10-L11)
- 职责: ADB 操作异常类

#### 模块级函数

文件末尾提供了模块级单例函数，直接调用 `_adb` 实例：

```python
_adb = AdbCore()

def tap(x, y, device=None) -> bool:
    return _adb.tap(x, y, device=device)
# ... 等其他便捷函数
```

---

### 4.2 配置管理器 — `core/config_manager.py`

#### 模块职责

统一管理所有 JSON 配置文件的读写，提供线程安全的原子写入、懒加载、键路径访问等特性。

#### 关键类

**`ConfigManager`**（单例模式）

- 位置: [config_manager.py](file:///workspace/PY/core/config_manager.py#L13-L238)
- 职责: 配置文件统一管理器

| 方法 | 签名 | 说明 |
|------|------|------|
| `__new__` | `(cls, *args, **kwargs)` | 单例实现 |
| `get_config` | `(key_path: str, default=None)` | 按键路径获取配置（如 `"buy_params.user_price"`） |
| `set_config` | `(key_path: str, value) -> None` | 按键路径设置配置（原子写入） |
| `get_workflow` | `(name: str) -> dict` | 获取指定工作流 |
| `set_workflow` | `(name: str, workflow: dict) -> None` | 保存工作流 |
| `get_all_workflows` | `() -> dict` | 获取所有工作流 |
| `delete_workflow` | `(name: str) -> None` | 删除工作流 |
| `reload` | `() -> None` | 从磁盘重新加载所有配置 |
| `save_config` | `() -> None` | 强制保存配置 |
| `save_workflows` | `() -> None` | 强制保存工作流 |

#### 默认配置结构

`DEFAULT_CONFIG` 包含以下顶级配置分组：

| 分组 | 说明 |
|------|------|
| `buy_params` | 购买参数（用户价格、价格系数、最低价格、邮件上限） |
| `mail_params` | 邮件参数（邮件计数文件、自动递增） |
| `schedule` | 定时任务配置 |
| `recognition` | 识别参数（模板阈值、模板目录、OCR GPU） |
| `ocr_regions` | OCR 识别区域（价格区域、按钮区域） |
| `wifi_control` | WiFi 控制命令 |
| `device` | 设备配置（游戏包名、基础分辨率、scrcpy 路径） |
| `timing` | 时间参数（默认等待、截屏等待等） |
| `logging` | 日志配置（文件、级别、大小） |
| `ui` | UI 配置（主题、悬浮窗、颜色） |
| `execution` | 执行策略（错误策略、重试次数） |
| `coordinate` | 坐标配置（自动缩放、不匹配警告） |
| `telemetry` | 遥测配置 |

#### 核心机制

- **原子写入**: 使用临时文件 + `shutil.move` 确保配置文件不会损坏
- **键路径访问**: 通过 `"a.b.c"` 形式访问嵌套字典
- **线程安全**: 使用 `threading.Lock` 保护并发访问
- **懒加载**: 首次访问时才加载配置文件
- **配置迁移**: 配合 `config_migrator.py` 实现版本升级

---

### 4.3 步骤执行引擎 — `core/step_executor.py`

#### 模块职责

按照工作流定义的步骤序列逐一执行，支持暂停、停止、错误恢复、变量系统、条件分支、循环等高级功能。

#### 关键类

**`StepExecutor`**（继承 `QObject`）

- 位置: [step_executor.py](file:///workspace/PY/core/step_executor.py#L21-L800)
- 职责: 工作流步骤执行引擎

#### 信号列表

| 信号 | 参数 | 触发时机 |
|------|------|----------|
| `step_started` | `(index: int, step_type: str)` | 步骤开始执行时 |
| `step_completed` | `(index: int, step_type: str)` | 步骤执行成功时 |
| `step_failed` | `(index: int, step_type: str, error: str)` | 步骤执行失败时 |
| `workflow_started` | `(name: str)` | 工作流开始时 |
| `workflow_completed` | `(name: str)` | 工作流成功完成时 |
| `workflow_failed` | `(name: str, error: str)` | 工作流失败时 |
| `workflow_paused` | - | 工作流暂停时 |
| `workflow_stopped` | - | 工作流被停止时 |
| `progress_updated` | `(current: int, total: int)` | 执行进度更新时 |
| `check_image_result` | `(found: bool)` | 图像匹配结果 |
| `ocr_result` | `(text: str)` | OCR 识别结果 |
| `resolution_mismatch` | `(msg: str)` | 分辨率不匹配警告 |

#### 主要方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `execute_workflow` | `(workflow_name, start_step=0) -> bool` | 执行指定工作流，支持从某步开始 |
| `execute_step` | `(workflow_name, step_index) -> bool` | 执行单个步骤（测试用） |
| `pause` | `() -> None` | 暂停执行 |
| `resume` | `() -> None` | 恢复执行 |
| `stop` | `() -> None` | 停止执行 |
| `is_running` | `() -> bool` | 是否正在运行 |
| `is_paused` | `() -> bool` | 是否已暂停 |
| `get_variable` | `(name, default=None)` | 获取变量值 |
| `set_variable` | `(name, value) -> None` | 设置变量值 |
| `clear_variables` | `() -> None` | 清空所有变量 |

#### 支持的步骤类型

| 类型 | 关键参数 | 说明 |
|------|----------|------|
| `tap` | `x`, `y`, `wait_after` | 点击屏幕坐标 |
| `long_press` | `x`, `y`, `duration`, `wait_after` | 长按 |
| `swipe` | `x1`, `y1`, `x2`, `y2`, `duration` | 滑动 |
| `keyevent` | `key` | 按键事件 |
| `wait` | `seconds` | 等待 |
| `wifi` | `action` (enable/disable) | 开关 WiFi |
| `force_stop` | `package`, `wait_after` | 强制停止应用 |
| `launch` | `package`, `wait_after` | 启动应用 |
| `screenshot` | `save_path` | 截屏保存 |
| `pull_file` | `remote`, `local` | 拉取文件 |
| `delete_file` | `path` | 删除文件 |
| `check_image` | `template`, `threshold`, `assign_variable` | 模板匹配检测 |
| `ocr_region` | `region`, `assign_variable` | OCR 区域识别 |
| `tap_point` | `x`, `y`, `wait_after` | 点坐标点击（同 tap） |
| `call_workflow` | `workflow` | 调用子工作流 |
| `condition` | `check`, `then_steps`, `else_steps` | 条件分支 |
| `loop` | `max_count`, `condition`, `steps` | 循环执行 |
| `input_text` | `text` | 输入文本 |
| `variable` | `var_name`, `var_type`, `var_value` | 设置变量 |
| `adb_command` | `adb_cmd`, `assign_variable` | 执行原始 ADB 命令 |
| `expression` | - | 执行表达式求值 |

#### 错误处理策略

步骤支持 `on_fail` 字段，值可以是：

| 值 | 行为 |
|----|------|
| `stop` | 停止工作流（默认） |
| `retry` | 重试直到成功或被停止 |
| `recover` | 执行恢复工作流后重试当前步骤 |
| `skip` | 跳过失败步骤，继续下一步 |

---

### 4.4 工作流编排引擎 — `core/workflow_engine.py`

#### 模块职责

实现游戏自动化主循环，包括价格检查、购买决策、卡邮件流程、游戏恢复等业务逻辑。

#### 关键类

**`WorkflowEngine`**（继承 `QObject`）

- 位置: [workflow_engine.py](file:///workspace/PY/core/workflow_engine.py#L362-L452)
- 职责: 工作流编排引擎，管理主循环线程

#### 内部工作类

**`_WorkflowWorker`**（继承 `QObject`）

- 位置: [workflow_engine.py](file:///workspace/PY/core/workflow_engine.py#L19-L359)
- 职责: 在独立线程中运行主循环逻辑

#### 信号列表

| 信号 | 参数 | 说明 |
|------|------|------|
| `price_updated` | `(price: int)` | 价格更新 |
| `mail_count_updated` | `(count: int)` | 邮件计数更新 |
| `status_updated` | `(status: str, color: str)` | 状态文本更新 |
| `cycle_completed` | `(cycle: int)` | 完成一个购买周期 |
| `error_occurred` | `(error: str)` | 发生错误 |

#### 主要方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `start` | `() -> None` | 启动主循环（新线程） |
| `stop` | `() -> None` | 停止主循环 |
| `pause` | `() -> None` | 暂停 |
| `resume` | `() -> None` | 恢复 |
| `is_running` | `() -> bool` | 是否运行中 |
| `get_current_price` | `() -> int` | 获取当前价格 |
| `get_mail_count` | `() -> int` | 获取邮件计数 |
| `reset_mail_count` | `() -> None` | 重置邮件计数 |

#### 主循环流程

```
开始
  ↓
刷新价格
  ↓
识别按钮文字 ──┬── 中文含"方" → 确认购买界面 → 执行购买 → 卡邮件流程
              │
              ├── 数字 → 购买界面 → 价格检查循环
              │                           ↓
              │                    价格合适？──是→ 购买 → 卡邮件
              │                           ↓否
              │                        继续刷新
              │
              └── 其他 → 恢复游戏 → 重启游戏 → 检测界面 → 恢复流程
```

---

### 4.5 截屏模块 — `core/screen_capture.py`

#### 模块职责

提供高效、稳定的屏幕截图能力，采用 scrcpy 流媒体方案为主，screencap 命令为兜底的双模式设计。

#### 关键类

**`ScrcpyCapture`**（继承 `QObject`）

- 位置: [screen_capture.py](file:///workspace/PY/core/screen_capture.py#L35-L473)
- 职责: 屏幕捕获模块

#### 信号列表

| 信号 | 参数 | 说明 |
|------|------|------|
| `frame_captured` | `(frame: np.ndarray)` | 新帧捕获 |
| `connection_lost` | - | 连接断开 |
| `connection_restored` | - | 连接恢复 |
| `error_occurred` | `(msg: str)` | 发生错误 |

#### 主要方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `start` | `(device_serial, server_jar_path, max_retries=3) -> bool` | 启动截屏 |
| `stop` | `() -> None` | 停止截屏 |
| `get_current_frame` | `() -> Optional[np.ndarray]` | 获取当前帧（线程安全） |
| `is_connected` | `() -> bool` | 是否已连接 |

#### 技术架构

```
scrcpy 模式（主）:
  Android 设备 → scrcpy-server.jar → H.264 流 → adb forward →
  → Socket → ffmpeg 解码 → MJPEG → OpenCV imdecode → 帧缓存

screencap 模式（兜底）:
  adb exec-out screencap -p → PNG 数据 → OpenCV imdecode → 帧缓存
```

#### 特性

- **自动重连**: scrcpy 连接断开后自动尝试重连
- **模式降级**: scrcpy 启动失败自动切换到 screencap 模式
- **线程安全**: 帧访问使用锁保护
- **限流输出**: 帧发射间隔约 33ms（~30fps）
- **资源清理**: 完整的资源释放流程

---

### 4.6 OCR 引擎 — `core/ocr_engine.py`

#### 模块职责

封装 EasyOCR，提供文字识别、价格识别、按钮文字分类等功能。

#### 关键类

**`OcrEngine`**（单例模式）

- 位置: [ocr_engine.py](file:///workspace/PY/core/ocr_engine.py#L9-L117)
- 职责: OCR 识别引擎

#### 主要方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `initialize` | `(gpu=False, progress_callback=None) -> bool` | 初始化 OCR 引擎 |
| `is_initialized` | `() -> bool` | 是否已初始化 |
| `recognize` | `(image, region=None) -> str` | 识别图像中的文字 |
| `recognize_price` | `(image, region=None) -> int` | 识别价格（返回整数） |
| `recognize_button` | `(image, region=None) -> tuple` | 识别按钮文字并分类 |

#### `recognize_button` 返回值

返回 `(type, text)` 元组，`type` 取值：

| 值 | 说明 |
|----|------|
| `"chinese"` | 包含中文字符 |
| `"number"` | 数字占比超过一半 |
| `"unknown"` | 其他情况 |

#### 价格识别特殊处理

- 去除非数字和逗号字符
- 移除末尾的 `8`（经验修正，替换为 `0`）
- 位数不足 6 位返回超大值（表示识别失败）

---

### 4.7 设备管理器 — `core/device_manager.py`

#### 模块职责

管理设备选择、连接状态监控、分辨率获取等设备相关功能。

#### 关键类

**`DeviceManager`**（继承 `QObject`）

- 位置: [device_manager.py](file:///workspace/PY/core/device_manager.py#L11-L86)
- 职责: 设备管理器

#### 信号列表

| 信号 | 参数 | 说明 |
|------|------|------|
| `device_connected` | `(serial: str)` | 设备重新连接 |
| `device_disconnected` | `(serial: str)` | 设备断开连接 |
| `device_changed` | `(serial: str)` | 当前设备变更 |
| `connection_status_changed` | `(connected: bool)` | 连接状态变化 |

#### 主要方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `refresh_device_list` | `() -> List[str]` | 刷新设备列表 |
| `select_device` | `(serial: str) -> bool` | 选择设备 |
| `get_current_device` | `() -> Optional[str]` | 获取当前设备 |
| `get_device_resolution` | `() -> Optional[Tuple[int, int]]` | 获取设备分辨率 |
| `check_connection` | `() -> bool` | 检查连接状态 |
| `start_monitoring` | `(interval=5.0) -> None` | 启动连接监控 |
| `stop_monitoring` | `() -> None` | 停止连接监控 |

---

### 4.8 其他核心模块

| 模块 | 文件 | 职责 |
|------|------|------|
| 错误策略 | [error_policy.py](file:///workspace/PY/core/error_policy.py) | 错误分类、重试策略、退避算法 |
| 表达式求值 | [expression_eval.py](file:///workspace/PY/core/expression_eval.py) | 安全的表达式求值器 |
| 配置迁移 | [config_migrator.py](file:///workspace/PY/core/config_migrator.py) | 配置版本迁移与验证 |
| 日志系统 | [logger.py](file:///workspace/PY/core/logger.py) | 日志初始化、Qt 日志处理器 |
| 结构化日志 | [structured_log.py](file:///workspace/PY/core/structured_log.py) | 结构化日志格式 |
| 任务状态 | [task_state_manager.py](file:///workspace/PY/core/task_state_manager.py) | 多任务状态持久化 |
| 操作录制 | [recorder.py](file:///workspace/PY/core/recorder.py) | 操作录制与回放 |
| 遥测 | [telemetry.py](file:///workspace/PY/core/telemetry.py) | 使用数据收集 |

---

## 5. UI 模块详解

### 5.1 主窗口 — `ui/main_window.py`

#### 模块职责

应用主窗口，负责初始化所有核心模块、布局管理、信号连接、任务管理等。

#### 关键类

**`MainWindow`**（继承 `QMainWindow`）

- 位置: [main_window.py](file:///workspace/PY/ui/main_window.py#L105-L691)
- 职责: 应用主窗口

#### 主要成员

| 成员 | 类型 | 说明 |
|------|------|------|
| `_config_manager` | `ConfigManager` | 配置管理器 |
| `_adb_core` | `AdbCore` | ADB 核心 |
| `_device_manager` | `DeviceManager` | 设备管理器 |
| `_screen_capture` | `ScrcpyCapture` | 截屏模块 |
| `_ocr_engine` | `OcrEngine` | OCR 引擎 |
| `_step_executor` | `StepExecutor` | 步骤执行器 |
| `_task_state` | `TaskStateManager` | 任务状态管理 |
| `_floating_widget` | `FloatingWidget` | 悬浮窗 |

#### UI 结构

```
MainWindow
├── TaskTabBar (顶部任务标签栏)
├── Body (水平布局)
│   ├── SidebarWidget (左侧边栏，260px)
│   │   ├── DeviceBindWidget (设备绑定)
│   │   ├── WorkflowSwitcher (工作流切换)
│   │   └── StepListWidget (步骤预览列表)
│   └── MainSplitter (垂直分割)
│       ├── CenterSplitter (水平分割)
│       │   ├── QStackedWidget (面板容器)
│       │   │   ├── WorkflowPanel
│       │   │   ├── ConfigPanel
│       │   │   ├── DevicePanel
│       │   │   ├── StatusPanel
│       │   │   └── TestPanel
│       │   └── ScreenshotPicker (截屏选点)
│       └── LogPanel (日志面板)
└── StatusBar (状态栏)
```

---

### 5.2 功能面板 — `ui/panels/`

| 面板 | 文件 | 职责 |
|------|------|------|
| 工作流编辑 | [workflow_panel.py](file:///workspace/PY/ui/panels/workflow_panel.py) | 工作流增删改查、步骤编辑 |
| 参数配置 | [config_panel.py](file:///workspace/PY/ui/panels/config_panel.py) | 全局参数可视化配置 |
| 设备管理 | [device_panel.py](file:///workspace/PY/ui/panels/device_panel.py) | 设备列表、连接管理 |
| 运行监控 | [status_panel.py](file:///workspace/PY/ui/panels/status_panel.py) | 实时状态、价格显示、控制按钮 |
| 日志面板 | [log_panel.py](file:///workspace/PY/ui/panels/log_panel.py) | 运行日志展示、过滤 |
| 测试面板 | [test_panel.py](file:///workspace/PY/ui/panels/test_panel.py) | 单步测试、工作流测试 |

---

### 5.3 通用组件 — `ui/components/`

| 组件 | 文件 | 职责 |
|------|------|------|
| 设备绑定 | [device_bind_widget.py](file:///workspace/PY/ui/components/device_bind_widget.py) | 设备选择与绑定 |
| 空状态 | [empty_state_widget.py](file:///workspace/PY/ui/components/empty_state_widget.py) | 空状态、加载遮罩 |
| 悬浮窗 | [float_widget.py](file:///workspace/PY/ui/components/float_widget.py) | 悬浮状态显示窗 |
| 截屏选点 | [screenshot_picker.py](file:///workspace/PY/ui/components/screenshot_picker.py) | 截屏显示、坐标选取 |
| 侧边栏 | [sidebar_widget.py](file:///workspace/PY/ui/components/sidebar_widget.py) | 可折叠侧边栏 |
| 步骤编辑器 | [step_editor.py](file:///workspace/PY/ui/components/step_editor.py) | 单步骤属性编辑 |
| 步骤列表 | [step_list_widget.py](file:///workspace/PY/ui/components/step_list_widget.py) | 步骤列表、拖拽排序 |
| 任务标签 | [task_tab_bar.py](file:///workspace/PY/ui/components/task_tab_bar.py) | 多任务标签栏 |
| 工作流切换 | [workflow_switcher.py](file:///workspace/PY/ui/components/workflow_switcher.py) | 工作流下拉选择器 |

---

### 5.4 对话框 — `ui/dialogs/`

| 对话框 | 文件 | 职责 |
|--------|------|------|
| 设置向导 | [setup_wizard.py](file:///workspace/PY/ui/dialogs/setup_wizard.py) | 初始设置向导 |
| 片段管理 | [snippet_manager_dialog.py](file:///workspace/PY/ui/dialogs/snippet_manager_dialog.py) | 代码片段管理 |
| 工作流管理 | [workflow_manager_dialog.py](file:///workspace/PY/ui/dialogs/workflow_manager_dialog.py) | 工作流导入导出管理 |

---

## 6. 配置系统

### 6.1 配置文件清单

| 文件 | 路径 | 说明 |
|------|------|------|
| 全局配置 | [config.json](file:///workspace/PY/config/config.json) | 所有全局参数 |
| 坐标配置 | [coordinates.json](file:///workspace/PY/config/coordinates.json) | 坐标点集中管理（历史） |
| 工作流配置 | [workflows.json](file:///workspace/PY/config/workflows.json) | 所有工作流定义 |
| 任务配置 | [tasks.json](file:///workspace/PY/config/tasks.json) | 多任务状态 |
| UI 状态 | [ui_state.json](file:///workspace/PY/config/ui_state.json) | UI 布局持久化 |

### 6.2 配置访问方式

通过 `ConfigManager` 的键路径（dot-path）方式访问：

```python
# 获取
price = config_manager.get_config("buy_params.user_price", 0.5)
threshold = config_manager.get_config("recognition.template_threshold", 0.85)

# 设置
config_manager.set_config("buy_params.user_price", 1.0)
```

### 6.3 JSON Schema 验证

配置文件有对应的 JSON Schema 用于验证：

- `config/schema/config.schema.json`
- `config/schema/workflows.schema.json`

---

## 7. 工作流系统

### 7.1 工作流数据结构

```json
{
  "workflows": {
    "workflow_name": {
      "description": "工作流描述",
      "device_resolution": {
        "width": 2400,
        "height": 1080
      },
      "steps": [
        {
          "type": "tap",
          "x": 100,
          "y": 200,
          "comment": "点击说明",
          "wait_after": 1.0,
          "enabled": true,
          "on_fail": "stop"
        }
      ]
    }
  }
}
```

### 7.2 预置工作流

| 工作流名称 | 说明 |
|------------|------|
| `after_buy` | 购买后操作（卸装备、转仓库） |
| `begin` | 开始匹配并重启游戏 |
| `ru_run_1` | 卡邮件-断网流程 |
| `ru_run_2` | 卡邮件-开网领奖 |
| `restart` | 重启游戏 |
| `ru_run` | 恢复-有对局 |
| `kai_run` | 恢复-无对局 |
| `dl_run` | 恢复-需要登录 |
| `refresh_path` | 刷新路径 |
| `e_adb_buy` | 执行购买 |
| `programme_choose_N` | 选择方案 N |
| `kaishi` | 开始 |
| `fin` | 结束 |

---

## 8. 依赖关系

### 8.1 Python 依赖

**文件**: [requirements.txt](file:///workspace/PY/requirements.txt)

| 包名 | 版本要求 | 用途 |
|------|----------|------|
| `PyQt5` | `>=5.15` | GUI 框架 |
| `easyocr` | `>=1.7` | OCR 文字识别 |
| `opencv-python` | `>=4.8` | 图像处理、模板匹配 |
| `numpy` | `>=1.24` | 数值计算 |
| `Pillow` | `>=10.0` | 图像处理 |
| `pyinstaller` | `>=6.0` | 打包分发 |

### 8.2 外部依赖

| 依赖 | 说明 |
|------|------|
| **ADB** | Android 调试桥，必须安装并在 PATH 中 |
| **ffmpeg** | scrcpy 模式下用于视频解码（可选，screencap 模式不需要） |
| **Android 设备** | 需开启 USB 调试 |
| **EasyOCR 模型** | 首次运行自动下载中英文模型 |

### 8.3 模块依赖图

```
main.py
  ├─ ui/main_window.py
  │   ├─ core/config_manager.py
  │   │   └─ core/config_migrator.py
  │   ├─ core/adb_core.py
  │   ├─ core/device_manager.py
  │   │   └─ core/adb_core.py
  │   ├─ core/screen_capture.py
  │   ├─ core/ocr_engine.py
  │   ├─ core/step_executor.py
  │   │   ├─ core/error_policy.py
  │   │   └─ core/expression_eval.py
  │   ├─ core/workflow_engine.py
  │   │   └─ core/step_executor.py
  │   ├─ core/task_state_manager.py
  │   └─ ui/* (所有 UI 模块)
  └─ core/logger.py
```

---

## 9. 项目运行方式

### 9.1 环境准备

#### 1. 安装 Python 依赖

```bash
cd PY
pip install -r requirements.txt
```

#### 2. 安装 ADB

确保 `adb` 命令在系统 PATH 中可用。

#### 3. 安装 ffmpeg（可选，scrcpy 模式需要）

确保 `ffmpeg` 命令在系统 PATH 中可用。

#### 4. 配置 Android 设备

- 启用 USB 调试
- 通过 USB 连接电脑
- 授权调试请求

### 9.2 启动程序

```bash
cd PY
python main.py
```

### 9.3 首次使用流程

1. 启动程序后，在侧边栏选择设备
2. 等待截屏连接建立（scrcpy 模式或 screencap 模式）
3. 选择/编辑工作流
4. 配置购买参数（用户价格、价格系数等）
5. 切换到「运行监控」面板
6. 点击「开始」按钮

### 9.4 打包为 EXE

使用 PyInstaller 打包：

```bash
cd PY
pyinstaller app.spec
```

打包产物在 `dist/` 目录下。

### 9.5 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl + B` | 切换侧边栏显示/隐藏 |
| `Ctrl + Shift + L` | 切换日志面板显示/隐藏 |

---

## 10. 数据模型

### 10.1 步骤数据模型

```python
Step = {
    "type": str,           # 步骤类型（见步骤类型表）
    "comment": str,        # 注释/说明
    "enabled": bool,       # 是否启用
    "wait_after": float,   # 执行后等待秒数
    "on_fail": str,        # 失败策略: stop/retry/recover/skip
    "recover_workflow": str,  # 恢复工作流（on_fail=recover 时）
    # ... 其他类型特定字段
}
```

### 10.2 工作流数据模型

```python
Workflow = {
    "description": str,       # 工作流描述
    "device_resolution": {    # 基准设备分辨率
        "width": int,
        "height": int
    },
    "steps": List[Step]       # 步骤列表
}
```

### 10.3 任务数据模型

```python
Task = {
    "id": str,                # 任务 ID
    "title": str,             # 任务标题
    "workflow": str,          # 绑定的工作流名称
    "bound_device": str,      # 绑定的设备序列号
    "bound_device_label": str, # 设备显示标签
    "selected_step_index": int # 当前选中的步骤索引
}
```

---

## 附录：关键文件速查表

| 功能 | 文件路径 |
|------|----------|
| 程序入口 | [main.py](file:///workspace/PY/main.py) |
| 主窗口 | [main_window.py](file:///workspace/PY/ui/main_window.py) |
| ADB 核心 | [adb_core.py](file:///workspace/PY/core/adb_core.py) |
| 配置管理 | [config_manager.py](file:///workspace/PY/core/config_manager.py) |
| 步骤执行 | [step_executor.py](file:///workspace/PY/core/step_executor.py) |
| 工作流引擎 | [workflow_engine.py](file:///workspace/PY/core/workflow_engine.py) |
| 截屏模块 | [screen_capture.py](file:///workspace/PY/core/screen_capture.py) |
| OCR 引擎 | [ocr_engine.py](file:///workspace/PY/core/ocr_engine.py) |
| 设备管理 | [device_manager.py](file:///workspace/PY/core/device_manager.py) |
| 全局配置 | [config.json](file:///workspace/PY/config/config.json) |
| 工作流配置 | [workflows.json](file:///workspace/PY/config/workflows.json) |
| 样式表 | [style.qss](file:///workspace/PY/ui/resources/style.qss) |
| 依赖清单 | [requirements.txt](file:///workspace/PY/requirements.txt) |
| 设计文档 | [设计文档.md](file:///workspace/PY/设计文档.md) |
