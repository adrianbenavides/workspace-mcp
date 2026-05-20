import asyncio
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool

def create_server(name: str) -> Server:
    """Creates and configures the MCP server instance.

    Args:
        name: The name of the server.

    Returns:
        A configured Server instance.
    """
    server = Server(name)

    @server.list_tools() # type: ignore
    async def handle_list_tools() -> list[Tool]:
        """List available tools."""
        return [
            Tool(
                name="read_isolated_file",
                description="Read a file from the secure sandbox.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path to the file in the sandbox."}
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="execute_job",
                description="Execute a whitelisted shell command.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The whitelisted command to execute."},
                        "args": {"type": "array", "items": {"type": "string"}, "description": "Arguments for the command."}
                    },
                    "required": ["command"],
                },
            ),
        ]

    return server

async def run_server(server: Server, socket_path: str) -> None:
    """Runs the MCP server using a Unix Domain Socket transport.

    Args:
        server: The MCP server instance to run.
        socket_path: The path to the Unix Domain Socket.
    """
    path = Path(socket_path)
    if path.exists():
        path.unlink()

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handles a single client connection."""
        # Note: In a real implementation, we'd use mcp server's connection handling.
        # For now, we'll use a placeholder that matches the SDK's transport expectations.
        # This is a bit complex due to how the SDK handles transports.
        # Usually we'd use mcp.server.stdio.run_server for stdio.
        # For UDS, we'd need a custom transport implementation.
        # Let's start with the socket setup first to satisfy the test.
        pass

    srv = await asyncio.start_unix_server(handle_client, socket_path)
    
    try:
        async with srv:
            await srv.serve_forever()
    except asyncio.CancelledError:
        pass
    finally:
        if path.exists():
            path.unlink()
