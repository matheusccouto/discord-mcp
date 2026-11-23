"""Discord REST API exposed as an MCP server.

Tools are generated from Discord's OpenAPI spec, cut to whole path families. FastMCP
Gateway serves this behind OAuth; this file only talks to Discord over HTTP.
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

SPEC_PATH = Path(__file__).with_name("discord-openapi.json")
PUBLIC = os.environ.get("PUBLIC_URL", "https://login.invalid")
CHALLENGE = (
    f'Bearer resource_metadata="{PUBLIC}/.well-known/oauth-protected-resource/mcp"'
)

API_ROOT = "https://discord.com/api/v10"
DEFAULT_FAMILIES = "channels,users"


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


GEMINI_REJECTS = frozenset({"$schema", "additionalProperties", "$defs", "const"})
INT32 = 2**31 - 1

type JSON = dict[str, JSON] | list[JSON] | str | int | float | bool | None


def scrub(schema: JSON) -> JSON:
    """Return the schema without the keywords the Gemini connector refuses.

    The connector fails registration on ``$schema``, ``additionalProperties``,
    ``$defs`` and ``const``, so a ``const`` becomes a one-value ``enum`` and the rest
    is dropped. Integer bounds are clamped to 32 bits and made ints.
    """
    if isinstance(schema, list):
        return [scrub(item) for item in schema]
    if not isinstance(schema, dict):
        return schema

    clean = {
        key: scrub(value) for key, value in schema.items() if key not in GEMINI_REJECTS
    }
    if "const" in schema:
        clean["enum"] = [schema["const"]]
    for bound in ("maximum", "minimum"):
        value = clean.get(bound)
        if isinstance(value, float):
            clean[bound] = int(min(max(value, -INT32), INT32))
    return clean


def gemini_safe(_route: object, component: object) -> None:
    """Scrub what the Gemini connector refuses, from both of a tool's schemas."""
    if not isinstance(component, OpenAPITool):
        return
    component.parameters = cast("dict[str, Any]", scrub(component.parameters))
    if component.output_schema:
        component.output_schema = cast("dict[str, Any]", scrub(component.output_schema))


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
    """Build the MCP server from the filtered spec and a Discord client."""
    spec = read_spec()
    return FastMCP.from_openapi(
        openapi_spec=cast("dict[str, Any]", scrub(filtered(spec, families()))),
        client=client,
        name="discord",
        mcp_component_fn=gemini_safe,
        validate_output=False,
        auth=login(),
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
                response = Response("", 401, {"WWW-Authenticate": CHALLENGE})
                await response(scope, receive, send)
                return
        await self.inner(scope, receive, send)


app = RequireAuth(mcp.http_app(stateless_http=True))  # Vercel loads `app`

if __name__ == "__main__":
    mcp.run()  # transport comes from FASTMCP_TRANSPORT; the Gateway injects http
