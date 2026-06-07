# Tasks

## Phase 1：基础设施（与 Phase 3 并行开发）

- [x] Task 1.1: 创建项目目录结构
  - [x] 创建 config/、core/、core/actions/、ui/、ui/panels/、ui/components/、ui/resources/、ui/resources/icons/、lib/ 目录
  - [x] 从 Escrcpy 提取 scrcpy-server.jar 到 lib/ 目录
- [x] Task 1.2: 编写 config.json
  - [x] 提取当前代码中所有配置参数（user_price、mail_limit、price_coefficient、min_price 等）
  - [x] 添加设计文档规划的全部配置项（定时启动、OCR 区域、WiFi 控制命令等）
- [x] Task 1.3: 编写 workflows.json
  - [x] 从 ka.py 提取 after_buy、begin、ru_run_1、kaishi、ru_run_2、fin 工作流
  - [x] 从 Restart.py 提取 restart、ru、kai、dl、ru_run、kai_run、dl_run 工作流
  - [x] 从 e_adb_buy.py 提取 e_adb_buy 工作流
  - [x] 从 sale.py 提取 sale、frist、second、get_you 工作流
  - [x] 每个工作流包含 description、device_resolution(2400x1080)、steps 字段，步骤中坐标直接嵌入
- [x] Task 1.4: 编写配置管理器
  - [x] 实现 config_manager.py：JSON 配置文件统一读写管理器
  - [x] 支持热更新（GUI 修改后立即写入）
  - [x] 支持格式校验和损坏恢复默认值
- [x] Task 1.5: 编写 ADB 核心模块
  - [x] 实现 adb_core.py：统一 ADB 命令执行器，使用 subprocess.run
  - [x] 支持超时控制、输出捕获、错误处理
  - [x] 消除 6 处重复的 adb_command_basic()

## Phase 2：步骤执行引擎

- [x] Task 2.1: 编写 scrcpy 截屏模块
  - [x] 实现 screen_capture.py：通过 scrcpy-server 后台流截屏
  - [x] 启动 scrcpy-server（adb shell app_process），通过 socket 接收 H.264 流
  - [x] 使用 OpenCV+FFmpeg 解码 H.264 帧为 numpy 数组
  - [x] 持久连接 + 帧缓冲（只保留最新帧）
  - [x] 连接断开自动重试（最多 3 次）
  - [x] 提供获取当前帧的接口（供步骤引擎和截屏选点使用）
- [x] Task 2.2: 编写 OCR 引擎模块
  - [x] 实现 ocr_engine.py：EasyOCR 单例懒加载
  - [x] 异步初始化，启动时显示加载进度
  - [x] 支持价格识别（数字清理、末位纠正、位数校验）
  - [x] 支持按钮文字识别（中文/数字判断）
- [x] Task 2.3: 编写设备管理模块
  - [x] 实现 device_manager.py：设备列表、连接、断开检测
  - [x] 获取设备分辨率（用于坐标自动换算）
  - [x] 单设备操作模式
- [x] Task 2.4: 编写步骤执行引擎
  - [x] 实现 step_executor.py：支持全部 18 种步骤类型
  - [x] tap、long_press、swipe、keyevent、wait、wifi、force_stop、launch
  - [x] screenshot、pull_file、delete_file、check_image、ocr_region、tap_point
  - [x] call_workflow、condition（JSON 结构化条件 + then_steps/else_steps）、loop（max_count + condition 双控）、input_text
  - [x] 支持暂停/停止/单步执行
  - [x] 步骤级错误恢复（retry_count + on_fail: stop/skip/retry/recover）
  - [x] 自动分辨率换算（基准分辨率 vs 设备分辨率，按宽高分别缩放）
- [x] Task 2.5: 集成测试
  - [x] 用 workflows.json 中的工作流验证步骤执行是否正确
  - [x] 验证 after_buy 工作流执行
  - [x] 验证 check_image 和 ocr_region 步骤

## Phase 3：GUI 主框架（与 Phase 1 并行开发）

- [x] Task 3.1: 编写主窗口
  - [x] 实现 main_window.py：左侧导航栏 + 右侧面板区域 + 底部日志区 + 状态栏
  - [x] 导航项：工作流编辑、配置、设备管理、运行监控
  - [x] 面板切换逻辑
- [x] Task 3.2: 编写新入口文件
  - [x] 实现 main.py：初始化配置管理器、ADB 核心、启动 GUI
  - [x] QSystemTrayIcon 系统托盘（显示/隐藏/退出）
- [x] Task 3.3: 编写深色主题样式表
  - [x] 实现 style.qss：科技感风格，与游戏风格匹配
- [x] Task 3.4: 编写日志面板
  - [x] 实现 log_panel.py：QTextEdit + 自定义 Handler
  - [x] 支持级别过滤（DEBUG/INFO/WARNING/ERROR）
  - [x] 支持颜色区分
- [x] Task 3.5: 集成日志系统
  - [x] 全局使用 logging 替代 print
  - [x] 双输出到 GUI 日志面板和文件

## Phase 4：步骤编辑器面板

- [x] Task 4.1: 编写工作流编辑面板
  - [x] 实现 workflow_panel.py：工作流选择 + 截屏预览 + 步骤列表 + 步骤详情
- [x] Task 4.2: 编写步骤列表组件
  - [x] 实现 step_list_widget.py：QListWidget 内置拖拽排序、选中高亮
- [x] Task 4.3: 编写单步编辑器
  - [x] 实现 step_editor.py：根据步骤类型动态显示参数表单
- [x] Task 4.4: 编写截屏选点组件
  - [x] 实现 screenshot_picker.py：从 scrcpy 实时帧获取画面
  - [x] 可缩放 QLabel 显示、实时坐标、点击标注
  - [x] 自动换算为手机实际坐标（考虑缩放比例）
  - [x] 支持手动校准模式
