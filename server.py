"""Discord API exposed as an MCP server.

The tool surface comes from Discord's official OpenAPI spec, cut down to whole path
families: everything under /channels and /users, nothing else. Publishing it on
FastMCP Gateway adds HTTPS, OAuth and a per-call log; this file only talks to Discord.

Env:
  DISCORD_BOT_TOKEN  required at call time
  DISCORD_FAMILIES   optional, comma separated path families (default: channels,users)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx2
from fastmcp import FastMCP

SPEC_PATH = Path(__file__).with_name("discord-openapi.json")
API_ROOT = "https://discord.com/api/v10"
DEFAULT_FAMILIES = ("channels", "users")


def families() -> list[str]:
    """Path families to expose: the first segment of the route, e.g. /channels/{id}."""
    raw = os.environ.get("DISCORD_FAMILIES", "")
    chosen = [name.strip() for name in raw.split(",") if name.strip()]
    return chosen or list(DEFAULT_FAMILIES)


def filtered_spec(families: list[str]) -> dict:
    """The spec with only the chosen families kept.

    Cutting before parsing also skips routes FastMCP's validator rejects, like the
    empty enums Discord ships under /guilds.
    """
    spec = json.loads(SPEC_PATH.read_text())
    prefixes = tuple(f"/{name}/" for name in families)
    spec["paths"] = {
        route: operations
        for route, operations in spec["paths"].items()
        if route.startswith(prefixes)
    }
    return spec


def build() -> FastMCP:
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    client = httpx2.AsyncClient(
        base_url=API_ROOT,
        headers={"Authorization": f"Bot {token}", "User-Agent": "discord-mcp (1.0)"},
        timeout=20,
    )
    return FastMCP.from_openapi(
        openapi_spec=filtered_spec(families()),
        client=client,
        name="discord",
    )


mcp = build()

if __name__ == "__main__":
    mcp.run()  # transport comes from FASTMCP_TRANSPORT; the Gateway injects http
