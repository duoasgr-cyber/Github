# UI 重构开发步骤

## 三个大模块

| 模块 | 目标 | 改动范围 |
|------|------|----------|
| M1 步骤内分组卡片 | 字段按语义分组渲染，解决组可见性问题 | step_editor.py, field_group_widget.py(新), style.qss |
| M2 方案B布局 + 投屏升级 | 编辑区与投屏区左右分区，截屏升级为实时投屏 | workflow_panel.py, main_window.py, screenshot_picker.py, screen_capture.py |
| M3 工作流编排可视化 | 工作流间调用/条件关系可见可编辑 | workflow_engine.py, 新增流程图组件, condition步骤增强 |

模块间依赖：M1 独立，M2 依赖 M1 完成后再调整布局，M3 依赖 M1+M2 稳定后进行。

---

## M1：步骤内分组卡片

### M1-1 新增分组数据结构

**文件**: `PY/ui/components/step_editor.py`

**改动**:
- 在 step_editor.py 顶部新增 `FIELD_GROUPS` 字典，定义 6 种分组的标题和颜色
- 新增 `STEP_FIELD_GROUPS` 字典，为每个步骤类型定义分组+字段列表
- 保留原 `STEP_FIELD_DEFS` 不删除，仅标记为兼容用途

**产出**: 数据结构就位，不影响现有渲染

**验证**: `python -c "from ui.components.step_editor import STEP_FIELD_GROUPS; print(len(STEP_FIELD_GROUPS))"` 无报错

---

### M1-2 新建 FieldGroupWidget 卡片组件

**文件**: `PY/ui/components/field_group_widget.py`（新建）

**改动**:
- 创建 `FieldGroupWidget(QWidget)`，包含：
  - 带颜色圆点的 header（标题 + 可选的"投屏选点"按钮）
  - 内部 `QFormLayout` 供外部添加字段行
  - `coord_pick` 参数控制是否显示选点按钮
  - `pick_button` 属性供外部连接信号
- 卡片用 `QFrame` 包裹，设置 `objectName` 用于 QSS 定位

**验证**: 单独创建 `FieldGroupWidget("coord", {"label":"坐标参数","color":"#00ff88"}, coord_pick=True)` 并 `show()`，确认 header 渲染正确、选点按钮可点击

---

### M1-3 重构 StepEditor._rebuild_form

**文件**: `PY/ui/components/step_editor.py`

**改动**:
- `_rebuild_form()` 从遍历 `STEP_FIELD_DEFS[type]` 改为遍历 `STEP_FIELD_GROUPS[type]`
- 每个分组创建一个 `FieldGroupWidget`，在其 `form_layout` 中添加字段控件
- 坐标类分组（coord / coord_src / coord_dst）传入 `coord_pick=True`
- 选点按钮的 `clicked` 信号连接到新方法 `_on_pick_requested(group_key)`
- 新增信号 `coord_pick_requested = pyqtSignal(str)`
- `_create_field_widget` / `_set_field_value` / `_get_field_value` 不变，复用

**验证**:
- 打开 app，选择 tap 步骤，确认显示 3 张分组卡片（基本属性/坐标参数/执行后处理）
- 选择 swipe 步骤，确认显示 4 张卡片（基本属性/起点坐标/终点坐标/滑动时长+备注）
- 选择 condition 步骤，确认条件/满足/不满足三张卡片独立显示
- 编辑字段值，确认 `step_changed` 信号正常触发、数据保存正确

---

### M1-4 适配 update_coord_fields

**文件**: `PY/ui/components/step_editor.py`

**改动**:
- 新增 `_active_pick_group` 属性，记录当前选点模式对应的分组（coord / coord_src / coord_dst）
- `_on_pick_requested(group_key)` 设置 `_active_pick_group` 并发射 `coord_pick_requested` 信号
- `update_coord_fields(x, y)` 根据 `_active_pick_group` 决定回填 x1/y1 还是 x2/y2

**验证**:
- swipe 步骤点击"起点坐标"卡片的"投屏选点"，在截屏上点一下，确认回填 x1/y1
- 点击"终点坐标"的"投屏选点"，确认回填 x2/y2
- tap 步骤点击"坐标参数"的"投屏选点"，确认回填 x/y

---

### M1-5 QSS 样式补充

**文件**: `PY/ui/resources/style.qss`

**改动**:
- 新增 `#fieldGroupCard` 样式（边框、圆角、背景）
- 新增分组 header 的 hover 效果（可选）
- 确保与现有深色主题一致

**验证**: 视觉检查所有步骤类型的卡片样式统一、颜色圆点显示正确

---

### M1-6 所有步骤类型遍历测试

**改动**: 无新代码，纯测试

