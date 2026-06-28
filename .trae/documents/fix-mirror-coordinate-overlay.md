# 修复投屏窗口坐标悬浮显示

## 问题分析

用户看不到坐标悬浮显示，原因有两个：

### 原因 1：实现位置错误（主因）
用户看到的"右侧投屏窗口"是 `ScreenshotPicker` 内嵌的 `EmbeddedMirrorView`（位于 `embedded_mirror_widget.py`），而坐标悬浮标签被错误地实现到了 `MirrorGraphicsView`（位于 `mirror_window.py`）。`MirrorWindow` 在项目中**未被任何其他文件引用**，用户根本看不到这个窗口。

组件层级：
```
MainWindow → QSplitter → ScreenshotPicker → EmbeddedMirrorView  ← 用户看到的
```

### 原因 2：QGraphicsTextItem 技术方案不可行
当前实现使用 `QGraphicsTextItem` + HTML CSS 做悬浮标签，存在两个技术缺陷：
- **`background-color` CSS 在 Qt 的 QTextDocument 中不生效**：`<div style='background-color:rgba(0,0,0,180)'>` 不会渲染背景色，文字直接叠在视频上几乎不可见
- **`ItemIgnoresTransformations` + `mapToScene` 定位不稳定**：缩放/滚动后位置会偏移

## 修复方案

### 改用 QLabel 作为 viewport 子控件
使用 `QLabel` 作为 `QGraphicsView.viewport()` 的子控件，而非场景中的 `QGraphicsTextItem`：
- 始终渲染在场景内容之上，不受缩放/平移影响
- 支持 `setStyleSheet` 设置背景色、圆角等样式
- 定位简单：直接设置 geometry 相对 viewport 右下角

### 具体改动

#### 文件 1：`d:\Github\PY\ui\components\embedded_mirror_widget.py`（核心修复）
在 `EmbeddedMirrorView` 类中添加坐标悬浮标签：
1. `__init__()` 中创建 `QLabel` 作为 `self.viewport()` 的子控件
2. 设置样式：半透明深色背景 + 蓝色文字 + Consolas 字体 + 圆角
3. 添加 `_update_coord_overlay(x, y)` 方法：更新文本 + 重定位到 viewport 右下角
4. 在 `mouseMoveEvent` 中调用 `_update_coord_overlay`
5. 添加 `leaveEvent`：鼠标离开时隐藏
6. 在 `resizeEvent` 中重定位
7. 添加 `_last_coord` 缓存属性

#### 文件 2：`d:\Github\PY\ui\mirror_window.py`（同步修复）
移除 `MirrorGraphicsView` 中不可用的 `QGraphicsTextItem` 实现，改用同样的 `QLabel` 方案：
1. 删除 `_coord_overlay` 的 `QGraphicsTextItem` 创建代码
2. 创建 `QLabel` 作为 `self.viewport()` 的子控件
3. 重写 `_update_coord_overlay` 使用 QLabel 方案
4. 其余逻辑（mouseMoveEvent/leaveEvent/resizeEvent）保持不变

## 验证步骤
1. 启动应用，连接设备
2. 鼠标悬停右侧投屏区域，确认右下角出现半透明坐标标签
3. 移动鼠标，坐标实时更新
4. 鼠标离开投屏区域，标签隐藏
5. 缩放/平移后标签仍在右下角
