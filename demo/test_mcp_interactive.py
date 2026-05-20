import asyncio
import json
import os
from pathlib import Path

SOCKET_PATH = "/tmp/workspace_mcp.sock"

# Setup the test environment before connecting
def setup_sandbox():
    sandbox_dir = Path(os.path.expanduser("~/.workspace_mcp_sandbox"))
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    test_file = sandbox_dir / "test.txt"
    test_file.write_text("Inside Sandbox Content: Verification Success!", encoding="utf-8")
    print(f"✅ Sandbox initialized: {sandbox_dir}")
    print(f"✅ Created test file: {test_file}")

async def send_rpc(writer, reader, request_id, method, params):
    req = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params
    }
    print(f"\n➡️ SENDING: {method} (ID: {request_id})")
    print(json.dumps(req, indent=2))
    writer.write(json.dumps(req).encode() + b"\n")
    await writer.drain()
    
    response = await reader.readline()
    if not response:
        raise ConnectionError("Server closed UDS connection prematurely.")
    res = json.loads(response.decode())
    print(f"⬅️ RECEIVED:")
    print(json.dumps(res, indent=2))
    return res

async def main():
    setup_sandbox()
    
    print(f"\nConnecting to UDS socket: {SOCKET_PATH}...")
    try:
        reader, writer = await asyncio.open_unix_connection(SOCKET_PATH)
        print("Connected successfully!")
    except Exception as e:
        print(f"❌ Error connecting: {e}. Is the server running?")
        print("Please start the server first in another window:")
        print("  PYTHONPATH=src uv run python -m workspace_mcp.server --config config.toml")
        return

    test_results = []
    
    try:
        # 1. Mandatory Handshake
        handshake_res = await send_rpc(writer, reader, 1, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "interactive-tester", "version": "1.0.0"}
        })
        
        # Send initialized notification
        writer.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}).encode() + b"\n")
        await writer.drain()
        
        # -------------------------------------------------------------
        # FEATURE 1: read_isolated_file
        # -------------------------------------------------------------
        
        # Test Case 1.1: Valid Read
        res = await send_rpc(writer, reader, 2, "tools/call", {
            "name": "read_isolated_file",
            "arguments": {"path": "test.txt"}
        })
        passed = (
            "result" in res 
            and res["result"].get("isError") is False 
            and "Verification Success!" in res["result"]["content"][0]["text"]
        )
        test_results.append(("1.1: Valid File Read (Success)", passed, res))
        
        # Test Case 1.2: Path Traversal Rejection (Relative Escape)
        res = await send_rpc(writer, reader, 3, "tools/call", {
            "name": "read_isolated_file",
            "arguments": {"path": "../secret_file.txt"}
        })
        passed = (
            "result" in res 
            and res["result"].get("isError") is True 
            and "traversal" in res["result"]["content"][0]["text"].lower()
        )
        test_results.append(("1.2: Path Traversal Rejection", passed, res))
        
        # Test Case 1.3: Path Traversal Rejection (Absolute Escape)
        res = await send_rpc(writer, reader, 4, "tools/call", {
            "name": "read_isolated_file",
            "arguments": {"path": "/etc/passwd"}
        })
        passed = (
            "result" in res 
            and res["result"].get("isError") is True 
            and "absolute path" in res["result"]["content"][0]["text"].lower()
        )
        test_results.append(("1.3: Absolute Path Escape Rejection", passed, res))

        # -------------------------------------------------------------
        # FEATURE 2: execute_job
        # -------------------------------------------------------------
        
        # Test Case 2.1: Valid Whitelisted Command
        res = await send_rpc(writer, reader, 5, "tools/call", {
            "name": "execute_job",
            "arguments": {"command": "echo", "args": ["HelloSecureWorld"]}
        })
        passed = (
            "result" in res 
            and res["result"].get("isError") is False 
            and "HelloSecureWorld" in res["result"]["content"][0]["text"]
        )
        test_results.append(("2.1: Whitelisted Command Execution (Success)", passed, res))
        
        # Test Case 2.2: Rejection of Non-whitelisted Command
        res = await send_rpc(writer, reader, 6, "tools/call", {
            "name": "execute_job",
            "arguments": {"command": "cat", "args": ["config.toml"]}
        })
        passed = (
            "result" in res 
            and res["result"].get("isError") is True 
            and "not whitelisted" in res["result"]["content"][0]["text"].lower()
        )
        test_results.append(("2.2: Non-whitelisted Command Rejection", passed, res))
        
        # Test Case 2.3: Rejection of Malicious Arguments (Regex Violation)
        res = await send_rpc(writer, reader, 7, "tools/call", {
            "name": "execute_job",
            "arguments": {"command": "echo", "args": ["hello; rm -rf /"]}
        })
        passed = (
            "result" in res 
            and res["result"].get("isError") is True 
            and "argument rejection" in res["result"]["content"][0]["text"].lower()
        )
        test_results.append(("2.3: Malicious Argument Rejection", passed, res))
        
        # Test Case 2.4: Command Timeout Verification
        res = await send_rpc(writer, reader, 8, "tools/call", {
            "name": "execute_job",
            "arguments": {"command": "sleep", "args": ["5"]}
        })
        passed = (
            "result" in res 
            and res["result"].get("isError") is True 
            and "timed out" in res["result"]["content"][0]["text"].lower()
        )
        test_results.append(("2.4: Command Timeout Rejection", passed, res))

    finally:
        writer.close()
        await writer.wait_closed()
        print("\nDisconnected.")

    # Print a beautiful verification report
    print("\n" + "="*80)
    print("                      MCP SERVER SECURITY VERIFICATION REPORT")
    print("="*80)
    for title, passed, res in test_results:
        status = "🟢 PASS" if passed else "🔴 FAIL"
        print(f"[{status}] {title}")
        if not passed:
            print(f"   Details: {json.dumps(res, indent=2)}")
        else:
            msg = res["result"]["content"][0]["text"].strip().replace('\n', ' ')
            # Truncate message for neatness
            if len(msg) > 60:
                msg = msg[:57] + "..."
            print(f"   Output:  {msg}")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