**验证**:
- 逐一选择 20 种步骤类型，确认每种都正确渲染分组卡片
- 确认字段值加载、编辑、保存全部正常
- 确认原 `STEP_FIELD_DEFS` 中定义的字段在 `STEP_FIELD_GROUPS` 中没有遗漏
- 确认 `condition` 的 check / then_steps / else_steps 和 `loop` 的 steps 字段渲染为独立的流程控制卡片

---

## M2：方案B布局 + 投屏升级

### M2-1 ScrcpyCapture 增加帧回调接口

**文件**: `PY/core/screen_capture.py`

**改动**:
- `ScrcpyCapture` 新增 `frame_ready = pyqtSignal(QImage)` 信号
- 在 scrcpy 视频流解码回调中，每帧发射 `frame_ready`
- 保留原有的 `screenshot_to_file()` 方法不删除

**验证**: 连接设备后，`frame_ready` 信号能持续发射 QImage

---

### M2-2 ScreenshotPicker 升级为投屏窗口

**文件**: `PY/ui/components/screenshot_picker.py`

**改动**:
- 新增 `_live_mode` 属性，控制当前是实时投屏还是单次截屏
- 连接 `ScrcpyCapture.frame_ready` 信号，收到帧后更新显示
- 画面保持 16:9 等比缩放，居中显示，黑边填充
- 保留原有选点交互：`point_selected` 信号、缩放、校准模式、键盘导航
- 新增 `enter_pick_mode(group_key)` 方法：边框变绿 + 显示十字准线
- 新增 `exit_pick_mode()` 方法：恢复正常状态
- 设备未连接时显示 `EmptyStateWidget`

**验证**:
- 连接设备后画面实时更新
- 点击画面选点，确认 `point_selected` 信号正常发射
- 16:9 画面不被拉伸
- 断开设备后显示空状态提示

---

### M2-3 WorkflowPanel 布局调整

**文件**: `PY/ui/panels/workflow_panel.py`

**改动**:
- 当前布局：左(步骤列表) | 右上(编辑器) + 右下(截屏)
- 改为：左上(步骤列表) + 左下(编辑器) | 右(投屏)
- 具体实现：
  - 外层 `QSplitter(Qt.Horizontal)` 保留
  - 左侧 widget：`QVBoxLayout`，上方放 `_step_list`，下方放 `_step_editor`
  - 右侧 widget：放 `_screenshot_picker`（已升级为投屏）
  - splitter 比例从 1:2 改为 5:4

**验证**:
- 步骤列表和编辑器在左侧上下排列
- 投屏窗口在右侧独立一列
- 拖动 splitter 可调整左右比例

---

### M2-4 MainWindow 适配

**文件**: `PY/ui/main_window.py`

**改动**:
- `center_splitter` 的 `setStretchFactor` 从 (3, 2) 改为 (5, 4)
- `_screenshot_picker` 的引用改为从 `WorkflowPanel` 内部获取（或保持现有引用方式）
- `_update_screenshot_empty_state()` 逻辑适配投屏模式
- `_on_screenshot_point_selected()` 不变
- `_save_ui_state()` / 持久化适配新的 splitter 比例

**验证**:
- 启动后布局正确：侧边栏 | 编辑区+步骤列表 | 投屏窗口 | 日志
- splitter 比例持久化正常
- Ctrl+B 折叠侧边栏正常
- Ctrl+Shift+L 切换日志面板正常

---

### M2-5 投屏选点联动

**文件**: `PY/ui/panels/workflow_panel.py`, `PY/ui/components/step_editor.py`, `PY/ui/components/screenshot_picker.py`

**改动**:
- `StepEditor.coord_pick_requested` 信号连接到 `WorkflowPanel._on_coord_pick_requested`
- `_on_coord_pick_requested(group_key)` 调用 `_screenshot_picker.enter_pick_mode(group_key)`
- `ScreenshotPicker.point_selected` 信号连接到 `StepEditor.update_coord_fields`（已有）
- 选点完成后自动调用 `exit_pick_mode()`

**验证**:
- 点击坐标卡片的"投屏选点"按钮 → 投屏窗口边框变绿+十字准线
- 在投屏上点一下 → 坐标回填到对应字段 → 投屏恢复正常
- swipe 的起点/终点选点互不干扰

---

### M2-6 投屏回退兼容

**改动**: 无新代码，测试场景

**验证**:
- 设备未连接时，投屏区显示空状态，编辑器正常工作
- scrcpy 进程异常退出时，`connection_lost` 信号触发，界面不崩溃
- 手动截屏功能保留（投屏窗口工具栏增加"手动截图"按钮，回退到 adb screencap）

---

