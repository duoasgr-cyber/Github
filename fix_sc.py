import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

filepath = r'D:\Github\PY\core\screen_capture.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

fixes = {
    72: '            logger.info("\u5c1d\u8bd5\u542f\u52a8scrcpy\u8fde\u63a5 (%d/%d): %s", attempt, max_retries, device_serial)',
    96: '        logger.info("\u505c\u6b62\u5c4f\u5e55\u6355\u83b7: %s", self._device_serial)',
    157: '            raise RuntimeError(f"scrcpy\u670d\u52a1\u542f\u52a8\u5931\u8d25: {stderr_output}")',
    178: '            raise RuntimeError("\u65e0\u6cd5\u8bfb\u53d6\u8bbe\u5907\u540d\u79f0\u957f\u5ea6")',
    183: '                logger.info("\u8bbe\u5907\u540d\u79f0: %s", device_name.decode(errors="replace"))',
    217: '            raise RuntimeError("ffmpeg\u672a\u627e\u5230\uff0c\u8bf7\u786e\u4fddfmpeg\u5df2\u5b89\u88c5\u5e76\u6dfb\u52a0\u5230PATH")',
    248: '        logger.debug("socket\u8bfb\u53d6\u7ebf\u7a0b\u542f\u52a8 [gen=%d]", gen)',
    343: '        logger.info("screencap\u56de\u9000\u6a21\u5f0f\u542f\u52a8")',
    400: '            logger.info("\u81ea\u52a8\u91cd\u8fde (%d/%d)", attempt, self._max_reconnect)',
    411: '                    logger.info("\u81ea\u52a8\u91cd\u8fde\u6210\u529f")',
    414: '                logger.error("\u81ea\u52a8\u91cd\u8fde\u5931\u8d25 (%d/%d): %s", attempt, self._max_reconnect, e)',
    416: '        logger.warning("\u81ea\u52a8\u91cd\u8fde\u5931\u8d25\uff0c\u5207\u6362\u5230screencap\u56de\u9000\u6a21\u5f0f")',
}

changed = 0
for idx, replacement in fixes.items():
    if idx < len(lines):
        lines[idx] = replacement
        changed += 1

print("Changed " + str(changed) + " lines in screen_capture.py")

new_content = '\n'.join(lines)
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Saved")
