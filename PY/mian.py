import time
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog
import logging
import os
import re
import easyocr
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageDraw, ImageFont
import pystray

# 本地模块
import ka_choose
import sale
from device_manager import DeviceManager
from floating_window import FloatingWindow


"""
使用前须知:
本程序仅供学习参考，切勿用于非法用途
"""
# 设置须知
"""
1.you.txt中输入你当前的邮件数量
2.用户定价.txt中输入你的理想价格（单发）
3.在配置中准备好需要买的子弹（单种）
4.打开投票软件，确认窗口名称
5.在三角洲中打开方案界面，并选择你需要购买的方案
6.为保证程序不出错误，请把永不息屏和勿扰模式打开，电脑保持工作
7.确保仓库空间足够
"""

#更新日志
"""
v1.1：
1.优化了文字识别的逻辑与方式，现在识别速度更快了（现在刷新价格会与用户抢界面）
2.增加了智能的登录逻辑，会自动登录当前的qq账号
3.增加了对邮件的智能识别，在超出190封邮件后会自动停止
4.增加了是否卡成功邮件的判断，而且会自动识别胸挂与背包位置并领出
5.优化了卡邮件的方式，现在成功率更高了
6.增加了自动售卖的模块
7.能手动校准来解决设备不同的兼容问题（这需要一些时间）
8.兼容了新赛季的购买模式
"""

# 设置日志
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    encoding='utf-8'
)

# 全局变量
time_check = True
button_text = "None"
user_choose = 0
current_price = 0  # 当前价格

print("正在初始化EasyOCR...")
ocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
print("EasyOCR初始化完成！")


# ==================== 工具函数 ====================

def safe_remove_file(file_path, max_retries=3, delay=0.5):
    """安全删除文件，带重试机制"""
    for attempt in range(max_retries):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"成功删除文件: {file_path}")
                return True
        except PermissionError as e:
            if attempt < max_retries - 1:
                print(f"第{attempt+1}次尝试删除失败，{delay}秒后重试...")
                time.sleep(delay)
            else:
                print(f"删除失败，文件可能被占用: {file_path}")
                raise e
    return False


def detect_content_type_and_recognize(image_path):
    """
    使用EasyOCR智能判断图片内容是中文还是数字
    返回: (content_type, result_text)
    """
    try:
        img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        
        if img is None:
            print(f"无法读取图片: {image_path}")
            return 'unknown', "识别失败"
        
        result = ocr_reader.readtext(img)
        
        if not result or len(result) == 0:
            print("未识别到任何文本")
            return 'unknown', "识别失败"
        
        all_texts = []
        for detection in result:
            bbox, text, confidence = detection
            all_texts.append(text)
        
        combined_text = ''.join(all_texts)
        print(f"EasyOCR识别结果: '{combined_text}'")
        
        has_digits = any(char.isdigit() for char in combined_text)
        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in combined_text)
        
        if has_digits:
            digits = re.findall(r'[\d,]', combined_text)
            if digits:
                digit_text = ''.join(digits)
                if digit_text and digit_text[-1] == '8':
                    digit_text = digit_text[:-1] + '0'
                digit_text = digit_text.replace(',', '')
                print(f"提取数字: '{digit_text}'")
                return 'number', digit_text
        
        if has_chinese:
            cleaned_text = combined_text.replace(' ', '')
            print(f"中文识别结果: '{cleaned_text}'")
            return 'chinese', cleaned_text
        
        return 'unknown', "识别失败"
            
    except Exception as e:
        print(f"识别失败: {str(e)}")
        return 'unknown', "识别失败"


def get_button_text():
    """获取按钮文字，使用优化后的识别逻辑"""
    import e_adb_png_path
    e_adb_png_path.capture_screen_region(1300,648,1580,705)
    
    # 主程序 - 测试您的图片
    image_path = "button.png"

    if os.path.exists(image_path):
        content_type, result_text = detect_content_type_and_recognize(image_path)
        print(f"\n最终结果:")
        print(f"类型: {content_type}")
        print(f"识别文本: '{result_text}'")
        safe_remove_file(image_path)
        return content_type, result_text
    else:
        print(f"文件 {image_path} 不存在")
        return "unknown", ""


def refresh_price():
    """刷新价格"""
    import ka_choose
    ka_choose.programme_choose(0)
    time.sleep(0.01)
    ka_choose.programme_choose(choose=user_choose)


def check_mail_safety():
    """检查邮件数量是否安全"""
    try:
        with open('you.txt', 'r') as f:
            mail_count = int(f.read().strip())

        if mail_count > 190:
            messagebox.showinfo("警告", "邮件即将卡满，自动停止")
            return False
        return True
    except:
        return True


def get_current_mail_count():
    """获取当前邮件数量"""
    try:
        with open('you.txt', 'r') as f:
            count = int(f.read().strip())
        return count
    except:
        return 0


