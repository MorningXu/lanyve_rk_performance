# =================================================
# @author: MorningXu (morningxu1991@163.com)
# @version v1.0.0
# @date: 2025-05-29
# @brief: GPU 频率和负载采集器
# @copyright:
# ==================================================

"""GPU 采集器：采集 GPU 频率和负载"""

import logging
from typing import Optional

from collectors.base import BaseCollector
from config import GPU_DEVFREQ_PATH, GPU_LOAD_PATHS

logger = logging.getLogger("lanyve_rk_performance.collectors.gpu")


class GpuCollector(BaseCollector):
    """GPU 数据采集器

    通过 devfreq 获取 GPU 频率，通过多种路径获取 GPU 负载。
    """

    def collect(self) -> dict:
        """采集 GPU 数据

        Returns:
            {
                "frequency": float,   # GPU 频率 (MHz)
                "load": float,        # GPU 负载 (%)
            }
        """
        result = {
            "frequency": None,
            "load": None,
        }

        # 读取 GPU 频率
        result["frequency"] = self.read_sysfs_freq(GPU_DEVFREQ_PATH)

        # 尝试多个路径读取 GPU 负载
        result["load"] = self._read_gpu_load()

        return result

    def _read_gpu_load(self) -> Optional[float]:
        """尝试从多个路径读取 GPU 负载

        Returns:
            GPU 负载百分比，不可用返回 None
        """
        for path in GPU_LOAD_PATHS:
            content = self.read_sysfs(path)
            if content is not None:
                try:
                    # devfreq load 格式: "XX@NNNNMHz" 或纯数字
                    if "@" in content:
                        load_str = content.split("@")[0]
                    else:
                        load_str = content
                    return round(float(load_str.strip()), 1)
                except (ValueError, IndexError):
                    continue
        return None
