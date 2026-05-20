import pytest
from workspace_mcp.config import load_config


def test_load_config_valid(tmp_path: pytest.TempPathFactory) -> None:
    # Use any because pytest.TempPathFactory is a factory, but tmp_path fixture is Path
    config_file = tmp_path / "config.toml"  # type: ignore
    config_file.write_text("""
[server]
socket_path = "/tmp/test.sock"

[security]
sandbox_directory = "~/test_sandbox"
""")
    config = load_config(str(config_file))
    assert config["server"]["socket_path"] == "/tmp/test.sock"
    assert config["security"]["sandbox_directory"] == "~/test_sandbox"


def test_load_config_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        load_config("non_existent.toml")
