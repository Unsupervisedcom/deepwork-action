#!/usr/bin/env python3
"""
Merge the deepwork MCP server entry into an existing .mcp.json file.

Usage: python3 merge-mcp-config.py <path-to-mcp.json>

Reads the JSON file, adds/replaces the 'deepwork' entry under 'mcpServers',
and writes the result back to the same file.
"""
import json
import sys
from pathlib import Path

mcp_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".mcp.json")

existing: dict = {}
if mcp_path.exists():
    try:
        existing = json.loads(mcp_path.read_text())
    except json.JSONDecodeError:
        existing = {}

existing.setdefault("mcpServers", {})["deepwork"] = {
    "command": "uvx",
    "args": ["deepwork", "serve", "--platform", "claude"],
}

mcp_path.write_text(json.dumps(existing, indent=2) + "\n")
print(f"Written {mcp_path}")
