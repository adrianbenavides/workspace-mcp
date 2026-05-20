import asyncio
import sys
from workspace_mcp.config import load_config

async def run_client(socket_path: str) -> None:
    """Connects to the MCP server via UDS and performs a basic handshake.

    Args:
        socket_path: The path to the Unix Domain Socket.
    """
    print(f"Connecting to {socket_path}...")
    try:
        reader, writer = await asyncio.open_unix_connection(socket_path)
        print("Connected!")
        # Basic MCP init would go here
        writer.close()
        await writer.wait_closed()
        print("Connection closed.")
    except Exception as e:
        print(f"Failed to connect: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import os
    config_path = "config.toml"
    if os.path.exists(config_path):
        config = load_config(config_path)
        socket_path = config["server"]["socket_path"]
    else:
        socket_path = "/tmp/workspace_mcp.sock"
    
    asyncio.run(run_client(socket_path))
