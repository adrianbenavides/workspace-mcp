import asyncio
import json
import sys
from workspace_mcp.config import load_config

async def run_client(socket_path: str) -> None:
    """Connects to the MCP server via UDS and performs a basic handshake."""
    print(f"Connecting to {socket_path}...")
    try:
        reader, writer = await asyncio.open_unix_connection(socket_path)
        print("Connected!")
        
        # 1. Send initialize request
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        print("Sending initialize request...")
        writer.write(json.dumps(init_req).encode() + b"\n")
        await writer.drain()

        # Read initialize response
        line = await reader.readline()
        if not line:
            print("Server closed connection prematurely.")
            return
        
        init_res = json.loads(line.decode())
        print(f"Initialize Response: {json.dumps(init_res, indent=2)}")
        
        # 2. Send initialized notification
        init_notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        print("Sending initialized notification...")
        writer.write(json.dumps(init_notif).encode() + b"\n")
        await writer.drain()
        
        # 3. Send tools/list request
        list_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }
        print("Sending tools/list request...")
        writer.write(json.dumps(list_req).encode() + b"\n")
        await writer.drain()

        # Read tools/list response
        line = await reader.readline()
        if not line:
            print("Server closed connection prematurely during tools list.")
            return
        
        list_res = json.loads(line.decode())
        print(f"Tools List Response: {json.dumps(list_res, indent=2)}")
        
        writer.close()
        await writer.wait_closed()
        print("Connection closed.")
    except Exception as e:
        print(f"Failed to connect or perform handshake: {e}")
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
