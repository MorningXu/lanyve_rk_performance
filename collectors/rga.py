# =================================================
# @author: MorningXu (morningxu1991@163.com)
# @version v1.0.0
# @date: 2026-06-01
# @brief: RGA 频率和负载采集器
# @copyright:
# ==================================================

"""RGA 采集器：通过 devfreq 或 debugfs 采集 RGA 频率和负载"""

import logging
import os
import re
from typing import Optional

from collectors.base import BaseCollector
from config import RGA_DEVFREQ_CANDIDATES

logger = logging.getLogger("lanyve_rk_performance.collectors.rga")

# RGA debugfs 负载路径
RGA_DEBUGFS_LOAD_PATH = "/sys/kernel/debug/rkrga/load"


class RgaCollector(BaseCollector):
    """RGA 数据采集器

    优先通过 devfreq 获取 RGA 频率和负载；
    若无 devfreq 设备，则回退到 debugfs 读取负载。
    """

    def __init__(self):
        self._freq_path: Optional[str] = None
        self._load_path: Optional[str] = None
        self._use_debugfs = False
        self._probed = False

    def _probe(self):
        """探测 RGA 数据来源"""
        # 优先尝试 devfreq
        for keyword in RGA_DEVFREQ_CANDIDATES:
            found = self.discover_devfreq(keyword)
            if found:
                name, freq_path = found[0]
                self._freq_path = freq_path
                # 负载文件与频率文件在同一目录下
                load_path = os.path.join(os.path.dirname(freq_path), "load")
                if os.path.exists(load_path):
                    self._load_path = load_path
                logger.info("发现 RGA 设备: %s (freq=%s, load=%s)", name, self._freq_path, self._load_path)
                break

        # devfreq 未找到，尝试 debugfs
        if not self._freq_path:
            if os.path.exists(RGA_DEBUGFS_LOAD_PATH):
                self._use_debugfs = True
                logger.info("RGA 使用 debugfs 负载路径: %s", RGA_DEBUGFS_LOAD_PATH)
            else:
                logger.info("未发现 RGA 设备")

        self._probed = True

    def collect(self) -> dict:
        """采集 RGA 数据

        Returns:
            {
                "frequency": float,       # RGA 频率 (MHz)
                "load": float,            # RGA 总负载 (%)
                "core_loads": list,       # 各 core 负载 [{"name": str, "load": float}]
            }
        """
        if not self._probed:
            self._probe()

        result = {
            "frequency": None,
            "load": None,
            "core_loads": [],
        }

        # 读取频率（仅 devfreq 模式）
        if self._freq_path:
            result["frequency"] = self.read_sysfs_freq(self._freq_path)

        # 读取负载
        if self._use_debugfs:
            result.update(self._read_debugfs_load())
        elif self._load_path:
            result["load"] = self._read_devfreq_load()

        return result

    def _read_devfreq_load(self) -> Optional[float]:
        """从 devfreq load 文件读取 RGA 负载

        Returns:
            RGA 负载百分比，不可用返回 None
        """
        content = self.read_sysfs(self._load_path)
        if content is not None:
            try:
                # devfreq load 格式: "XX@NNNNMHz" 或纯数字
                if "@" in content:
                    load_str = content.split("@")[0]
                else:
                    load_str = content
                return round(float(load_str.strip()), 1)
            except (ValueError, IndexError):
                pass
        return None

    def _read_debugfs_load(self) -> dict:
        """从 debugfs 读取 RGA 各 core 负载

        Returns:
            {"load": float, "core_loads": [{"name": str, "load": float}]}
        """
        content = self.read_sysfs(RGA_DEBUGFS_LOAD_PATH)
        if content is None:
            return {}

        core_loads = []
        # 匹配格式: scheduler[N]: <name> ... load = XX%
        pattern = re.compile(r"scheduler\[\d+\]:\s+(\S+)\s+.*?load\s*=\s*(\d+)%", re.DOTALL)
        for match in pattern.finditer(content):
            name = match.group(1)
            load = float(match.group(2))
            core_loads.append({"name": name, "load": load})

        # 总负载取各 core 的最大值
        total_load = max((c["load"] for c in core_loads), default=None)
        if total_load is not None:
            total_load = round(total_load, 1)

        return {"load": total_load, "core_loads": core_loads}
