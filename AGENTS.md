# discord-mcp

## Commands

- `uv run fastmcp inspect fastmcp.json`: list the exposed tools without calling Discord.
- `env -u PYTHONPATH uv run --project . pytest`: 7 tests, no network. The ambient
  `PYTHONPATH` points at another venv and shadows this one's `mcp`.
- `uvx ruff check .` and `uvx ruff format --check .`
- `uvx ty check`

## References

Fetch these before guessing at an API; each is what the tool itself publishes.

- FastMCP: <https://gofastmcp.com/llms.txt>
- FastMCP Gateway: <https://docs.horizon.prefect.io/llms.txt>
- uv: <https://docs.astral.sh/uv/llms.txt>
- ruff: <https://docs.astral.sh/ruff/llms.txt>
- ty: <https://docs.astral.sh/ty/llms.txt>
- Discord: no llms.txt. The machine-readable source is the OpenAPI spec at
  <https://github.com/discord/discord-api-spec>, vendored here as
  `discord-openapi.json`.
