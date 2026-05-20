import pytest
from pathlib import Path
from workspace_mcp.tools import read_isolated_file

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
