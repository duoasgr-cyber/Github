# 三角洲自动抢购工具 — AI 开发任务清单

> 本文件供 AI 编码助手按序执行。所有任务条目均基于对实际代码的核验，**不要凭名称猜测文件存在性**——下面每条都附了已确认的代码位置。

---

## 0. 项目上下文（已核验事实）

- 项目根目录：`PY/`
- 真实入口：`PY/main.py`（78 行）
- 打包配置：`PY/app.spec`（当前指向不存在的 `app.py`，需修复）
- 屏幕捕获：`PY/core/screen_capture.py`（scrcpy 主路径 + screencap 兜底，两条路径都走 `cv2.IMREAD_COLOR`，色彩空间本就一致）
- 步骤执行器：`PY/core/step_executor.py`（**800 行，仓库最大单文件**，20+ step 类型）
- 工作流引擎：`PY/core/workflow_engine.py`（452 行，含价格/邮件/恢复业务流程）
- 日志：`PY/core/logger.py`（用 `FileHandler`，未接 `RotatingFileHandler`）
- 配置：`PY/config/config.json`（含 `logging.max_log_size_mb` 但未被读取）

### 不要相信以下"看似存在"的文件（实际不存在）

- `mirror_window.py` — 不存在
- `ui/components/embedded_mirror_widget.py` — 不存在
- `app.py` — 不存在（spec 引用它，但真实入口是 `main.py`）

### 不要把这些当缺陷修（它们已正确或不存在）

- ❌ RGB/BGR 颜色空间不一致 — 两条路径都用 `cv2.IMREAD_COLOR`，一致
- ❌ screencap 缺 `cv2.imdecode` 返回空防护 — `screen_capture.py:348` 已有 `if frame is not None:`
- ❌ `call_workflow` 未实现 — `step_executor.py:580-586` 已实现并注册
- ❌ `timing.screenshot_wait` 浮点误差 — `config.json:49` 就是 `0.0`，无误差

---

## 1. AI 执行约束（强制）

1. **禁止虚构文件**：任何"重构/提取/下沉到 X 文件"的动作，必须先用 Glob/Grep 确认源文件存在。
2. **禁止过度设计**：这是单游戏工具，价格/邮件/恢复是核心业务，不要引入"可插拔策略接口"。只外置常量到 config，不改架构。
3. **禁止扩范围**：每个任务只做该任务列出的动作。发现新问题写入"待办备注"区，不要顺手改。
4. **禁止裸 except**：新增代码只在系统边界（subprocess、文件 IO、socket）做异常处理，且必须捕获具体异常类型。
5. **禁止新增文档**：除本文件外不创建任何 `*.md`、`README`、`CHANGELOG`。
6. **禁止删测试**：`tests/__init__.py` 为 0 字节是正常包标记，不要动。
7. **编码统一 UTF-8**：所有改动的文件保存为 UTF-8 无 BOM。
8. **每完成一个任务**：运行该任务的"验收命令"，输出必须达标才能进入下一个。

---

## 2. P0 — 正确性与可构建性（必须最先完成）

### P0-1 修复源码中文日志乱码（mojibake）

**背景**：5 个源文件的中文字符串被错误转码（UTF-8↔GBK 互误），日志输出为乱码。

**已确认乱码位置与字符数**：

| 文件 | 乱码字符数 |
|---|---|
| `core/screen_capture.py` | 43 |
| `ui/main_window.py` | 28 |
| `ui/panels/workflow_panel.py` | 17 |
| `ui/components/step_editor.py` | 11 |
| `_fix_bytes.py` | 19（此文件在 P0-4 删除，无需修） |

**动作**：
1. 逐文件用 Read 读取，识别形如 `灏濊瘯鍚姩` `杩炴帴` `鍚姩` `澶辫触` `鎺ㄩ€` 等 mojibake 段落。
2. 用正确中文替换。示例对照：
   - `"灏濊瘯鍚姩scrcpy杩炴帴 (%d/%d): %s"` → `"尝试启动scrcpy连接 (%d/%d): %s"`
   - `"scrcpy杩炴帴鎴愬姛: %s"` → `"scrcpy连接成功: %s"`
   - `"scrcpy杩炴帴澶辫触锛屽垏鎹㈠埌screencap鍥為€€妯″紡"` → `"scrcpy连接失败，切换到screencap回退模式"`
