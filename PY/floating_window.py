import tkinter as tk


class FloatingWindow:
    """右上角悬浮窗，显示实时价格"""
    
    def __init__(self, root):
        self.root = root
        self.window = tk.Toplevel(root)
        self.window.title("实时价格")
        
        # 设置窗口属性
        self.window.attributes('-topmost', True)  # 置顶
        self.window.attributes('-toolwindow', True)  # 工具窗口
        self.window.overrideredirect(True)  # 移除标题栏
        self.window.attributes('-alpha', 0.85)  # 设置透明度（0.0-1.0）
        
        # 设置窗口大小和位置（增加高度以显示邮件封数）
        self.window.geometry('180x100')
        self.window.geometry('+{}+{}'.format(
            self.root.winfo_screenwidth() - 190,
            20
        ))
        
        # 设置背景色（半透明效果下的背景色）
        self.window.configure(bg='#1a1a2e')
        
        # 创建价格标签（价格和"当前价格："在同一行）
        self.price_label = tk.Label(
            self.window,
            text="当前价格：0",
            font=('Arial', 12, 'bold'),
            bg='#1a1a2e',
            fg='#00ff88',
            justify='center'
        )
        self.price_label.pack(expand=True, fill='both', padx=10, pady=5)
        
        # 创建邮件封数标签
        self.mail_label = tk.Label(
            self.window,
            text="邮件：0",
            font=('Arial', 11),
            bg='#1a1a2e',
            fg='#ffaa00',
            justify='center'
        )
        self.mail_label.pack(expand=True, fill='both', padx=10, pady=5)
        
        # 创建状态标签
        self.status_label = tk.Label(
            self.window,
            text="等待中...",
            font=('Arial', 9),
            bg='#1a1a2e',
            fg='#a0a0a0',
            justify='center'
        )
        self.status_label.pack(expand=True, fill='both', padx=10, pady=2)
        
        # 窗口关闭事件
        self.window.protocol('WM_DELETE_WINDOW', self.on_close)
        
        # 当前显示的数据
        self.current_price = 0
        self.current_mail_count = 0
        self.current_status = "等待中..."
        self.current_color = '#a0a0a0'
        
    def update_price(self, price):
        """更新价格显示（线程安全）"""
        self.current_price = price
        self.root.after(0, self._update_price_ui, price)
    
    def _update_price_ui(self, price):
        """实际更新UI（在主线程中运行）"""
        if price > 1000000000:
            self.price_label.config(text="当前价格：未知", fg='#ff6b6b')
            self.status_label.config(text="识别错误", fg='#ff6b6b')
        else:
            self.price_label.config(text=f"当前价格：{price:,}", fg='#00ff88')
            self.status_label.config(text="正常", fg='#4caf50')
    
    def update_mail_count(self, count):
        """更新邮件封数显示（线程安全）"""
        self.current_mail_count = count
        self.root.after(0, self._update_mail_ui, count)
    
    def _update_mail_ui(self, count):
        """实际更新邮件封数UI（在主线程中运行）"""
        self.mail_label.config(text=f"邮件：{count}")
    
    def update_status(self, status, color='#a0a0a0'):
        """更新状态显示（线程安全）"""
        self.current_status = status
        self.current_color = color
        self.root.after(0, self._update_status_ui, status, color)
    
    def _update_status_ui(self, status, color):
        """实际更新UI（在主线程中运行）"""
        self.status_label.config(text=status, fg=color)
    
    def on_close(self):
        """窗口关闭事件"""
        pass  # 不允许关闭
