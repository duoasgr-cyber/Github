import json
import time
import os
import subprocess
import cv2

# 本地模块

b = [455,131]
# 1. 读取数据
def du():
    try:
        with open('数据.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# 2. 保存数据
def bao(shu):
    with open('数据.json', 'w', encoding='utf-8') as f:
        json.dump(shu, f, ensure_ascii=False, indent=2)

def jt():
    adb_command_basic("adb shell screencap -p /sdcard/jt.png")
    adb_command_basic("adb pull /sdcard/jt.png")
    adb_command_basic("adb shell rm /sdcard/jt.png")
    print("截图成功，保存为jt.png，已可供调用")

def adb_command_basic(command):
    full_command = command
    subprocess.run(full_command, shell=True, check=True)

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
    print("a=")
    a = input()
    if os.path.exists("/sdcard/jt.png"):
        os.remove("/sdcard/jt.png")

    # 判断结果
    if similarity >= 0.5:
        print(f"相似度: {similarity:.0%}")
        print(f"   位置: ({location[0]}, {location[1]})")
        adb_click(location[0],location[1])
        return location[0],location[1]
    else:
        print(f"相似度: {similarity:.0%}")
        return False,False

def adb_click(x, y):
    """点击屏幕"""
    subprocess.run(f"adb shell input tap {x} {y}", shell=True)



