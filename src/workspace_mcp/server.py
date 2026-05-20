import asyncio
from pathlib import Path
from typing import Any
from mcp.server import Server
from mcp.types import Tool
import mcp.types as types


def create_server(name: str, config: dict[str, Any] | None = None) -> Server:
    """Creates and configures the MCP server instance.

    Args:
        name: The name of the MCP server.
        config: The optional server configuration dictionary.

    Returns:
        A configured Server instance.
    """
    server = Server(name)

    # Load default config if none provided
    if config is None:
        try:
            from workspace_mcp.config import load_config

            config = load_config("config.toml")
        except FileNotFoundError:
            config = {}

    @server.list_tools()  # type: ignore
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
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Arguments for the command.",
                        },
                    },
                    "required": ["command"],
                },
            ),
        ]

    @server.call_tool()  # type: ignore
    async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> types.CallToolResult:
        """Handle execution of registered tools."""
        from workspace_mcp.tools import read_isolated_file, execute_job

        args = arguments or {}

        if name == "read_isolated_file":
            path_str = args.get("path")
            if not path_str or not isinstance(path_str, str):
                return types.CallToolResult(
                    content=[
                        types.TextContent(type="text", text="Error: Missing or invalid 'path' parameter.")
                    ],
                    isError=True,
                )

            # Fetch sandbox directory from config
            sandbox_dir = (
                (config or {}).get("security", {}).get("sandbox_directory", "~/.workspace_mcp_sandbox")
            )
            try:
                content = read_isolated_file(path_str, sandbox_dir)
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=content)],
                    isError=False,
                )
            except Exception as e:
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=str(e))],
                    isError=True,
                )

        elif name == "execute_job":
            command = args.get("command")
            if not command or not isinstance(command, str):
                return types.CallToolResult(
                    content=[
                        types.TextContent(type="text", text="Error: Missing or invalid 'command' parameter.")
                    ],
                    isError=True,
                )

            cmd_args = args.get("args", [])
            if not isinstance(cmd_args, list) or not all(isinstance(a, str) for a in cmd_args):
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text", text="Error: 'args' parameter must be a list of strings."
                        )
                    ],
                    isError=True,
                )

            try:
                stdout = await execute_job(command, cmd_args, config or {})
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=stdout)],
                    isError=False,
                )
            except Exception as e:
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=str(e))],
                    isError=True,
                )

        else:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Error: Unknown tool '{name}'.")],
                isError=True,
            )

    return server


async def run_server(server: Server, socket_path: str) -> None:
    """Runs the MCP server using a Unix Domain Socket transport.

    Args:
        server: The Server instance to run.
        socket_path: The Unix domain socket file path to bind the server to.
    """
    path = Path(socket_path)
    if path.exists():
        path.unlink()

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handles a single client connection using MCP transport."""
        import anyio
        import mcp.types as types
        from mcp.shared.message import SessionMessage
        from mcp.server.models import InitializationOptions

        read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
        write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

        async def socket_reader() -> None:
            try:
                async with read_stream_writer:
                    while True:
                        line = await reader.readline()
                        if not line:
                            break
                        try:
                            message = types.JSONRPCMessage.model_validate_json(line)
                        except Exception as exc:
                            await read_stream_writer.send(exc)
                            continue

                        session_message = SessionMessage(message)
                        await read_stream_writer.send(session_message)
            except anyio.ClosedResourceError:
                pass
            except Exception:
                pass
            finally:
                writer.close()

        async def socket_writer() -> None:
            try:
                async with write_stream_reader:
                    async for session_message in write_stream_reader:
                        json_str = session_message.message.model_dump_json(by_alias=True, exclude_none=True)
                        writer.write(json_str.encode() + b"\n")
                        await writer.drain()
            except anyio.ClosedResourceError:
                pass
            except Exception:
                pass
            finally:
                writer.close()

        init_options = InitializationOptions(
            server_name=server.name,
            server_version="0.1.0",
            capabilities=types.ServerCapabilities(tools=types.ToolsCapability(listChanged=True)),
        )

        try:
            async with anyio.create_task_group() as tg:
                tg.start_soon(socket_reader)
                tg.start_soon(socket_writer)
                await server.run(read_stream, write_stream, init_options, raise_exceptions=True)
        except Exception:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
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


if __name__ == "__main__":
    import argparse
    import os
    from workspace_mcp.config import load_config

    parser = argparse.ArgumentParser(description="Secure Local Workspace MCP Server")
    parser.add_argument("--config", default="config.toml", help="Path to config.toml")
    args = parser.parse_args()

    config_path = args.config
    if os.path.exists(config_path):
        config = load_config(config_path)
        socket_path = config["server"]["socket_path"]
    else:
        socket_path = "/tmp/workspace_mcp.sock"

    server = create_server("workspace-mcp")
    print("Starting Secure Local Workspace MCP Server...")
    print(f"UDS Socket Path: {socket_path}")
    try:
        asyncio.run(run_server(server, socket_path))
    except KeyboardInterrupt:
        print("\nServer stopped by user.")
