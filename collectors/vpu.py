# =================================================
# @author: MorningXu (morningxu1991@163.com)
# @version v1.0.0
# @date: 2025-05-29
# @brief: VPU 频率采集器
# @copyright:
# ==================================================

"""VPU 采集器：自动探测并采集 VPU 编解码器频率"""

import logging

from collectors.base import BaseCollector
from config import VPU_DEVFREQ_CANDIDATES

logger = logging.getLogger("lanyve_rk_performance.collectors.vpu")


class VpuCollector(BaseCollector):
    """VPU 数据采集器

    通过自动探测 devfreq 下的 rkvenc/rkvdec 等设备获取频率。
    首次调用时探测，后续缓存探测结果。
    """

    def __init__(self):
        self._discovered: list[tuple[str, str]] = []
        self._probed = False

    def _probe(self):
        """探测 VPU 相关的 devfreq 设备"""
        for keyword in VPU_DEVFREQ_CANDIDATES:
            found = self.discover_devfreq(keyword)
            self._discovered.extend(found)
        if self._discovered:
            logger.info("发现 VPU 设备: %s", [name for name, _ in self._discovered])
        else:
            logger.info("未发现 VPU 设备")
        self._probed = True

    def collect(self) -> dict:
        """采集 VPU 数据

        Returns:
            {
                "encoders": [{"name": str, "frequency": float}],  # 编码器列表
                "decoders": [{"name": str, "frequency": float}],  # 解码器列表
            }
        """
        if not self._probed:
            self._probe()

        result = {"encoders": [], "decoders": []}

        for name, freq_path in self._discovered:
            freq = self.read_sysfs_freq(freq_path)
            entry = {"name": name, "frequency": freq}
            if "enc" in name.lower():
                result["encoders"].append(entry)
            else:
                result["decoders"].append(entry)

        return result
