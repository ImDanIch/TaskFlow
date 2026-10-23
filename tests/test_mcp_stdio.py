import asyncio
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_stdio_tools(git_vault):
    vault, _ = git_vault
    async def scenario():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_server.server"],
            cwd=str(Path(__file__).resolve().parents[1]),
            env={**os.environ, "TASKFLOW_KB_PATH": str(vault.root)},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert {tool.name for tool in tools.tools} == {
                    "get_note", "search_notes", "ingest_note",
                }
                for content in ("# MCP test", "# Updated MCP test"):
                    result = await session.call_tool("ingest_note", {
                        "note_path": "Test.md", "content": content,
                    })
                    assert not result.isError
                    assert result.structuredContent["status"] in {"created", "updated"}
                    assert len(result.structuredContent["commit_hash"]) == 40
                    result = await session.call_tool("get_note", {"note_path": "Test.md"})
                    assert not result.isError
                    assert result.content[0].text == content
                result = await session.call_tool("search_notes", {"query": "updated"})
                assert not result.isError
                assert "Test.md" in str(result.content)
                for tool, arguments in [
                    ("get_note", {"note_path": "missing.md"}),
                    ("get_note", {"note_path": "../outside.md"}),
                    ("ingest_note", {"note_path": "../outside.md", "content": "bad"}),
                ]:
                    result = await session.call_tool(tool, arguments)
                    assert result.isError

    async def timed():
        await asyncio.wait_for(scenario(), timeout=60)

    asyncio.run(timed())
