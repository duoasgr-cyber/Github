# 跳转机制 (Jump/Goto) 设计规范

## 1. 背景与目标

### 1.1 现状问题

当前项目的工作流执行逻辑中，步骤之间只能按顺序执行或通过 `condition`/`loop`/`call_workflow` 三种流程控制结构进行分支。步骤之间无法建立灵活的跳转关系。

从 `legacy/` 目录中的脚本（`ka.py`, `sale.py` 等）和 `workflow_engine.py` 可以看到，实际业务流程中存在大量"执行完某步骤后跳到前面/后面某步骤"的需求（如比价循环、恢复流程等），目前这些关系全部硬编码在 Python 代码中，无法通过 UI 配置。

### 1.2 目标

- 在现有步骤系统中新增跳转(Goto)能力，作为 step 的可选属性
- 支持三种跳转模式：无条件跳转、条件跳转、循环回跳
- 在步骤列表 UI 中直观展示跳转关系（跳转出箭头 + 跳入点标记）
- 标签自动生成（`#` + 4位十六进制），用户无需手动管理
- 防死循环保护（全局最大跳转次数限制）
- 不破坏现有步骤类型和数据结构（所有新字段均为可选）

## 2. 数据模型

### 2.1 Step 新增字段

在现有 step dict 上新增以下字段（均为可选，不影响现有步骤）：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `jump_to` | `str` | `""` | 跳转目标标签，如 `"#56D6"`。为空表示无跳转 |
| `jump_count` | `int` | `0` | 最大跳转次数。0 = 无限次（仅受全局限制保护） |
| `jump_condition` | `dict \| null` | `null` | 条件跳转时的判断条件，格式同 condition step 的 `check` 字段 |
| `jump_label` | `str` | `""` | 自身标签名，系统自动生成（`#XXXX` 格式） |
| `is_jump_target` | `bool` | `false` | 是否标记为跳入点（UI 展示用） |

### 2.2 完整 Step 示例

```json
{
  "type": "tap",
  "x": 500,
  "y": 500,
  "wait_after": 1.0,
  "jump_to": "#56D6",
  "jump_count": 1,
  "jump_condition": null,
  "jump_label": "",
  "is_jump_target": false,
  "comment": "点击后跳转到标签#56D6"
}
```

### 2.3 跳转标签格式

- 格式：`#` + 4位十六进制大写字母（如 `#56D6`、`#A3F1`、`#00FF`）
- 由系统自动生成，保证同一工作流内唯一
- 通过扫描所有步骤的 `jump_label` 和 `is_jump_target` 字段构建映射表

### 2.4 Workflow 级别：jump_labels 映射表

每个 workflow 的 steps 数组在执行前，系统会扫描构建 `jump_labels` 映射表：

```python
jump_labels = {
    "#56D6": 3,   # 标签 #56D6 对应 steps[3]
    "#A3F1": 7,   # 标签 #A3F1 对应 steps[7]
}
```

该映射表不持久化到 JSON 文件（每次执行前动态构建），但 `jump_label` 和 `is_jump_target` 字段会随 step 一起保存。

## 3. 跳转模式

### 3.1 无条件跳转

```json
{ "type": "tap", "x": 500, "y": 500, "jump_to": "#56D6" }
```

步骤执行成功后，立即跳转到 `#56D6` 对应的步骤继续执行。

### 3.2 条件跳转

```json
{
  "type": "tap",
  "x": 500, "y": 500,
  "jump_to": "#56D6",
  "jump_condition": {
    "type": "image_found",
    "template": "button.png",
    "threshold": 0.85
  }
}
```

步骤执行成功后，评估 `jump_condition`：
- 条件满足 → 跳转到 `#56D6`
- 条件不满足 → 继续执行下一步（i+1）

条件格式复用现有 condition step 的 `check` 字段格式，评估逻辑复用 `_evaluate_condition()` 方法。

### 3.3 循环回跳

```json
{ "type": "wait", "seconds": 1, "jump_to": "#LOOP_START", "jump_count": 10 }
```

