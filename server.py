"""Discord REST API as an MCP server.

Tools come from Discord's OpenAPI spec, cut to whole path families and cleaned of the
JSON Schema keywords the Gemini connector rejects. A GitHub login guards the app, and
nothing but discord.com is ever called.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import httpx2
from fastmcp import FastMCP
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.providers.openapi.components import OpenAPITool
from starlette.responses import Response

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

SPEC = Path(__file__).with_name("discord-openapi.json")
API = "https://discord.com/api/v10"
FAMILIES = "channels,users"
REJECTED = frozenset({"$schema", "additionalProperties", "$defs", "const"})
INT32 = 2**31 - 1
METADATA = "/.well-known/oauth-protected-resource/mcp"

type JSON = dict[str, JSON] | list[JSON] | str | int | float | bool | None


def family(route: str) -> str:
    """Return the family of a route: /channels/{id}/messages belongs to channels."""
    return route.strip("/").split("/")[0]


def clean(schema: JSON) -> JSON:
    """Return the schema without the keywords the Gemini connector refuses.

    A ``const`` becomes a one-value ``enum``; the other keys are dropped, and float
    bounds are clamped to 32-bit ints.
    """
    if isinstance(schema, list):
        return [clean(item) for item in schema]
    if not isinstance(schema, dict):
        return schema

    cleaned = {
        key: clean(value) for key, value in schema.items() if key not in REJECTED
    }
    if "const" in schema:
        cleaned["enum"] = [schema["const"]]
    for bound in ("maximum", "minimum"):
        value = cleaned.get(bound)
        if isinstance(value, float):
            cleaned[bound] = int(min(max(value, -INT32), INT32))
    return cleaned


def gemini_safe(_route: object, tool: object) -> None:
    """Clean a generated tool: scrub its input, drop its output schema."""
    if isinstance(tool, OpenAPITool):
        tool.parameters = cast("dict[str, Any]", clean(tool.parameters))
        tool.output_schema = None


def login() -> GitHubProvider | None:
    """Return the GitHub login, or nothing when its credentials are absent."""
    if not os.environ.get("GITHUB_CLIENT_ID"):
        return None
    return GitHubProvider(
        client_id=os.environ["GITHUB_CLIENT_ID"],
        client_secret=os.environ["GITHUB_CLIENT_SECRET"],
        base_url=os.environ["PUBLIC_URL"],
        jwt_signing_key=os.environ["JWT_SIGNING_KEY"],
    )


def build(client: httpx2.AsyncClient) -> FastMCP:
    """Build the MCP server from the chosen families and a Discord client."""
    spec = json.loads(SPEC.read_text())
    keep = os.environ.get("DISCORD_FAMILIES", FAMILIES).split(",")
    spec["paths"] = {
        route: operations
        for route, operations in spec["paths"].items()
        if family(route) in keep
    }
    return FastMCP.from_openapi(
        openapi_spec=spec,
        client=client,
        name="discord",
        mcp_component_fn=gemini_safe,
        auth=login(),
    )


mcp = build(
    httpx2.AsyncClient(
        base_url=API,
        headers={
            "Authorization": f"Bot {os.environ['DISCORD_BOT_TOKEN']}",
            "User-Agent": "discord-mcp (1.0)",
        },
        timeout=20,
    )
)


class RequireAuth:
    """Answer 401 on /mcp for every method when the request has no credentials."""

    def __init__(self, inner: ASGIApp) -> None:
        """Keep the app to fall through to."""
        self.inner = inner

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Return the challenge, or hand the request over."""
        if scope["type"] == "http" and scope["path"].startswith("/mcp"):
            names = {name.lower() for name, _ in scope["headers"]}
            if b"authorization" not in names:
                public = os.environ.get("PUBLIC_URL", "https://login.invalid")
                challenge = f'Bearer resource_metadata="{public}{METADATA}"'
                response = Response("", 401, {"WWW-Authenticate": challenge})
                await response(scope, receive, send)
                return
        await self.inner(scope, receive, send)


app = RequireAuth(mcp.http_app(stateless_http=True))  # Vercel loads `app`

if __name__ == "__main__":
    mcp.run()  # transport comes from FASTMCP_TRANSPORT; the Gateway injects http
