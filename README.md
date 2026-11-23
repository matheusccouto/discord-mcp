# discord-mcp

Discord's REST API as an MCP server, generated from
[Discord's OpenAPI spec](https://github.com/discord/discord-api-spec).

## Surface

`/channels` and `/users` only: 62 tools. Everything else — guilds, applications,
webhooks, invites — stays out. Change the families with `DISCORD_FAMILIES`, comma
separated; the first segment of a route is its family.

## Run

```bash
cp .env.example .env     # set DISCORD_BOT_TOKEN
uv sync
uv run --env-file .env fastmcp run fastmcp.json --transport http
```

## Deploy

`server.py` exports `app = mcp.http_app()`, and the transport answers at `/mcp`, so
any ASGI host serves it. On Vercel, leave Build Command and Install Command empty.

Point [FastMCP Gateway](https://gofastmcp.com/docs/deployment/fastmcp-gateway) at this
repository and set `DISCORD_BOT_TOKEN` as a secret. The Gateway serves it over HTTPS
behind OAuth, so a client connects by URL and signs in with the Gateway account. The
bot token stays in the environment.

The bot needs View Channels, Send Messages and Read Message History. It reaches every
channel those permissions allow.