步骤执行成功后跳转回 `#LOOP_START`，最多回跳 10 次。第 11 次执行该步骤时不再跳转，继续往下执行。

内部维护 `jump_counters: dict[str, int]`，key 为 `jump_to` 标签名，value 为已跳转次数。

## 4. 执行逻辑

### 4.1 修改 `_run_steps()` 方法

文件：`PY/core/step_executor.py`

当前实现（简化）：
```python
def _run_steps(self, steps, workflow_name, start_step, total_steps):
    for i in range(start_step, total_steps):
        # ... stop/pause 检查 ...
        self.execute_step(workflow_name, i)
    self.workflow_completed.emit(workflow_name)
```

修改后：
```python
def _run_steps(self, steps, workflow_name, start_step, total_steps):
    # 构建跳转标签映射表
    self._jump_labels = self._build_jump_labels(steps)
    self._jump_counters = {}  # label -> jump count
    self._total_jumps = 0     # 全局跳转计数

    i = start_step
    while i < total_steps:
        # ... stop/pause 检查（同原逻辑）...

        self.progress_updated.emit(i + 1, total_steps)
        success = self.execute_step(workflow_name, i)

        # 跳转处理
        step = steps[i]
        jump_to = step.get("jump_to", "")
        if jump_to:
            jump_result = self._handle_jump(step, i, steps)
            if jump_result == "jumped":
                i = self._jump_labels.get(jump_to, i + 1)
                continue
            elif jump_result == "error":
                return False
            # "continue" = 不跳转，继续下一步

        i += 1

    self.workflow_completed.emit(workflow_name)
    return True
```

### 4.2 `_handle_jump()` 方法

```python
def _handle_jump(self, step: dict, current_index: int, steps: list) -> str:
    """处理步骤跳转。返回 'jumped' / 'continue' / 'error'。"""
    jump_to = step.get("jump_to", "")
    if not jump_to:
        return "continue"

    # 检查跳转目标是否存在
    if jump_to not in self._jump_labels:
        self._structured_log(logging.ERROR, "Jump target not found: %s", jump_to)
        return "continue"  # 目标不存在则继续执行

    # 条件跳转：评估条件
    jump_condition = step.get("jump_condition")
    if jump_condition:
        condition_result = self._evaluate_condition(jump_condition)
        if not condition_result:
            return "continue"  # 条件不满足，继续下一步

    # 循环回跳：检查次数限制
    jump_count = step.get("jump_count", 0)
    if jump_count > 0:
        current_count = self._jump_counters.get(jump_to, 0)
        if current_count >= jump_count:
            return "continue"  # 已达最大次数，不再跳转
        self._jump_counters[jump_to] = current_count + 1

    # 全局防死循环保护
    self._total_jumps += 1
    if self._total_jumps > self._MAX_JUMPS:
        error_msg = f"Max jump limit ({self._MAX_JUMPS}) exceeded"
        self._structured_log(logging.ERROR, error_msg)
        self.workflow_failed.emit(self._current_workflow, error_msg)
        return "error"

    self._structured_log(logging.INFO, "Jumping from step %d to %s (index %d)",
                         current_index, jump_to, self._jump_labels[jump_to])
    return "jumped"
```

### 4.3 `_build_jump_labels()` 方法

```python
@staticmethod
def _build_jump_labels(steps: list) -> dict:
    """扫描步骤，构建 jump_labels 映射表：label -> step_index。"""
    labels = {}
    for i, step in enumerate(steps):
        label = step.get("jump_label", "")
        if label:
            labels[label] = i
        elif step.get("is_jump_target", False):
            # 标记为跳入点但没有标签，自动生成
            label = StepExecutor._generate_label(set(labels.keys()))
            step["jump_label"] = label
            labels[label] = i
    return labels

@staticmethod
def _generate_label(existing: set) -> str:
    """生成唯一的跳转标签。"""
    import random
    for _ in range(100):
        label = f"#{random.randint(0, 0xFFFF):04X}"
        if label not in existing:
            return label
    raise RuntimeError("Failed to generate unique jump label")
```

