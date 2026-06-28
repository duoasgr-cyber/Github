"""Scrcpy 性能基准测试套件（scrcpy 4.0 迁移验证）。

用法:
    python tests/test_performance_benchmark.py --output report.json
    python tests/test_performance_benchmark.py --compare baseline.json

用于验证 scrcpy 4.0 迁移后的性能指标是否满足要求。
"""

import json
import os
import statistics
import sys
import time
import unittest
from dataclasses import dataclass, field
from typing import List, Optional

# 项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@dataclass
class PerformanceMetrics:
    """性能指标数据类。"""
    test_duration_sec: float = 0.0
    total_frames: int = 0
    first_frame_time_ms: float = 0.0
    frame_intervals_ms: List[float] = field(default_factory=list)
    cpu_samples: List[float] = field(default_factory=list)
    memory_mb_samples: List[float] = field(default_factory=list)

    @property
    def avg_fps(self) -> float:
        if self.test_duration_sec == 0:
            return 0.0
        return self.total_frames / self.test_duration_sec

    @property
    def p99_frame_interval_ms(self) -> float:
        if not self.frame_intervals_ms:
            return 0.0
        sorted_intervals = sorted(self.frame_intervals_ms)
        idx = int(len(sorted_intervals) * 0.99)
        return sorted_intervals[min(idx, len(sorted_intervals) - 1)]

    @property
    def avg_cpu_pct(self) -> float:
        return statistics.mean(self.cpu_samples) if self.cpu_samples else 0.0

    @property
    def peak_memory_mb(self) -> float:
        return max(self.memory_mb_samples) if self.memory_mb_samples else 0.0

    def to_dict(self) -> dict:
        return {
            'test_duration_sec': round(self.test_duration_sec, 2),
            'total_frames': self.total_frames,
            'first_frame_time_ms': round(self.first_frame_time_ms, 2),
            'avg_fps': round(self.avg_fps, 2),
            'p99_frame_interval_ms': round(self.p99_frame_interval_ms, 2),
            'avg_cpu_pct': round(self.avg_cpu_pct, 2),
            'peak_memory_mb': round(self.peak_memory_mb, 2),
        }


def run_benchmark(
    serial: str = "",
    duration_sec: int = 60,
    output_file: Optional[str] = None,
) -> PerformanceMetrics:
    """运行性能基准测试。

    Args:
        serial: 设备序列号（空则使用默认设备）
        duration_sec: 测试持续时间（秒）
        output_file: 结果输出文件路径（JSON 格式）

    Returns:
        性能指标对象
    """
    from core.screen_capture import ScrcpyCapture

    metrics = PerformanceMetrics()

    # 尝试导入 psutil 用于资源监控（可选）
    try:
        import psutil
        process = psutil.Process()
        has_psutil = True
    except ImportError:
        has_psutil = False

    capture = ScrcpyCapture()
    start_time = time.monotonic()
    capture.start(serial=serial)

    last_version = -1
    sample_interval = 1.0  # 每秒采样一次系统资源
    last_sample_time = start_time
    last_frame_time = start_time

    try:
        while time.monotonic() - start_time < duration_sec:
            result = capture.get_current_frame_if_new(last_version)
            if result:
                frame, new_version = result
                last_version = new_version
                metrics.total_frames += 1
                now = time.monotonic()
                if metrics.first_frame_time_ms == 0:
                    metrics.first_frame_time_ms = (now - start_time) * 1000
                # 记录帧间隔
                interval_ms = (now - last_frame_time) * 1000
                metrics.frame_intervals_ms.append(interval_ms)
                last_frame_time = now

            # 系统资源采样（可选）
            if has_psutil and (time.monotonic() - last_sample_time >= sample_interval):
                try:
                    metrics.cpu_samples.append(process.cpu_percent())
                    metrics.memory_mb.append(process.memory_info().rss / 1024 / 1024)
                except Exception:
                    pass
                last_sample_time = time.monotonic()

            time.sleep(0.001)  # 避免 busy-wait

    finally:
        metrics.test_duration_sec = time.monotonic() - start_time
        capture.stop()

    # 输出结果
    print("\n" + "=" * 60)
    print("Scrcpy 性能基准测试结果")
    print("=" * 60)
    for key, value in metrics.to_dict().items():
        print(f"  {key}: {value}")

    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(metrics.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"\n性能报告已保存至: {output_file}")

    return metrics


