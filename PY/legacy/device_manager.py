# device_manager.py
import subprocess

class DeviceManager:
    _current_device = None  # 类变量，存储当前选择的设备序列号

    @classmethod
    def get_device_list(cls):
        """获取已连接的ADB设备列表，返回序列号列表"""
        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"执行 'adb devices' 失败: {e}")
            return []

        lines = result.stdout.strip().split('\n')
        devices = []
        for line in lines[1:]:  # 跳过第一行标题 'List of devices attached'
            parts = line.strip().split('\t')
            if len(parts) == 2 and parts[1] == 'device':  # 只筛选出已授权的设备
                devices.append(parts[0])
        return devices

    @classmethod
    def select_and_set_device(cls):
        """交互式选择设备，并设置为当前设备。返回设备序列号。"""
        devices = cls.get_device_list()

        if not devices:
            print("错误: 未找到任何已连接的ADB设备。请确保设备已连接并授权。")
            return None

        if len(devices) == 1:
            cls._current_device = devices[0]
            print(f"已自动选择唯一设备: {cls._current_device}")
            return cls._current_device

        # 多台设备，让用户选择
        print("\n检测到多台ADB设备:")
        for idx, device in enumerate(devices):
            print(f"  [{idx}] {device}")

        while True:
            try:
                choice = input(f"请选择设备编号 (0-{len(devices)-1}): ").strip()
                choice_idx = int(choice)
                if 0 <= choice_idx < len(devices):
                    cls._current_device = devices[choice_idx]
                    print(f"已选择设备: {cls._current_device}")
                    return cls._current_device
                else:
                    print("编号超出范围，请重新输入。")
            except ValueError:
                print("输入无效，请输入数字编号。")

    @classmethod
    def get_current_device(cls):
        """获取当前已选定的设备序列号。如果未选择，则返回None。"""
        return cls._current_device

    @classmethod
    def set_current_device(cls, device_serial):
        """手动设置当前设备（可用于脚本或测试）。"""
        cls._current_device = device_serial