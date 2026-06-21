"""MCP server exposing knowledge base tools over SSE and stdio transports.

SSE transport: mounted at /mcp on the FastAPI app (main.py)
Stdio transport: run `python -m app.mcp.stdio_server`
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "knowledge-base",
    instructions=(
        "Knowledge base management system. Use these tools to search, read, create, "
        "update, and analyze documents. Supports semantic search, knowledge graph "
        "exploration, folder/tag management, and AI-powered document analysis. "
        "Documents created via MCP are saved as drafts for human review."
    ),
)

# Import tools, resources, and prompts to register them
from app.mcp.tools import search, read, write, analyze, graph, folders  # noqa: F401
from app.mcp import resources, prompts  # noqa: F401
