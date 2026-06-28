# CTRL+Z 撤销/重做 —— 补缺口与修 bug

## Summary

撤销/重做功能**已存在**于 [workflow_panel.py](file:///d:/Github/PY/ui/panels/workflow_panel.py)（栈、`_push_undo`/`_undo`/`_redo`、↶↷ 按钮、CTRL+Z/Y 快捷键全部就绪），但有 6 个缺口/bug 导致：调序与启用切换不可撤销、切换工作流会跨流串台、保存/执行不清栈、快照未剥离 preview 有内存爆炸风险。

本计划**补缺口 + 修 bug**，让现有实现符合 grill 锁定的设计。不重写、不扩展范围。

## Current State Analysis

**已正确接入撤销的变异点**（无需改动）：
- `add_step` ([L591](file:///d:/Github/PY/ui/panels/workflow_panel.py#L591))
- `delete_step` ([L616](file:///d:/Github/PY/ui/panels/workflow_panel.py#L616))
- `copy_step` ([L636](file:///d:/Github/PY/ui/panels/workflow_panel.py#L636))
- `move_step_up` / `move_step_down` ([L657](file:///d:/Github/PY/ui/panels/workflow_panel.py#L657), [L679](file:///d:/Github/PY/ui/panels/workflow_panel.py#L679))

**数据流事实**（来自探索）：
- 配置真相源是 `config_manager.get_workflow(name)["steps"]`，`refresh_step_list()` 从它灌入 `StepListWidget`。
- `_push_undo()` 从 `config_manager` 读取（即变异前状态），所以在变异处理函数开头调用即可正确快照前置状态。
- 撤销栈在 `workflow_panel`，不在 widget；快捷键在 main_window 转发到 `workflow_editor._undo()/_redo()`。

## Proposed Changes

### 改动 A：新增两个辅助方法（workflow_panel.py）

在 [_push_undo 上方](file:///d:/Github/PY/ui/panels/workflow_panel.py#L534) 新增：

```python
def _clear_undo_redo(self):
    """清空撤销/重做栈。用于工作流切换、保存、执行场景。"""
    self._undo_stack.clear()
    self._redo_stack.clear()
    self._update_undo_redo_buttons()

def _snapshot_steps(self, steps):
    """深拷贝步骤并剥离 preview 字段，防 base64 图撑爆内存。"""
    snapshot = []
    for s in steps:
        light = {k: v for k, v in s.items() if k != "preview"}
        snapshot.append(copy.deepcopy(light))
    return snapshot
```

**Why**：`_clear_undo_redo` 给清栈场景统一入口；`_snapshot_steps` 落实 Q9-A（剥离 preview）防内存爆炸。先剥离再 deepcopy，避免复制 base64 大字符串。

---

### 改动 B：快照剥离 preview（workflow_panel.py，gap #5）

替换三处 `copy.deepcopy(workflow.get("steps", []))`：

- [_push_undo L540](file:///d:/Github/PY/ui/panels/workflow_panel.py#L540) → `self._undo_stack.append(self._snapshot_steps(workflow.get("steps", [])))`
- [_undo L553](file:///d:/Github/PY/ui/panels/workflow_panel.py#L553) → `self._redo_stack.append(self._snapshot_steps(workflow.get("steps", [])))`
- [_redo L567](file:///d:/Github/PY/ui/panels/workflow_panel.py#L567) → `self._undo_stack.append(self._snapshot_steps(workflow.get("steps", [])))`

**Why**：Q9-A 锁定。50 步 × base64 缩略图不剥离可达数百 MB。

---

### 改动 C：拖拽调序入栈（workflow_panel.py，gap #1）

在 [_on_step_order_changed L439-441](file:///d:/Github/PY/ui/panels/workflow_panel.py#L439-L448) 的 guard 之后、写 config 之前，插入：

```python
self._push_undo()
```

**Why**：`_push_undo` 读 config（仍是旧顺序），正确快照调序前状态。补全 v1 范围里的"调序可撤销"。

---

### 改动 D：启用/禁用切换入栈（gap #2）

当前 [_on_step_toggle_enabled 在 main_window L421-435](file:///d:/Github/PY/ui/main_window.py#L421-L435) 直接改 config，绕过 workflow_panel。

**重构**：在 workflow_panel 新增 `toggle_step_enabled(index)`：

```python
def toggle_step_enabled(self, index: int):
    if not self._current_workflow_name:
        return
    workflow = self._config_manager.get_workflow(self._current_workflow_name)
    if not workflow:
        return
    steps = workflow.get("steps", [])
    if index >= len(steps):
        return
    self._push_undo()
    steps[index]["enabled"] = not steps[index].get("enabled", True)
    workflow["steps"] = steps
    self._config_manager.set_workflow(self._current_workflow_name, workflow)
    self.refresh_step_list()
```

main_window 的 [_on_step_toggle_enabled L421-435](file:///d:/Github/PY/ui/main_window.py#L421-L435) 改为转发：

```python
def _on_step_toggle_enabled(self, index: int):
    self._panels["workflow_editor"].toggle_step_enabled(index)
```

**Why**：所有 step 变异 + undo 集中在 workflow_panel。该函数被两处调用（侧边栏信号 L780、Space 快捷键 L599），都会自动受益。

---

### 改动 E：切换工作流清栈（workflow_panel.py，gap #3）

在 [on_workflow_selected L522-531](file:///d:/Github/PY/ui/panels/workflow_panel.py#L522-L531) 的两个分支（`index < 0` 和正常分支）开头各加：

```python
self._clear_undo_redo()
```

**Why**：C1 锁定。否则 A 切 B 后按 CTRL+Z 会把 A 的快照应用到 B，跨工作流串台、数据破坏。这是 6 个缺口里最高危的 bug。

---

### 改动 F：保存清栈（main_window.py，gap #4）

在 [_save_all L584-592](file:///d:/Github/PY/ui/main_window.py#L584-L592) 保存成功后（`self._toast.success` 之前）加：

```python
self._panels["workflow_editor"]._clear_undo_redo()
```

**Why**：C2 / Q12-P 锁定。保存后撤销栈清空，避免"撤销→内存与磁盘不一致→再保存覆盖磁盘 preview"的数据破坏链。

---

### 改动 G：执行工作流清栈（main_window.py，gap #6）

在 [启动工作流 worker 的方法 L858-876](file:///d:/Github/PY/ui/main_window.py#L858-L876)，于 L868（创建 `_WorkflowWorker` 之前）加：

```python
self._panels["workflow_editor"]._clear_undo_redo()
```

**Why**：C5 锁定。执行会写入 running/success/fail 等状态，不该被撤销回退。

## Decisions（grill 锁定，不再重议）

| 维度 | 决定 |
|---|---|
| 范围 | v1 只做 step_list 的删/复制/调序/启用切换撤销。step_editor/workflow/config/运行时动作**显式砍掉** |
| 架构 | 快照法 (Memento)，栈在 workflow_panel |
| 粒度 | 每个信号边界 = 1 次快照（非每字符） |
| Redo | CTRL+Y 配对，新动作清空 redo 栈（已实现） |
| 清栈时机 | C1 切换工作流 + C2 保存 + C3 不持久化 + C4 上限 50 + C5 执行 |
| Preview | 快照剥离，撤销后缩略图消失（出路 1） |

## Known Limitation（必须知晓）

改动 B 会**改变现有行为**：当前 undo 保留 preview（deepcopy 含 base64），改后 undo 丢失 preview。

后果链：
1. 撤销后识别类步骤（check_image/ocr_region）缩略图退化为 🔍 占位符
2. 此时若保存，磁盘上该步骤的 preview 也被清空
3. **preview 是可再生的运行时产物**——重跑该步骤即可恢复

这是 Q9-A（剥离 preview 防内存爆炸）与 Q12-P（保存清栈）锁定设计的必然代价。若无法接受，需回到 grill 重议 Q9（改选 B 引用共享，复杂度大）。

## Verification

1. **调序撤销**：拖拽调序 → CTRL+Z → 顺序恢复；CTRL+Y → 顺序再变。
2. **启用切换撤销**：Space 禁用某步 → CTRL+Z → 恢复启用；侧边栏右键切换同样生效。
3. **跨工作流不串台**：工作流 A 撤销几步 → 切到 B → CTRL+Z 无反应（栈已清），B 步骤不变。
4. **保存清栈**：做几步变异 → CTRL+S → ↶ 按钮变灰，CTRL+Z 无反应。
5. **执行清栈**：变异几步 → 启动工作流 → ↶ 按钮变灰。
6. **内存**：50 步带图工作流，连续 60 次变异 → 内存稳定（旧快照被弹，preview 未入栈）。
7. **preview 丢失**：跑 check_image 出图 → 删一步 → CTRL+Z 恢复 → 该步缩略图为 🔍（预期行为）。
8. **现有功能回归**：add/delete/copy/move up/move down 的撤销仍正常。
