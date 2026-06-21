import time
import subprocess

 # 本地模块
from device_manager import DeviceManager  # 导入设备管理器
import e_adb_png_path

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

def after_buy():
    time.sleep(3)
    adb_command_basic("shell input tap 1851 1145") # 点制式卷
    time.sleep(1)
    adb_command_basic("shell input tap 1600 1145") # 点使用
    time.sleep(1)
    adb_command_basic("shell input tap 2680 1050") # 点取消制式卷的x
    print("正在卸下装备")
    time.sleep(1)
    adb_command_basic("shell input tap 2555 1145") # 点右下角确认
    time.sleep(1)
    adb_command_basic("shell input tap 1402 939") # 点提示的确认
    time.sleep(1)
    print("已打开准备好的主界面") # 准备进行卡邮件的固定操作
    adb_command_basic("shell input tap 222 1150") # 点仓库
    time.sleep(1)
    adb_command_basic("shell input tap 946 1150") # 点全部转移
    time.sleep(1)
    adb_command_basic("shell input keyevent 4") # 返回
    time.sleep(1)

def begin():
    adb_command_basic("shell input tap 2392 1138")# 点开始匹配
    time.sleep(15.0)
    adb_command_basic("shell am force-stop com.tencent.tmgp.dfm")
    time.sleep(0.5)
    adb_command_basic("shell monkey -p com.tencent.tmgp.dfm -c android.intent.category.LAUNCHER 1")
    time.sleep(25) # 等待三角洲启动
    while True:
        time.sleep(0.2)
        ru = e_adb_png_path.p(r"C:\Users\Administrator\Desktop\PY\tp\kai_1.jpg")
        time.sleep(0.2)
        kaishi = e_adb_png_path.p(r"C:\Users\Administrator\Desktop\PY\tp\kai_2.jpg")
        if ru or kaishi:
            return ru, kaishi



def ru_run_1 ():
    adb_command_basic("shell svc wifi disable")
    print("关闭了WiFi")
    adb_command_basic("shell input tap 1731 872") # 点重新连接
    time.sleep(0.5)
    adb_command_basic("shell input tap 2555 1145") # 打开烽火主页面
    time.sleep(0.5)
    adb_command_basic("shell input tap 2580 81") # 点掉广告
    time.sleep(0.5)
    adb_command_basic("shell input keyevent 4")
    time.sleep(0.4)
    adb_command_basic("shell input tap 1170 855")  # 点取消重连
    time.sleep(0.1)
    adb_command_basic("shell input tap 2392 1138") # 点备战
    time.sleep(5)
    adb_command_basic("shell input tap 1700 860") # 点确认重连
    time.sleep(0.2)
    adb_command_basic("shell input tap 1132 315") # 选择大坝
    time.sleep(1.0)
    adb_command_basic("shell input tap 2408 975") # 开始
    time.sleep(0.5)
    adb_command_basic("shell input tap 2555 1145")  # 点右下角确认
    time.sleep(1)
    adb_command_basic("shell input tap 1402 939")  # 点提示的确认
    time.sleep(3)
    adb_command_basic("shell input tap 1700 860") # 点确认重连

    # 之后运行ka_choose的模块

def kaishi ():
    adb_command_basic("shell input tap 2392 1138") # 点备战
    time.sleep(1)
    adb_command_basic("shell input tap 1132 315") # 选择大坝
    time.sleep(1)
    adb_command_basic("shell input tap 2408 975") # 开始
    time.sleep(1)
    adb_command_basic("shell input tap 1978 1141") # 点方案
    time.sleep(0.5)



def ru_run_2():
    time.sleep(1)
    adb_command_basic("shell svc wifi enable")  ##开WiFi
    print("已经开启WiFi")
    time.sleep(10.0)
    adb_command_basic("shell input tap 1700 860") # 点确认重连
    time.sleep(0.3)
    adb_command_basic("shell input swipe 2500 1150 2500 1150 5000")##长按方案的操作
    time.sleep(5)
    adb_command_basic("shell input tap 1170 855")  # 点取消重连
    time.sleep(1)
    adb_command_basic("shell input tap 1170 855")  # 点取消重连
    time.sleep(15.0)
    adb_command_basic("shell input tap 2580 81")  # 点掉广告，新赛季增加的步骤
    time.sleep(1.5)
    adb_command_basic("shell input tap 1320 970") # 点掉通行证
    time.sleep(1.5)
    adb_command_basic("shell input tap 1320 970") # 点掉3x3提示
    time.sleep(3)
    adb_command_basic("shell input tap 2564 49")  # 点开邮件
    time.sleep(1.5)
    adb_command_basic("shell input tap 180 180")  # 点开系统的页面，而不是停在交易行零哈弗币的页面
    time.sleep(1.5)
    if e_adb_png_path.p(r"C:\Users\Administrator\Desktop\PY\tp\yji.jpg"):
        # 这用来确实是否在邮件界面了，没有则不执行

        if e_adb_png_path.p(r"C:\Users\Administrator\Desktop\PY\tp\kt.jpg"):
            print("卡邮件成功了")
            ka_rt = True
            adb_command_basic("shell input tap 2667 1058")  # 点部分领取
            time.sleep(1)
            adb_command_basic("shell input tap 1117 1141")  # 勾选包和胸挂
            time.sleep(0.8)
            adb_command_basic("shell input tap 1298 1141")  # 勾选包和胸挂
            time.sleep(0.8)
            adb_command_basic("shell input tap 2555 1145")  # 点领取
            time.sleep(2)
            adb_command_basic("shell input tap 100 100")  # 点返回
        elif e_adb_png_path.p(r"C:\Users\Administrator\Desktop\PY\tp\kf.jpg"):
            print("看起来没有卡成功")
            ka_rt = False
        else:
            print("没有识别到图片，包应该是在最后两个")
            adb_command_basic("shell input tap 2667 1058")  ##点部分领取
            time.sleep(1)
            # 滑倒最右边
            adb_command_basic('shell input swipe 1700 1141 1147 1141 100')
            time.sleep(1)
            adb_command_basic('shell input swipe 1700 1141 1147 1141 100')
            time.sleep(1)
            adb_command_basic('shell input swipe 1700 1141 1147 1141 100')
            time.sleep(1)
            adb_command_basic('shell input swipe 1700 1141 1147 1141 100')

            adb_command_basic("shell input tap 1945 1141")  # 勾选包和胸挂_2
            time.sleep(0.8)
            adb_command_basic("shell input tap 2088 1141")  # 勾选包和胸挂_2
            time.sleep(0.8)
            adb_command_basic("shell input tap 2555 1145")  # 点领取
            time.sleep(2)
            adb_command_basic("shell input tap 100 100")  # 点返回
            ka_rt = True
        time.sleep(2)
        adb_command_basic("shell input tap 100 100")  # 点返回
        time.sleep(1)
        adb_command_basic("shell input tap 1450 870")  # 点掉跳出的丢失装备提示
        time.sleep(1)
        print("回到了主界面")
        return ka_rt
    return "dk"

def fin():
    time.sleep(1)
    adb_command_basic("shell input tap 2392 1138")  ##点备战
    # time.sleep(1)
    # adb_command_basic("shell input tap 1132 315")  ##选择大坝
    # 省去选择地图的步骤
    time.sleep(1)
    adb_command_basic("shell input tap 2408 975")  ##开始
    time.sleep(1)
    adb_command_basic("shell input tap 1978 1141")  # 点方案
    time.sleep(0.5)


