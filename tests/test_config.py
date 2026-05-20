import pytest
from workspace_mcp.config import load_config

def test_load_config_valid(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("""
[server]
socket_path = "/tmp/test.sock"

[security]
sandbox_directory = "~/test_sandbox"
""")
    config = load_config(str(config_file))
    assert config["server"]["socket_path"] == "/tmp/test.sock"
    assert config["security"]["sandbox_directory"] == "~/test_sandbox"

def test_load_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config("non_existent.toml")
