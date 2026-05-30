# =================================================
# @author: MorningXu (morningxu1991@163.com)
# @version v1.0.0
# @date: 2025-05-29
# @brief: lanyve_rk_performance 启动入口
# @copyright:
# ==================================================

"""lanyve_rk_performance 启动入口"""

import logging
import os
import sys

from config import SERVER_HOST, SERVER_PORT

# 确保 web 包可被导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.app import create_app


def check_permissions():
    """检查运行权限并输出提示"""
    npu_load = "/sys/kernel/debug/rknpu/load"
    if not os.path.exists(npu_load):
        logging.warning("NPU 负载文件 %s 不存在，请确保已挂载 debugfs", npu_load)
        logging.warning("可执行: sudo mount -t debugfs none /sys/kernel/debug")
    elif not os.access(npu_load, os.R_OK):
        logging.warning("无权限读取 NPU 负载数据，建议使用 sudo 运行")


def main():
    """主入口"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    check_permissions()

    app = create_app()
    logging.getLogger("lanyve_rk_performance").info(
        "lanyve_rk_performance 启动中... 访问 http://%s:%d", SERVER_HOST, SERVER_PORT
    )

    import asyncio
    from aiohttp import web

    web.run_app(app, host=SERVER_HOST, port=SERVER_PORT)


if __name__ == "__main__":
    main()
