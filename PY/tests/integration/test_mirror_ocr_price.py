"""在线投屏 OCR 价格识别集成测试。

测试目标：验证在后投屏（scrcpy 模式）下，OCR 能否正确识别游戏中的价格数字。

前置条件：
    1. ADB 已安装且设备已连接（adb devices 能看到设备）
    2. 设备上已安装 scrcpy-server（lib/scrcpy-server.jar）
    3. 游戏《三角洲行动》已打开，且当前画面显示有价格的界面
    4. config.json 中 ocr_regions.price_region 已配置为正确的坐标
       （可用 UI 的坐标选择器标定，或在脚本中手动指定）

运行方式：
    cd PY
    python tests/integration/test_mirror_ocr_price.py

    或带参数指定设备：
    python tests/integration/test_mirror_ocr_price.py --serial emulator-5554
    python tests/integration/test_mirror_ocr_price.py --serial <device> --gpu --save-screenshot
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# 确保 PY 目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

# ===========================================================================
#  日志配置
# ===========================================================================
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mirror-ocr-test")

# ===========================================================================
#  测试参数
# ===========================================================================
# 等待投屏帧稳定的时间（秒）
FRAME_WARMUP_SECONDS = 3.0
# 采集多少帧进行测试
TEST_FRAME_COUNT = 5
# 帧间隔（秒）
FRAME_INTERVAL = 0.5
# OCR 价格区域（从 config.json 读取；亦可在此覆盖）
PRICE_REGION_OVERRIDE: dict | None = None  # 例如 {"left": 1316, "top": 648, "right": 1590, "bottom": 703}


def check_adb_device(serial: str | None = None) -> str | None:
    """检查 ADB 连接和设备状态。返回设备序列号，失败返回 None。"""
    import subprocess

    # 检查 adb 是否可用
    try:
        result = subprocess.run(
            ["adb", "version"], capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            logger.error("ADB 不可用，请确认已安装并加入 PATH")
            return None
        logger.info("ADB 版本: %s", result.stdout.strip().split("\n")[0])
    except FileNotFoundError:
        logger.error("未找到 adb 命令，请安装 Android SDK Platform Tools")
        return None
    except Exception as e:
        logger.error("检查 ADB 版本失败: %s", e)
        return None

    # 列出设备
    try:
        result = subprocess.run(
            ["adb", "devices", "-l"], capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split("\n")[1:]  # 跳过 "List of devices attached"
        devices = [line.split()[0] for line in lines if line.strip() and "device" in line]
        if not devices:
            logger.error("未检测到已连接的设备。请确认 USB 调试已开启且授权。")
            return None
        logger.info("已连接设备: %s", devices)
    except Exception as e:
        logger.error("列出设备失败: %s", e)
        return None

    # 如果指定了 serial，验证设备存在
    if serial:
        if serial not in devices:
            logger.error("指定设备 %s 不在已连接列表中: %s", serial, devices)
            return None
        return serial

    # 自动选择第一个设备
    return devices[0]


def get_price_region() -> dict | None:
    """从 config.json 读取 price_region。"""
    if PRICE_REGION_OVERRIDE:
        logger.info("使用手动指定的 price_region: %s", PRICE_REGION_OVERRIDE)
        return PRICE_REGION_OVERRIDE

    config_path = PROJECT_ROOT / "config" / "config.json"
    if not config_path.exists():
        logger.warning("config.json 不存在: %s", config_path)
        return None

    import json
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    region = config.get("ocr_regions", {}).get("price_region", {})
    # 检查是否为全零（未配置）
    if region and all(v == 0 for v in region.values()):
        logger.warning("price_region 全为零（未配置），请先用坐标选择器标定价格区域")
        logger.warning("  可使用 tools/roi_selector.py 或 UI 中的坐标选择器")
        return None

    logger.info("从 config.json 读取 price_region: %s", region)
    return region


def test_ocr_on_captured_frames(
    serial: str,
    gpu: bool = False,
    save_screenshot: bool = False,
) -> bool:
    """核心测试：启动投屏采集 → 初始化 OCR → 识别价格。

    Returns:
        True 如果所有帧都成功识别到有效价格，否则 False。
    """
    from PyQt5.QtCore import QTimer

    # ---- 导入所需模块 ----
    from core.ocr_engine import initialize as ocr_init, recognize_price, is_initialized
    from core.screen_capture import ScrcpyCapture
    from core.config_manager import ConfigManager

    # ---- 初始化 QApplication（ScrcpyCapture 需要事件循环） ----
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # ---- 读取价格区域 ----
    price_region = get_price_region()
    if price_region is None:
        logger.warning("未配置 price_region，将使用整帧进行 OCR（可能不准）")

    # ---- 初始化 OCR ----
    logger.info("正在初始化 OCR 引擎 (gpu=%s)...", gpu)
    ocr_ok = ocr_init(gpu=gpu)
    if not ocr_ok:
        logger.error("OCR 初始化失败！无法继续测试")
        return False
    logger.info("OCR 引擎初始化完成")

    # ---- 启动投屏采集 ----
    logger.info("正在启动 scrcpy 投屏采集 (serial=%s)...", serial)
    capture = ScrcpyCapture()
    capture.start(serial=serial)

    # 等待首帧
    logger.info("等待投屏帧稳定（%s 秒）...", FRAME_WARMUP_SECONDS)
    warmup_elapsed = 0
    while warmup_elapsed < FRAME_WARMUP_SECONDS:
        app.processEvents()
        time.sleep(0.1)
        warmup_elapsed += 0.1
        frame = capture.get_current_frame()
        if frame is not None:
            logger.info("  已收到首帧 (shape=%s), 继续等待稳定...", frame.shape)
            break
    else:
        logger.warning("  预热期内未收到帧，继续尝试...")

    # ---- 采集多帧进行 OCR 测试 ----
    logger.info("=" * 60)
    logger.info("开始 OCR 价格识别测试（采集 %d 帧，间隔 %.1fs）", TEST_FRAME_COUNT, FRAME_INTERVAL)
    logger.info("=" * 60)

    success_count = 0
    results = []

    for i in range(TEST_FRAME_COUNT):
        # 等待新帧
        app.processEvents()
        time.sleep(FRAME_INTERVAL)

        frame = capture.get_current_frame()
        if frame is None:
            logger.error("  [%d/%d] 获取帧失败 — 投屏可能已断开", i + 1, TEST_FRAME_COUNT)
            results.append((i + 1, None, "获取帧失败"))
            continue

        logger.info("  [%d/%d] 帧 shape=%s, dtype=%s", i + 1, TEST_FRAME_COUNT, frame.shape, frame.dtype)

        # 保存截图（用于离线复查）
        if save_screenshot or i == 0:
            screenshot_dir = PROJECT_ROOT / "tests" / "integration" / "screenshots"
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            screenshot_path = screenshot_dir / f"frame_{i + 1:02d}.png"
            cv2.imwrite(str(screenshot_path), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            logger.info("    截图已保存: %s", screenshot_path)

        # 执行 OCR 价格识别
        raw_price = recognize_price(frame, price_region)
        logger.info("    识别结果: %d", raw_price)

        # 判断结果
        if raw_price == 100_000_000_000_000:
            logger.warning("    → 哨兵值（价格过短或 OCR 未初始化），可能价格区域不对或画面无价格")
            results.append((i + 1, raw_price, "哨兵值"))
        elif raw_price > 1_000_000_000:
            logger.warning("    → 价格异常（>10亿），可能识别错误")
            results.append((i + 1, raw_price, "异常大值"))
        else:
            logger.info("    → 有效价格: %d", raw_price)
            results.append((i + 1, raw_price, "有效"))
            success_count += 1

    # ---- 清理 ----
    logger.info("停止投屏采集...")
    capture.stop()
    app.processEvents()

    # ---- 汇总 ----
    logger.info("=" * 60)
    logger.info("测试结果汇总:")
    logger.info("  总帧数: %d", TEST_FRAME_COUNT)
    logger.info("  识别成功: %d", success_count)
    logger.info("  成功率: %.0f%%", success_count / TEST_FRAME_COUNT * 100)
    logger.info("  详细结果:")
    for idx, price, status in results:
        status_icon = "✅" if status == "有效" else "❌"
        logger.info("    帧%d: %s %d (%s)", idx, status_icon, price, status)
    logger.info("=" * 60)

    if success_count == 0:
        logger.error("❌ 所有帧均未识别到有效价格！")
        logger.error("   请检查：")
        logger.error("   1. 游戏是否在价格显示界面")
        logger.error("   2. price_region 坐标是否正确（当前: %s）", price_region)
        logger.error("   3. 投屏分辨率是否与坐标匹配")
        logger.error("   4. 查看上方 raw result 日志判断 OCR 读到什么")
        return False

    if success_count < TEST_FRAME_COUNT:
        logger.warning("⚠️ 部分帧识别失败，请检查上方日志")
        return False

    logger.info("✅ 所有帧 OCR 价格识别成功！后投屏 OCR 管线工作正常。")
    return True


def main():
    global TEST_FRAME_COUNT, FRAME_INTERVAL, PRICE_REGION_OVERRIDE

    _frames_default = TEST_FRAME_COUNT
    _interval_default = FRAME_INTERVAL

    parser = argparse.ArgumentParser(
        description="在线投屏 OCR 价格识别集成测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python tests/integration/test_mirror_ocr_price.py
  python tests/integration/test_mirror_ocr_price.py --serial emulator-5554
  python tests/integration/test_mirror_ocr_price.py --gpu --save-screenshot
  python tests/integration/test_mirror_ocr_price.py --frames 10 --interval 1.0
        """,
    )
    parser.add_argument("--serial", type=str, default=None, help="设备序列号（默认自动选择）")
    parser.add_argument("--gpu", action="store_true", help="使用 GPU 加速 OCR")
    parser.add_argument("--save-screenshot", action="store_true", help="保存所有测试帧截图")
    parser.add_argument("--frames", type=int, default=_frames_default, help=f"测试帧数（默认 {_frames_default}）")
    parser.add_argument("--interval", type=float, default=_interval_default, help=f"帧间隔秒数（默认 {_interval_default}）")
    parser.add_argument(
        "--region",
        type=str,
        default=None,
        help='手动指定价格区域，格式: "left,top,right,bottom"（如 "1316,648,1590,703"）',
    )
    args = parser.parse_args()

    # 更新全局参数
    TEST_FRAME_COUNT = args.frames
    FRAME_INTERVAL = args.interval
    if args.region:
        parts = args.region.split(",")
        if len(parts) != 4:
            logger.error("--region 格式错误，应为: left,top,right,bottom")
            sys.exit(1)
        PRICE_REGION_OVERRIDE = {
            "left": int(parts[0]),
            "top": int(parts[1]),
            "right": int(parts[2]),
            "bottom": int(parts[3]),
        }

    logger.info("=" * 60)
    logger.info("在线投屏 OCR 价格识别集成测试")
    logger.info("=" * 60)
    logger.info("测试参数: frames=%d, interval=%.1fs, gpu=%s, save=%s",
                TEST_FRAME_COUNT, FRAME_INTERVAL, args.gpu, args.save_screenshot)

    # ---- 第1步：检查 ADB 和设备 ----
    logger.info("--- 第1步：检查 ADB 和设备连接 ---")
    device_serial = check_adb_device(args.serial)
    if device_serial is None:
        logger.error("设备检查失败，测试终止")
        sys.exit(1)
    logger.info("使用设备: %s", device_serial)

    # ---- 第2步：运行投屏 OCR 测试 ----
    logger.info("--- 第2步：启动投屏 OCR 测试 ---")
    ok = test_ocr_on_captured_frames(
        serial=device_serial,
        gpu=args.gpu,
        save_screenshot=args.save_screenshot,
    )

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
