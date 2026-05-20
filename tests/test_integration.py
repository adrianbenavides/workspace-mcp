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
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
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
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
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


@pytest.mark.asyncio
async def test_integration_read_isolated_file(tmp_path: Path) -> None:
    # Setup sandbox
    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()

    # Create target file
    target_file = sandbox_dir / "integration_test.txt"
    target_file.write_text("secure integration content")

    socket_path = Path("/tmp/test_mcp_read_isolated.sock")
    config = {
        "server": {"socket_path": str(socket_path)},
        "security": {"sandbox_directory": str(sandbox_dir)},
    }

    server = create_server("test-server", config=config)
    server_task = asyncio.create_task(run_server(server, str(socket_path)))

    # Wait for the socket to be created
    for _ in range(10):
        if socket_path.exists():
            break
        await asyncio.sleep(0.1)

    assert socket_path.exists(), "Server socket was not created"

    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))

        # Perform handshake first
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }
        writer.write(json.dumps(init_req).encode() + b"\n")
        await writer.drain()
        await reader.readline()

        notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        writer.write(json.dumps(notif).encode() + b"\n")
        await writer.drain()

        # Call tool: read_isolated_file success case
        tool_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "read_isolated_file", "arguments": {"path": "integration_test.txt"}},
        }
        writer.write(json.dumps(tool_req).encode() + b"\n")
        await writer.drain()

        resp_line = await reader.readline()
        res = json.loads(resp_line.decode())

        # Verify success response
        assert "result" in res, f"Expected 'result' in response, got: {res}"
        result = res["result"]
        assert result.get("isError") is False
        assert len(result.get("content", [])) == 1
        assert result["content"][0]["text"] == "secure integration content"

        # Call tool: read_isolated_file failure case (path traversal)
        tool_fail_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "read_isolated_file", "arguments": {"path": "../outside.txt"}},
        }
        writer.write(json.dumps(tool_fail_req).encode() + b"\n")
        await writer.drain()

        resp_line_fail = await reader.readline()
        res_fail = json.loads(resp_line_fail.decode())

        # Verify failure response
        assert "result" in res_fail
        assert res_fail["result"].get("isError") is True
        assert "Access denied" in res_fail["result"]["content"][0]["text"]

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


@pytest.mark.asyncio
async def test_integration_execute_job(tmp_path: Path) -> None:
    socket_path = Path("/tmp/test_mcp_execute_job.sock")
    config = {
        "server": {"socket_path": str(socket_path)},
        "execution": {
            "default_timeout_seconds": 2.0,
            "allowed_commands": [
                {"name": "echo", "binary": "/bin/echo", "allowed_arguments_regex": ["^[a-zA-Z0-9_! -]+$"]}
            ],
        },
    }

    server = create_server("test-server", config=config)
    server_task = asyncio.create_task(run_server(server, str(socket_path)))

    # Wait for the socket to be created
    for _ in range(10):
        if socket_path.exists():
            break
        await asyncio.sleep(0.1)

    assert socket_path.exists(), "Server socket was not created"

    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))

        # Perform handshake first
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }
        writer.write(json.dumps(init_req).encode() + b"\n")
        await writer.drain()
        await reader.readline()

        notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        writer.write(json.dumps(notif).encode() + b"\n")
        await writer.drain()

        # Call tool: execute_job success case
        tool_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "execute_job",
                "arguments": {"command": "echo", "args": ["hello-integration"]},
            },
        }
        writer.write(json.dumps(tool_req).encode() + b"\n")
        await writer.drain()

        resp_line = await reader.readline()
        res = json.loads(resp_line.decode())

        # Verify success response
        assert "result" in res, f"Expected 'result' in response, got: {res}"
        result = res["result"]
        assert result.get("isError") is False
        assert len(result.get("content", [])) == 1
        assert result["content"][0]["text"].strip() == "hello-integration"

        # Call tool: execute_job failure case (not whitelisted)
        tool_fail_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "execute_job", "arguments": {"command": "cat", "args": ["config.toml"]}},
        }
        writer.write(json.dumps(tool_fail_req).encode() + b"\n")
        await writer.drain()

        resp_line_fail = await reader.readline()
        res_fail = json.loads(resp_line_fail.decode())

        # Verify failure response
        assert "result" in res_fail
        assert res_fail["result"].get("isError") is True
        assert "not whitelisted" in res_fail["result"]["content"][0]["text"]

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