def compare_with_baseline(
    current: PerformanceMetrics,
    baseline_path: str,
) -> dict:
    """与基线数据对比，生成差异报告。

    Args:
        current: 当前测试指标
        baseline_path: 基线 JSON 文件路径

    Returns:
        差异报告字典
    """
    with open(baseline_path, 'r', encoding='utf-8') as f:
        baseline = json.load(f)

    report = {
        'metrics': {},
        'summary': {'passed': 0, 'failed': 0, 'warnings': 0},
    }

    thresholds = {
        'first_frame_time_ms': ('<=', 1.1),   # 不超过基线的 110%
        'avg_fps': ('>=', 0.9),               # 不低于基线的 90%
        'p99_frame_interval_ms': ('<=', 1.1),
        'avg_cpu_pct': ('<=', 1.1),
        'peak_memory_mb': ('<=', 1.15),
    }

    for key, (op, threshold) in thresholds.items():
        current_val = getattr(current, key)
        baseline_val = baseline.get(key, 0)

        if baseline_val == 0 or baseline_val is None:
            continue

        ratio = current_val / baseline_val
        passed = False

        if op == '<=':
            passed = ratio <= threshold
        elif op == '>=':
            passed = ratio >= threshold

        status = 'PASS' if passed else ('WARN' if ratio < threshold * 1.2 else 'FAIL')
        if status == 'PASS':
            report['summary']['passed'] += 1
        elif status == 'WARN':
            report['summary']['warnings'] += 1
        else:
            report['summary']['failed'] += 1

        report['metrics'][key] = {
            'baseline': round(baseline_val, 2),
            'current': round(current_val, 2),
            'ratio': round(ratio, 3),
            'status': status,
        }

    return report


class TestScrcpy4VersionDetection(unittest.TestCase):
    """scrcpy 4.0 版本检测单元测试。"""

    def test_parse_major_version_v4(self):
        """_parse_major_version 应正确解析 4.x 版本号。"""
        from core.screen_capture import _parse_major_version
        self.assertEqual(_parse_major_version("4.0.0"), 4)
        self.assertEqual(_parse_major_version("4.1.2"), 4)

    def test_parse_major_version_v3(self):
        """_parse_major_version 应正确解析 3.x 版本号（向后兼容）。"""
        from core.screen_capture import _parse_major_version
        self.assertEqual(_parse_major_version("3.3.4"), 3)
        self.assertEqual(_parse_major_version("3.0"), 3)

    def test_parse_major_version_invalid(self):
        """_parse_major_version 对无效输入应返回默认值 4。"""
        from core.screen_capture import _parse_major_version
        self.assertEqual(_parse_major_version(""), 4)
        self.assertEqual(_parse_major_version("abc"), 4)
        self.assertEqual(_parse_major_version("1.0"), 2)  # 最小支持 2.x


class TestVersionCompatibilityCheck(unittest.TestCase):
    """版本兼容性检查测试。"""

    def test_compatible_versions(self):
        """相邻主版本应通过兼容性检查。"""
        from core.screen_capture import ScrcpyCapture
        cap = ScrcpyCapture()
        self.assertTrue(cap._validate_version_compatibility("4.0.0", "3.3.4"))
        self.assertTrue(cap._validate_version_compatibility("3.3.4", "4.0.0"))

    def test_incompatible_versions(self):
        """版本差距过大应发出警告并返回 False。"""
        from core.screen_capture import ScrcpyCapture
        cap = ScrcpyCapture()
        # 使用 assertLogs 捕获警告日志
        with self.assertLogs('core.screen_capture', level='WARNING'):
            result = cap._validate_version_compatibility("4.0.0", "2.0")
        self.assertFalse(result)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrcpy 性能基准测试 (scrcpy 4.0)")
    parser.add_argument("--serial", default="", help="设备序列号")
    parser.add_argument("--duration", type=int, default=60, help="测试时长(秒)")
    parser.add_argument("--output", default="performance-report.json", help="输出文件")
    parser.add_argument("--compare", default=None, help="对比基线文件")
    parser.add_argument("--unit-tests", action="store_true", help="仅运行单元测试")

    args = parser.parse_args()

    if args.unit_tests:
        # 运行单元测试
        unittest.main(argv=[''], exit=True)
    else:
        # 运行性能基准测试
        metrics = run_benchmark(
            serial=args.serial,
            duration_sec=args.duration,
            output_file=args.output,
        )

        if args.compare:
            print("\n" + "-" * 60)
            print("与基线对比:")
            print("-" * 60)
            report = compare_with_baseline(metrics, args.compare)
            for key, data in report['metrics'].items():
                icon = "✅" if data['status'] == 'PASS' else ("⚠️" if data['status'] == 'WARN' else "❌")
                print(f"  {icon} {key}: {data['status']} "
                      f"(基线={data['baseline']}, 当前={data['current']}, 比值={data['ratio']})")

            summary = report['summary']
            print(f"\n汇总: ✅{summary['passed']} ⚠️{summary['warnings']} ❌{summary['failed']}")
