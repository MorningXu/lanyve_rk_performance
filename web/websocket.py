# =================================================
# @author: MorningXu (morningxu1991@163.com)
# @version v1.0.0
# @date: 2025-05-29
# @brief: WebSocket 后台推送引擎
# @copyright:
# ==================================================

"""WebSocket 推送引擎：管理连接、后台定时采集、广播数据"""

import asyncio
import json
import logging
import time
from typing import Set

from aiohttp import web

from collectors.cpu import CpuCollector
from collectors.disk import DiskCollector
from collectors.gpu import GpuCollector
from collectors.memory import MemoryCollector
from collectors.npu import NpuCollector
from collectors.thermal import ThermalCollector
from collectors.vpu import VpuCollector
from config import (
    DEFAULT_REFRESH_INTERVAL,
    MAX_REFRESH_INTERVAL,
    MIN_REFRESH_INTERVAL,
)

logger = logging.getLogger("lanyve_rk_performance.websocket")


class WebSocketManager:
    """WebSocket 连接管理和数据推送管理器"""

    def __init__(self):
        self._clients: Set[web.WebSocketResponse] = set()
        self._refresh_interval = DEFAULT_REFRESH_INTERVAL / 1000.0  # 秒
        self._running = False
        self._task: asyncio.Task = None

        # 初始化采集器
        self._cpu = CpuCollector()
        self._gpu = GpuCollector()
        self._npu = NpuCollector()
        self._vpu = VpuCollector()
        self._memory = MemoryCollector()
        self._disk = DiskCollector()
        self._thermal = ThermalCollector()

    async def handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        """处理 WebSocket 连接

        Args:
            request: HTTP 请求对象

        Returns:
            WebSocket 响应对象
        """
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self._clients.add(ws)
        logger.info("WebSocket 客户端连接，当前连接数: %d", len(self._clients))

        # 发送当前刷新间隔
        try:
            await ws.send_json({
                "type": "config",
                "interval": int(self._refresh_interval * 1000),
            })
        except Exception:
            pass

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    await self._handle_message(ws, msg.data)
                elif msg.type in (web.WSMsgType.ERROR, web.WSMsgType.CLOSE):
                    break
        except Exception as e:
            logger.debug("WebSocket 异常: %s", e)
        finally:
            self._clients.discard(ws)
            logger.info("WebSocket 客户端断开，当前连接数: %d", len(self._clients))

        return ws

    async def _handle_message(self, ws: web.WebSocketResponse, data: str):
        """处理客户端发来的消息

        Args:
            ws: WebSocket 连接
            data: 消息内容
        """
        try:
            msg = json.loads(data)
        except json.JSONDecodeError:
            return

        if msg.get("type") == "set_interval":
            value = msg.get("value", DEFAULT_REFRESH_INTERVAL)
            value = max(MIN_REFRESH_INTERVAL, min(MAX_REFRESH_INTERVAL, int(value)))
            self._refresh_interval = value / 1000.0
            logger.info("刷新间隔更新为 %d ms", value)
            # 通知所有客户端
            await self._broadcast_json({
                "type": "config",
                "interval": value,
            })

    async def start(self, app: web.Application):
        """启动后台推送任务

        Args:
            app: aiohttp 应用实例
        """
        self._running = True
        self._task = asyncio.create_task(self._push_loop())

    async def stop(self, app: web.Application):
        """停止后台推送任务

        Args:
            app: aiohttp 应用实例
        """
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # 关闭所有客户端连接
        for ws in list(self._clients):
            await ws.close()
        self._clients.clear()

    async def _push_loop(self):
        """后台推送循环，定时采集数据并广播"""
        while self._running:
            start = time.monotonic()

            try:
                # 并行采集所有数据（同步 I/O 用 to_thread 包装）
                data = await self._collect_all()

                await self._broadcast_json({
                    "type": "data",
                    "timestamp": time.time(),
                    "data": data,
                })
            except Exception as e:
                logger.error("采集或推送数据时出错: %s", e)

            elapsed = time.monotonic() - start
            sleep_time = max(0.05, self._refresh_interval - elapsed)
            await asyncio.sleep(sleep_time)

    async def _collect_all(self) -> dict:
        """并行采集所有指标

        Returns:
            完整的指标数据字典
        """
        results = await asyncio.gather(
            asyncio.to_thread(self._cpu.collect),
            asyncio.to_thread(self._gpu.collect),
            asyncio.to_thread(self._npu.collect),
            asyncio.to_thread(self._vpu.collect),
            asyncio.to_thread(self._memory.collect),
            asyncio.to_thread(self._disk.collect),
            asyncio.to_thread(self._thermal.collect),
        )

        return {
            "cpu": results[0],
            "gpu": results[1],
            "npu": results[2],
            "vpu": results[3],
            "memory": results[4],
            "disk": results[5],
            "thermal": results[6],
        }

    async def _broadcast_json(self, data: dict):
        """向所有客户端广播 JSON 数据

        Args:
            data: 要广播的数据
        """
        if not self._clients:
            return

        payload = json.dumps(data)
        disconnected = set()

        for ws in self._clients:
            try:
                await ws.send_str(payload)
            except Exception:
                disconnected.add(ws)

        self._clients -= disconnected
