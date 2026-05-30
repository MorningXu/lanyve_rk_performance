# =================================================
# @author: MorningXu (morningxu1991@163.com)
# @version v1.0.0
# @date: 2025-05-29
# @brief: 内存和 DDR 频率采集器
# @copyright:
# ==================================================

"""内存采集器：采集内存使用率和 DDR 频率"""

import logging
from typing import Optional

from collectors.base import BaseCollector
from config import DDR_DEVFREQ_PATH, MEMINFO_PATH

logger = logging.getLogger("lanyve_rk_performance.collectors.memory")


class MemoryCollector(BaseCollector):
    """内存数据采集器

    通过 /proc/meminfo 获取内存使用情况，通过 devfreq/dmc 获取 DDR 频率。
    """

    def collect(self) -> dict:
        """采集内存数据

        Returns:
            {
                "total_mib": float,      # 总内存 (MiB)
                "used_mib": float,       # 已用内存 (MiB)
                "free_mib": float,       # 空闲内存 (MiB)
                "available_mib": float,  # 可用内存 (MiB)
                "usage_percent": float,  # 使用率 (%)
                "ddr_frequency": float,  # DDR 频率 (MHz)
            }
        """
        result = {
            "total_mib": None,
            "used_mib": None,
            "free_mib": None,
            "available_mib": None,
            "usage_percent": None,
            "ddr_frequency": None,
        }

        meminfo = self._parse_meminfo()
        if meminfo:
            total = meminfo.get("MemTotal", 0)
            available = meminfo.get("MemAvailable", 0)
            free = meminfo.get("MemFree", 0)
            buffers = meminfo.get("Buffers", 0)
            cached = meminfo.get("Cached", 0)

            if total > 0:
                used = total - available
                result["total_mib"] = round(total / 1024, 1)
                result["used_mib"] = round(used / 1024, 1)
                result["free_mib"] = round((free + buffers + cached) / 1024, 1)
                result["available_mib"] = round(available / 1024, 1)
                result["usage_percent"] = round(used / total * 100, 1)

        # 读取 DDR 频率
        result["ddr_frequency"] = self.read_sysfs_freq(DDR_DEVFREQ_PATH)

        return result

    def _parse_meminfo(self) -> Optional[dict]:
        """解析 /proc/meminfo

        Returns:
            {key: value_in_KiB} 字典，读取失败返回 None
        """
        content = self.read_sysfs(MEMINFO_PATH)
        if content is None:
            return None

        info = {}
        for line in content.split("\n"):
            parts = line.split()
            if len(parts) >= 2:
                key = parts[0].rstrip(":")
                try:
                    info[key] = int(parts[1])
                except ValueError:
                    continue
        return info
