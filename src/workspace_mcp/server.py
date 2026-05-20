import asyncio
from pathlib import Path
from mcp.server import Server
from mcp.types import Tool

def create_server(name: str) -> Server:
    """Creates and configures the MCP server instance."""
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
    """Runs the MCP server using a Unix Domain Socket transport."""
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
            capabilities=types.ServerCapabilities(
                tools=types.ToolsCapability(listChanged=True)
            )
        )

        try:
            async with anyio.create_task_group() as tg:
                tg.start_soon(socket_reader)
                tg.start_soon(socket_writer)
                await server.run(
                    read_stream,
                    write_stream,
                    init_options,
                    raise_exceptions=True
                )
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
