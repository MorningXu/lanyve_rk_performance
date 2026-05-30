# =================================================
# @author: MorningXu (morningxu1991@163.com)
# @version v1.0.0
# @date: 2025-05-29
# @brief: NPU 频率和负载采集器
# @copyright:
# ==================================================

"""NPU 采集器：采集 NPU 频率和三核负载"""

import logging
import subprocess
from typing import Optional

from collectors.base import BaseCollector
from config import NPU_DEVFREQ_PATH, NPU_LOAD_PATH

logger = logging.getLogger("lanyve_rk_performance.collectors.npu")


class NpuCollector(BaseCollector):
    """NPU 数据采集器

    通过 devfreq 获取 NPU 频率，通过 debugfs/rknpu 获取三核负载。
    需要挂载 debugfs 且有读取权限（建议 sudo 运行）。
    """

    def collect(self) -> dict:
        """采集 NPU 数据

        Returns:
            {
                "frequency": float,       # NPU 频率 (MHz)
                "core_load": [float x 3], # 三核负载 (%)
                "total_load": float,      # NPU 总负载 (%)
                "available": bool,        # NPU 负载是否可读
            }
        """
        result = {
            "frequency": None,
            "core_load": [None, None, None],
            "total_load": None,
            "available": True,
        }

        # 读取 NPU 频率
        result["frequency"] = self.read_sysfs_freq(NPU_DEVFREQ_PATH)

        # 读取 NPU 负载
        load_data = self._read_npu_load()
        if load_data is not None:
            result["core_load"] = load_data
            valid_values = [v for v in load_data if v is not None]
            if valid_values:
                result["total_load"] = round(sum(valid_values) / len(valid_values), 1)
        else:
            # 尝试 mount debugfs
            result["available"] = self._try_mount_debugfs()

        return result

    def _read_npu_load(self) -> Optional[list]:
        """读取 NPU 三核负载

        Returns:
            [core0_load, core1_load, core2_load] 列表，不可用返回 None
        """
        content = self.read_sysfs(NPU_LOAD_PATH)
        if content is None:
            return None

        try:
            # 格式: "NPU load:  Core0: XX%, Core1: XX%, Core2: XX%"
            loads = []
            for part in content.split("Core")[1:]:
                value_str = part.split(":")[1].split("%")[0].strip()
                loads.append(round(float(value_str), 1))
            return loads if len(loads) == 3 else None
        except (ValueError, IndexError):
            logger.debug("解析 NPU 负载失败: %s", content)
            return None

    @staticmethod
    def _try_mount_debugfs() -> bool:
        """尝试挂载 debugfs 以获取 NPU 负载

        Returns:
            挂载是否成功
        """
        try:
            subprocess.run(
                ["mount", "-t", "debugfs", "none", "/sys/kernel/debug"],
                capture_output=True,
                timeout=5,
            )
            # 验证是否可读
            import os
            return os.access(NPU_LOAD_PATH, os.R_OK)
        except (subprocess.SubprocessError, OSError):
            return False
