"""Backend'in htr-kraken / transkribus / search-server MCP sunucularina
gercek MCP (stdio) protokolu uzerinden client olarak baglandigi katman.

Her sunucu tek bir subprocess olarak acilir ve baglanti FastAPI app'in
omru boyunca canli tutulur (bkz. main.py lifespan) - sorgu basina yeniden
baslatmak, ozellikle embedding modelinin yuklenme suresi yuzunden cok
yavas olurdu.
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class McpServerClient:
    def __init__(
        self,
        name: str,
        command: str,
        args: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        # Alt process PATH/DLL bulma vb. icin ebeveyn ortamini miras almali;
        # sadece verilen env ile degistirmek Windows'ta python'un kendisini
        # bulamamasina yol acabiliyor.
        full_env = {**os.environ, **(env or {})}
        self._params = StdioServerParameters(command=command, args=args, cwd=cwd, env=full_env)
        self._stack = AsyncExitStack()
        self.session: ClientSession | None = None

    async def start(self) -> None:
        read, write = await self._stack.enter_async_context(stdio_client(self._params))
        self.session = await self._stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()

    async def stop(self) -> None:
        await self._stack.aclose()

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any], timeout: float | None = None
    ) -> Any:
        if self.session is None:
            raise RuntimeError(f"{self.name} MCP client henüz başlatılmadı")

        # timeout olmadan asagidaki cagri (ör. yavas bir Kraken calismasi)
        # sonsuza kadar bekleyebilir - tek is parcacikli asyncio event
        # loop'unda bu, SADECE bu istegi degil, ayni sunucudaki TUM diger
        # istekleri de (ilgisiz olanlar dahil) donduruyordu. wait_for,
        # makul bir sinir koyup asilirsa duzgun bir hata dondurur.
        try:
            if timeout is not None:
                result = await asyncio.wait_for(
                    self.session.call_tool(tool_name, arguments), timeout=timeout
                )
            else:
                result = await self.session.call_tool(tool_name, arguments)
        except TimeoutError:
            raise RuntimeError(
                f"{self.name}.{tool_name} {timeout} saniye içinde tamamlanmadı (zaman aşımı). "
                "Sunucu aşırı yüklenmiş olabilir; diğer uygulamaları kapatıp tekrar deneyin."
            ) from None

        if result.isError:
            raise RuntimeError(f"{self.name}.{tool_name} hata döndürdü: {result.content}")

        if result.structuredContent is not None:
            payload = result.structuredContent
            # FastMCP, list/scalar donen tool'lari {"result": ...} ile sarar.
            if isinstance(payload, dict) and set(payload.keys()) == {"result"}:
                return payload["result"]
            return payload

        for block in result.content:
            if getattr(block, "type", None) == "text":
                try:
                    return json.loads(block.text)
                except json.JSONDecodeError:
                    return block.text
        return None


class McpClientManager:
    def __init__(self) -> None:
        self._clients: dict[str, McpServerClient] = {}

    async def start(
        self,
        name: str,
        command: str,
        args: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        client = McpServerClient(name, command, args, cwd, env)
        await client.start()
        self._clients[name] = client

    def get(self, name: str) -> McpServerClient:
        if name not in self._clients:
            raise RuntimeError(f"MCP client başlatılmamış: {name}")
        return self._clients[name]

    def is_started(self, name: str) -> bool:
        return name in self._clients

    async def stop_all(self) -> None:
        for client in self._clients.values():
            await client.stop()
        self._clients.clear()
