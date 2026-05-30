# =================================================
# @author: MorningXu (morningxu1991@163.com)
# @version v1.0.0
# @date: 2025-05-29
# @brief: 磁盘使用率采集器
# @copyright:
# ==================================================

"""磁盘采集器：采集根分区磁盘使用率"""

import logging
import os

from collectors.base import BaseCollector

logger = logging.getLogger("lanyve_rk_performance.collectors.disk")


class DiskCollector(BaseCollector):
    """磁盘数据采集器

    通过 os.statvfs 获取磁盘使用情况。
    """

    def __init__(self, mount_point: str = "/"):
        self._mount_point = mount_point

    def collect(self) -> dict:
        """采集磁盘数据

        Returns:
            {
                "total_gib": float,       # 总空间 (GiB)
                "used_gib": float,        # 已用空间 (GiB)
                "free_gib": float,        # 空闲空间 (GiB)
                "usage_percent": float,   # 使用率 (%)
            }
        """
        result = {
            "total_gib": None,
            "used_gib": None,
            "free_gib": None,
            "usage_percent": None,
        }

        try:
            stat = os.statvfs(self._mount_point)
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bavail * stat.f_frsize
            used = total - free

            gib = 1024 ** 3
            result["total_gib"] = round(total / gib, 1)
            result["used_gib"] = round(used / gib, 1)
            result["free_gib"] = round(free / gib, 1)

            if total > 0:
                result["usage_percent"] = round(used / total * 100, 1)
        except OSError as e:
            logger.debug("读取磁盘信息失败: %s", e)

        return result
