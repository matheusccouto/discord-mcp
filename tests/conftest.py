"""Set the environment before any test module imports the server.

``server.py`` builds its MCP object at import, and the build refuses to run without
a bot token, so the token has to exist first.
"""

import os

os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
