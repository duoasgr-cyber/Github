# 跳转机制实现任务清单

## Task 1: 核心执行逻辑 — 跳转框架
**文件**: `PY/core/step_executor.py`
- 新增 `_MAX_JUMPS = 1000` 常量
- 新增 `_build_jump_labels(steps)` 静态方法：扫描步骤构建 `label -> index` 映射表
- 新增 `_generate_label(existing)` 静态方法：生成唯一 `#XXXX` 标签
- 新增 `_handle_jump(step, current_index, steps)` 方法：处理跳转逻辑（无条件/条件/循环回跳/防死循环）
- 修改 `_run_steps()` 方法：将 `for` 循环改为 `while` 循环，在每步执行后调用 `_handle_jump()` 处理跳转

## Task 2: 步骤编辑器 — 跳转配置字段
**文件**: `PY/ui/components/step_editor.py`
- 在 `ADVANCED_FIELDS` 中新增 `jump_to`（lineedit）、`jump_count`（spinbox）、`is_jump_target`（checkbox）
- 确保这些字段在 `_on_field_changed()` 中被正确读取和保存

## Task 3: 步骤列表 UI — 跳转/跳入点展示
**文件**: `PY/ui/components/step_list_widget.py`
- `StepItemWidget._setup_ui()` 中新增跳转信息行和跳入点标记的 QLabel
- 跳转信息行显示格式：`跳转 [->#XXXX ×N]`（蓝色 `#58a6ff`）
- 跳入点标记显示格式：`跳入点 [#XXXX]`（红色 `#f85149`）
- 跳转按钮可点击，点击发射信号
- `StepListWidget` 新增 `step_jump_clicked = pyqtSignal(str)` 信号
- `StepItemWidget` 新增 `update_step_data()` 中同步更新跳转展示

## Task 4: 面板层 — 跳转联动
**文件**: `PY/ui/panels/workflow_panel.py` 和 `PY/ui/panels/main_flow_panel.py`
- 连接 `step_jump_clicked` 信号
- 收到信号后：查找目标标签对应的步骤索引，滚动列表到该位置并高亮选中

## Task 5: 单元测试
**文件**: `PY/tests/test_jump_mechanism.py`
- 测试无条件跳转
- 测试条件跳转（条件满足/不满足）
- 测试循环回跳（次数限制）
- 测试防死循环保护
- 测试标签生成唯一性
- 测试跳转目标不存在时的降级行为
