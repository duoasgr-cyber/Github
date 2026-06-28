# Tasks

- [x] Task 1: 修改 `EmbeddedMirrorView.mousePressEvent` 移除普通模式下的 `add_marker()` 调用
  - [x] SubTask 1.1: 将普通模式分支中的 `add_marker()` 调用移除，仅保留 `point_clicked.emit()`
  - [x] SubTask 1.2: 确保校准模式下点击仍添加标记
  - [x] SubTask 1.3: 确保选点模式下点击不添加标记（当前已正确，仅验证）

# Task Dependencies
- 无外部依赖
