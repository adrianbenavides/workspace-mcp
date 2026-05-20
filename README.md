# Secure Local Workspace Model Context Protocol (MCP) Server

A local daemon acting as a Model Context Protocol (MCP) server. It exposes secure, isolated system-level tools to AI agents (MCP Clients). To ensure maximum security and avoid exposing network ports, the daemon communicates exclusively over Unix Domain Sockets (UDS).

See [ARCHITECTURE.md](ARCHITECTURE.md) to learn more about the design.

## ⚙️ Configuration (`config.toml`)

Copy `config.toml.example` to `config.toml` to customize the MCP server:

```bash
cp config.toml.example config.toml
```

### Example Layout
```toml
[server]
socket_path = "/tmp/workspace_mcp.sock"

[security]
sandbox_directory = "~/.workspace_mcp_sandbox"

[execution]
default_timeout_seconds = 30.0

[[execution.allowed_commands]]
name = "ls"
binary = "/bin/ls"
allowed_arguments_regex = ["^-[la]{1,2}$", "^$"]
```

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have `uv` installed. If not, install it using:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Environment Setup
Sync the dependencies and initialize the virtual environment:
```bash
uv sync
```

### 3. Run the demo

Startup the daemon, specifying the configuration:
```bash
PYTHONPATH=src uv run python -m workspace_mcp.server --config config.toml
```

To test the server connection, fetch its tool schemas, and simulate an agent command:
```bash
PYTHONPATH=src uv run python -m workspace_mcp.client
```

To test all the features:
```bash
uv run python demo/test_mcp_interactive.py
```

Observe the raw JSON-RPC response payloads:
- **`test.txt` valid read**: Returns a standard `TextContent` block with `isError=False`.
- **Traversal escapes (`../` and `/etc/passwd`)**: Denied immediately by the server, returning a descriptive `Access denied` message inside `TextContent` with `isError=True`.
- **`echo HelloSecureWorld`**: Returns the standard output with `isError=False`.
- **`cat` command**: Blocked by security validation, returning `Access denied: command 'cat' is not whitelisted` with `isError=True`.
- **Chained malicious args (`hello; rm -rf /`)**: Blocked by regex validations, returning `Argument rejection` with `isError=True`.
- **`sleep 5` command**: Triggers the async subprocess execution timeout (1.0s limit configured for `sleep`), returning `Command 'sleep' timed out after 1.0 seconds` with `isError=True`.

### 4. Development

Run checks (linting and tests):
```bash
uv run poe check
```

Run specific tasks:

```bash
uv run poe lint    # Run ruff check
uv run poe format  # Run ruff format
uv run poe test    # Run pytest
uv run mypy .      # Run type checking
```
