"""MCP 서버 공통 프레임워크.

stdin/stdout JSON-RPC 2.0 기반 MCP 프로토콜을 구현한다.
각 서버는 MCPServer를 상속하고 도구를 등록하면 된다.

Claude Code CLI는 Content-Length 헤더 없이 JSON + newline 방식으로 통신한다.
"""

import json
import logging
import sys
from typing import Any, Callable

import requests

logger = logging.getLogger("mosaiq.mcp")


class MCPServer:
    """MCP 서버 베이스 클래스."""

    DEFAULT_TIMEOUT = 30

    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self._tools: dict[str, dict] = {}
        self._handlers: dict[str, Callable] = {}
        self._default_headers: dict[str, str] = {}

    def tool(self, name: str, description: str, parameters: dict):
        """도구를 등록하는 데코레이터."""
        def decorator(fn: Callable):
            self._tools[name] = {
                "name": name,
                "description": description,
                "inputSchema": {
                    "type": "object",
                    "properties": parameters.get("properties", {}),
                    "required": parameters.get("required", []),
                },
            }
            self._handlers[name] = fn
            return fn
        return decorator

    # ── 공통 유틸 ──────────────────────────────────────────────

    def set_headers(self, headers: dict[str, str]) -> None:
        """공통 API 헤더를 설정한다."""
        self._default_headers = headers

    def api_get(self, url: str, **kwargs) -> requests.Response:
        """타임아웃과 공통 헤더가 적용된 GET 요청."""
        kwargs.setdefault("timeout", self.DEFAULT_TIMEOUT)
        kwargs.setdefault("headers", self._default_headers)
        resp = requests.get(url, **kwargs)
        resp.raise_for_status()
        return resp

    def api_post(self, url: str, **kwargs) -> requests.Response:
        """타임아웃과 공통 헤더가 적용된 POST 요청."""
        kwargs.setdefault("timeout", self.DEFAULT_TIMEOUT)
        kwargs.setdefault("headers", self._default_headers)
        resp = requests.post(url, **kwargs)
        resp.raise_for_status()
        return resp

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """바이트 수를 읽기 좋은 문자열로 변환한다."""
        for unit in ("B", "KB", "MB", "GB"):
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    # ── JSON-RPC 통신 ────────────────────────────────────────

    def _read_message(self) -> dict | None:
        """stdin에서 JSON-RPC 메시지를 읽는다. JSON-per-line 방식."""
        while True:
            line = sys.stdin.readline()
            if not line:
                return None
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                logger.warning("잘못된 JSON 무시: %s", line[:100])
                continue

    def _send_message(self, msg: dict) -> None:
        """stdout으로 JSON-RPC 메시지를 보낸다. JSON + newline 방식."""
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()

    def _send_result(self, id: Any, result: Any) -> None:
        self._send_message({"jsonrpc": "2.0", "id": id, "result": result})

    def _send_error(self, id: Any, code: int, message: str) -> None:
        self._send_message({
            "jsonrpc": "2.0",
            "id": id,
            "error": {"code": code, "message": message},
        })

    def _handle_initialize(self, id: Any, params: dict) -> None:
        self._send_result(id, {
            "protocolVersion": "2025-11-25",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": self.name, "version": self.version},
        })

    def _handle_initialized(self) -> None:
        pass  # notification, no response

    def _handle_tools_list(self, id: Any) -> None:
        self._send_result(id, {"tools": list(self._tools.values())})

    def _handle_tools_call(self, id: Any, params: dict) -> None:
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        handler = self._handlers.get(tool_name)
        if not handler:
            self._send_error(id, -32601, f"Unknown tool: {tool_name}")
            return

        try:
            result = handler(**arguments)
            self._send_result(id, {
                "content": [{"type": "text", "text": str(result)}],
            })
        except Exception as e:
            self._send_result(id, {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            })

    def run(self) -> None:
        """MCP 서버를 시작한다. stdin/stdout으로 JSON-RPC 메시지를 처리한다."""
        logger.info("Starting %s MCP server...", self.name)

        while True:
            msg = self._read_message()
            if msg is None:
                break

            method = msg.get("method", "")
            id = msg.get("id")
            params = msg.get("params", {})

            if method == "initialize":
                self._handle_initialize(id, params)
            elif method == "notifications/initialized":
                self._handle_initialized()
            elif method == "tools/list":
                self._handle_tools_list(id)
            elif method == "tools/call":
                self._handle_tools_call(id, params)
            elif method == "ping":
                self._send_result(id, {})
            elif id is not None:
                self._send_error(id, -32601, f"Method not found: {method}")
