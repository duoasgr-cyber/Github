# 三角洲自动抢购工具 v2.0 重构 Spec

## Why
当前代码存在硬编码坐标、重复 ADB 函数、配置散落、无 GUI 编辑能力等问题，需要完全重写为模块化的 PyQt5 GUI 应用，支持工作流可视化编辑、scrcpy 后台流截屏、自动分辨率适配等能力。

## What Changes
- **BREAKING**: 完全重写，旧代码仅作参考，不保留旧文件结构
- 新增 scrcpy-server 后台流截屏模块（替代 PC 截屏和 ADB screencap）
- 新增 JSON 配置体系（config.json + workflows.json），坐标嵌入工作流步骤
- 新增步骤执行引擎，支持 18 种步骤类型
- 新增 PyQt5 GUI（主窗口 + 步骤编辑器 + 配置面板 + 设备面板 + 状态面板）
- 新增自动分辨率适配（比例换算 + 手动校准）
- 新增步骤级错误恢复（retry_count + on_fail 动作）
- 新增 EasyOCR 单例懒加载 + 异步初始化
- 新增 logging + 自定义 Handler 双输出（GUI + 文件）

## Impact
- Affected code: 所有现有 Python 文件（mian.py, ka.py, e_adb_buy.py 等 15+ 个文件）将被新架构替代
- Affected data: you.txt、用户定价.txt 将被 config.json 替代；数据.json 将被 workflows.json 替代
- Affected dependencies: 新增 PyQt5、pyav（可选）；移除 pystray；保留 easyocr、opencv-python、numpy、Pillow

## ADDED Requirements

### Requirement: scrcpy 后台流截屏
系统 SHALL 通过直接集成 scrcpy-server.jar 实现后台视频流截屏，不依赖投屏软件窗口可见。

#### Scenario: 启动 scrcpy 连接
- **WHEN** 用户选择设备并启动程序
- **THEN** 系统通过 `adb shell app_process` 启动 scrcpy-server，通过 socket 接收 H.264 视频流，使用 OpenCV+FFmpeg 解码为 numpy 数组

#### Scenario: 持久连接与帧缓冲
- **WHEN** scrcpy 连接建立后
- **THEN** 系统保持持久连接，帧缓冲区只保留最新一帧，旧帧丢弃

#### Scenario: 获取当前帧
- **WHEN** 步骤执行引擎或截屏选点组件请求截图
- **THEN** 系统从帧缓冲区返回最新帧的 numpy 数组

#### Scenario: 连接断开恢复
- **WHEN** scrcpy 连接断开（设备断开、server 崩溃）
- **THEN** 系统自动尝试重新建立连接，最多重试 3 次

### Requirement: JSON 配置体系
系统 SHALL 使用 config.json 和 workflows.json 管理所有配置，支持热更新。

#### Scenario: config.json 结构
- **WHEN** 程序启动
- **THEN** 加载 config.json，包含全部规划配置项（购买参数、邮件参数、定时启动、识别参数、OCR 区域、WiFi 控制命令等）

#### Scenario: workflows.json 结构
- **WHEN** 程序启动
- **THEN** 加载 workflows.json，每个工作流包含 description、device_resolution、steps 字段，步骤中坐标直接嵌入

#### Scenario: 配置热更新
- **WHEN** GUI 修改配置参数
- **THEN** 立即写入 JSON 文件，运行中的工作流下次读取时生效

#### Scenario: 配置损坏恢复
- **WHEN** JSON 文件格式损坏
- **THEN** 启动时校验格式，损坏时自动恢复默认值

### Requirement: 步骤执行引擎
系统 SHALL 支持 18 种步骤类型的执行，支持暂停/停止/单步执行。

#### Scenario: 支持的步骤类型
- **WHEN** 步骤执行引擎处理工作流
- **THEN** 支持 tap、long_press、swipe、keyevent、wait、wifi、force_stop、launch、screenshot、pull_file、delete_file、check_image、ocr_region、tap_point、call_workflow、condition、loop、input_text 共 18 种类型

#### Scenario: 步骤级错误恢复
- **WHEN** 步骤执行失败
- **THEN** 根据 retry_count 重试，仍失败则执行 on_fail 动作（stop/skip/retry/recover）

#### Scenario: 暂停与停止
- **WHEN** 用户点击暂停/停止按钮
- **THEN** 当前步骤完成后暂停/停止执行，不支持步骤中途中断

### Requirement: 自动分辨率适配
系统 SHALL 根据设备分辨率自动换算工作流中的坐标。

#### Scenario: 比例换算
- **WHEN** 工作流记录的基准分辨率与设备实际分辨率不同
- **THEN** 按宽高分别计算缩放比，分别应用到 x 和 y 坐标

