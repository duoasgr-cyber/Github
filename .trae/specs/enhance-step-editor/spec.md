# 步骤编辑器与列表增强 Spec

## Why
当前步骤编辑器采用通用反射式编辑，不区分步骤类型，所有类型共享同一套表单；dict/list 字段显示为 JSON 字符串难以编辑；很多 Schema 定义的可选字段（display_name、on_fail、retry_count 等）在数据中不存在时无法编辑。步骤列表显示信息有限，缺少 display_name、on_fail 策略等关键信息。

## What Changes
- 步骤编辑器从"反射式通用编辑"改为"按类型定制表单"，每种步骤类型定义专属字段列表、控件类型和默认值
- 表单分区布局：基础信息区 + 类型专属参数区 + 高级选项折叠区
- 特殊字段使用专用控件（on_fail 下拉框、region 四坐标编辑、var_type 下拉框、workflow 选择框、keyevent 按键选择框、wifi action 选择框）
- 坐标获取功能扩展到 swipe 类型（支持两次点击选取起止点）
- 步骤列表增加 display_name 显示、on_fail 策略图标、retry_count 标记、禁用样式增强
- 步骤列表摘要信息扩展，增加 on_fail 等字段
- 步骤列表右键菜单增加"重置执行结果"选项

## Impact
- Affected code: `ui/components/step_editor.py`（主要改造）、`ui/components/step_list_widget.py`（增强显示）
- Affected data: workflows.json 中步骤可能新增 display_name、on_fail、retry_count 等字段（向后兼容，这些字段均为可选）
- Affected schema: `config/schema/workflows.schema.json` 无需修改（已定义所有字段）

## ADDED Requirements

### Requirement: 按步骤类型定制编辑表单
系统 SHALL 为每种步骤类型提供专属的编辑表单，而非通用反射式编辑。

#### Scenario: 加载步骤时按类型渲染表单
- **WHEN** 用户选中一个步骤
- **THEN** 编辑器根据步骤类型查找对应的字段配置表，仅显示该类型相关的字段，并为每个字段使用指定的控件类型

#### Scenario: 字段不存在时使用默认值
- **WHEN** 步骤数据中缺少某个可选字段
- **THEN** 编辑器仍显示该字段的控件，使用字段配置中定义的默认值

#### Scenario: 保存步骤时写入所有已编辑字段
- **WHEN** 用户修改字段值后触发保存
- **THEN** 将所有字段的当前值（包括从默认值修改的字段）写入步骤数据，未修改的可选字段不写入（保持数据精简）

### Requirement: 表单三区布局
系统 SHALL 将步骤编辑表单分为三个区域：基础信息区、类型专属参数区、高级选项折叠区。

#### Scenario: 基础信息区
- **WHEN** 任何步骤类型被选中
- **THEN** 顶部固定显示"显示名称"（display_name）文本框和"启用"（enabled）勾选框

#### Scenario: 类型专属参数区
- **WHEN** 用户选中某步骤类型
- **THEN** 中部可滚动区域显示该类型的必填参数和可选参数，必填参数标签带红色星号标记

#### Scenario: 高级选项折叠区
- **WHEN** 用户展开高级选项
- **THEN** 底部显示 on_fail（失败策略下拉框）、retry_count（重试次数）、assign_variable（赋值变量名）、recover_workflow（恢复工作流名）、comment（备注）字段，默认折叠

### Requirement: 专用字段控件
系统 SHALL 为特定字段提供专用控件替代通用文本框。

#### Scenario: on_fail 下拉框
- **WHEN** 编辑 on_fail 字段
- **THEN** 使用 QComboBox，选项为：fail（默认）、retry、backoff、skip、abort、stop、recover

#### Scenario: region 四坐标编辑
- **WHEN** 编辑 ocr_region 步骤的 region 字段
- **THEN** 使用 4 个 QSpinBox 分别编辑 left、top、right、bottom，替代 JSON 字符串

#### Scenario: var_type 下拉框
- **WHEN** 编辑 variable 步骤的 var_type 字段
- **THEN** 使用 QComboBox，选项为：bool、int、string

#### Scenario: workflow 选择框
- **WHEN** 编辑 call_workflow 步骤的 workflow 字段
- **THEN** 使用 QComboBox，从 workflows.json 中已有的工作流名称列表中选择，同时支持手动输入

#### Scenario: keyevent 按键选择框
- **WHEN** 编辑 keyevent 步骤的 key 字段
- **THEN** 使用 QComboBox，预置常用按键码（KEYCODE_HOME、KEYCODE_BACK、KEYCODE_MENU、KEYCODE_POWER、KEYCODE_VOLUME_UP、KEYCODE_VOLUME_DOWN、KEYCODE_ENTER、KEYCODE_TAB 等），同时支持手动输入数字

#### Scenario: wifi action 选择框
- **WHEN** 编辑 wifi 步骤的 action 字段
- **THEN** 使用 QComboBox，选项为：enable、disable

#### Scenario: threshold 范围限制
- **WHEN** 编辑 check_image 步骤的 threshold 字段
- **THEN** 使用 QDoubleSpinBox，范围 0.0~1.0，步长 0.05，默认值 0.85

### Requirement: 坐标获取扩展到 swipe
系统 SHALL 对 swipe 步骤类型支持从投屏获取起止坐标。

#### Scenario: swipe 步骤的坐标获取
- **WHEN** 用户在 swipe 步骤编辑器中点击"从投屏获取坐标"
- **THEN** 进入两次点击模式：第一次点击设置 (x1, y1)，第二次点击设置 (x2, y2)，提示文字引导用户操作

#### Scenario: 坐标获取按钮对所有坐标步骤可见
- **WHEN** 用户选中 tap、long_press、tap_point 或 swipe 步骤
- **THEN** 显示"从投屏获取坐标"按钮区域

### Requirement: 步骤列表信息增强
系统 SHALL 在步骤列表中显示更丰富的信息。

#### Scenario: 显示 display_name
- **WHEN** 步骤有 display_name 字段且非空
- **THEN** 列表第一行显示 display_name 而非类型中文名，类型中文名以小字标签形式附加显示

#### Scenario: 显示 on_fail 策略标记
- **WHEN** 步骤的 on_fail 字段不是默认值 "fail"
- **THEN** 在摘要行末尾显示策略标记文字（如"重试×3"、"跳过"、"中止"等）

#### Scenario: 禁用步骤样式增强
- **WHEN** 步骤 enabled=false
- **THEN** 左侧颜色条变灰，整行文字半透明（opacity 0.5）

#### Scenario: 摘要信息扩展
- **WHEN** 步骤列表渲染摘要行
- **THEN** 所有类型的摘要增加 on_fail 字段（当非默认值时显示），condition 类型显示 then_steps/else_steps 步骤数量

### Requirement: 右键菜单增加重置执行结果
系统 SHALL 在步骤列表右键菜单中增加"重置执行结果"选项。

#### Scenario: 重置执行结果
- **WHEN** 用户右键点击步骤并选择"重置执行结果"
- **THEN** 清除该步骤的 execution_result 和 preview 字段，列表显示更新

## MODIFIED Requirements

### Requirement: 工作流步骤编辑器
从通用反射式编辑改为按类型定制表单，增加三区布局、专用控件、坐标获取扩展。

### Requirement: 步骤列表显示
从简单的双行显示增强为包含 display_name、on_fail 标记、禁用样式增强的丰富显示。

## REMOVED Requirements

（无移除项）
