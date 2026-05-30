# =================================================
# @author: MorningXu (morningxu1991@163.com)
# @version v1.0.0
# @date: 2025-05-29
# @brief: 采集器基类，提供通用 sysfs/procfs 文件读取方法
# @copyright:
# ==================================================

"""采集器基类"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("lanyve_rk_performance.collectors")


class BaseCollector:
    """采集器基类，提供安全读取 sysfs/procfs 文件的通用方法"""

    @staticmethod
    def read_sysfs(path: str) -> Optional[str]:
        """安全读取 sysfs 文件，返回字符串内容

        Args:
            path: sysfs 文件路径

        Returns:
            文件内容字符串，读取失败返回 None
        """
        try:
            with open(path, "r") as f:
                return f.read().strip()
        except (FileNotFoundError, PermissionError, OSError) as e:
            logger.debug("读取 %s 失败: %s", path, e)
            return None

    @staticmethod
    def read_sysfs_int(path: str) -> Optional[int]:
        """安全读取 sysfs 文件并转为整数

        Args:
            path: sysfs 文件路径

        Returns:
            整数值，读取或转换失败返回 None
        """
        content = BaseCollector.read_sysfs(path)
        if content is not None:
            try:
                return int(content)
            except ValueError:
                logger.debug("转换整数失败: %s -> %s", path, content)
        return None

    @staticmethod
    def read_sysfs_freq(path: str) -> Optional[float]:
        """读取 devfreq 频率并转为 MHz

        Args:
            path: devfreq cur_freq 文件路径

        Returns:
            频率（MHz），读取失败返回 None
        """
        value = BaseCollector.read_sysfs_int(path)
        if value is not None:
            return round(value / 1_000_000, 1)
        return None

    @staticmethod
    def discover_devfreq(keyword: str) -> list[tuple[str, str]]:
        """在 /sys/class/devfreq/ 下自动探测包含关键字的设备

        Args:
            keyword: 设备名关键字（如 rkvenc、rkvdec）

        Returns:
            匹配的 (设备名, cur_freq路径) 列表
        """
        devfreq_base = "/sys/class/devfreq"
        results = []
        try:
            for entry in os.listdir(devfreq_base):
                if keyword in entry.lower():
                    freq_path = os.path.join(devfreq_base, entry, "cur_freq")
                    if os.path.exists(freq_path):
                        results.append((entry, freq_path))
        except OSError:
            pass
        return results