3. 只改字符串字面量，**不改任何逻辑、变量名、日志格式占位符**。

**验收命令**：
```bash
grep -rP '[鍚鐨澶鑷杩鐜鍑璁鎺鍒鍙璇]{2,}' --include='*.py' PY/ | grep -v '_fix_bytes' | wc -l
```
输出必须为 `0`。

---

### P0-2 修复 app.spec 入口

**背景**：`app.spec:34` 写的是 `Analysis(['app.py'], ...)`，但 `app.py` 不存在，真实入口是 `main.py`。当前 spec 无法构建。

**动作**：
1. 将 `app.spec` 第 34 行 `'app.py'` 改为 `'main.py'`。
2. 不要改 `name='三角洲自动抢购工具'`、datas、hiddenimports 等其他字段。

**验收命令**：
```bash
grep -n "Analysis" PY/app.spec
```
输出应包含 `['main.py']`，不含 `'app.py'`。

---

### P0-3 删除重复入口 mian.py

**背景**：`PY/main.py`(78 行) 是真正入口，`PY/mian.py`(532 行) 是拼写错的旧版本，并存会造成事故。

**动作**：
1. 用 Read 确认 `mian.py` 内容确为旧版入口（无被其他文件 import）。
2. 用 Grep 全仓库搜 `import mian` / `from mian`，确认零引用。
3. 删除 `PY/mian.py`。

**验收命令**：
```bash
ls PY/mian.py 2>&1
grep -rn "import mian\|from mian" PY/ --include='*.py' | wc -l
```
第一条应输出 `No such file`，第二条应为 `0`。

---

### P0-4 清理根目录一次性脚本

**背景**：`PY/` 根目录散落 44 个 `_*.py` / `e_*.py` 历史 patch/审计脚本，污染构建、lint、IDE 索引。

**动作**：
1. 列出 `PY/_*.py` 和 `PY/e_*.py` 全部文件。
2. 对每个文件用 Grep 确认**未被任何 `core/`、`ui/`、`tests/` 下的文件 import**。
3. 批量删除。被 import 的保留并记录到"待办备注"。

**禁止删除**：`main.py`、`app.spec`、`requirements.txt`、`开发步骤.md`、`设计文档.md`、`数据.json`、`用户定价.txt`、`you.txt` 等业务文件。

**验收命令**：
```bash
ls PY/_*.py PY/e_*.py 2>&1 | grep -c "No such file"
```
应输出 `2`（两类都消失）。

---

### P0-5 接入日志轮转

**背景**：`logger.py:16` 用 `logging.FileHandler`，`config.json:56` 的 `max_log_size_mb` 配了但没被读取。

**动作**：
1. 修改 `PY/core/logger.py` 的 `setup_logging`：
   - 从参数或 config 读取 `max_log_size_mb`（默认 1）。
   - `FileHandler` 换成 `logging.handlers.RotatingFileHandler(log_file, maxBytes=max_log_size_mb*1024*1024, backupCount=5, encoding='utf-8')`。
   - 保留原有 formatter、qt_handler 逻辑。
2. 修改 `PY/main.py` 调用处：把 `logging.max_log_size_mb` 传给 `setup_logging`。
3. 不要改 `get_logger`。

**验收命令**：
```bash
grep -n "RotatingFileHandler" PY/core/logger.py
grep -n "max_log_size_mb" PY/main.py
```
两条都要有非空输出。

---

### P0-6 处理死状态 _use_scrcpy

**背景**：`screen_capture.py` 中 `_use_scrcpy` 只被写（第 77/91/409/419 行），从不被业务读取（仅 test 在 assert）。

**动作**（二选一）：
- **方案 A（推荐）**：删除 `_use_scrcpy` 的所有赋值与初始化；同步删 `tests/test_screen_capture.py` 里对它的 assert。
- **方案 B**：在 `get_current_frame` 或日志路径用它区分来源。仅在确实需要区分时选 B。

**验收命令**：
```bash
grep -n "_use_scrcpy" PY/core/screen_capture.py
```
方案 A 应无输出；方案 B 应同时有读和写。

---

## 3. P1 — 架构解耦（P0 全部通过后开始）

### P1-1 拆分 step_executor.py

