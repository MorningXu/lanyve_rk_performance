# =================================================
# @author: MorningXu (morningxu1991@163.com)
# @version v1.0.0
# @date: 2025-05-29
# @brief: 温度采集器，动态探测 thermal zone
# @copyright:
# ==================================================

"""温度采集器：动态探测 thermal zone 并采集各组件温度"""

import logging
import os
from typing import Optional

from collectors.base import BaseCollector
from config import THERMAL_BASE_PATH

logger = logging.getLogger("lanyve_rk_performance.collectors.thermal")


# RK3588 标准 thermal zone 映射（type 名 -> 显示名）
THERMAL_LABELS = {
    "cpu0-thermal": "A76_0/1",
    "cpu1-thermal": "A76_2/3",
    "cpu2-thermal": "A55",
    "gpu-thermal": "GPU",
    "npu-thermal": "NPU",
    "soc-thermal": "SOC",
    "bigcore0-thermal": "A76_0/1",
    "bigcore1-thermal": "A76_2/3",
    "littlecore-thermal": "A55",
    "center-thermal": "Center",
    "dsu-thermal": "DSU",
}


class ThermalCollector(BaseCollector):
    """温度数据采集器

    首次调用时遍历 /sys/class/thermal/ 动态探测 thermal zone，
    将 type 名映射为可读标签，后续采集时直接读取。
    """

    def __init__(self):
        self._zones: list[tuple[str, str]] = []  # [(label, temp_path), ...]
        self._probed = False

    def _probe(self):
        """探测所有 thermal zone 并建立映射"""
        try:
            entries = sorted(os.listdir(THERMAL_BASE_PATH))
        except OSError:
            logger.debug("无法列出 %s", THERMAL_BASE_PATH)
            self._probed = True
            return

        for entry in entries:
            if not entry.startswith("thermal_zone"):
                continue

            type_path = os.path.join(THERMAL_BASE_PATH, entry, "type")
            temp_path = os.path.join(THERMAL_BASE_PATH, entry, "temp")

            zone_type = self.read_sysfs(type_path)
            if zone_type is None:
                continue

            if not os.path.exists(temp_path):
                continue

            # 尝试匹配已知标签
            label = self._map_label(zone_type, entry)
            self._zones.append((label, temp_path))

        if self._zones:
            logger.info(
                "发现温度传感器: %s",
                {label: path for label, path in self._zones},
            )
        self._probed = True

    @staticmethod
    def _map_label(zone_type: str, zone_name: str) -> str:
        """将 thermal zone type 映射为可读标签

        Args:
            zone_type: thermal zone 的 type 值
            zone_name: thermal zone 的名称（如 thermal_zone0）

        Returns:
            可读的温度标签
        """
        # 先用 type 匹配
        zone_type_lower = zone_type.lower()
        for key, label in THERMAL_LABELS.items():
            if key.lower() == zone_type_lower:
                return label

        # 再用 zone 编号推断（RK3588 标准映射）
        try:
            idx = int(zone_name.replace("thermal_zone", ""))
            default_labels = {
                0: "A76_0/1", 1: "A76_2/3", 2: "A55",
                3: "GPU", 4: "NPU", 5: "SOC", 6: "DSU",
            }
            return default_labels.get(idx, zone_type)
        except ValueError:
            return zone_type

    def collect(self) -> dict:
        """采集温度数据

        Returns:
            {
                "sensors": [
                    {"label": str, "temperature": float},  # 温度 (°C)
                ],
            }
        """
        if not self._probed:
            self._probe()

        sensors = []
        for label, temp_path in self._zones:
            temp_raw = self.read_sysfs_int(temp_path)
            temp_c = round(temp_raw / 1000, 1) if temp_raw is not None else None
            sensors.append({"label": label, "temperature": temp_c})

        return {"sensors": sensors}

    def get_sensor_temp(self, label_keyword: str) -> Optional[float]:
        """获取指定传感器的温度

        Args:
            label_keyword: 标签关键字（如 "GPU"、"NPU"）

        Returns:
            温度值（°C），未找到返回 None
        """
        data = self.collect()
        for sensor in data["sensors"]:
            if label_keyword.upper() in sensor["label"].upper():
                return sensor["temperature"]
        return None
