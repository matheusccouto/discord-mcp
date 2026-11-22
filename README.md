# discord-mcp

Discord's REST API as an MCP server. The tools are generated from Discord's official
OpenAPI spec, so they follow the API instead of drifting from it, and whole path
families are cut away so the tool list stays usable by a model.

## Tools

The default surface is two families: `/channels` (50 operations) and `/users` (12).
Guilds, applications, webhooks, invites and lobbies stay out.

Change it with `DISCORD_FAMILIES`, comma separated. Family is the first segment of the
route, so `/channels/{channel_id}/messages` belongs to `channels`:

```bash
DISCORD_FAMILIES=channels,users
```

An unknown family fails the build and lists the available ones, so a typo cannot
quietly produce a server with no tools. `guilds` is a valid family name but currently
fails the parser: Discord's spec ships empty enums under `/guilds/{guild_id}/requests`
that FastMCP's validator rejects.

The spec is vendored in `discord-openapi.json`, taken from
[discord/discord-api-spec](https://github.com/discord/discord-api-spec). To refresh it,
replace the file; the filter runs at startup.

## Run locally

```bash
uv sync
DISCORD_BOT_TOKEN=... uv run fastmcp run fastmcp.json --transport http
```

`fastmcp.json` is the project entry: `server.py`, object `mcp`, environment from
`pyproject.toml` through uv. `uv run fastmcp inspect fastmcp.json` lists the tools
without calling Discord.

## Checks

```bash
uv run pytest             # 7 tests, no network
uvx ruff check .          # every ruff rule, four documented ignores
uvx ruff format --check .
uvx ty check
```

## Deploy on FastMCP Gateway

Point the Gateway at this repository and set the environment:

- `DISCORD_BOT_TOKEN` — Secret, the bot token
- `DISCORD_FAMILIES` — optional, defaults to `channels,users`

The Gateway serves it over HTTPS behind OAuth: a client connects with the URL and
signs in with the Gateway account, so the endpoint is authenticated without any auth
code here. The bot token is the credential for Discord; it never leaves the
environment.

## Bot setup

1. Create an application at <https://discord.com/developers/applications> and add a bot.
2. Grant View Channels, Send Messages and Read Message History. The bot reaches every
   channel those permissions allow; deny a channel with an overwrite to keep it out of
   reach.
3. Copy the token into the Gateway environment.

## Reuse

Each person runs their own copy with their own bot: fork or clone, deploy on the
Gateway, set `DISCORD_BOT_TOKEN`. There is no shared credential to hand out.
