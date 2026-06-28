# 跳转机制实现检查清单

## 数据模型
- [ ] Step 新增 `jump_to` 字段（str，默认 ""）
- [ ] Step 新增 `jump_count` 字段（int，默认 0）
- [ ] Step 新增 `jump_condition` 字段（dict|null，默认 null）
- [ ] Step 新增 `jump_label` 字段（str，默认 ""）
- [ ] Step 新增 `is_jump_target` 字段（bool，默认 false）
- [ ] 所有新字段均为可选，不影响现有步骤

## 执行逻辑
- [ ] `_build_jump_labels()` 正确扫描步骤构建映射表
- [ ] `_generate_label()` 生成唯一 `#XXXX` 标签
- [ ] `_handle_jump()` 无条件跳转正确
- [ ] `_handle_jump()` 条件跳转：条件满足时跳转，不满足时继续
- [ ] `_handle_jump()` 循环回跳：次数限制正确
- [ ] 防死循环保护：全局 1000 次限制
- [ ] `_run_steps()` 改为 while 循环后顺序执行不受影响
- [ ] 跳转目标不存在时降级为继续执行（不崩溃）

## UI 展示
- [ ] 步骤列表显示跳转信息行 `跳转 [->#XXXX ×N]`
- [ ] 步骤列表显示跳入点标记 `跳入点 [#XXXX]`
- [ ] 跳转按钮可点击，点击后列表滚动到目标步骤
- [ ] 步骤编辑器高级选项中显示 jump_to / jump_count / is_jump_target
- [ ] 编辑器修改跳转字段后正确保存

## 面板联动
- [ ] WorkflowPanel 连接 step_jump_clicked 信号
- [ ] MainFlowPanel 连接 step_jump_clicked 信号
- [ ] 点击跳转按钮后正确滚动并高亮目标步骤

## 测试
- [ ] 无条件跳转测试通过
- [ ] 条件跳转测试通过
- [ ] 循环回跳测试通过
- [ ] 防死循环测试通过
- [ ] 标签生成唯一性测试通过
- [ ] 跳转目标不存在降级测试通过
