# 修复步骤列表蓝色选中背景与内容未垂直对齐

## Summary
修复工作流编辑面板左侧步骤列表在选中状态下，整行蓝色背景与右侧图标、文本在垂直方向上未居中对齐的问题。

## Current State Analysis

相关文件：

- [PY/ui/components/step_list_widget.py](file:///d:/Github/PY/ui/components/step_list_widget.py) — 步骤列表与自定义 item widget 实现
- [PY/ui/resources/style.qss](file:///d:/Github/PY/ui/resources/style.qss) — 全局样式，包含 `QListWidget::item` 与 `:selected` 样式

当前 `StepItemWidget` 布局关键点：

1. 整体使用 `QHBoxLayout`，`setContentsMargins(8, 4, 4, 4)`，上下边距均为 4px。
2. 左侧为固定 40×40 的图标/缩略图 `QLabel`。
3. 右侧 `text_container` 使用 `QVBoxLayout`，内部上下排列两行 `QLabel`（标题、摘要），未设置垂直方向大小策略。
4. `QListWidget::item` 在全局 qss 中设置 `padding: 12px 20px`，且选中态背景色为 `#1f6feb`。

问题根因：

- `text_container` 默认 `Preferred/Preferred` 大小策略，在 `QHBoxLayout` 中会占满整个 item 的可用高度，导致两行文本靠上排列。
- 图标在 `QHBoxLayout` 中默认垂直居中，但文本整体偏上，二者视觉中心不一致。
- 全局 `QListWidget::item` 的 padding 与 `StepItemWidget` 内部 margin 叠加，使蓝色选中背景边界与内容边界不完全重合，进一步放大“没对齐”的观感。

## Proposed Changes

### 1. PY/ui/components/step_list_widget.py — StepItemWidget 内部对齐

- 在创建 `text_container` 后，设置其垂直大小策略为 `Maximum`，使其高度贴合文本内容，从而与图标作为一个整体在 item 中垂直居中：
  ```python
  text_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
  ```
- 在 `text_layout` 末尾增加 `addStretch(1)`，保证两行文本在容器内部也整体居中（防御性措施）。
- 将 `layout.setContentsMargins(8, 4, 4, 4)` 调整为 `layout.setContentsMargins(8, 6, 6, 6)`，使上下、左右内边距更对称。

### 2. PY/ui/components/step_list_widget.py — StepListWidget 样式隔离

- 在 `StepListWidget.__init__` 中设置对象名：
  ```python
  self.setObjectName("stepListWidget")
  ```
- 在 `StepListWidget` 中通过 `setStyleSheet` 覆盖全局 qss，仅针对该列表移除 item padding 并保留选中蓝色背景：
  ```qss
  QListWidget#stepListWidget::item {
      padding: 0px;
  }
  QListWidget#stepListWidget::item:selected {
      background-color: #1f6feb;
  }
  ```

### 3. PY/ui/resources/style.qss — 验证全局样式影响（只读评估）

- 全局 `QListWidget::item { padding: 12px 20px; }` 仍会被 `configNavList` 等其他列表使用，不做修改。
- 通过 `#stepListWidget` 选择器覆盖，保证只影响步骤列表。

## Assumptions & Decisions

- “蓝色选中”指的是 QListWidget 选中项的整行蓝色背景（用户已确认）。
- 修复方向为垂直对齐（用户已确认），不改动水平方向布局。
- 保持图标尺寸 40×40、文本字号、左侧类型颜色条绘制逻辑不变。
- 最小改动：不重构步骤列表渲染机制，仅调整对齐相关的大小策略与边距。

## Verification Steps

1. 启动应用并进入工作流编辑面板。
2. 添加若干步骤，包括：
   - 仅有一行标题的步骤（如 `wait` 无摘要时）。
   - 有两行摘要的步骤（如 `tap` 含坐标参数）。
   - 带缩略图的识别步骤（如 `check_image`）。
3. 依次选中各步骤，检查蓝色背景是否上下对称地包裹图标与文本。
4. 运行工作流，确认运行中脉冲边框、左侧类型颜色条位置无异常。
5. 检查配置面板左侧 `configNavList` 等其他 QListWidget，确认未受本次样式隔离影响。
