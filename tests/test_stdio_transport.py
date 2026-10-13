"""End-to-end stdio transport test against a freshly spawned server process.

Verifies the MCP handshake (list tools) works over real stdio and that the
server fails closed without a token. Runs fully offline."""

import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")

EXPECTED_TOOLS = {
    "vw_get_stats",
    "vw_scan_history",
    "vw_scan_status",
    "vw_scan_report",
    "vw_submit_scan",
}


def _env():
    env = dict(os.environ)
    env["PYTHONPATH"] = SRC + os.pathsep + env.get("PYTHONPATH", "")
    env.pop("VULNWATCH_API_TOKEN", None)  # deterministic: never inherit an ambient token
    return env


def test_stdio_handshake_lists_expected_tools():
    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "vulnwatch_mcp"], env=_env())
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                return [t.name for t in (await session.list_tools()).tools]

    assert set(asyncio.run(run())) == EXPECTED_TOOLS


def test_no_token_call_fails_closed_over_stdio():
    """list_tools works without a token (auth is per-call), but calling a read
    tool must refuse before any network use."""

    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "vulnwatch_mcp"], env=_env())
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                res = await session.call_tool("vw_get_stats", {})
                return [getattr(c, "text", "") or str(c) for c in res.content]

    texts = asyncio.run(run())
    assert any("VULNWATCH_API_TOKEN is not set" in t for t in texts), texts