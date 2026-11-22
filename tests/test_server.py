"""Tests for the OpenAPI surface and for how a tool call reaches Discord."""

import json

import httpx2
import pytest
from fastmcp import Client

import server

# 50 operations under /channels plus 12 under /users in the vendored spec.
DEFAULT_TOOL_COUNT = 62

# Every field MessageResponse marks as required, so FastMCP's output validation
# accepts the fake reply instead of failing before the request is inspected.
DISCORD_MESSAGE = {
    "id": "42",
    "channel_id": "999",
    "content": "oi",
    "timestamp": "2026-11-22T18:00:00.000000+00:00",
    "edited_timestamp": None,
    "tts": False,
    "mention_everyone": False,
    "mentions": [],
    "mention_roles": [],
    "attachments": [],
    "embeds": [],
    "components": [],
    "pinned": False,
    "type": 0,
    "flags": 0,
    "author": {
        "id": "1",
        "username": "clawdinhobot",
        "avatar": None,
        "discriminator": "0",
        "public_flags": 0,
        "flags": 0,
        "global_name": None,
        "primary_guild": None,
    },
}


def unused_client() -> httpx2.AsyncClient:
    """Return a client a test never calls; build() only needs something to hold."""
    return httpx2.AsyncClient(base_url=server.API_ROOT)


def test_family_of_uses_the_first_segment() -> None:
    """Read the family from the first segment, whatever comes after it."""
    assert server.family_of("/channels/123/messages") == "channels"
    assert server.family_of("/users/@me/guilds") == "users"


def test_defaults_to_channels_and_users(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fall back to the two default families when the variable is unset."""
    monkeypatch.delenv("DISCORD_FAMILIES", raising=False)

    assert server.families() == ["channels", "users"]


def test_default_families_exist_in_the_spec() -> None:
    """Catch a vendored spec that lost a family the default points at."""
    available = {server.family_of(route) for route in server.read_spec()["paths"]}

    assert {"channels", "users"} <= available


def test_filtered_drops_every_other_family() -> None:
    """Keep the chosen family and drop the routes of every other one."""
    spec = server.filtered(server.read_spec(), ["users"])

    assert {server.family_of(route) for route in spec["paths"]} == {"users"}
    assert "/channels/{channel_id}/messages" not in spec["paths"]


def test_missing_token_refuses_to_build(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse to start without a bot token, rather than fail on the first call."""
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)

    with pytest.raises(KeyError, match="DISCORD_BOT_TOKEN"):
        server.bot_token()


async def test_create_message_posts_to_the_channel() -> None:
    """Send the tool call to Discord as a POST on the channel's message route."""
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json=DISCORD_MESSAGE)

    client = httpx2.AsyncClient(
        transport=httpx2.MockTransport(handler), base_url=server.API_ROOT
    )

    async with Client(server.build(client)) as mcp_client:
        await mcp_client.call_tool(
            "create_message", {"channel_id": "999", "content": "oi"}
        )

    assert seen["method"] == "POST"
    assert seen["url"] == f"{server.API_ROOT}/channels/999/messages"
    assert seen["body"] == {"content": "oi"}


async def test_deployed_server_exposes_the_default_families() -> None:
    """Serve the two default families on the object the Gateway loads."""
    async with Client(server.mcp) as mcp_client:
        names = {tool.name for tool in await mcp_client.list_tools()}

    assert "create_message" in names
    assert len(names) == DEFAULT_TOOL_COUNT
    assert "get_guild" not in names
    assert "execute_webhook" not in names


async def test_narrower_surface_drops_the_other_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Answer a narrower DISCORD_FAMILIES with fewer tools."""
    monkeypatch.setenv("DISCORD_FAMILIES", "users")

    async with Client(server.build(unused_client())) as mcp_client:
        names = {tool.name for tool in await mcp_client.list_tools()}

    assert "get_my_user" in names
    assert "create_message" not in names
