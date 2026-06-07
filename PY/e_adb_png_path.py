import os
from PIL import ImageGrab
import subprocess
import pygetwindow as gw
import cv2

from device_manager import DeviceManager  # 导入设备管理器

def adb_command_basic(command):
    """
    执行ADB命令。自动使用在device_manager中选定的设备。
    如果未选择设备，命令将执行失败。
    """
    device_serial = DeviceManager.get_current_device()
    if device_serial:
        full_command = f"adb -s {device_serial} {command}"
    else:
        # 如果没有选定设备，可以在这里添加逻辑，例如自动选择第一个设备
        # 但更推荐在主程序中明确选择。这里我们先报错。
        print("错误: 未选定ADB设备。请先运行设备选择。")
        # 或者，选择不指定设备，这可能在多设备时出错
        full_command = f"adb {command}"
        print(f"警告: 将在无设备指定情况下执行命令: {full_command}")

    # 打印命令以便调试（可选）
    # print(f"执行: {full_command}")
    try:
        subprocess.run(full_command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"ADB命令执行失败: {e}")
        # 根据您的需求决定是否抛出异常
        # raise

def capture_screen_region(left, top, right, bottom):
    """截取屏幕指定矩形区域"""
    screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
    screenshot.save('button.png')
def other_screen():
    adb_command_basic("shell screencap -p /sdcard/b.png")
    adb_command_basic("pull /sdcard/b.png")
    adb_command_basic("shell rm /sdcard/b.png")

def jt():
    adb_command_basic("shell screencap -p /sdcard/jt.png")
    adb_command_basic("pull /sdcard/jt.png")
    adb_command_basic("shell rm /sdcard/jt.png")
    print("截图成功，保存为jt.png，已可供调用")

def p(buttton_name):
    # 截取图片
    jt()

    # 读取图片
    screen = cv2.imread("jt.png")
    button = cv2.imread(buttton_name)

    # 查找按钮
    result = cv2.matchTemplate(screen, button, cv2.TM_CCOEFF_NORMED)
    _, similarity, _, location = cv2.minMaxLoc(result)

    # 删去截图
    if os.path.exists("/sdcard/jt.png"):
        os.remove("/sdcard/jt.png")

    # 判断结果
    if similarity > 0.85:
        print(f"相似度: {similarity:.0%}")
        print(f"   位置: ({location[0]}, {location[1]})")
        return True
    else:
        print(f"相似度: {similarity:.0%}")
        return False



