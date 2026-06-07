import e_adb_png_path
import sale

import time

def check_get_you():
    if  e_adb_png_path.p(r"D:\Desktop\PY\tp"):
        print("成功领出")
        # 前往出售
    else:
        print("没能领出，仓库空间不够了")

def check_sale_finish():
    if e_adb_png_path.p(r"D:\Desktop\PY\tp\jy.jpg"): # 用来确认再出售界面
       sale.frist()
       check = e_adb_png_path.p(r"D:\Desktop\PY\tp\sale.jpg")
       while check: # 等待子弹卖出
            check = e_adb_png_path.p(r"D:\Desktop\PY\tp\sale.jpg")
            print("已经出卖掉了，可以接着卖")
       sale.second()