import subprocess
import threading
import time


def adb_command_basic(command):
    full_command = f"adb {command}"
    subprocess.run(full_command, shell=True, check=True)


def adb_cs_basic():
    for i in range(1500):

        adb_command_basic("shell input tap 2335 685") # 加号位置


def adb_liandian():
    # 每次调用时创建新线程
    t1 = threading.Thread(target=adb_cs_basic)
    t2 = threading.Thread(target=adb_cs_basic)

    # 启动新线程
    t1.start()
    t2.start()


    # 等待所有线程完成
    t1.join()
    t2.join()


    print("正常运行连点器")

