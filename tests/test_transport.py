import pytest
import asyncio
from pathlib import Path
from workspace_mcp.server import create_server, run_server


@pytest.mark.asyncio
async def test_run_server_creates_socket() -> None:
    # Use a shorter path for AF_UNIX
    socket_path = Path("/tmp/test_mcp_uds.sock")
    server = create_server("test-server")

    # Run the server in the background
    task = asyncio.create_task(run_server(server, str(socket_path)))

    # Wait a bit for the socket to be created
    for _ in range(10):
        if socket_path.exists():
            break
        await asyncio.sleep(0.1)

    try:
        assert socket_path.exists()
    finally:
        # Stop the server
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Check for cleanup
        assert not socket_path.exists()
