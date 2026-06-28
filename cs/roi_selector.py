import win32gui, win32ui, win32con
import numpy as np
import cv2

TARGET_KEYWORD = "Escrcpy"

def get_hwnd_by_keyword(keyword):
    result = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if keyword in title:
                result.append(hwnd)
        return True
    win32gui.EnumWindows(callback, None)
    return result[0] if result else None

def capture_window(hwnd):
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    w, h = right - left, bottom - top
    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
    saveDC.SelectObject(saveBitMap)
    result = saveDC.BitBlt((0, 0), (w, h), mfcDC, (0, 0), win32con.SRCCOPY)
    bmpinfo = saveBitMap.GetInfo()
    bmpstr = saveBitMap.GetBitmapBits(True)
    img = np.frombuffer(bmpstr, dtype=np.uint8).reshape((bmpinfo["bmHeight"], bmpinfo["bmWidth"], 4))
    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)
    return img

def click_event(event, x, y, flags, points):
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))

if __name__ == "__main__":
    hwnd = get_hwnd_by_keyword(TARGET_KEYWORD)
    if not hwnd:
        print("未找到目标窗口")
        raise SystemExit

    frame = capture_window(hwnd)
    cv2.imwrite("window_capture.png", frame)
    print("已保存窗口截图: window_capture.png")

    points = []
    cv2.namedWindow("Select ROI", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("Select ROI", click_event, points)

    while True:
        temp = frame.copy()
        for p in points:
            cv2.circle(temp, p, 5, (0, 0, 255), -1)
        if len(points) == 2:
            x1, y1 = points[0]
            x2, y2 = points[1]
            x, y = min(x1, x2), min(y1, y2)
            w, h = abs(x2 - x1), abs(y2 - y1)
            cv2.rectangle(temp, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.imshow("Select ROI", temp)
        if cv2.waitKey(1) & 0xFF == 27:
            break
        if len(points) >= 2 and cv2.waitKey(1) & 0xFF == 13:
            break

    if len(points) == 2:
        x1, y1 = points[0]
        x2, y2 = points[1]
        x, y = min(x1, x2), min(y1, y2)
        w, h = abs(x2 - x1), abs(y2 - y1)
        roi = (x, y, w, h)
        roi_img = frame[y:y+h, x:x+w]
        cv2.imwrite("roi_sample.png", roi_img)
        print("你的 ROI 坐标是：", roi)
    else:
        print("未完成 ROI 选择")