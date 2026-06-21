"""Bridge MCP tools to OpenAI/Anthropic function-calling format."""

import inspect
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _python_type_to_json_schema(annotation) -> dict:
    """Convert a Python type annotation to a JSON Schema fragment."""
    if annotation is inspect.Parameter.empty:
        return {"type": "string"}

    origin = getattr(annotation, "__origin__", None)
    if origin is list:
        args = getattr(annotation, "__args__", [])
        item_type = _python_type_to_json_schema(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": item_type}
    if origin is dict:
        return {"type": "object"}

    # Handle Optional[X] (Union[X, None])
    annotation_str = str(annotation)
    if "Optional" in annotation_str or "None" in annotation_str:
        args = getattr(annotation, "__args__", [])
        if args:
            # Get the first non-None type
            for arg in args:
                if arg is not type(None):
                    return _python_type_to_json_schema(arg)

    return {"type": _TYPE_MAP.get(annotation, "string")}


def build_openai_tools_from_mcp(mcp_instance) -> list[dict]:
    """Extract tool definitions from FastMCP instance into OpenAI tools format."""
    tools = []
    tool_manager = getattr(mcp_instance, "_tool_manager", None)
    if not tool_manager:
        return tools

    registered_tools = getattr(tool_manager, "_tools", {})
    for name, tool_def in registered_tools.items():
        func = getattr(tool_def, "fn", None) or getattr(tool_def, "func", None)
        if not func:
            continue

        sig = inspect.signature(func)
        description = (tool_def.description or func.__doc__ or "").strip()

        properties = {}
        required = []
        for param_name, param in sig.parameters.items():
            prop = _python_type_to_json_schema(param.annotation)
            properties[param_name] = prop
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        tool_schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description[:1024],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                },
            },
        }
        if required:
            tool_schema["function"]["parameters"]["required"] = required

        tools.append(tool_schema)

    return tools


def convert_to_anthropic_tools(openai_tools: list[dict]) -> list[dict]:
    """Convert OpenAI tool format to Anthropic tool format."""
    anthropic_tools = []
    for t in openai_tools:
        func = t.get("function", {})
        anthropic_tools.append({
            "name": func["name"],
            "description": func.get("description", ""),
            "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
        })
    return anthropic_tools


async def execute_mcp_tool(mcp_instance, tool_name: str, arguments: dict) -> str:
    """Execute an MCP tool by name with given arguments. Returns JSON string."""
    tool_manager = getattr(mcp_instance, "_tool_manager", None)
    if not tool_manager:
        return json.dumps({"error": "Tool manager not available"})

    registered_tools = getattr(tool_manager, "_tools", {})
    tool_def = registered_tools.get(tool_name)
    if not tool_def:
        return json.dumps({"error": f"Tool '{tool_name}' not found"})

    func = getattr(tool_def, "fn", None) or getattr(tool_def, "func", None)
    if not func:
        return json.dumps({"error": f"Tool '{tool_name}' has no callable function"})

    try:
        result = await func(**arguments)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error("MCP tool '%s' execution error: %s", tool_name, e)
        return json.dumps({"error": str(e)})
