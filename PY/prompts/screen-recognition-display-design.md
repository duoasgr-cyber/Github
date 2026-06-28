# 屏幕识别步骤在脚本编辑器中的显示设计

## 目标
在脚本编辑器中实现屏幕识别步骤（`check_image` 和 `ocr_region`）的完整显示，包括：
1. **识别结果**：OCR 识别的文本结果、图像匹配的置信度等
2. **区域预览**：识别区域的截图预览或模板图像预览
3. **执行状态**：识别步骤的执行状态（成功/失败/进行中）

## 当前状态分析

### 现有实现
- **步骤编辑器** (`step_editor.py`)：显示步骤参数字段，但无识别结果和预览
- **步骤列表** (`step_list_widget.py`)：显示步骤类型和关键参数摘要，有执行状态颜色
- **步骤执行器** (`step_executor.py`)：执行步骤但未保存识别结果

### 缺失功能
1. 识别结果未保存到步骤数据中
2. 步骤编辑器无识别结果和预览显示区域
3. 步骤执行状态未与识别结果关联

## 详细设计方案

### 1. 数据结构扩展

#### 步骤数据结构增强
```python
# check_image 步骤数据结构
{
    "type": "check_image",
    "template": "button.png",
    "threshold": 0.85,
    "comment": "检测购买按钮",
    
    # 新增：执行结果字段
    "execution_result": {
        "status": "success",  # success/fail/pending/running
        "confidence": 0.92,   # 匹配置信度
        "match_location": {"x": 100, "y": 200},  # 匹配位置
        "timestamp": 1234567890,  # 执行时间戳
        "error_message": ""  # 错误信息
    },
    
    # 新增：预览数据
    "preview": {
        "template_image": "base64_encoded_template",  # 模板图像
        "match_region": {"x": 90, "y": 190, "w": 50, "h": 30},  # 匹配区域
        "screenshot_thumbnail": "base64_encoded_thumbnail"  # 截图缩略图
    }
}

# ocr_region 步骤数据结构
{
    "type": "ocr_region",
    "region": {"left": 100, "top": 200, "right": 300, "bottom": 250},
    "comment": "识别价格文本",
    
    # 新增：执行结果字段
    "execution_result": {
        "status": "success",
        "recognized_text": "¥1,280.00",  # 识别文本
        "confidence": 0.95,  # 识别置信度
        "timestamp": 1234567890,
        "error_message": ""
    },
    
    # 新增：预览数据
    "preview": {
        "region_image": "base64_encoded_region",  # 区域图像
        "highlighted_text": "base64_encoded_highlighted",  # 高亮文本图像
        "screenshot_thumbnail": "base64_encoded_thumbnail"
    }
}
```

### 2. 步骤执行器修改

