# =================================================
# @author: MorningXu (morningxu1991@163.com)
# @version v1.0.0
# @date: 2025-05-29
# @brief: CPU 频率和使用率采集器
# @copyright:
# ==================================================

"""CPU 采集器：采集各核心使用率和频率"""

import logging
import time
from typing import Optional

from collectors.base import BaseCollector
from config import CPU_FREQ_POLICIES, CPU_FREQ_PATH_TEMPLATE, CPU_STAT_PATH

logger = logging.getLogger("lanyve_rk_performance.collectors.cpu")


class CpuCollector(BaseCollector):
    """CPU 数据采集器

    通过 /proc/stat 两帧差值计算各核心使用率，
    通过 cpufreq policy 获取各簇频率。
    """

    def __init__(self):
        self._prev_stats: Optional[dict] = None

    def _read_proc_stat(self) -> Optional[dict]:
        """读取 /proc/stat 解析各 CPU 核心的时间片

        Returns:
            字典 {cpu_name: {'idle': ..., 'iowait': ..., 'total': ...}} 或 None
        """
        content = self.read_sysfs(CPU_STAT_PATH)
        if content is None:
            return None

        stats = {}
        for line in content.split("\n"):
            parts = line.split()
            if not parts or not parts[0].startswith("cpu"):
                continue
            name = parts[0]
            # cpu 总体（cpu）和各核心（cpu0, cpu1, ...）都需要
            if name == "cpu" or (name.startswith("cpu") and name[3:].isdigit()):
                values = [int(v) for v in parts[1:]]
                idle = values[3] if len(values) > 3 else 0
                iowait = values[4] if len(values) > 4 else 0
                total = sum(values)
                stats[name] = {"idle": idle, "iowait": iowait, "total": total}
        return stats

    def collect(self) -> dict:
        """采集 CPU 数据

        Returns:
            {
                "total_usage": float,        # CPU 总使用率 (%)
                "core_usage": [float x 8],   # 各核心使用率 (%)
                "frequencies": [float x 3],  # 各 policy 频率 (MHz)
            }
        """
        current_stats = self._read_proc_stat()
        result = {
            "total_usage": None,
            "core_usage": [None] * 8,
            "frequencies": [],
        }

        if current_stats and self._prev_stats:
            # 计算总使用率
            result["total_usage"] = self._calc_usage(
                self._prev_stats.get("cpu"), current_stats.get("cpu")
            )
            # 计算各核心使用率
            core_usages = []
            for i in range(8):
                key = f"cpu{i}"
                usage = self._calc_usage(
                    self._prev_stats.get(key), current_stats.get(key)
                )
                core_usages.append(usage)
            result["core_usage"] = core_usages

        self._prev_stats = current_stats

        # 读取各 policy 频率
        for policy in CPU_FREQ_POLICIES:
            path = CPU_FREQ_PATH_TEMPLATE.format(policy)
            freq = self.read_sysfs_freq(path)
            result["frequencies"].append(freq)

        return result

    @staticmethod
    def _calc_usage(prev: Optional[dict], curr: Optional[dict]) -> Optional[float]:
        """计算两帧之间的 CPU 使用率

        Args:
            prev: 上一帧统计数据
            curr: 当前帧统计数据

        Returns:
            使用率百分比（保留一位小数），数据不足返回 None
        """
        if prev is None or curr is None:
            return None
        total_diff = curr["total"] - prev["total"]
        if total_diff == 0:
            return None
        idle_diff = (curr["idle"] - prev["idle"]) + (curr["iowait"] - prev["iowait"])
        usage = (1.0 - idle_diff / total_diff) * 100.0
        return round(usage, 1)