def update_mail_count(floating_window=None):
    """更新邮件数量"""
    try:
        with open('you.txt', 'r') as f:
            count = int(f.read().strip())

        count += 1

        with open('you.txt', 'w') as f:
            f.write(str(count))

        print(f"当前邮件数量: {count}")
        
        if floating_window is not None:
            floating_window.update_mail_count(count)
            
        return count
    except:
        return 0


# ==================== 卡邮件流程 ====================
def card_mail_process(floating_window=None):
    """卡邮件的完整流程"""
    import ka

    # 购买后操作
    ka.after_buy()
    ru, kashi = ka.begin() # 开始卡邮件

    if ru:  # 如果有对局
        print("正在卡邮件...")
        ka.ru_run_1()
        ka_choose.programme_choose(choose=user_choose)

        result = ka.ru_run_2()

        if result: # 卡成功
            new_count = update_mail_count(floating_window)
            if new_count > 190:
                return False
        elif result == "dk":  # 未知界面
            print("未知界面")
            return True

        # 返回购买界面
        ka.fin()
        ka_choose.programme_choose(choose=user_choose)

    elif kashi:  # 如果没有对局
        print("直接进入购买界面")
        ka.kaishi()
        ka_choose.programme_choose(choose=user_choose)

    return True


# ==================== 价格检查流程 ====================
def check_price_loop(root, floating_window):
    """检查价格的主要循环"""
    global time_check, user_choose

    while True:
        has_number = False
        time.sleep(0.5)
        refresh_price()
        time.sleep(1)
        # 获取按钮文字
        content_type, result_text = get_button_text()
        print(f"按钮文字: {result_text}")

        # 检查是否有数字
        if content_type == "number":
            has_number = True

        # 检查文字中是否包含"方"
        if content_type == "chinese" or content_type == "mixed":
            # 移除空格后检查是否包含"方"
            cleaned_text = result_text.replace(' ', '')
            if "方" in cleaned_text:
                print("识别到包含'方'的文字，直接进行卡邮件操作")
                floating_window.update_status("确认购买界面", '#4caf50')
                # 先点击确认购买
                import e_adb_buy
                e_adb_buy.e_adb_buy()
                time.sleep(2)
                # 直接进行卡邮件操作
                if not card_mail_process(floating_window):
                    return
                continue
            else:
                # 其他中文界面，直接重启游戏
                print("识别到其他中文界面，直接重启游戏")
                floating_window.update_status("重启中...", '#ff6b6b')
                recover_game()
                continue

        if has_number:  # 购买界面
            print("在购买界面")
            floating_window.update_status("购买界面", '#4caf50')
            time_check = True

            while time_check:
                refresh_price()
                time.sleep(0.2)

                # 获取用户价格
                try:
                    with open('用户定价.txt', 'r', encoding='utf-8') as f:
                        user_price = int(f.read())
                except :
                    user_price = 0

                # 获取游戏价格
                import e_jiage
                game_price = e_jiage.get_jiage_price_ocr()
                
                # 立即更新悬浮窗价格
                floating_window.update_price(game_price)
                print(f"当前价格: {game_price}")
                
                if game_price > 1000000000:
                    print("出现未知错误")
                    break

                if game_price <= 300000: #小于30w元不购买
                    print(f"价格过小，不购买价格：{game_price}")
                    break

                # 比较价格
                elif user_price * 4560  >= game_price:
                    print(f"价格合适！用户价:{user_price * 4560 } 游戏价:{game_price}")
                    floating_window.update_status("购买中...", '#4caf50')

                    # 执行购买
                    import e_adb_buy
                    e_adb_buy.e_adb_buy()
                    time.sleep(2)

                    # 购买后进行卡邮件操作
                    if not card_mail_process(floating_window):
                        return
                    break
                else:
                    print(f"价格不合适，继续等待。用户价:{user_price * 4560 } 游戏价:{game_price}")
                    continue

            # 价格检查循环结束后，重新开始
            print("价格检查循环结束，重新开始")
            continue

        else:
            # 没有数字也没有"方"，不在购买界面
            print("不在购买界面，尝试恢复...")
            floating_window.update_status("恢复中...", '#ff6b6b')
            recover_game()
            continue


def recover_game():
    """尝试恢复游戏到正常状态"""
    import Restart
    import e_adb_png_path
    import time

    print("正在重启恢复...")
    is_recover = True
    Restart.restart()
    while is_recover:
        time.sleep(1)
        dl = e_adb_png_path.p(r".\tp\dl.jpg")
        ru = e_adb_png_path.p(r".\tp\kai_1.jpg")
        kai = e_adb_png_path.p(r".\tp\kai_2.jpg")

        if dl or ru or kai:
            is_recover = False
            if ru:
                Restart.ru_run()
            elif kai:
                Restart.kai_run()
            elif dl:
                time.sleep(1)
                if e_adb_png_path.p(r".\tp\dl.jpg"):
                    Restart.dl_run()


