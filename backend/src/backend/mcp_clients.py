"""Backend'in htr-kraken / transkribus / search-server MCP sunucularina
gercek MCP (stdio) protokolu uzerinden client olarak baglandigi katman.

Her sunucu tek bir subprocess olarak acilir ve baglanti FastAPI app'in
omru boyunca canli tutulur (bkz. main.py lifespan) - sorgu basina yeniden
baslatmak, ozellikle embedding modelinin yuklenme suresi yuzunden cok
yavas olurdu.
"""

from __future__ import annotations

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

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        if self.session is None:
            raise RuntimeError(f"{self.name} MCP client henüz başlatılmadı")

        result = await self.session.call_tool(tool_name, arguments)
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

    async def stop_all(self) -> None:
        for client in self._clients.values():
            await client.stop()
        self._clients.clear()