**背景**：800 行，20+ step 类型挤在一个分发表（`step_executor.py:408-423`）和一串 `_step_*` 方法里。

**动作**：
1. 新建 `PY/core/steps/` 目录。
2. 按 step 族拆分（建议）：
   - `steps/adb_ops.py`：`tap_point` / `input_text` / `adb_command` / `launch` / `screenshot` / `pull_file` / `delete_file`
   - `steps/vision.py`：`check_image` / `ocr_region`
   - `steps/flow_control.py`：`condition` / `loop` / `call_workflow` / `force_stop`
   - `steps/vars.py`：`variable` / `expression`
3. 每个文件导出一个 `register(dispatcher)` 函数或一组纯函数。
4. `step_executor.py` 主类只保留：分发字典组装、`execute_workflow`、`_interruptible_sleep`、递归防护。
5. **不要改 step 的 JSON schema 与执行语义**，纯结构搬运。

**验收命令**：
```bash
wc -l PY/core/step_executor.py
```
应 ≤ 300 行。

---

### P1-2 给 call_workflow 加递归防护

**背景**：`step_executor.py:580-586` 的 `_step_call_workflow` 直接 `self.execute_workflow(workflow_name)`，无递归上限，用户配置成环会栈溢出。

**动作**：
1. 在 `StepExecutor` 加实例字段 `self._workflow_call_stack: list[str] = []`。
2. `_step_call_workflow` 入口：
   - 若 `workflow_name in self._workflow_call_stack`：log error，return False（环检测）。
   - 若 `len(self._workflow_call_stack) >= 8`：log error，return False（深度上限）。
   - 否则 push、调用 `execute_workflow`、finally pop。
3. `execute_workflow` 公共入口也 push/pop 调用栈，保证顶层调用清零。

**验收命令**：
```bash
grep -n "_workflow_call_stack\|MAX.*DEPTH\|call_stack" PY/core/step_executor.py
```
应同时出现深度上限与环检测两处逻辑。

---

### P1-3 补 schedule 执行闭环或移除 UI 入口

**背景**：`config_panel.py:104` 写 `schedule.enabled`、`:109` 写 `schedule.start_time`，但全仓库无 `QTimer` 或调度触发逻辑。

**动作**（二选一，先问用户偏好）：
- **方案 A（实现）**：在 `MainWindow.__init__` 后加 `QTimer`，按 `schedule.start_time` 到点调用 `workflow_engine.start()`；窗口关闭时 stop timer。
- **方案 B（移除）**：从 `config_panel.py` 删除 `schedule.enabled` / `schedule.start_time` 两个 widget；同步删 `config.json` 对应字段与 schema。

**验收命令**：
- 方案 A：`grep -n "QTimer" PY/ui/main_window.py` 有输出
- 方案 B：`grep -rn "schedule.enabled" PY/` 仅出现在 schema 注释或彻底消失

---

### P1-4 workflow_engine 业务常量外置

**背景**：`workflow_engine.py` 硬编码 workflow 名与文案，如 `:162` `execute_workflow("refresh_path")`、`:197` `"恢复中..."`、`:130` `max_mail_count` 默认 190。

**动作**：
1. 在 `config.json` 加 `workflow_engine` 段：
   ```json
   "workflow_engine": {
     "refresh_workflow": "refresh_path",
     "max_mail_count_default": 190,
     "status_recovering": "恢复中...",
     "status_running": "运行中",
     "status_mail_full": "邮件已满"
   }
   ```
2. 同步更新 `config/schema/config.schema.json`。
3. `workflow_engine.py` 改为从 `config_manager.get_config("workflow_engine.xxx")` 读取，保留兜底默认值。
4. **不要抽策略接口**，只外置常量。

**验收命令**：
```bash
grep -n "refresh_path\|恢复中" PY/core/workflow_engine.py
```
应无硬编码字面量（只剩从 config 读取的代码）。

---

## 4. P2 — 测试与 CI（P1 全部通过后开始）

### P2-1 处理空测试目录

**背景**：`tests/stability/`、`tests/workflow_replay/` 只有 `__init__.py`，无任何测试文件。

**动作**（二选一）：
- **方案 A**：在两个目录各补至少 1 个真实测试文件（见 P2-2）。
- **方案 B**：删除两个空目录（保留 `tests/__init__.py` 不动）。