def create_tray_icon():
    """创建系统托盘图标"""
    # 创建一个简单的图标
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), color='#1a1a2e')
    dc = ImageDraw.Draw(image)
    
    # 绘制一个简单的图标（圆形）
    dc.ellipse([8, 8, width-8, height-8], fill='#00ff88', outline='#00ff88')
    dc.text((width//2-12, height//2-8), "购", fill='#1a1a2e')
    
    return image


def setup_tray_icon(root, floating_window):
    """设置系统托盘图标"""
    def on_show_window(icon, item):
        """显示主窗口"""
        root.deiconify()
        root.lift()
    
    def on_hide_window(icon, item):
        """隐藏主窗口"""
        root.withdraw()
    
    def on_exit(icon, item):
        """退出程序"""
        icon.stop()
        root.quit()
    
    # 创建托盘图标菜单
    menu = (
        pystray.MenuItem("显示窗口", on_show_window),
        pystray.MenuItem("隐藏窗口", on_hide_window),
        pystray.MenuItem("退出", on_exit),
    )
    
    # 创建托盘图标
    icon = pystray.Icon("game_auto_buy", create_tray_icon(), "游戏自动购买程序", menu)
    
    # 在后台运行托盘图标
    tray_thread = threading.Thread(target=icon.run, daemon=True)
    tray_thread.start()
    
    return icon


# ==================== 主程序 ====================
def main():
    """主函数"""
    global user_choose
    
    print("="*60)
    print("游戏自动购买程序")
    print("="*60)
    
    # 创建主窗口
    root = tk.Tk()
    root.title("游戏自动购买程序")
    root.geometry("300x200")
    
    # 创建悬浮窗
    floating_window = FloatingWindow(root)
    
    # 初始化邮件数量显示
    initial_mail_count = get_current_mail_count()
    floating_window.update_mail_count(initial_mail_count)
    print(f"初始邮件数量: {initial_mail_count}")
    
    # 选择ADB设备
    print("正在检测ADB设备...")
    selected_device = DeviceManager.select_and_set_device()
    if selected_device is None:
        print("错误: 未选定ADB设备，程序退出")
        return
    print(f"已选择设备: {selected_device}")
    
    # 检查邮件安全性
    if not check_mail_safety():
        return
    
    # 获取用户选择
    user_choose = simpledialog.askinteger("选择方案", "请输入要购买的方案编号（0-4）", 
                                       minvalue=0, maxvalue=4)
    if user_choose is None:
        print("用户取消操作")
        return
    
    print(f"用户选择的方案: {user_choose}")
    
    # 询问是否需要定时启动
    use_timer = messagebox.askyesno("定时启动", "是否需要定时启动？\n\n选择'是'设置启动时间\n选择'否'立即启动")
    
    if use_timer:
        # 获取启动时间
        start_time_str = simpledialog.askstring("设置启动时间", "请输入启动时间（格式：HH:MM，例如：14:30）")
        
        if start_time_str:
            try:
                # 解析时间
                start_hour, start_minute = map(int, start_time_str.split(':'))
                
                # 计算等待时间
                import datetime
                now = datetime.datetime.now()
                start_time = now.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
                
                if start_time <= now:
                    # 如果时间已过，设置为明天
                    start_time += datetime.timedelta(days=1)
                
                wait_seconds = (start_time - now).total_seconds()
                wait_hours = int(wait_seconds // 3600)
                wait_minutes = int((wait_seconds % 3600) // 60)
                
                print(f"计划启动时间: {start_time.strftime('%H:%M:%S')}")
                print(f"等待时间: {wait_hours}小时{wait_minutes}分钟")
                messagebox.showinfo("定时启动", f"程序将在 {start_time.strftime('%H:%M:%S')} 启动\n等待时间: {wait_hours}小时{wait_minutes}分钟")
                
                # 等待到指定时间
                time.sleep(wait_seconds)
                print("定时启动时间到达，开始运行...")
                
            except Exception as e:
                print(f"时间解析错误: {str(e)}")
                messagebox.showerror("错误", f"时间格式错误，请使用HH:MM格式\n错误信息: {str(e)}")
                return
        else:
            print("用户取消定时启动")
            return
    
    # 设置系统托盘图标
    tray_icon = setup_tray_icon(root, floating_window)
    
    # 隐藏主窗口，只显示悬浮窗和托盘图标
    root.withdraw()
    print("主窗口已隐藏，程序运行在后台（可通过系统托盘图标显示窗口）")
    
    # 开始价格检查循环
    try:
        price_thread = threading.Thread(target=check_price_loop, args=(root, floating_window), daemon=True)
        price_thread.start()
        
        root.mainloop()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序发生错误: {str(e)}")
        logging.error(f"程序发生错误: {str(e)}")
    finally:
        print("程序结束")


if __name__ == "__main__":
    main()