#### 保存识别结果
```python
# step_executor.py 修改
class StepExecutor:
    # 新增信号
    step_result_updated = pyqtSignal(int, dict)  # (步骤索引, 结果数据)
    
    def _execute_check_image(self, step: dict, step_index: int):
        """执行图像匹配步骤并保存结果"""
        try:
            # 获取当前帧
            frame = self._screen_capture.get_current_frame()
            if frame is None:
                raise Exception("获取屏幕帧失败")
            
            # 加载模板
            template = self._load_template(step["template"])
            threshold = step.get("threshold", 0.85)
            
            # 执行匹配
            result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            
            # 构建结果数据
            execution_result = {
                "status": "success" if max_val >= threshold else "fail",
                "confidence": float(max_val),
                "match_location": {"x": int(max_loc[0]), "y": int(max_loc[1])},
                "timestamp": int(time.time()),
                "error_message": ""
            }
            
            # 构建预览数据
            preview = {
                "template_image": self._image_to_base64(template),
                "match_region": {
                    "x": int(max_loc[0]),
                    "y": int(max_loc[1]),
                    "w": template.shape[1],
                    "h": template.shape[0]
                },
                "screenshot_thumbnail": self._create_thumbnail(frame)
            }
            
            # 更新步骤数据
            step["execution_result"] = execution_result
            step["preview"] = preview
            
            # 发送信号
            self.step_result_updated.emit(step_index, {
                "execution_result": execution_result,
                "preview": preview
            })
            
            return max_val >= threshold
            
        except Exception as e:
            execution_result = {
                "status": "fail",
                "confidence": 0,
                "match_location": None,
                "timestamp": int(time.time()),
                "error_message": str(e)
            }
            step["execution_result"] = execution_result
            self.step_result_updated.emit(step_index, {
                "execution_result": execution_result
            })
            raise
    
    def _execute_ocr_region(self, step: dict, step_index: int):
        """执行 OCR 识别步骤并保存结果"""
        try:
            # 获取当前帧
            frame = self._screen_capture.get_current_frame()
            if frame is None:
                raise Exception("获取屏幕帧失败")
            
            # 获取区域
            region = step.get("region", {})
            left = region.get("left", 0)
            top = region.get("top", 0)
            right = region.get("right", 0)
            bottom = region.get("bottom", 0)
            
            # 裁剪区域
            roi = frame[top:bottom, left:right]
            
            # 执行 OCR
            text = self._ocr_engine.recognize(roi)
            
            # 构建结果数据
            execution_result = {
                "status": "success",
                "recognized_text": text,
                "confidence": 0.95,  # 实际置信度从 OCR 引擎获取
                "timestamp": int(time.time()),
                "error_message": ""
            }
            
            # 构建预览数据
            preview = {
                "region_image": self._image_to_base64(roi),
                "highlighted_text": self._highlight_text_in_image(frame, region, text),
                "screenshot_thumbnail": self._create_thumbnail(frame)
            }
            
            # 更新步骤数据
            step["execution_result"] = execution_result
            step["preview"] = preview
            
            # 发送信号
            self.step_result_updated.emit(step_index, {
                "execution_result": execution_result,
                "preview": preview
            })
            
            return text
            
        except Exception as e:
            execution_result = {
                "status": "fail",
                "recognized_text": "",
                "confidence": 0,
                "timestamp": int(time.time()),
                "error_message": str(e)
            }
            step["execution_result"] = execution_result
            self.step_result_updated.emit(step_index, {
                "execution_result": execution_result
            })
            raise
    
    def _image_to_base64(self, image: np.ndarray) -> str:
        """将图像转换为 base64 字符串"""
        _, buffer = cv2.imencode('.png', image)
        return base64.b64encode(buffer).decode('utf-8')
    
    def _create_thumbnail(self, frame: np.ndarray, size=(100, 100)) -> str:
        """创建缩略图"""
        thumbnail = cv2.resize(frame, size)
        return self._image_to_base64(thumbnail)
    
    def _highlight_text_in_image(self, frame: np.ndarray, region: dict, text: str) -> str:
        """在图像中高亮显示识别的文本"""
        # 创建副本
        highlighted = frame.copy()
        
        # 绘制矩形
        left = region.get("left", 0)
        top = region.get("top", 0)
        right = region.get("right", 0)
        bottom = region.get("bottom", 0)
        
        cv2.rectangle(highlighted, (left, top), (right, bottom), (0, 255, 0), 2)
        
        # 添加文本
        cv2.putText(highlighted, text, (left, top - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        return self._image_to_base64(highlighted)
```

### 3. 步骤编辑器 UI 修改

