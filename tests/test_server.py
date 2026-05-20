from workspace_mcp.server import create_server

def test_create_server() -> None:
    server = create_server("test-server")
    assert server.name == "test-server"
