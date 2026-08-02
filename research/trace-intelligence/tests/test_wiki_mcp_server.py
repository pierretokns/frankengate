import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wiki_agentic_rag_benchmark import fixture


def rpc(process: subprocess.Popen[str], payload: dict) -> dict:
    process.stdin.write(json.dumps(payload) + "\n")
    process.stdin.flush()
    return json.loads(process.stdout.readline())


def notify(process: subprocess.Popen[str], payload: dict) -> None:
    process.stdin.write(json.dumps(payload) + "\n")
    process.stdin.flush()


def test_mcp_contract_uses_same_search_backend(tmp_path: Path) -> None:
    corpus = tmp_path / "fixture.json"
    corpus.write_text(json.dumps(fixture(2)), encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "wiki_mcp_server.py", "--corpus", str(corpus), "--backend", "hybrid"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        initialized = rpc(process, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}})
        assert initialized["result"]["serverInfo"]["name"] == "frankengate-wiki"
        notify(process, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        tools = rpc(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        assert {tool["name"] for tool in tools["result"]["tools"]} == {"search", "get_page", "expand_links"}
        result = rpc(process, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search", "arguments": {"query": "When does Atlas-00 deploy?", "k": 5}}})
        value = json.loads(result["result"]["content"][0]["text"])
        assert any(row["page_id"] == "wiki-00/operations" for row in value)
    finally:
        process.terminate()
        process.wait(timeout=5)
