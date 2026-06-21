"""Stdio MCP server entry point for Claude Desktop / Cursor / Windsurf.

Configure in Claude Desktop settings (~/.claude/claude_desktop_config.json):
{
  "mcpServers": {
    "knowledge-base": {
      "command": "python",
      "args": ["-m", "app.mcp.stdio_server"],
      "cwd": "/path/to/backend"
    }
  }
}
"""

import asyncio
import sys
import os

# Ensure the backend directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.mcp.server import mcp


def main():
    """Entry point for stdio MCP transport."""
    asyncio.run(mcp.run(transport="stdio"))


if __name__ == "__main__":
    main()
