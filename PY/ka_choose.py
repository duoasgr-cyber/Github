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

def programme_choose (choose):
    if choose == 0:
        adb_command_basic("shell input tap 350 210")
        print("您选择了初始方案")
    if choose == 1:
        adb_command_basic("shell input tap 350 420")
        print("您选择了方案1")
    if choose == 2:
        adb_command_basic("shell input tap 350 550")
        print("您选择了方案2")
    if choose == 3:
        adb_command_basic("shell input tap 350 680")
        print("您选择了方案3")
    if choose == 4:
        adb_command_basic("shell input tap 350 810")
        print("您选择了方案4")

