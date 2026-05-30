# =================================================
# @author: MorningXu (morningxu1991@163.com)
# @version v1.0.0
# @date: 2025-05-29
# @brief: aiohttp 应用工厂
# @copyright:
# ==================================================

"""aiohttp 应用工厂：路由注册、静态文件服务"""

import asyncio
import json
import logging
import os

from aiohttp import web

from web.websocket import WebSocketManager
from web.performance import (
    handle_get_status,
    handle_set_cpu,
    handle_set_gpu,
    handle_set_npu,
    handle_set_all,
)

logger = logging.getLogger("lanyve_rk_performance.web")


def create_app() -> web.Application:
    """创建 aiohttp 应用实例

    Returns:
        配置好路由和生命周期的 web.Application
    """
    app = web.Application()

    # WebSocket 管理器
    ws_manager = WebSocketManager()

    # 静态文件目录
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

    # 路由注册
    app.router.add_get("/", lambda req: _serve_index(req, static_dir))
    app.router.add_static("/static", static_dir, name="static")
    app.router.add_get("/logo.png", lambda req: _serve_logo(req, static_dir))
    app.router.add_get("/favicon.ico", lambda req: _serve_favicon(req, static_dir))
    app.router.add_get("/ws", ws_manager.handle_ws)
    app.router.add_get("/api/snapshot", lambda req: _snapshot(req, ws_manager))

    # 性能模式切换 API
    app.router.add_get("/api/performance/status", handle_get_status)
    app.router.add_post("/api/performance/cpu", handle_set_cpu)
    app.router.add_post("/api/performance/gpu", handle_set_gpu)
    app.router.add_post("/api/performance/npu", handle_set_npu)
    app.router.add_post("/api/performance/all", handle_set_all)

    # 生命周期钩子
    app.on_startup.append(ws_manager.start)
    app.on_cleanup.append(ws_manager.stop)

    logger.info("应用路由注册完成，静态文件目录: %s", static_dir)
    return app


async def _serve_index(request: web.Request, static_dir: str) -> web.Response:
    """返回 index.html

    Args:
        request: HTTP 请求
        static_dir: 静态文件目录

    Returns:
        HTML 响应
    """
    index_path = os.path.join(static_dir, "index.html")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
        return web.Response(text=content, content_type="text/html")
    except FileNotFoundError:
        return web.Response(text="index.html not found", status=404)


async def _serve_logo(request: web.Request, static_dir: str) -> web.Response:
    """返回 logo.png

    Args:
        request: HTTP 请求
        static_dir: 静态文件目录

    Returns:
        图片响应
    """
    logo_path = os.path.join(static_dir, "logo.png")
    try:
        with open(logo_path, "rb") as f:
            content = f.read()
        return web.Response(body=content, content_type="image/png")
    except FileNotFoundError:
        return web.Response(text="logo.png not found", status=404)


async def _serve_favicon(request: web.Request, static_dir: str) -> web.Response:
    """返回 favicon.ico（复用 logo.png）

    Args:
        request: HTTP 请求
        static_dir: 静态文件目录

    Returns:
        图片响应
    """
    favicon_path = os.path.join(static_dir, "logo.png")
    try:
        with open(favicon_path, "rb") as f:
            content = f.read()
        return web.Response(body=content, content_type="image/x-icon")
    except FileNotFoundError:
        return web.Response(text="favicon not found", status=404)


async def _snapshot(request: web.Request, ws_manager: WebSocketManager) -> web.Response:
    """REST 快照接口，返回当前采集的一次数据

    Args:
        request: HTTP 请求
        ws_manager: WebSocket 管理器

    Returns:
        JSON 响应
    """
    data = await ws_manager._collect_all()
    return web.json_response(data)
