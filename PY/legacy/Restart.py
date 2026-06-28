import subprocess
import time

import e_adb_png_path
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
def restart():
    adb_command_basic("shell am force-stop com.tencent.tmgp.dfm")
    time.sleep(0.5)
    adb_command_basic("shell monkey -p com.tencent.tmgp.dfm -c android.intent.category.LAUNCHER 1")
    time.sleep(30.0) # 等待三角洲启动
    "重新启动三角洲"

def ru():
    adb_command_basic("shell input tap 1170 855")  # 点取消重连 
    time.sleep(1)
    adb_command_basic("shell input tap 1170 855")  # 点取消重连
    time.sleep(1)
    adb_command_basic("shell input tap 1320 970") # 点掉通行证
    time.sleep(1.5)
    adb_command_basic("shell input tap 1320 970") # 点掉3x3提示
    time.sleep(1)
    adb_command_basic("shell input tap 2555 1145")  ##打开烽火主页面
    time.sleep(1)
    adb_command_basic("shell input tap 2580 81")  ##点掉广告
    time.sleep(1)
    adb_command_basic("shell input tap 2580 81")  ##点掉广告
    time.sleep(2)
    adb_command_basic("shell input keyevent 4")
    time.sleep(1)
    adb_command_basic("shell input tap 1170 855")  # 点取消重连
    time.sleep(1)
    adb_command_basic("shell input tap 2392 1138")  ##点备战
    time.sleep(1)
    adb_command_basic("shell input tap 1132 315")  ##选择大坝
    time.sleep(1)
    adb_command_basic("shell input tap 2408 975")  ##开始
    time.sleep(1)
    adb_command_basic("shell input tap 1978 1141")  # 点方案

def kai():
    adb_command_basic("shell input tap 2555 1145")  ##打开烽火主页面
    time.sleep(0.8)
    adb_command_basic("shell input tap 2580 81")  ##点掉广告
    time.sleep(1.0)
    adb_command_basic("shell input tap 2580 81")  ##点掉广告
    time.sleep(0.8)
    adb_command_basic("shell input keyevent 4")
    time.sleep(1)
    adb_command_basic("shell input tap 1170 855")  # 点取消重连
    time.sleep(1)
    adb_command_basic("shell input tap 2392 1138")  ##点备战
    time.sleep(1)
    adb_command_basic("shell input tap 1132 315")  ##选择大坝
    time.sleep(1)
    adb_command_basic("shell input tap 2408 975")  ##开始
    time.sleep(1)
    adb_command_basic("shell input tap 1978 1141")  # 点方案
    time.sleep(1)

def dl():
    adb_command_basic("shell input tap 855 1080")  # 同意协议
    time.sleep(3)
    adb_command_basic("shell input tap 1635 990")  # qq登录
    time.sleep(3)
    adb_command_basic("shell input tap 628 2350") # 同意
    time.sleep(2)
    adb_command_basic("shell input tap 628 2350") # 同意
    time.sleep(10)


def ru_run():
    adb_command_basic("shell input tap 1170 855")  # 点取消重连
    time.sleep(1)
    adb_command_basic("shell input tap 1170 855")  # 点取消重连
    time.sleep(1)
    adb_command_basic("shell input tap 1320 970") # 点掉通行证
    time.sleep(1.5)
    adb_command_basic("shell input tap 1320 970") # 点掉3x3提示
    time.sleep(2)
    adb_command_basic("shell input tap 2555 1145")  ##打开烽火主页面
    time.sleep(1)
    adb_command_basic("shell input tap 2580 81")  ##点掉广告
    time.sleep(1)
    adb_command_basic("shell input tap 2580 81")  ##点掉广告
    time.sleep(2)
    adb_command_basic("shell input keyevent 4")
    time.sleep(1)
    adb_command_basic("shell input tap 1170 855")  # 点取消重连
    time.sleep(1)
    adb_command_basic("shell input tap 2392 1138")  ##点备战
    time.sleep(1)
    adb_command_basic("shell input tap 1132 315")  ##选择大坝
    time.sleep(1)
    adb_command_basic("shell input tap 2408 975")  ##开始
    time.sleep(1)
    adb_command_basic("shell input tap 1978 1141")  # 点方案

def kai_run():
    time.sleep(1)
    adb_command_basic("shell input tap 2555 1145")  ##打开烽火主页面
    time.sleep(2)
    adb_command_basic("shell input tap 2580 81")  ##点掉广告
    time.sleep(1.0)
    adb_command_basic("shell input tap 2580 81")  ##点掉广告
    time.sleep(1)
    adb_command_basic("shell input keyevent 4")
    time.sleep(1)
    adb_command_basic("shell input tap 1170 855")  # 点取消重连
    time.sleep(1)
    adb_command_basic("shell input tap 2392 1138")  ##点备战
    time.sleep(1)
    adb_command_basic("shell input tap 1132 315")  ##选择大坝
    time.sleep(1)
    adb_command_basic("shell input tap 2408 975")  ##开始
    time.sleep(1)
    adb_command_basic("shell input tap 1978 1141")  # 点方案
    time.sleep(1)

def dl_run():
    adb_command_basic("shell input tap 855 1080")  # 同意协议
    time.sleep(3)
    adb_command_basic("shell input tap 1635 990")  # qq登录
    time.sleep(3)
    adb_command_basic("shell input tap 628 2350") # 同意
    time.sleep(2)
    adb_command_basic("shell input tap 628 2350") # 同意
    time.sleep(10)