### 4.4 防死循环保护

- 全局常量 `_MAX_JUMPS = 1000`
- 每次跳转递增 `_total_jumps`
- 超过限制时：记录错误日志 → emit `workflow_failed` → 停止执行

## 5. UI 展示

### 5.1 步骤列表项展示

文件：`PY/ui/components/step_list_widget.py`

在 `StepItemWidget._setup_ui()` 中，步骤文本区域下方新增跳转信息行：

```
02. 移动鼠标  [点击]
              跳转 [->#56D6 ×1]     ← jump_to 不为空时显示
              跳入点 [#56D6]        ← is_jump_target 或 jump_label 不为空时显示
```

### 5.2 样式规范

- **跳转信息行**：蓝色文字 `#58a6ff`，字体 9px，显示在摘要行下方
- **跳入点标记**：红色 `#f85149`，带旗帜图标，显示在跳转信息行下方
- 点击跳转按钮：发射 `step_jump_clicked` 信号，携带目标标签名，由外部处理滚动和高亮

### 5.3 StepListWidget 新增信号

```python
step_jump_clicked = pyqtSignal(str)  # 携带 jump_to 标签名
```

外部（WorkflowPanel / MainFlowPanel）连接此信号，实现点击跳转按钮后滚动到目标步骤。

### 5.4 步骤编辑器跳转配置

文件：`PY/ui/components/step_editor.py`

在 `ADVANCED_FIELDS` 中新增：

```python
"jump_to": ("lineedit", {"placeholder": "跳转目标标签，如 #56D6", "default": ""}),
"jump_count": ("spinbox", {"min": 0, "max": 9999, "default": 0}),
"is_jump_target": ("checkbox", {"default": False}),
```

- `jump_to`：文本输入框，用户输入目标标签名
- `jump_count`：数字输入框，0 表示无限次
- `is_jump_target`：复选框，勾选后自动生成 `jump_label`

注意：`jump_condition` 和 `jump_label` 不直接在编辑器中暴露（`jump_label` 自动生成，`jump_condition` 后续迭代再加）。

## 6. 标签自动生成

### 6.1 生成规则

```python
import random

@staticmethod
def _generate_label(existing: set) -> str:
    for _ in range(100):
        label = f"#{random.randint(0, 0xFFFF):04X}"
        if label not in existing:
            return label
    raise RuntimeError("Failed to generate unique jump label")
```

### 6.2 生成时机

- 步骤保存时，如果 `is_jump_target` 为 true 但 `jump_label` 为空，自动生成
- 在 `_build_jump_labels()` 中处理（执行前扫描）
- 在 UI 层（`_on_step_changed`）中也可以提前生成，让用户看到标签名

## 7. 涉及文件清单

| 文件 | 修改内容 |
|------|----------|
| `PY/core/step_executor.py` | 新增 `_MAX_JUMPS`、`_build_jump_labels()`、`_generate_label()`、`_handle_jump()`；修改 `_run_steps()` 为 while 循环 + 跳转逻辑 |
| `PY/ui/components/step_list_widget.py` | `StepItemWidget` 新增跳转/跳入点展示行；`StepListWidget` 新增 `step_jump_clicked` 信号 |
| `PY/ui/components/step_editor.py` | `ADVANCED_FIELDS` 新增 `jump_to`、`jump_count`、`is_jump_target` |
| `PY/ui/panels/workflow_panel.py` | 连接 `step_jump_clicked` 信号，实现点击跳转后滚动到目标步骤 |
| `PY/ui/panels/main_flow_panel.py` | 同上 |

## 8. 非目标

- 不修改现有的 `call_workflow`、`condition`、`loop` 步骤类型的行为
- 不改变 `workflows.json` 的整体结构（仅 step 内新增可选字段）
- 不修改 `workflow_engine.py` 的硬编码逻辑（那是后续独立重构任务）
- 不在本次实现 `jump_condition` 的 UI 编辑器（条件跳转的条件通过 JSON 手动输入，后续迭代再加可视化编辑器）