**禁止**：不要动 `tests/__init__.py` 的 0 字节内容，那是正常包标记。

**验收命令**：
```bash
find PY/tests/stability PY/tests/workflow_replay -name 'test_*.py' | wc -l
```
方案 A 应 ≥ 2；方案 B 应 `No such file or directory`。

---

### P2-2 补关键回归用例

在 `tests/` 下补以下用例（每条一个 `test_*.py` 或合并到一个文件多个 test 函数）：

| 用例 | 覆盖目标 |
|---|---|
| `test_no_mojibake.py` | 扫描所有 `core/*.py` `ui/**/*.py`，断言不含 mojibake 字符集 |
| `test_call_workflow_recursion.py` | 构造 A→B→A 环配置，断言 `_step_call_workflow` 返回 False 且不栈溢出 |
| `test_log_rotation.py` | 配 `max_log_size_mb=1`，写 >1MB 日志，断言产生 `.1` 备份 |
| `test_spec_buildable.py` | 静态检查 `app.spec` 引用的入口文件存在、datas 路径存在 |
| `test_step_dispatch.py` | 对 `step_executor` 每种 step 类型喂最小 step dict，断言分发到对应处理函数（mock adb） |

**验收命令**：
```bash
cd PY && python -m pytest tests/ -q
```
全部通过。

---

### P2-3 CI 闭环

**动作**：
1. 确认 `requirements.txt` 完整（含 `easyocr`、`cv2`、`numpy`、`PyQt5`、`pyinstaller`）。
2. 加一个最小 CI 配置（GitHub Actions 或等价）：`pip install -r requirements.txt` → `pytest tests/` → `pyinstaller app.spec`。
3. 构建产物名与 `app.spec` 的 `name='三角洲自动抢购工具'` 对齐。

**验收命令**：
```bash
cd PY && python -m pytest tests/ -q && pyinstaller app.spec --noconfirm
ls "dist/三角洲自动抢购工具/"
```
两条都成功。

---

## 5. 执行顺序（强制）

```
P0-1 编码乱码
  └─> P0-2 修 spec
        └─> P0-3 删 mian.py
              └─> P0-4 清根目录脚本
                    └─> P0-5 日志轮转
                          └─> P0-6 死状态
                                └─> P1-1 拆 step_executor
                                      └─> P1-2 递归防护
                                            └─> P1-3 schedule 闭环（需用户决策 A/B）
                                                  └─> P1-4 常量外置
                                                        └─> P2-1..P2-3
```

**P0-1 必须最先**：在乱码没修前，对 `screen_capture.py` / `main_window.py` 的任何改动都会在 mojibake 里踩坑。

**P1-3 需要用户决策**：执行到此处时，用 AskUserQuestion 询问选方案 A（实现定时）还是 B（移除入口）。

---

## 6. 待办备注区（AI 发现新问题时写入此处，不要顺手改）

<!-- 示例格式：
- [发现] YYYY-MM-DD 在 xxx.py:NN 发现 yyy 问题，建议列入下一轮。
-->

（空）

---

## 7. 验收口径汇总

| 阶段 | 通过标准 |
|---|---|
| P0 全过 | `grep -rP '[鍚鐨澶鑷杩鐜鍑璁鎺鍒鍙璇]{2,}' --include='*.py' PY/ \| wc -l` = 0；`ls PY/mian.py` 不存在；`ls PY/_*.py PY/e_*.py` 不存在；`app.spec` 含 `main.py`；`logger.py` 含 `RotatingFileHandler` |
| P1 全过 | `wc -l PY/core/step_executor.py` ≤ 300；`step_executor.py` 含深度上限+环检测；`workflow_engine.py` 无硬编码 workflow 名 |
| P2 全过 | `pytest tests/` 全绿；`pyinstaller app.spec` 产出 `dist/三角洲自动抢购工具/` |

---

## 8. 给 AI 的最后提醒

- 你不是在"重构一个通用自动化框架"，你在修一个**单游戏抢购工具的稳定性和可构建性**。每多一层抽象都是负债。
- 遇到不确定的文件存在性，**先 Glob 再动手**。上一轮计划就因为没核验文件，列了 3 个不存在的文件当 P1 主力。
- 每个 P0 任务完成后，先跑验收命令，再开下一个。不要批量改完一次性验。
