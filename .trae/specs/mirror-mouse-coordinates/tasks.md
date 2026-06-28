# Tasks

- [x] Task 1: 在 MirrorGraphicsView 中添加右下角坐标悬浮标签
  - [x] SubTask 1.1: 在 `MirrorGraphicsView.__init__()` 中创建 `QGraphicsTextItem` 作为坐标标签，设置初始样式（半透明背景、亮色文字、Consolas 字体、右下角定位）
  - [x] SubTask 1.2: 实现 `_update_coord_label(x, y)` 方法，更新标签文本并根据视图尺寸重新定位到右下角
  - [x] SubTask 1.3: 在 `resizeEvent` 中调用坐标标签重定位，确保窗口大小变化时标签始终在右下角

- [x] Task 2: 连接 mouse_moved 信号到坐标标签更新
  - [x] SubTask 2.1: 在 `MirrorGraphicsView` 的 `mouseMoveEvent` 或通过信号槽机制，调用 `_update_coord_label()` 更新坐标显示
  - [x] SubTask 2.2: 处理鼠标离开视图时的标签隐藏逻辑（可使用 `leaveEvent`）

- [x] Task 3: 验证坐标显示效果
  - [x] SubTask 3.1: 启动应用并连接设备，确认鼠标悬停时右下角正确显示设备坐标
  - [x] SubTask 3.2: 确认坐标值与现有工具栏坐标一致
  - [x] SubTask 3.3: 确认缩放/平移后坐标仍然准确

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 1, Task 2]
