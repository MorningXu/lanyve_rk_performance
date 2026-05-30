# =================================================
# @author: MorningXu (morningxu1991@163.com)
# @version v1.0.0
# @date: 2025-05-30
# @brief: CPU/GPU/NPU 性能模式切换 API handler
# @copyright:
# ==================================================

"""性能模式切换：通过 sysfs 设置 governor 为 performance"""

import asyncio
import logging

from aiohttp import web

import config

logger = logging.getLogger("lanyve_rk_performance.performance")


def _read_sysfs(path: str) -> str | None:
    """读取 sysfs 文件内容

    Args:
        path: sysfs 文件路径

    Returns:
        文件内容字符串（去除首尾空白），读取失败返回 None
    """
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except (FileNotFoundError, PermissionError, OSError) as e:
        logger.warning("读取 sysfs 失败 %s: %s", path, e)
        return None


def _write_sysfs(path: str, value: str) -> bool:
    """向 sysfs 文件写入值

    Args:
        path: sysfs 文件路径
        value: 要写入的值

    Returns:
        写入成功返回 True，失败返回 False
    """
    try:
        with open(path, "w") as f:
            f.write(value)
        logger.info("写入 sysfs 成功: %s = %s", path, value)
        return True
    except (FileNotFoundError, PermissionError, OSError) as e:
        logger.error("写入 sysfs 失败 %s: %s", path, e)
        return False


def _toggle_governor(path: str, default_governor: str) -> dict:
    """切换 governor：performance ↔ default

    读取当前 governor，若为 performance 则恢复为 default_governor，否则设为 performance。

    Args:
        path: sysfs governor 文件路径
        default_governor: 默认 governor 名称

    Returns:
        包含 success、governor、performance 的字典
    """
    current = _read_sysfs(path)
    if current == "performance":
        target = default_governor
    else:
        target = "performance"
    ok = _write_sysfs(path, target)
    new_gov = _read_sysfs(path)
    return {
        "success": ok,
        "governor": new_gov,
        "performance": new_gov == "performance",
    }


def _toggle_cpu() -> dict:
    """切换所有 CPU policy 的 governor（toggle）

    Returns:
        包含各 policy 设置结果的字典
    """
    results = {}
    for policy_id in config.CPU_FREQ_POLICIES:
        path = config.CPU_GOVERNOR_PATH_TEMPLATE.format(policy_id)
        results[f"policy{policy_id}"] = _toggle_governor(path, config.CPU_DEFAULT_GOVERNOR)
    return results


def _toggle_gpu() -> dict:
    """切换 GPU governor（toggle）

    Returns:
        包含设置结果的字典
    """
    return _toggle_governor(config.GPU_GOVERNOR_PATH, config.GPU_DEFAULT_GOVERNOR)


def _toggle_npu() -> dict:
    """切换 NPU governor（toggle）

    Returns:
        包含设置结果的字典
    """
    return _toggle_governor(config.NPU_GOVERNOR_PATH, config.NPU_DEFAULT_GOVERNOR)


def _get_status() -> dict:
    """读取当前所有设备的 governor 状态

    Returns:
        包含 CPU/GPU/NPU 当前 governor 的字典
    """
    cpu = {}
    for policy_id in config.CPU_FREQ_POLICIES:
        path = config.CPU_GOVERNOR_PATH_TEMPLATE.format(policy_id)
        cpu[f"policy{policy_id}"] = _read_sysfs(path)

    return {
        "cpu": cpu,
        "gpu": _read_sysfs(config.GPU_GOVERNOR_PATH),
        "npu": _read_sysfs(config.NPU_GOVERNOR_PATH),
    }


async def handle_get_status(request: web.Request) -> web.Response:
    """查询当前 governor 状态

    Args:
        request: HTTP 请求

    Returns:
        JSON 响应，包含各设备当前 governor
    """
    status = await asyncio.to_thread(_get_status)
    return web.json_response(status)


async def handle_set_cpu(request: web.Request) -> web.Response:
    """CPU governor toggle

    Args:
        request: HTTP 请求

    Returns:
        JSON 响应，包含各 policy 设置结果及 performance 标记
    """
    result = await asyncio.to_thread(_toggle_cpu)
    all_ok = all(r["success"] for r in result.values())
    all_perf = all(r["performance"] for r in result.values())
    return web.json_response({
        "success": all_ok,
        "performance": all_perf,
        "details": result,
    })


async def handle_set_gpu(request: web.Request) -> web.Response:
    """GPU governor toggle

    Args:
        request: HTTP 请求

    Returns:
        JSON 响应，包含设置结果及 performance 标记
    """
    result = await asyncio.to_thread(_toggle_gpu)
    return web.json_response({
        "success": result["success"],
        "performance": result["performance"],
        "details": result,
    })


async def handle_set_npu(request: web.Request) -> web.Response:
    """NPU governor toggle

    Args:
        request: HTTP 请求

    Returns:
        JSON 响应，包含设置结果及 performance 标记
    """
    result = await asyncio.to_thread(_toggle_npu)
    return web.json_response({
        "success": result["success"],
        "performance": result["performance"],
        "details": result,
    })


async def handle_set_all(request: web.Request) -> web.Response:
    """CPU/GPU/NPU 全部 toggle

    Args:
        request: HTTP 请求

    Returns:
        JSON 响应，包含所有设备设置结果及 performance 标记
    """
    cpu = await asyncio.to_thread(_toggle_cpu)
    gpu = await asyncio.to_thread(_toggle_gpu)
    npu = await asyncio.to_thread(_toggle_npu)

    cpu_ok = all(r["success"] for r in cpu.values())
    all_ok = cpu_ok and gpu["success"] and npu["success"]
    all_perf = all(r["performance"] for r in cpu.values()) and gpu["performance"] and npu["performance"]

    return web.json_response({
        "success": all_ok,
        "performance": all_perf,
        "details": {"cpu": cpu, "gpu": gpu, "npu": npu},
    })
