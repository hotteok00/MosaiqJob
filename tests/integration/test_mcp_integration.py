"""MCP 설정 관련 테스트.

MCP 서버는 claude mcp add로 영구 등록되므로,
파이프라인에서 별도 MCP 관리가 필요 없다.
여기서는 mcp_tools의 설정 함수들과 .mcp.json 생성 로직을 검증한다.
"""

import json
from unittest.mock import patch

import pytest

from agents.mcp_tools import write_mcp_config, remove_mcp_config


class TestWriteMcpConfig:
    @patch.dict("os.environ", {"NOTION_API_KEY": "ntn_key"}, clear=True)
    def test_creates_mcp_json_with_notion(self, tmp_path):
        with patch("agents.mcp_tools.MCP_CONFIG_PATH", tmp_path / ".mcp.json"):
            path = write_mcp_config()
            config = json.loads(path.read_text())
            assert "notion" in config["mcpServers"]
            assert config["mcpServers"]["notion"]["env"]["NOTION_API_TOKEN"] == "ntn_key"

    @patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_token"}, clear=True)
    def test_creates_mcp_json_with_github(self, tmp_path):
        with patch("agents.mcp_tools.MCP_CONFIG_PATH", tmp_path / ".mcp.json"):
            path = write_mcp_config()
            config = json.loads(path.read_text())
            assert "github" in config["mcpServers"]

    @patch.dict("os.environ", {
        "NOTION_API_KEY": "ntn_key",
        "GITHUB_TOKEN": "ghp_token",
        "GOOGLE_CLIENT_ID": "g_id",
        "GOOGLE_CLIENT_SECRET": "g_secret",
    }, clear=True)
    def test_creates_all_servers(self, tmp_path):
        with patch("agents.mcp_tools.MCP_CONFIG_PATH", tmp_path / ".mcp.json"):
            path = write_mcp_config()
            config = json.loads(path.read_text())
            assert len(config["mcpServers"]) == 3

    @patch.dict("os.environ", {}, clear=True)
    def test_creates_empty_config(self, tmp_path):
        with patch("agents.mcp_tools.MCP_CONFIG_PATH", tmp_path / ".mcp.json"):
            path = write_mcp_config()
            config = json.loads(path.read_text())
            assert config["mcpServers"] == {}


class TestRemoveMcpConfig:
    def test_removes_existing_file(self, tmp_path):
        config_path = tmp_path / ".mcp.json"
        config_path.write_text("{}")
        with patch("agents.mcp_tools.MCP_CONFIG_PATH", config_path):
            remove_mcp_config()
            assert not config_path.exists()

    def test_no_error_if_missing(self, tmp_path):
        config_path = tmp_path / ".mcp.json"
        with patch("agents.mcp_tools.MCP_CONFIG_PATH", config_path):
            remove_mcp_config()


class TestPipelineWithMcp:
    """MCP가 영구 등록된 상태에서 소스 분석 동작 확인."""

    def test_analyze_source_works_without_mcp_management(self):
        from agents.source import analyze_source
        result = analyze_source(["Python"])
        assert result == "mocked claude response"
