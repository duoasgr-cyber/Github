import pygetwindow as gw
import win32gui
import win32con
import time
import ctypes


def force_activate_window(window_title, retry=3):
    """
    强制激活窗口的最终方案
    """
    for attempt in range(retry):
        try:
            # 1. 先找到所有可能的窗口
            all_windows = gw.getAllWindows()
            target_windows = []

            for win in all_windows:
                if window_title.lower() in win.title.lower():
                    target_windows.append(win)

            if not target_windows:
                print(f"未找到包含 '{window_title}' 的窗口")
                time.sleep(0.5)
                continue

            # 2. 对每个匹配的窗口尝试激活
            for win in target_windows:
                try:
                    # 如果窗口最小化，先恢复
                    if win.isMinimized:
                        win.restore()

                    # 尝试通过系统API强制激活
                    hwnd = win32gui.FindWindow(None, win.title)
                    if hwnd:
                        # 尝试用更底层的方法
                        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        win32gui.BringWindowToTop(hwnd)
                        win32gui.SetWindowPos(
                            hwnd,
                            win32con.HWND_TOPMOST,
                            0, 0, 0, 0,
                            win32con.SWP_NOSIZE | win32con.SWP_NOMOVE
                        )
                        time.sleep(0.05)
                        win32gui.SetWindowPos(
                            hwnd,
                            win32con.HWND_NOTOPMOST,
                            0, 0, 0, 0,
                            win32con.SWP_NOSIZE | win32con.SWP_NOMOVE
                        )
                        time.sleep(0.05)
                        win32gui.SetForegroundWindow(hwnd)
                        time.sleep(0.1)
                        ctypes.windll.user32.SwitchToThisWindow(hwnd, True)

                    # 3. 用pygetwindow再次尝试
                    time.sleep(0.1)
                    win.activate()
                    time.sleep(0.1)
                    win.activate()  # 再次确认

                    print(f"成功激活窗口: {win.title}")
                    return True

                except Exception as e:
                    print(f"激活窗口时出错: {e}")
                    continue

        except Exception as e:
            print(f"第{attempt + 1}次尝试失败: {e}")
            time.sleep(0.5)

    print("所有尝试都失败了")
    return False


force_activate_window("Mirr")
