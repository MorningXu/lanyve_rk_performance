# =================================================
# @author: MorningXu (morningxu1991@163.com)
# @version v1.0.0
# @date: 2025-05-29
# @brief: lanyve_rk_performance 配置文件，定义 sysfs 路径和服务参数
# @copyright:
# ==================================================

"""lanyve_rk_performance 全局配置"""

# 服务配置
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8080

# 默认刷新间隔（毫秒）
DEFAULT_REFRESH_INTERVAL = 1000
# 最小/最大刷新间隔（毫秒）
MIN_REFRESH_INTERVAL = 500
MAX_REFRESH_INTERVAL = 10000

# 历史数据窗口大小
HISTORY_WINDOW_SIZE = 60

# CPU sysfs 路径
CPU_STAT_PATH = "/proc/stat"
CPU_FREQ_POLICIES = [0, 4, 6]  # RK3588 有3组 cpufreq policy
CPU_FREQ_PATH_TEMPLATE = "/sys/devices/system/cpu/cpufreq/policy{}/scaling_cur_freq"

# GPU sysfs 路径
GPU_DEVFREQ_PATH = "/sys/class/devfreq/fb000000.gpu/cur_freq"
GPU_LOAD_PATHS = [
    "/sys/class/devfreq/fb000000.gpu/load",
    "/sys/class/misc/mali0/device/utilisation",
]

# NPU sysfs 路径
NPU_DEVFREQ_PATH = "/sys/class/devfreq/fdab0000.npu/cur_freq"
NPU_LOAD_PATH = "/sys/kernel/debug/rknpu/load"

# DDR sysfs 路径
DDR_DEVFREQ_PATH = "/sys/class/devfreq/dmc/cur_freq"

# RGA devfreq 候选路径（自动探测）
RGA_DEVFREQ_CANDIDATES = ["rga"]

# 温度传感器 sysfs 路径
THERMAL_BASE_PATH = "/sys/class/thermal"

# 内存信息路径
MEMINFO_PATH = "/proc/meminfo"

# VPU devfreq 候选路径（自动探测）
VPU_DEVFREQ_CANDIDATES = ["rkvenc", "rkvdec", "vepu", "vdpu"]

# 性能模式 sysfs 路径
CPU_GOVERNOR_PATH_TEMPLATE = "/sys/devices/system/cpu/cpufreq/policy{}/scaling_governor"
GPU_GOVERNOR_PATH = "/sys/class/devfreq/fb000000.gpu/governor"
NPU_GOVERNOR_PATH = "/sys/class/devfreq/fdab0000.npu/governor"

# 默认 governor（用于 toggle 恢复）
CPU_DEFAULT_GOVERNOR = "ondemand"
GPU_DEFAULT_GOVERNOR = "simple_ondemand"
NPU_DEFAULT_GOVERNOR = "rknpu_ondemand"
