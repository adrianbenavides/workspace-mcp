import os
import re
import asyncio
from pathlib import Path
from typing import Any


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
            pass
        curr = curr.parent

    # 5. Read and return file contents
    try:
        return resolved_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found inside sandbox: {path_str}")


async def execute_job(command_name: str, args: list[str], config: dict[str, Any]) -> str:
    """Executes a whitelisted command in a secure, isolated sandbox environment.

    Args:
        command_name: The whitelisted command name.
        args: The arguments passed to the command.
        config: The parsed server configuration dictionary.

    Returns:
        The standard output of the executed process.

    Raises:
        ValueError: If the command is not whitelisted or arguments do not match
                    configured whitelist regexes.
        TimeoutError: If the process execution exceeds the configured timeout.
    """
    # 1. Binary Lookup and Whitelist Matching
    execution_config = config.get("execution", {})
    allowed_commands = execution_config.get("allowed_commands", [])

    matched_cmd = None
    for cmd in allowed_commands:
        if cmd.get("name") == command_name:
            matched_cmd = cmd
            break

    if not matched_cmd:
        raise ValueError(f"Access denied: command '{command_name}' is not whitelisted.")

    binary_path = matched_cmd.get("binary")
    if not binary_path:
        raise ValueError(f"Access denied: no binary path defined for '{command_name}'.")

    # 2. Argument Verification
    allowed_regexes = matched_cmd.get("allowed_arguments_regex", [])

    if not allowed_regexes:
        # Strictly reject if any arguments are passed but none are allowed
        if args:
            raise ValueError(f"Access denied: Argument rejection for '{args[0]}'. No arguments allowed.")
    else:
        # Check every argument against the whitelisted regex patterns
        for arg in args:
            matched = False
            for pattern in allowed_regexes:
                if re.match(pattern, arg):
                    matched = True
                    break
            if not matched:
                raise ValueError(
                    f"Access denied: Argument rejection for '{arg}'. Does not match allowed patterns."
                )

    # 3. Environment Sanitization
    # Only keep basic safe system path defaults, completely clearing standard host environment
    cleaned_env = {"PATH": "/bin:/usr/bin:/sbin:/usr/sbin"}

    # 4. Timeout Configuration
    default_timeout = execution_config.get("default_timeout_seconds", 30.0)
    timeout = matched_cmd.get("timeout_seconds", default_timeout)

    # 5. Async Subprocess Spawning
    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            binary_path,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=cleaned_env,
        )

        # Wait for the subprocess with timeout
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        if proc.returncode != 0:
            # Return stderr output combined or just decoded stdout.
            # Our tests expect stdout or standard returned command outputs.
            return stdout.decode(errors="replace")

        return stdout.decode(errors="replace")

    except asyncio.TimeoutError:
        if proc:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
        raise TimeoutError(f"Command '{command_name}' timed out after {timeout} seconds.")
    except Exception as e:
        if proc:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
        raise e
