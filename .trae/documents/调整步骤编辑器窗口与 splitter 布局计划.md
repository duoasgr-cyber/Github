# 调整步骤编辑器窗口与 Splitter 布局计划

## Summary
在不改动 `step_editor.py` 字段加载逻辑的前提下，优化主窗口、工作流面板及步骤编辑器区域的多层 splitter 初始比例，并将工作流右侧面板中的步骤编辑器与截图选择器改为可拖拽的垂直 QSplitter，从而显著增大“显示步骤内容的窗口”。

## Current State Analysis
1. **[main_window.py](file:///d:/Github/PY/ui/main_window.py)**
   - `center_splitter`（水平）：左侧 stacked panels / 右侧截图预览，stretch factor 为 `3:2`。
   - `main_splitter`（垂直）：中心区域 / 日志面板，stretch factor 为 `5:1`，初始 `sizes=[620, 180]`。
2. **[workflow_panel.py](file:///d:/Github/PY/ui/panels/workflow_panel.py)**
   - 水平 `splitter`：左侧步骤列表 / 右侧编辑区，stretch factor 为 `1:2`。
   - 右侧 `right_widget` 使用 `QVBoxLayout`，`StepEditor` stretch=3、`ScreenshotPicker` stretch=2，**两者之间没有可拖拽分隔**。
3. **[step_editor.py](file:///d:/Github/PY/ui/components/step_editor.py)**
   - 字段容器使用 `QScrollArea`，未设置最小高度，容易被压缩。

综上，步骤编辑器区域同时受到三层布局挤压：主窗口日志过高、右侧截图区不可压缩、步骤编辑器自身无最小高度约束。

## Proposed Changes

### 1. [main_window.py](file:///d:/Github/PY/ui/main_window.py) — 主窗口层级比例
- 修改 `main_splitter` 初始 `sizes`：由 `[620, 180]` 调整为 `[720, 160]`，让中心编辑区获得更多高度。
- 修改 `center_splitter` stretch factor：由 `3:2` 调整为 `5:3`，让左侧工作流编辑区相对右侧截图区更宽。
- 在 `_save_ui_state` / 恢复逻辑中保持对这两个 splitter 的持久化，逻辑已存在，只需确认字段正确写入。

### 2. [workflow_panel.py](file:///d:/Github/PY/ui/panels/workflow_panel.py) — 工作流面板层级
- 调整水平 `splitter` stretch factor：由 `1:2` 调整为 `1:3`，让右侧编辑+截图区更宽。
- 在 `right_widget` 中，把垂直 `QVBoxLayout` 替换为 `QSplitter(Qt.Vertical)`：
  - `right_splitter.addWidget(self._step_editor)`
  - `right_splitter.addWidget(self._screenshot_picker)`
  - `right_splitter.setStretchFactor(0, 3)`
  - `right_splitter.setStretchFactor(1, 1)`
  - `right_splitter.setChildrenCollapsible(False)`
  - 设置默认 `sizes=[400, 200]`，让步驟编辑器默认更大。
- 为 `StepEditor` 设置最小高度 `280`。
- 暴露 `right_splitter.sizes()` 与 `set_right_splitter_sizes(sizes)`，供主窗口持久化。

### 3. [step_editor.py](file:///d:/Github/PY/ui/components/step_editor.py) — 步骤编辑器自身
- 为 `StepEditor` 本身设置 `setMinimumHeight(300)`，防止被过度压缩。
- 为字段滚动区 `scroll` 设置 `setMinimumHeight(200)`，确保字段内容可见。

### 4. [main_window.py](file:///d:/Github/PY/ui/main_window.py) — 持久化右侧面板状态
- 在 `_save_ui_state` 中增加保存 `workflow_panel` 右侧垂直 splitter 的 sizes：`self._panels["workflow_editor"].get_right_splitter_sizes()`。
- 在恢复逻辑中调用 `self._panels["workflow_editor"].set_right_splitter_sizes(...)`。

## Assumptions & Decisions
- 不修复 `insertRow` 报错相关的字段加载逻辑（用户已确认当前代码无需改动）。
- 使用 `QSplitter` 实现可拖拽调整，保持用户交互一致性。
- 只调整比例与可拖拽性，不改动颜色、字体、样式表等视觉风格。
- 主窗口最小尺寸保持 `1200x800`，不引入新的响应式断点。

## Verification Steps
1. 启动应用，进入“工作流编辑”面板。
2. 观察步骤编辑器区域是否明显大于当前截图。
3. 拖拽以下 splitter，确认流畅且无异常：
   - 主窗口中心区域与日志面板之间（垂直）
   - 工作流编辑区与右侧截图区之间（水平）
   - 步骤编辑器与截图选择器之间（新增垂直 splitter）
4. 调整大小后关闭应用，重启确认各 splitter 位置已恢复。
5. 选择不同步骤，确认步骤编辑器字段区域正常显示且无报错。
