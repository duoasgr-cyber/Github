# 修复步骤列表点击无响应（回退错误改动 + 正确对齐方案）

## Summary

上次修复"蓝色选中背景与文本图标垂直不对齐"时，在 `StepListWidget.__init__` 中调用了 `setStyleSheet()`，导致点击步骤列表项完全无响应。需要回退该错误改动，改用全局 QSS 选择器覆盖 padding，并保留有效的对齐修复。

## Current State Analysis

当前 [step\_list\_widget.py](file:///d:/Github/PY/ui/components/step_list_widget.py) 中存在的问题：

1. **第 409-413 行**：`StepListWidget.__init__` 中直接调用了 `self.setStyleSheet(...)`，这是导致点击无响应的根因。

   * Qt 对设置了独立 stylesheet 的 widget 会启用 `WA_StyleSheet` 属性，改变事件处理流程。

   * 配合 `setItemWidget()` 使用时，自定义 widget 拦截鼠标事件，`QListWidget` 无法收到点击，选择机制失效。

2. **第 287 行**：`text_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)` — 这部分对齐修复是正确的，保留。

3. **第 237 行**：`layout.setContentsMargins(8, 6, 6, 6)` — 边距调整是正确的，保留。

4. **第 319 行**：`text_layout.addStretch(1)` — 文本居中辅助，保留。

## Proposed Changes

### 1. [PY/ui/components/step\_list\_widget.py](file:///d:/Github/PY/ui/components/step_list_widget.py) — 移除 setStyleSheet 调用

* 删除 `StepListWidget.__init__` 中的 `self.setStyleSheet(...)` 调用（第 410-413 行）。

* 保留 `self.setObjectName("stepListWidget")`，供全局 QSS 使用。

### 2. [PY/ui/resources/style.qss](file:///d:/Github/PY/ui/resources/style.qss) — 在全局 QSS 中添加步骤列表专用规则

在现有 `QListWidget::item:hover:!selected` 规则之后，添加针对 `#stepListWidget` 的覆盖规则：

```css
/* Step list widget — override global item padding for custom item widgets */
QListWidget#stepListWidget::item {
    padding: 0px;
}
QListWidget#stepListWidget::item:selected {
    background-color: #1f6feb;
}
```

这样做的好处：

* 样式由全局 QSS 统一管理，不触发 per-widget stylesheet 事件处理变更。

* `#stepListWidget` 选择器只影响步骤列表，不影响 `#configNavList` 等其他 QListWidget。

* 点击事件正常传递到 `QListWidget`，选择机制恢复工作。

## Assumptions & Decisions

* 回退 `setStyleSheet()` 调用是修复点击无响应的必要操作。

* 全局 QSS 中用 `#stepListWidget` 选择器覆盖 padding 是安全做法，不影响其他列表。

* 保留上次正确的对齐修复（QSizePolicy.Maximum、边距调整、addStretch）。

## Verification Steps

1. 启动应用，进入工作流编辑面板。
2. 点击步骤列表中的各项，确认选中高亮正常切换。
3. 确认蓝色选中背景与图标/文本在垂直方向上对齐。
4. 右键点击步骤，确认上下文菜单正常弹出。
5. 拖拽步骤排序，确认拖拽功能正常。
6. 检查配置面板左侧导航列表，确认未受影响。