- [x] Task 4.5: 实现步骤 CRUD
  - [x] 添加、删除、修改、复制步骤
  - [x] 保存后 workflows.json 同步更新
- [x] Task 4.6: 实现工作流管理
  - [x] 新建、删除、重命名工作流

## Phase 5：步骤测试功能

- [x] Task 5.1: 单步测试
  - [x] 选中步骤后点击「测试」，立即执行该步骤
- [x] Task 5.2: 从某步开始运行
  - [x] 选中步骤后点击「从这步运行」，从该步开始执行整个工作流
- [x] Task 5.3: 整个工作流试运行
  - [x] 点击「运行此工作流」，完整执行
- [x] Task 5.4: 执行过程可视化
  - [x] 当前执行步骤高亮，进度条显示

## Phase 6：配置面板 + 设备面板 + 状态面板

- [x] Task 6.1: 编写参数配置面板
  - [x] 实现 config_panel.py：购买参数、邮件参数、定时启动、识别参数、OCR 区域
  - [x] GUI 修改后立即写入 config.json（热更新）
- [x] Task 6.2: 编写设备管理面板
  - [x] 实现 device_panel.py：设备列表、连接、快捷操作、自定义 ADB 命令
- [x] Task 6.3: 编写运行监控面板
  - [x] 实现 status_panel.py：实时价格、邮件、状态、操作按钮、连点器
- [x] Task 6.4: 编写悬浮窗组件
  - [x] 实现 float_widget.py：PyQt5 QWidget，置顶无标题栏
  - [x] 实时显示价格（绿色）、邮件数量（橙色）、运行状态（灰色）

## Phase 7：工作流编排引擎

- [x] Task 7.1: 编写工作流编排引擎
  - [x] 实现 workflow_engine.py：主循环编排（价格检查 → 购买 → 卡邮件完整流程）
  - [x] loop 步骤：max_count + condition 双控
  - [x] condition 步骤：JSON 结构化条件 + then_steps/else_steps
- [x] Task 7.2: 主循环可视化
  - [x] 在 GUI 中展示主循环的编排逻辑

## Phase 8：打包与美化

- [x] Task 8.1: PyInstaller 打包
  - [x] onedir 模式，scrcpy-server.jar 打包在内
  - [x] EasyOCR 模型首次运行时下载
- [x] Task 8.2: 图标设计
  - [x] 应用图标、托盘图标
- [x] Task 8.3: QSS 细节优化
  - [x] 动画效果、过渡效果
- [x] Task 8.4: 异常处理完善
  - [x] 全局异常捕获、优雅退出
- [x] Task 8.5: 编写依赖清单
  - [x] requirements.txt

# Task Dependencies
- [Task 1.1] 无依赖
- [Task 1.2] 无依赖
- [Task 1.3] 无依赖
- [Task 1.4] depends on [Task 1.1, Task 1.2, Task 1.3]
- [Task 1.5] depends on [Task 1.1]
- [Task 2.1] depends on [Task 1.5]
- [Task 2.2] depends on [Task 1.1]
- [Task 2.3] depends on [Task 1.5]
- [Task 2.4] depends on [Task 1.4, Task 2.1, Task 2.2, Task 2.3]
- [Task 2.5] depends on [Task 2.4]
- [Task 3.1] depends on [Task 1.1]
- [Task 3.2] depends on [Task 3.1, Task 1.4, Task 1.5]
- [Task 3.3] depends on [Task 3.1]
- [Task 3.4] depends on [Task 3.1]
- [Task 3.5] depends on [Task 3.4]
- [Task 4.1] depends on [Task 2.4, Task 3.1]
- [Task 4.2] depends on [Task 4.1]
- [Task 4.3] depends on [Task 4.1]
- [Task 4.4] depends on [Task 2.1, Task 4.1]
- [Task 4.5] depends on [Task 4.2, Task 4.3]
- [Task 4.6] depends on [Task 4.1]
- [Task 5.1] depends on [Task 4.5]
- [Task 5.2] depends on [Task 4.5]
- [Task 5.3] depends on [Task 4.5]
- [Task 5.4] depends on [Task 5.1]
- [Task 6.1] depends on [Task 1.4, Task 3.1]
- [Task 6.2] depends on [Task 2.3, Task 3.1]
- [Task 6.3] depends on [Task 2.2, Task 3.1]
- [Task 6.4] depends on [Task 3.1]
- [Task 7.1] depends on [Task 2.4, Task 6.3]
- [Task 7.2] depends on [Task 7.1]
- [Task 8.1] depends on [Task 7.1]
- [Task 8.2] 无依赖
- [Task 8.3] depends on [Task 3.3]
- [Task 8.4] depends on [Task 7.1]
- [Task 8.5] depends on [Task 8.1]

# Parallel Execution Groups
- Group 1 (并行): Task 1.1, Task 1.2, Task 1.3, Task 3.1, Task 3.3, Task 8.2
- Group 2 (并行): Task 1.4, Task 1.5, Task 3.4
- Group 3 (并行): Task 2.1, Task 2.2, Task 2.3, Task 3.5
- Group 4: Task 2.4, Task 3.2
- Group 5 (并行): Task 4.1, Task 6.1, Task 6.2, Task 6.3, Task 6.4
- Group 6 (并行): Task 4.2, Task 4.3, Task 4.4, Task 4.6
- Group 7: Task 4.5
- Group 8 (并行): Task 5.1, Task 5.2, Task 5.3, Task 5.4
- Group 9: Task 7.1
- Group 10 (并行): Task 7.2, Task 8.1, Task 8.3, Task 8.4, Task 8.5
