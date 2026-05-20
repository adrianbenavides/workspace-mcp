import pytest
import os
from pathlib import Path
from typing import Any
from workspace_mcp.tools import read_isolated_file, execute_job

def test_read_isolated_file_success(tmp_path: Path) -> None:
    # Setup sandbox
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    
    # Create target file
    target_file = sandbox / "test.txt"
    target_file.write_text("hello sandbox")
    
    # Run
    content = read_isolated_file("test.txt", str(sandbox))
    assert content == "hello sandbox"

def test_read_isolated_file_traversal_relative(tmp_path: Path) -> None:
    # Setup sandbox
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    
    # Create file outside
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("secrets")
    
    # Run traversal attempt should raise ValueError
    with pytest.raises(ValueError, match="path traversal|outside the sandbox"):
        read_isolated_file("../outside.txt", str(sandbox))

def test_read_isolated_file_traversal_absolute(tmp_path: Path) -> None:
    # Setup sandbox
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    
    # Attempting to read using absolute path should raise ValueError
    with pytest.raises(ValueError, match="path traversal|outside the sandbox|absolute path"):
        read_isolated_file("/etc/passwd", str(sandbox))

def test_read_isolated_file_symlink_file(tmp_path: Path) -> None:
    # Setup sandbox
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    
    # Create a real file inside sandbox
    real_file = sandbox / "real.txt"
    real_file.write_text("real content")
    
    # Create a symlink to that file inside sandbox
    link_file = sandbox / "link.txt"
    link_file.symlink_to(real_file)
    
    # Reading the symlink should raise ValueError as symlinks are strictly rejected
    with pytest.raises(ValueError, match="symbolic link|symlink"):
        read_isolated_file("link.txt", str(sandbox))

def test_read_isolated_file_symlink_dir(tmp_path: Path) -> None:
    # Setup sandbox
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    
    # Create a directory inside sandbox
    sub_dir = sandbox / "subdir"
    sub_dir.mkdir()
    
    # Create a symlink directory inside sandbox
    link_dir = sandbox / "linkdir"
    link_dir.symlink_to(sub_dir, target_is_directory=True)
    
    # Create a file in subdir
    target = sub_dir / "test.txt"
    target.write_text("hello")
    
    # Attempt to read through symlink directory path should raise ValueError
    with pytest.raises(ValueError, match="symbolic link|symlink"):
        read_isolated_file("linkdir/test.txt", str(sandbox))

@pytest.fixture
def sample_config() -> dict[str, Any]:
    return {
        "execution": {
            "default_timeout_seconds": 2.0,
            "allowed_commands": [
                {
                    "name": "echo",
                    "binary": "/bin/echo",
                    "allowed_arguments_regex": ["^[a-zA-Z0-9_! -]+$"]
                },
                {
                    "name": "ls",
                    "binary": "/bin/ls",
                    "allowed_arguments_regex": ["^-[la]{1,2}$"]
                },
                {
                    "name": "sleep",
                    "binary": "/bin/sleep",
                    "allowed_arguments_regex": ["^[0-9]+$"]
                },
                {
                    "name": "no-args",
                    "binary": "/bin/echo"
                }
            ]
        }
    }

@pytest.mark.asyncio
async def test_execute_job_success(sample_config: dict[str, Any]) -> None:
    output = await execute_job("echo", ["hello"], sample_config)
    assert output.strip() == "hello"

@pytest.mark.asyncio
async def test_execute_job_not_whitelisted(sample_config: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="not whitelisted|not allowed"):
        await execute_job("cat", ["file.txt"], sample_config)

@pytest.mark.asyncio
async def test_execute_job_invalid_args(sample_config: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="Argument rejection|not allowed"):
        await execute_job("echo", ["hello; rm -rf /"], sample_config)

@pytest.mark.asyncio
async def test_execute_job_no_args_configured_rejection(sample_config: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="Argument rejection|no arguments allowed|not allowed"):
        await execute_job("no-args", ["some-arg"], sample_config)

@pytest.mark.asyncio
async def test_execute_job_env_cleaning() -> None:
    config_with_env = {
        "execution": {
            "default_timeout_seconds": 2.0,
            "allowed_commands": [
                {
                    "name": "env",
                    "binary": "/usr/bin/env",
                    "allowed_arguments_regex": ["^$"]
                }
            ]
        }
    }
    os.environ["SECRET_TOKEN_XYZ"] = "extremely_private"
    try:
        output = await execute_job("env", [], config_with_env)
        assert "SECRET_TOKEN_XYZ" not in output
    finally:
        del os.environ["SECRET_TOKEN_XYZ"]

@pytest.mark.asyncio
async def test_execute_job_timeout(sample_config: dict[str, Any]) -> None:
    sample_config["execution"]["default_timeout_seconds"] = 0.1
    with pytest.raises(TimeoutError, match="Command timed out|timed out"):
        await execute_job("sleep", ["2"], sample_config)
