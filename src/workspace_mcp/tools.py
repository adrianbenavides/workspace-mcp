import os
from pathlib import Path

def read_isolated_file(path_str: str, sandbox_dir_str: str) -> str:
    """Reads a file from the secure sandbox, enforcing path traversal and symlink checks.

    Args:
        path_str: The relative path to the file inside the sandbox.
        sandbox_dir_str: The path to the secure sandbox directory.

    Returns:
        The content of the file as a string.

    Raises:
        ValueError: If the path is outside the sandbox, is a symbolic link,
                    or contains any symbolic links in its components.
    """
    # 1. Expand and resolve the sandbox directory
    sandbox_path = Path(os.path.expanduser(sandbox_dir_str)).resolve()

    # 2. Treat target path
    # If the user passed an absolute path, prevent traversal attempt
    # Resolve the combined path to canonical form
    raw_target_path = Path(os.path.expanduser(path_str))
    
    if raw_target_path.is_absolute():
        # Absolute path traversal check
        raise ValueError("Access denied: absolute path escape attempted.")

    combined_path = sandbox_path / raw_target_path
    resolved_path = combined_path.resolve()

    # 3. Traversal check: Target must be strictly inside the sandbox
    try:
        # Check if the resolved target path starts with the resolved sandbox directory
        resolved_path.relative_to(sandbox_path)
    except ValueError:
        raise ValueError("Access denied: path traversal outside the sandbox directory.")

    # Also, ensure it's not the sandbox directory itself
    if resolved_path == sandbox_path:
        raise ValueError("Access denied: cannot read the sandbox directory itself.")

    # 4. Strict Symlink Check: No component of the target path (nor the target itself)
    # can be a symbolic link. Check from resolved path all the way up to the root.
    curr = resolved_path
    while curr != curr.parent:
        # We use lstat or is_symlink on the actual path to verify if it is a link.
        # Note: resolved_path.resolve() resolves symlinks. But we want to ensure
        # that the user's requested path did not involve *any* symlinks to get here.
        # So we also check the components along the combined_path before resolving,
        # or we check resolved_path elements. Actually, check both to be absolutely safe!
        if curr.is_symlink():
            raise ValueError("Access denied: symbolic links are strictly blocked.")
        curr = curr.parent

    # Check the un-resolved path components as well to prevent symlink-racing
    curr = combined_path
    while curr != sandbox_path and curr != curr.parent:
        try:
            if curr.is_symlink():
                raise ValueError("Access denied: symbolic links are strictly blocked.")
        except FileNotFoundError:
            # If a component doesn't exist, we can't check if it's a symlink, but we will catch
            # FileNotFoundError when we try to read it anyway.
            pass
        curr = curr.parent

    # 5. Read and return file contents
    try:
        return resolved_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found inside sandbox: {path_str}")