#### 添加识别结果显示区域
```python
# step_editor.py 修改
class StepEditor(QWidget):
    def __init__(self, config_manager=None, parent=None):
        super().__init__(parent)
        # ... 现有初始化代码 ...
        
        # 新增：识别结果容器
        self._recognition_container = QWidget()
        self._setup_recognition_ui()
        layout.addWidget(self._recognition_container)
        
        # 连接信号
        self._step_executor = None  # 需要从外部设置
    
    def _setup_recognition_ui(self):
        """设置识别结果显示 UI"""
        layout = QVBoxLayout(self._recognition_container)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)
        
        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #30363d;")
        layout.addWidget(sep)
        
        # 标题
        title = QLabel("📊 识别结果")
        title.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        title.setStyleSheet("color: #58a6ff;")
        layout.addWidget(title)
        
        # 状态显示
        self._status_label = QLabel("状态: 待执行")
        self._status_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addWidget(self._status_label)
        
        # 结果显示
        self._result_label = QLabel("")
        self._result_label.setStyleSheet("color: #c9d1d9; font-size: 11px;")
        self._result_label.setWordWrap(True)
        layout.addWidget(self._result_label)
        
        # 预览图像容器
        self._preview_container = QWidget()
        preview_layout = QHBoxLayout(self._preview_container)
        preview_layout.setContentsMargins(0, 4, 0, 0)
        preview_layout.setSpacing(8)
        
        # 模板/区域预览
        self._template_preview = QLabel()
        self._template_preview.setFixedSize(100, 100)
        self._template_preview.setStyleSheet(
            "border: 1px solid #30363d; background-color: #161b22;"
        )
        self._template_preview.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self._template_preview)
        
        # 匹配结果预览
        self._match_preview = QLabel()
        self._match_preview.setFixedSize(100, 100)
        self._match_preview.setStyleSheet(
            "border: 1px solid #30363d; background-color: #161b22;"
        )
        self._match_preview.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(self._match_preview)
        
        preview_layout.addStretch()
        layout.addWidget(self._preview_container)
        
        # 初始隐藏
        self._recognition_container.setVisible(False)
    
    def set_step_executor(self, executor):
        """设置步骤执行器并连接信号"""
        self._step_executor = executor
        if executor:
            executor.step_result_updated.connect(self._on_step_result_updated)
    
    def _on_step_result_updated(self, step_index: int, result: dict):
        """步骤结果更新回调"""
        if step_index != self._current_index:
            return
        
        # 更新状态显示
        execution_result = result.get("execution_result", {})
        status = execution_result.get("status", "pending")
        
        status_colors = {
            "success": "#3fb950",
            "fail": "#f85149",
            "running": "#1f6feb",
            "pending": "#8b949e"
        }
        
        status_texts = {
            "success": "✅ 成功",
            "fail": "❌ 失败",
            "running": "🔄 执行中",
            "pending": "⏳ 待执行"
        }
        
        self._status_label.setText(f"状态: {status_texts.get(status, status)}")
        self._status_label.setStyleSheet(f"color: {status_colors.get(status, '#8b949e')}; font-size: 11px;")
        
        # 更新结果显示
        step_type = self._current_step.get("type", "")
        if step_type == "check_image":
            confidence = execution_result.get("confidence", 0)
            self._result_label.setText(f"匹配置信度: {confidence:.2%}")
        elif step_type == "ocr_region":
            text = execution_result.get("recognized_text", "")
            self._result_label.setText(f"识别文本: {text}")
        
        # 更新预览图像
        preview = result.get("preview", {})
        self._update_preview_images(preview, step_type)
        
        # 显示容器
        self._recognition_container.setVisible(True)
    
    def _update_preview_images(self, preview: dict, step_type: str):
        """更新预览图像"""
        if step_type == "check_image":
            # 显示模板图像
            template_image = preview.get("template_image", "")
            if template_image:
                self._set_image_from_base64(self._template_preview, template_image, "模板")
            
            # 显示匹配结果
            screenshot_thumbnail = preview.get("screenshot_thumbnail", "")
            if screenshot_thumbnail:
                self._set_image_from_base64(self._match_preview, screenshot_thumbnail, "匹配结果")
        
        elif step_type == "ocr_region":
            # 显示区域图像
            region_image = preview.get("region_image", "")
            if region_image:
                self._set_image_from_base64(self._template_preview, region_image, "识别区域")
            
            # 显示高亮文本
            highlighted_text = preview.get("highlighted_text", "")
            if highlighted_text:
                self._set_image_from_base64(self._match_preview, highlighted_text, "识别结果")
    
    def _set_image_from_base64(self, label: QLabel, base64_str: str, placeholder: str):
        """从 base64 字符串设置图像"""
        if not base64_str:
            label.setText(placeholder)
            return
        
        try:
            image_data = base64.b64decode(base64_str)
            pixmap = QPixmap()
            pixmap.loadFromData(image_data)
            label.setPixmap(pixmap.scaled(
                label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))
        except Exception:
            label.setText(placeholder)
    
    def load_step(self, index: int, step: dict):
        """加载步骤并显示识别结果"""
        # ... 现有代码 ...
        
        # 显示识别结果（如果有）
        step_type = step.get("type", "")
        if step_type in ("check_image", "ocr_region"):
            execution_result = step.get("execution_result")
            if execution_result:
                self._on_step_result_updated(index, {
                    "execution_result": execution_result,
                    "preview": step.get("preview", {})
                })
            else:
                self._recognition_container.setVisible(True)
                self._status_label.setText("状态: 待执行")
                self._status_label.setStyleSheet("color: #8b949e; font-size: 11px;")
                self._result_label.setText("")
                self._template_preview.setText("预览")
                self._match_preview.setText("预览")
        else:
            self._recognition_container.setVisible(False)
```

