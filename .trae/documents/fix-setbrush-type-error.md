# 修复 setBrush(Qt.NoBrush) 类型错误

## 问题
`embedded_mirror_widget.py` 第 263 行调用 `QGraphicsRectItem.setBrush(Qt.NoBrush)` 时抛出 TypeError：
```
setBrush(self, brush: Union[QBrush, Union[QColor, Qt.GlobalColor], QGradient]): argument 1 has unexpected type 'BrushStyle'
```

`Qt.NoBrush` 是 `Qt.BrushStyle` 枚举值，而 `QGraphicsRectItem.setBrush()` 只接受 `QBrush`/`QColor`/`QGradient`，不接受 `BrushStyle`。

> 注：`QPainter.setBrush()` 接受 `BrushStyle`，所以同文件第 417 行和 `step_list_widget.py` 第 604 行的 `painter.setBrush(Qt.NoBrush)` 没有问题。

## 修复

**文件**: `D:\Github\PY\ui\components\embedded_mirror_widget.py`
**行**: 263

将：
```python
self._pickup_border_item.setBrush(Qt.NoBrush)
```
改为：
```python
self._pickup_border_item.setBrush(QBrush(Qt.NoBrush))
```

需确认 `QBrush` 已在文件顶部导入。

## 验证
- 运行程序，触发选点模式（pickup mode），确认不再抛出 TypeError
- 确认蓝色边框 overlay 正常显示（无填充）
