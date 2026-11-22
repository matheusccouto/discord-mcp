"""Discord API exposed as an MCP server.

The tool surface comes from Discord's official OpenAPI spec, cut down to whole path
families: everything under /channels and /users, nothing else. Publishing it on
FastMCP Gateway adds HTTPS, OAuth and a per-call log; this file only talks to Discord.

Env:
  DISCORD_BOT_TOKEN  required, read at build time
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


def read_spec() -> dict:
    return json.loads(SPEC_PATH.read_text())


def family_of(route: str) -> str:
    """The first segment of a route: /channels/{id}/messages belongs to channels."""
    return route.strip("/").split("/")[0]


def chosen_families(spec: dict) -> list[str]:
    """The families to expose, refusing names the spec does not have."""
    requested = [name.strip() for name in os.environ.get("DISCORD_FAMILIES", "").split(",")]
    families = [name for name in requested if name]
    if not families:
        return list(DEFAULT_FAMILIES)

    available = {family_of(route) for route in spec["paths"]}
    unknown = sorted(set(families) - available)
    if unknown:
        raise ValueError(f"unknown DISCORD_FAMILIES {unknown}; available: {sorted(available)}")
    return families


def filtered(spec: dict, families: list[str]) -> dict:
    """The spec with only the chosen families kept.

    Cutting before parsing also avoids routes FastMCP's validator rejects: Discord
    ships empty enums under /guilds, so asking for that family fails the build.
    """
    spec["paths"] = {
        route: operations
        for route, operations in spec["paths"].items()
        if family_of(route) in families
    }
    return spec


def bot_token() -> str:
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN is not set")
    return token


def build() -> FastMCP:
    spec = read_spec()
    client = httpx2.AsyncClient(
        base_url=API_ROOT,
        headers={"Authorization": f"Bot {bot_token()}", "User-Agent": "discord-mcp (1.0)"},
        timeout=20,
    )
    return FastMCP.from_openapi(
        openapi_spec=filtered(spec, chosen_families(spec)),
        client=client,
        name="discord",
    )


mcp = build()

if __name__ == "__main__":
    mcp.run()  # transport comes from FASTMCP_TRANSPORT; the Gateway injects http
