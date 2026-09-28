#!/usr/bin/env python3
"""
Engel AI Main — Model Context Protocol (MCP) client.

Ported from OpenClaw (MIT) MCP integration (dist/bundle-mcp, agent-bundle-mcp-types):
a stdio JSON-RPC 2.0 client that spawns an MCP tool server, performs the
initialize handshake, lists its tools, and calls them. Lets Engel's agent reach
any MCP server (filesystem, git, browser, custom) the same way OpenClaw does.

Transport: newline-delimited JSON-RPC 2.0 over the server's stdin/stdout (MCP
stdio transport). Works with any MCP server launched as a subprocess, e.g.
  MCPClient("npx", ["-y", "@modelcontextprotocol/server-filesystem", "/some/dir"])

Reimplemented natively in Python; MIT-attributed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from typing import Any, Optional

MCP_PROTOCOL_VERSION = "2025-06-18"


class MCPClient:
    def __init__(self, command: str, args: Optional[list[str]] = None, *, cwd: Optional[str] = None,
                 env: Optional[dict] = None, timeout: float = 30.0):
        self.timeout = timeout
        self._id = 0
        self._server_info: dict = {}
        self.proc = subprocess.Popen(
            [command, *(args or [])],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1, cwd=cwd, env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self._lock = threading.Lock()

    def _rpc(self, method: str, params: Optional[dict] = None, notify: bool = False) -> Optional[dict]:
        with self._lock:
            msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
            if not notify:
                self._id += 1
                msg["id"] = self._id
            if params is not None:
                msg["params"] = params
            assert self.proc.stdin is not None
            self.proc.stdin.write(json.dumps(msg) + "\n")
            self.proc.stdin.flush()
            if notify:
                return None
            # read lines until we get the matching id (skip notifications/logs)
            assert self.proc.stdout is not None
            while True:
                line = self.proc.stdout.readline()
                if not line:
                    raise RuntimeError("MCP server closed the connection")
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue  # server log noise on stdout — skip
                if obj.get("id") == msg["id"]:
                    if "error" in obj:
                        raise RuntimeError(f"MCP error {obj['error'].get('code')}: {obj['error'].get('message')}")
                    return obj.get("result")

    def initialize(self, client_name: str = "engel-ai-main", client_version: str = "1.0.0") -> dict:
        result = self._rpc("initialize", {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "clientInfo": {"name": client_name, "version": client_version},
        }) or {}
        self._server_info = result.get("serverInfo", {})
        self._rpc("notifications/initialized", notify=True)
        return result

    def list_tools(self) -> list[dict]:
        return (self._rpc("tools/list") or {}).get("tools", [])

    def call_tool(self, name: str, arguments: Optional[dict] = None) -> dict:
        return self._rpc("tools/call", {"name": name, "arguments": arguments or {}}) or {}

    @staticmethod
    def text_of(result: dict) -> str:
        """Extract the text content of a tools/call result."""
        parts = []
        for c in (result or {}).get("content", []):
            if isinstance(c, dict) and c.get("type") == "text":
                parts.append(str(c.get("text") or ""))
        return "\n".join(parts)

    def close(self) -> None:
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass


def _cli(argv: Optional[list[str]] = None) -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Engel MCP client (stdio). Spawns an MCP server and lists/calls tools.")
    ap.add_argument("--command", required=True, help="server launch command, e.g. 'npx' or 'python'")
    ap.add_argument("--arg", action="append", default=[], help="server arg (repeatable)")
    ap.add_argument("--list", action="store_true", help="list the server's tools")
    ap.add_argument("--call", default="", help="tool name to call")
    ap.add_argument("--args-json", default="{}", help="JSON arguments for --call")
    a = ap.parse_args(argv)
    client = MCPClient(a.command, a.arg)
    try:
        info = client.initialize()
        si = info.get("serverInfo", {})
        print(f"connected: {si.get('name')} v{si.get('version')} (protocol {info.get('protocolVersion')})")
        if a.list or not a.call:
            for t in client.list_tools():
                print(f"  tool: {t.get('name')} — {t.get('description','')}")
        if a.call:
            res = client.call_tool(a.call, json.loads(a.args_json))
            print(f"  {a.call} -> {client.text_of(res)!r}")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
