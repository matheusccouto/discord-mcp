"""Discord REST API exposed as an MCP server.

Tools are generated from Discord's OpenAPI spec, cut to whole path families. The
server answers only when the URL carries the shared key; the Gemini connector can
send nothing else.
"""

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import httpx2
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from mcp.shared.exceptions import MCPError

if TYPE_CHECKING:
    from mcp.types import Request

SPEC_PATH = Path(__file__).with_name("discord-openapi.json")
API_ROOT = "https://discord.com/api/v10"
DEFAULT_FAMILIES = "channels,users"
UNAUTHORIZED = 401


def read_spec() -> dict:
    """Return the vendored OpenAPI document."""
    return json.loads(SPEC_PATH.read_text())


def family_of(route: str) -> str:
    """Return the family of a route: /channels/{id}/messages belongs to channels."""
    return route.strip("/").split("/")[0]


def families() -> list[str]:
    """Return the families to expose: DISCORD_FAMILIES, or the default."""
    return os.environ.get("DISCORD_FAMILIES", DEFAULT_FAMILIES).split(",")


def filtered(spec: dict, families: list[str]) -> dict:
    """Return the spec with only the chosen families kept.

    Cutting before parsing also skips the routes FastMCP's validator rejects:
    Discord ships empty enums under /guilds.
    """
    spec["paths"] = {
        route: operations
        for route, operations in spec["paths"].items()
        if family_of(route) in families
    }
    return spec


def bot_token() -> str:
    """Return the bot token from the environment; KeyError says what is missing."""
    return os.environ["DISCORD_BOT_TOKEN"]


class KeyGate(Middleware):
    """Refuse any request whose URL does not carry the shared key."""

    async def on_request(
        self,
        context: MiddlewareContext[Request],
        call_next: CallNext[Request, object],
    ) -> object:
        """Compare the key on the request URL, then hand the call over.

        In-memory transports have no URL, so there is nothing to compare and the
        call goes through: only a network caller can be gated.
        """
        try:
            request = get_http_request()
        except RuntimeError:
            return await call_next(context)
        if request.query_params.get("key") != os.environ["MCP_KEY"]:
            msg = "unauthorized: connect with ?key=<MCP_KEY> on the server URL"
            raise MCPError(UNAUTHORIZED, msg)
        return await call_next(context)


def build(client: httpx2.AsyncClient) -> FastMCP:
    """Build the MCP server from the filtered spec and a Discord client."""
    spec = read_spec()
    return FastMCP.from_openapi(
        openapi_spec=filtered(spec, families()),
        client=client,
        name="discord",
        middleware=[KeyGate()],
    )


mcp = build(
    httpx2.AsyncClient(
        base_url=API_ROOT,
        headers={
            "Authorization": f"Bot {bot_token()}",
            "User-Agent": "discord-mcp (1.0)",
        },
        timeout=20,
    )
)

if __name__ == "__main__":
    mcp.run()  # transport comes from FASTMCP_TRANSPORT; the Gateway injects http