#### Scenario: 手动校准
- **WHEN** 自动换算的坐标不准确
- **THEN** 用户可在截屏选点组件中微调坐标，校准后的坐标保存到工作流

### Requirement: PyQt5 GUI 主框架
系统 SHALL 提供 PyQt5 主窗口，左侧导航 + 右侧面板切换 + 底部日志区 + 状态栏。

#### Scenario: 面板切换
- **WHEN** 用户点击左侧导航项
- **THEN** 右侧显示对应面板（工作流编辑、配置、设备管理、运行监控）

#### Scenario: 日志面板
- **WHEN** 程序运行产生日志
- **THEN** 通过 logging 自定义 Handler 输出到 GUI 日志面板和文件，支持级别过滤和颜色

### Requirement: 工作流步骤编辑器
系统 SHALL 提供工作流步骤的可视化增删改查界面。

#### Scenario: 步骤列表拖拽排序
- **WHEN** 用户拖拽步骤列表项
- **THEN** 使用 QListWidget 内置拖拽功能调整步骤顺序

#### Scenario: 截屏选点
- **WHEN** 用户点击截屏按钮
- **THEN** 从 scrcpy 实时帧获取当前画面，显示在可缩放 QLabel 上，用户点击选择坐标后自动换算为手机实际坐标并填入编辑器

#### Scenario: 步骤编辑
- **WHEN** 用户选中步骤
- **THEN** 根据步骤类型动态显示参数表单，修改后保存到 workflows.json

### Requirement: 循环与条件步骤
系统 SHALL 支持 loop 和 condition 步骤类型。

#### Scenario: loop 步骤
- **WHEN** 执行 loop 步骤
- **THEN** 根据 max_count 和 condition 双重条件控制循环终止

#### Scenario: condition 步骤
- **WHEN** 执行 condition 步骤
- **THEN** 根据 JSON 结构化条件（如 check_image 结果）分支到 then_steps 或 else_steps

### Requirement: 悬浮窗与系统托盘
系统 SHALL 提供 PyQt5 QWidget 悬浮窗和 QSystemTrayIcon 系统托盘。

#### Scenario: 悬浮窗
- **WHEN** 程序运行
- **THEN** 右上角显示置顶无标题栏悬浮窗，实时显示价格、邮件数量、运行状态

#### Scenario: 系统托盘
- **WHEN** 用户关闭主窗口
- **THEN** 程序最小化到系统托盘，右键菜单支持显示/隐藏/退出

### Requirement: EasyOCR 单例懒加载
系统 SHALL 使用 EasyOCR 单例模式，异步初始化。

#### Scenario: 首次启动
- **WHEN** 程序启动
- **THEN** 异步加载 EasyOCR 模型，显示加载进度条，首次使用时模型已就绪

#### Scenario: 后续使用
- **WHEN** OCR 识别请求
- **THEN** 使用已初始化的单例实例，不重复创建

### Requirement: ADB 核心模块
系统 SHALL 使用 subprocess.run 统一封装所有 ADB 命令执行。

#### Scenario: ADB 命令执行
- **WHEN** 任何模块需要执行 ADB 命令
- **THEN** 通过 adb_core.py 统一执行，支持超时控制、输出捕获、错误处理

#### Scenario: WiFi 控制
- **WHEN** 工作流需要开关 WiFi
- **THEN** 通过 `adb shell svc wifi enable/disable` 执行

### Requirement: PyInstaller 打包
系统 SHALL 支持打包为 onedir 模式分发。

#### Scenario: 打包
- **WHEN** 执行 PyInstaller 打包
- **THEN** 生成 onedir 模式的发布包，scrcpy-server.jar 打包在内，EasyOCR 模型首次运行时下载

## MODIFIED Requirements

### Requirement: 设备管理
从交互式命令行选择改为 PyQt5 GUI 可视化管理，支持设备列表显示、连接、断开检测，同一时间只操作一个设备。

### Requirement: 价格监控主循环
从 mian.py 的硬编码无限循环改为工作流编排引擎驱动，通过 loop + condition 步骤实现，支持 GUI 启停控制。

## REMOVED Requirements

### Requirement: tkinter GUI
**Reason**: 迁移到 PyQt5
**Migration**: floating_window.py 的 tkinter Toplevel 替换为 PyQt5 QWidget

### Requirement: pystray 系统托盘
**Reason**: PyQt5 自带 QSystemTrayIcon
**Migration**: 替换为 QSystemTrayIcon

### Requirement: PIL.ImageGrab PC 截屏
**Reason**: 迁移到 scrcpy 后台流
**Migration**: 替换为 scrcpy-server 视频流帧提取

### Requirement: coordinates.json 独立坐标文件
**Reason**: 坐标嵌入 workflows.json 步骤中
**Migration**: 坐标直接写入工作流步骤的 x/y 字段
