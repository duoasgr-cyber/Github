import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

filepath = r'D:\Github\PY\core\screen_capture.py'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixes = {
    79: '                    logger.info("scrcpy\u8fde\u63a5\u6210\u529f: %s", device_serial)\n',
    82: '                logger.error("scrcpy\u8fde\u63a5\u5931\u8d25 (%d/%d): %s", attempt, max_retries, e)\n',
    89: '        logger.warning("scrcpy\u8fde\u63a5\u5931\u8d25\uff0c\u5207\u6362\u5230screencap\u56de\u9000\u6a21\u5f0f: %s", device_serial)\n',
    264: '                    logger.warning("\u5f02\u5e38\u5305\u5927\u5c0f: %d, \u8df3\u8fc7", packet_size)\n',
    279: '                logger.error("socket\u8bfb\u53d6\u7ebf\u7a0b\u5f02\u5e38 [gen=%d]: %s", gen, e)\n',
    281: '            logger.debug("socket\u8bfb\u53d6\u7ebf\u7a0b\u7ed3\u675f [gen=%d]", gen)\n',
    291: '        logger.debug("\u5e27\u89e3\u7801\u7ebf\u7a0b\u542f\u52a8 [gen=%d]", gen)\n',
    334: '                logger.error("\u5e27\u89e3\u7801\u7ebf\u7a0b\u5f02\u5e38 [gen=%d]: %s", gen, e)\n',
    336: '            logger.debug("\u5e27\u89e3\u7801\u7ebf\u7a0b\u7ed3\u675f [gen=%d]", gen)\n',
    356: '                logger.error("screencap\u56de\u9000\u6a21\u5f0f\u51fa\u9519: %s", e)\n',
    362: '        logger.info("screencap\u56de\u9000\u6a21\u5f0f\u7ed3\u675f")\n',
    381: '            logger.error("screencap\u5931\u8d25: %s", e)\n',
}

changed = 0
for idx, replacement in fixes.items():
    if idx < len(lines):
        lines[idx] = replacement
        changed += 1

print("Changed " + str(changed) + " lines")

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Saved")
