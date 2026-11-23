# discord-mcp

Discord's REST API as an MCP server, generated from
[Discord's OpenAPI spec](https://github.com/discord/discord-api-spec).

## Surface

`/channels` and `/users`: 62 tools. Guilds, applications, webhooks and invites stay
out. Change the families with `DISCORD_FAMILIES`, comma separated; the first segment
of a route is its family.

## Run

```bash
cp .env.example .env     # set DISCORD_BOT_TOKEN
uv sync
uv run --env-file .env fastmcp run fastmcp.json --transport http
```

## Authenticate

Without credentials the server is open, which is what a local run and
[FastMCP Gateway](https://docs.horizon.prefect.io/) want: the Gateway brings its own
OAuth. For a host without one, set these four and every `/mcp` request needs a login:

- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`: an OAuth app whose callback is
  `PUBLIC_URL/auth/callback`
- `JWT_SIGNING_KEY`: `openssl rand -hex 32`
- `PUBLIC_URL`: the deployment origin, no trailing slash

The server then answers as the authorization server for MCP clients: discovery,
dynamic registration, PKCE, and a 401 challenge on every method of `/mcp`.

## Deploy

`server.py` exports `app`, an ASGI app answering at `/mcp`, so any ASGI host serves
it. On Vercel, leave Build Command, Install Command and Output Directory empty.

## Bot permissions

View Channels, Send Messages, Read Message History, and whatever else the tools you
use require. The bot reads exactly the channels those permissions allow.
