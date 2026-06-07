import os
import cv2
import numpy as np
import easyocr
from functools import lru_cache
import re

import e_adb_png_path

# 初始化EasyOCR
print("正在初始化EasyOCR（e_jiage）...")
ocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
print("EasyOCR初始化完成（e_jiage）！")

# 全局变量
price = 100000000000


def fast_ocr_simple(image_path):
    """
    极速OCR识别（使用EasyOCR）- 与mian.py保持一致
    """
    # 读取图片（支持中文路径）
    img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        print(f"无法读取图片: {image_path}")
        return ""
    
    # 直接使用EasyOCR识别（不做复杂预处理，与mian.py一致）
    result = ocr_reader.readtext(img)
    
    if not result or len(result) == 0:
        print("EasyOCR未识别到任何文本")
        return ""
    
    # 合并所有识别到的文本
    all_texts = []
    for detection in result:
        bbox, text, confidence = detection
        all_texts.append(text)
    
    combined_text = ''.join(all_texts)
    print(f"EasyOCR识别结果: '{combined_text}'")
    
    # 清理识别结果，只保留数字和逗号
    cleaned_result = ''.join([c for c in combined_text if c.isdigit() or c == ','])
    # 移除前面多余的逗号
    cleaned_result = cleaned_result.lstrip(',')
    print(f"清理后的结果: '{cleaned_result}'")

    return cleaned_result


def get_jiage_price_ocr():
    e_adb_png_path.capture_screen_region(1316, 648, 1590, 703)

    image_path = "button.png"
    result = fast_ocr_simple(image_path)
    global price

    if result is None or result == "":
        price = 100000000000000
        print("未能识别到结果:", price)
        return price

    digits = re.findall(r'\d', result)

    if digits:
        price_str = ''.join(digits)
        
        # 与mian.py一致的8改0逻辑
        if price_str and price_str[-1] == '8':
            price_str = price_str[:-1] + '0'
            print("最后一位8改为0:", price_str)
        
        if len(price_str) < 6:
            price = 100000000000000
            print("识别结果小于6位数，改为默认值:", price)
        else:
            price = int(price_str)
            print("识别结果:", price)
    else:
        price = 100000000000000
        print("未能识别到数字:", price)
    
    if os.path.exists(image_path):
        try:
            os.remove(image_path)
        except:
            pass

    return price


def test_ocr_123png():
    """
    测试方法：使用e_jiage中的OCR识别123.png中的内容
    """
    image_path = "123.png"

    if not os.path.exists(image_path):
        print(f"文件 {image_path} 不存在")
        return ""

    result = fast_ocr_simple(image_path)
    print(f"123.png识别结果: {result}")

    # 尝试提取数字
    digits = re.findall(r'\d', result)
    if digits:
        price_str = ''.join(digits)
        # 检查最后一位是否为8，如果是则修改为0
        if price_str and price_str[-1] == '8':
            price_str = price_str[:-1] + '0'
            print(f"修改最后一位8为0: {price_str}")
        # 检查是否为6位数，如果是则改为默认值
        if len(price_str) == 6:
            price = 100000000000000
            print(f"识别结果为6位数，改为默认值: {price}")
        else:
            price = int(price_str)
            print(f"提取的数字: {price}")

    return result

if __name__ == "__main__":
    test_ocr_123png()