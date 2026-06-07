import os
from PIL import Image
import subprocess

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

def keep_part_of_image(image_path, output_path, crop_box):
    with Image.open(image_path) as img:
        # 截取指定区域
        cropped_img = img.crop(crop_box)
        # 保存截取的部分
        cropped_img.save(output_path)

def del_screenshot():
    """删除截图文件"""
    try:
        if os.path.exists('screenshot.png'):
            os.remove('screenshot.png')
        else:
            print("截图文件不存在，无需删除")
    except Exception as e:
        print(f"删除截图时发生错误: {e}")

def get_jiage_path():
    adb_command_basic("shell screencap -p /sdcard/screenshot.png")# 截取当前屏幕并保存到设备存储
    adb_command_basic("pull /sdcard/screenshot.png ./screenshot.png")# 将截图拉取到电脑
    adb_command_basic("shell rm /sdcard/screenshot.png")# 删除设备上的临时截图文件
    keep_part_of_image('screenshot.png', 'jiage.png', (165, 1122, 390, 1200))#处理截图
    del_screenshot()#删去截图
get_jiage_path()


