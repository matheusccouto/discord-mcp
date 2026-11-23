"""Tests for the tool surface, the schema cleaning and one Discord request."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx2
from fastmcp import Client

import server

if TYPE_CHECKING:
    import pytest

# 50 operations under /channels and 12 under /users, less the six DENIED ones.
TOOL_COUNT = 56


def idle_client() -> httpx2.AsyncClient:
    """Return a client a test never calls; build() only needs something to hold."""
    return httpx2.AsyncClient(base_url=server.API)


def test_family_is_the_first_segment() -> None:
    """Read the family from the first segment, whatever comes after it."""
    assert server.family("/channels/123/messages") == "channels"
    assert server.family("/users/@me/guilds") == "users"


def test_clean_drops_the_keywords_gemini_refuses() -> None:
    """Turn const into enum, drop additionalProperties, keep numbers in 32 bits."""
    dirty = json.loads(
        """
        {
          "additionalProperties": false,
          "properties": {
            "action": {"const": "approve"},
            "color": {"type": "integer", "maximum": 4294967295.0}
          }
        }
        """
    )

    cleaned = json.dumps(server.clean(dirty))

    assert "additionalProperties" not in cleaned
    assert '"enum": ["approve"]' in cleaned
    assert f'"maximum": {2**31 - 1}' in cleaned


async def test_serves_the_default_families() -> None:
    """Expose channels and users, and nothing from the other families."""
    async with Client(server.mcp) as client:
        names = {tool.name for tool in await client.list_tools()}

    assert len(names) == TOOL_COUNT
    assert "create_message" in names
    assert "get_guild" not in names


async def test_leaves_the_dangerous_operations_out() -> None:
    """Refuse the tools a message could talk the model into using against the user."""
    async with Client(server.mcp) as client:
        names = {tool.name for tool in await client.list_tools()}

    assert not names & server.DENIED


async def test_narrower_surface_drops_the_other_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Answer a narrower DISCORD_FAMILIES with fewer tools."""
    monkeypatch.setenv("DISCORD_FAMILIES", "users")

    async with Client(server.build(idle_client())) as client:
        names = {tool.name for tool in await client.list_tools()}

    assert "get_my_user" in names
    assert "create_message" not in names


async def test_create_message_posts_to_the_channel() -> None:
    """Send the tool call to Discord as a POST on the channel's message route."""
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"id": "42", "content": "oi"})

    client = httpx2.AsyncClient(
        transport=httpx2.MockTransport(handler), base_url=server.API
    )

    async with Client(server.build(client)) as mcp_client:
        await mcp_client.call_tool(
            "create_message", {"channel_id": "999", "content": "oi"}
        )

    assert seen["method"] == "POST"
    assert seen["url"] == f"{server.API}/channels/999/messages"
    assert seen["body"] == {"content": "oi"}


def test_login_is_off_without_github_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leave a deployment without GitHub credentials unguarded by this provider."""
    monkeypatch.delenv("GITHUB_CLIENT_ID", raising=False)

    assert server.login() is None
