import asyncio
import json
from pathlib import Path
import pytest
from workspace_mcp.server import create_server, run_server

@pytest.mark.asyncio
async def test_mcp_handshake_real() -> None:
    socket_path = Path("/tmp/test_mcp_handshake.sock")
    server = create_server("test-server")

    # Run the server in the background
    server_task = asyncio.create_task(run_server(server, str(socket_path)))

    # Wait for the socket to be created
    for _ in range(10):
        if socket_path.exists():
            break
        await asyncio.sleep(0.1)

    assert socket_path.exists(), "Server socket was not created"

    try:
        # Connect to the UDS server
        reader, writer = await asyncio.open_unix_connection(str(socket_path))

        # Send initialize request
        req = {
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
        writer.write(json.dumps(req).encode() + b"\n")
        await writer.drain()

        # Read response
        response_line = await reader.readline()
        assert response_line, "No response received from server"

        res = json.loads(response_line.decode())
        assert res.get("jsonrpc") == "2.0"
        assert res.get("id") == 1
        assert "result" in res
        assert res["result"]["serverInfo"]["name"] == "test-server"

        # Send initialized notification
        notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        writer.write(json.dumps(notif).encode() + b"\n")
        await writer.drain()

        # Close client connection
        writer.close()
        await writer.wait_closed()

    finally:
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
        if socket_path.exists():
            socket_path.unlink()