### 4. 步骤列表显示增强

#### 显示识别结果摘要
```python
# step_list_widget.py 修改
STEP_SUMMARY_FIELDS = {
    # ... 现有字段 ...
    "check_image": ["template", "threshold", "execution_result"],
    "ocr_region": ["region", "execution_result"],
}

def _format_summary(step: dict) -> str:
    """生成步骤关键参数摘要文本。"""
    step_type = step.get("type", "")
    fields = STEP_SUMMARY_FIELDS.get(step_type, [])
    parts = []
    for field in fields:
        if field == "execution_result":
            # 特殊处理执行结果
            result = step.get("execution_result")
            if result:
                status = result.get("status", "")
                if status == "success":
                    if step_type == "check_image":
                        confidence = result.get("confidence", 0)
                        parts.append(f"匹配成功({confidence:.0%})")
                    elif step_type == "ocr_region":
                        text = result.get("recognized_text", "")
                        if len(text) > 10:
                            text = text[:7] + "..."
                        parts.append(f"识别: {text}")
                elif status == "fail":
                    parts.append("匹配失败")
                elif status == "running":
                    parts.append("执行中...")
            continue
        
        value = step.get(field)
        if value is None or value == "":
            continue
        # wait_after 字段即使为 0 也显示
        if field not in ("wait_after", "wait_before") and value == 0:
            continue
        if field == "region" and isinstance(value, dict):
            parts.append(f"区域({value.get('left',0)},{value.get('top',0)},{value.get('right',0)},{value.get('bottom',0)})")
        else:
            # 截断过长的值
            val_str = str(value)
            if len(val_str) > 30:
                val_str = val_str[:27] + "..."
            parts.append(f"{field}={val_str}")
    return "  |  ".join(parts) if parts else ""
```

### 5. 工作流面板集成

#### 连接步骤执行器信号
```python
# workflow_panel.py 修改
class WorkflowPanel(QWidget):
    def __init__(self, config_manager, step_executor, parent=None):
        super().__init__(parent)
        # ... 现有初始化代码 ...
        
        # 设置步骤执行器
        self._step_editor.set_step_executor(step_executor)
        
        # 连接信号
        step_executor.step_result_updated.connect(self._on_step_result_updated)
    
    def _on_step_result_updated(self, step_index: int, result: dict):
        """步骤结果更新回调"""
        # 更新步骤列表显示
        if step_index < len(self._current_steps):
            # 更新步骤数据
            self._current_steps[step_index].update(result)
            
            # 刷新列表显示
            self._step_list.load_steps(self._current_steps)
            
            # 如果当前选中的是这个步骤，更新编辑器
            if self._step_editor.get_current_index() == step_index:
                self._step_editor._on_step_result_updated(step_index, result)
```

## 实现步骤

### 第一阶段：数据结构和执行器修改
1. 扩展步骤数据结构，添加 `execution_result` 和 `preview` 字段
2. 修改步骤执行器，保存识别结果和预览数据
3. 添加 `step_result_updated` 信号

### 第二阶段：UI 组件修改
1. 修改步骤编辑器，添加识别结果显示区域
2. 修改步骤列表，显示识别结果摘要
3. 修改工作流面板，连接信号和更新显示

### 第三阶段：测试和优化
1. 测试识别结果保存和显示
2. 测试预览图像加载和显示
3. 优化 UI 布局和样式
4. 处理边界情况和错误处理

## 注意事项

1. **性能考虑**：
   - 预览图像应使用缩略图，避免内存占用过大
   - 识别结果更新应异步处理，避免阻塞 UI

2. **错误处理**：
   - 识别失败时应显示错误信息
   - 图像加载失败时应显示占位符

3. **用户体验**：
   - 识别结果应实时更新
   - 预览图像应清晰可辨
   - 状态显示应直观明了

4. **数据持久化**：
   - 识别结果应保存到工作流配置中
   - 下次加载时应显示历史结果

## 预期效果

1. **步骤编辑器**：
   - 显示识别状态（成功/失败/执行中）
   - 显示识别结果（文本/置信度）
   - 显示预览图像（模板/区域/匹配结果）

2. **步骤列表**：
   - 显示识别结果摘要
   - 颜色区分识别状态
   - 实时更新执行状态

3. **整体效果**：
   - 用户可以直观看到识别步骤的执行情况
   - 方便调试和优化识别参数
   - 提高工作效率和准确性