# Tasks

## Phase 1：步骤类型字段配置表

- [x] Task 1.1: 定义 STEP_TYPE_FIELDS 配置表
  - [x] 在 step_editor.py 中定义 21 种步骤类型的字段配置，每种包含 required、optional、field_types 三个子字典
  - [x] field_types 为每个字段指定控件类型（spinbox/doublespinbox/lineedit/checkbox/combobox/region_editor）和控件参数（min/max/decimals/items/default/placeholder/suffix）
  - [x] 所有类型的高级选项统一包含：on_fail、retry_count、assign_variable、recover_workflow、comment
  - [x] 所有类型的基础信息统一包含：display_name、enabled

## Phase 2：步骤编辑器表单改造

- [x] Task 2.1: 实现三区布局
  - [x] 基础信息区：顶部固定区域，包含 display_name（QLineEdit）和 enabled（QCheckBox）
  - [x] 类型专属参数区：中部 QScrollArea，按 STEP_TYPE_FIELDS 配置动态生成字段控件
  - [x] 高级选项折叠区：底部 QGroupBox（可折叠），包含 on_fail、retry_count、assign_variable、recover_workflow、comment
  - [x] 移除旧的通用反射式编辑逻辑（_add_field 通用方法、FIELD_DISPLAY_ORDER 排序逻辑）

- [x] Task 2.2: 实现按类型动态生成字段控件
  - [x] load_step 方法改为：根据 step type 查找 STEP_TYPE_FIELDS 配置，按 required → optional 顺序生成控件
  - [x] 字段不存在于 step dict 时，使用配置中的默认值创建控件
  - [x] 必填字段标签添加红色星号 `*` 标记
  - [x] _on_field_changed 方法适配新的控件结构，仅写入用户实际修改过的字段

- [x] Task 2.3: 实现专用字段控件
  - [x] on_fail：QComboBox，items=["fail","retry","backoff","skip","abort","stop","recover"]
  - [x] region：4 个 QSpinBox（left/top/right/bottom），水平排列，替代 JSON 字符串
  - [x] var_type：QComboBox，items=["bool","int","string"]
  - [x] workflow：QComboBox，从 config_manager 获取工作流名称列表 + 可编辑
  - [x] key (keyevent)：QComboBox，预置常用按键码 + 可编辑
  - [x] action (wifi)：QComboBox，items=["enable","disable"]
  - [x] threshold：QDoubleSpinBox，range 0.0~1.0，step 0.05，default 0.85

- [x] Task 2.4: 坐标获取扩展到 swipe
  - [x] pickup_container 对 tap、long_press、tap_point、swipe 类型可见
  - [x] swipe 类型使用两次点击模式：第一次点击设 (x1,y1)，第二次点击设 (x2,y2)
  - [x] 提示文字根据步骤类型动态变化
  - [x] update_coord_fields 方法适配 swipe 的两次点击逻辑

## Phase 3：步骤列表增强

- [x] Task 3.1: display_name 显示
  - [x] 步骤有 display_name 时，第一行显示 display_name，类型中文名以括号附加
  - [x] 无 display_name 时保持原有行为（序号 + 类型中文名）

- [x] Task 3.2: on_fail 策略标记
  - [x] 扩展 STEP_SUMMARY_FIELDS，所有类型增加 on_fail 字段
  - [x] _format_summary 函数特殊处理 on_fail：非 "fail" 时显示中文策略名（retry→重试、skip→跳过、abort→中止、stop→停止、backoff→退避重试、recover→恢复）
  - [x] 有 retry_count > 0 时在策略标记后追加"×N"

- [x] Task 3.3: 禁用步骤样式增强
  - [x] 禁用步骤的左侧颜色条变灰（#484f58）
  - [x] 禁用步骤整行文字设置半透明效果（QColor alpha=128）

- [x] Task 3.4: condition/loop 摘要增强
  - [x] condition 类型摘要显示 then_steps 和 else_steps 的步骤数量
  - [x] loop 类型摘要显示 steps 的步骤数量

- [x] Task 3.5: 右键菜单增加"重置执行结果"
  - [x] 在右键菜单中添加"重置执行结果"选项
  - [x] 选中后清除步骤的 execution_result 和 preview 字段
  - [x] 发出信号通知 workflow_panel 更新数据

## Phase 4：集成与验证

- [x] Task 4.1: 编辑器与列表联动验证
  - [x] 验证编辑 display_name 后列表实时更新显示
  - [x] 验证编辑 on_fail/retry_count 后列表摘要实时更新
  - [x] 验证编辑 enabled 后列表样式实时更新
  - [x] 验证新增字段（如 display_name）能正确保存到 workflows.json

- [x] Task 4.2: 各步骤类型编辑器验证
  - [x] 逐一验证 21 种步骤类型的编辑器表单正确渲染
  - [x] 验证专用控件（region、on_fail、var_type、workflow、key、action）交互正常
  - [x] 验证 swipe 坐标两次点击模式正常工作

# Task Dependencies
- [Task 1.1] 无依赖
- [Task 2.1] depends on [Task 1.1]
- [Task 2.2] depends on [Task 2.1]
- [Task 2.3] depends on [Task 2.1]
- [Task 2.4] depends on [Task 2.1]
- [Task 3.1] 无依赖（可与 Phase 2 并行）
- [Task 3.2] 无依赖
- [Task 3.3] 无依赖
- [Task 3.4] 无依赖
- [Task 3.5] 无依赖
- [Task 4.1] depends on [Task 2.4, Task 3.5]
- [Task 4.2] depends on [Task 2.3, Task 2.4]

# Parallel Execution Groups
- Group 1: Task 1.1
- Group 2 (并行): Task 2.1, Task 3.1, Task 3.2, Task 3.3, Task 3.4, Task 3.5
- Group 3 (并行): Task 2.2, Task 2.3, Task 2.4
- Group 4 (并行): Task 4.1, Task 4.2