## M3：工作流编排可视化

### M3-1 增强 condition 步骤支持 call_workflow

**文件**: `PY/ui/components/step_editor.py`, `PY/core/step_executor.py`

**改动**:
- `condition` 类型的 `then_steps` / `else_steps` 字段支持两种模式：
  - 内嵌步骤列表（当前行为）
  - 调用指定工作流（新增）
- `StepEditor` 中 condition 的流程控制卡片增加模式切换（内嵌 / 调用工作流）
- `StepExecutor._execute_step` 的 condition 分支增加调用工作流的执行路径

**验证**:
- condition 步骤可以设置为"满足时调用 after_buy 工作流"
- 执行引擎能正确调用目标工作流

---

### M3-2 新增主工作流数据模型

**文件**: `PY/core/config_manager.py`, `PY/config/workflows.json`

**改动**:
- `workflows.json` 新增 `"main_flow"` 顶层字段，定义主流程编排
- 数据结构示例：
  ```json
  "main_flow": {
    "steps": [
      {"type": "call_workflow", "workflow": "refresh_price"},
      {"type": "condition", "check": {"type": "check_image", "template": "tp/kai_1.jpg"},
       "then_steps": [{"type": "call_workflow", "workflow": "card_mail_ru_run_1"}],
       "else_steps": [{"type": "call_workflow", "workflow": "card_mail_no_match"}]}
    ]
  }
  ```
- `ConfigManager` 新增 `get_main_flow()` / `set_main_flow()` 方法

**验证**:
- 主流程 JSON 读写正常
- 原有独立工作流不受影响

---

### M3-3 主流程编辑面板

**文件**: `PY/ui/panels/main_flow_panel.py`（新建）或集成到 `workflow_panel.py`

**改动**:
- 新增主流程编辑面板，显示主流程的步骤序列
- 复用 `StepListWidget` + `StepEditor` 组件
- 步骤类型限定为 `call_workflow` / `condition` / `loop` / `wait`
- condition 的 then/else 分支在编辑器中以缩进+竖线展示

**验证**:
- 主流程面板可编辑、保存
- condition 分支的嵌套结构正确显示

---

### M3-4 主流程执行引擎适配

**文件**: `PY/core/workflow_engine.py`

**改动**:
- `run_main_loop()` 从硬编码逻辑改为读取 `main_flow` 配置
- 递归执行 condition / loop 嵌套结构
- 保留 `_price_check_loop()` / `_card_mail_process()` 作为内置预设（向后兼容）

**验证**:
- 从 main_flow 配置执行的结果与硬编码逻辑一致
- 条件分支和循环执行正确

---

### M3-5 主流程导航入口

**文件**: `PY/ui/main_window.py`

**改动**:
- 侧边栏或导航栏增加"主流程"入口
- 点击后切换到主流程编辑面板
- 或者将主流程编辑集成到现有的工作流编辑面板中，作为特殊工作流处理

**验证**:
- 可从界面进入主流程编辑
- 主流程编辑与普通工作流编辑互不干扰

---

### M3-6 编排可视化（可选，高成本）

**文件**: 新增 `PY/ui/components/flow_chart_widget.py`

**改动**:
- 使用 QGraphicsScene / QGraphicsView 实现流程图渲染
- 每个工作流渲染为一个节点，condition 渲染为菱形分支
- 节点可拖拽调整位置
- 点击节点跳转到对应工作流的编辑面板
- 连线表示执行顺序，条件分支用不同颜色标注

**验证**:
- 主流程的流程图正确渲染
- 点击节点跳转正常
- 编辑工作流后流程图同步更新

---

## 开发顺序总览

```
M1-1 数据结构 ──→ M1-2 卡片组件 ──→ M1-3 渲染重构 ──→ M1-4 坐标适配 ──→ M1-5 QSS ──→ M1-6 测试
                                                                                          │
                                                                                          ▼
                                             M2-1 帧回调 ──→ M2-2 投屏升级 ──→ M2-3 布局调整 ──→ M2-4 主窗口适配
                                                                                          │
                                                    M2-5 选点联动 ←──────────────────────────┘
                                                          │
                                                          ▼
                                                       M2-6 兼容测试
                                                          │
                                                          ▼
M3-1 condition增强 ──→ M3-2 主流程数据 ──→ M3-3 编辑面板 ──→ M3-4 执行引擎 ──→ M3-5 导航入口 ──→ M3-6 流程图(可选)
```

M1 约 6 个步骤，M2 约 6 个步骤，M3 约 5-6 个步骤（含可选的流程图）。
每个模块完成后应独立可用：M1 完成后编辑器分组可用，M2 完成后布局和投屏可用，M3 完成后编排可视化可用。
