"""MCP 서버 파라미터 생성 테스트."""

from unittest.mock import patch

from agents.mcp_tools import (
    get_all_mcp_params,
    get_github_params,
    get_google_drive_params,
    get_notion_params,
)


class TestGetNotionParams:
    @patch.dict("os.environ", {"NOTION_API_KEY": "ntn_test_key_123"})
    def test_returns_params_with_key(self):
        params = get_notion_params()
        assert params is not None
        assert isinstance(params, dict)
        assert params["command"] == "npx"
        assert "@suekou/mcp-notion-server" in params["args"]
        assert params["env"]["NOTION_API_TOKEN"] == "ntn_test_key_123"

    @patch.dict("os.environ", {}, clear=True)
    def test_returns_none_without_key(self):
        params = get_notion_params()
        assert params is None

    @patch.dict("os.environ", {"NOTION_API_KEY": ""})
    def test_returns_none_with_empty_key(self):
        params = get_notion_params()
        assert params is None

    @patch.dict("os.environ", {"NOTION_API_KEY": "ntn_key"})
    def test_env_contains_notion_token(self):
        params = get_notion_params()
        assert params["env"]["NOTION_API_TOKEN"] == "ntn_key"


class TestGetGithubParams:
    @patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_test_token"})
    def test_returns_params_with_token(self):
        params = get_github_params()
        assert params is not None
        assert isinstance(params, dict)
        assert params["command"] == "npx"
        assert "@modelcontextprotocol/server-github" in params["args"]
        assert params["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"] == "ghp_test_token"

    @patch.dict("os.environ", {}, clear=True)
    def test_returns_none_without_token(self):
        params = get_github_params()
        assert params is None

    @patch.dict("os.environ", {"GITHUB_TOKEN": ""})
    def test_returns_none_with_empty_token(self):
        params = get_github_params()
        assert params is None


class TestGetGoogleDriveParams:
    @patch.dict("os.environ", {
        "GOOGLE_CLIENT_ID": "client_id_123",
        "GOOGLE_CLIENT_SECRET": "client_secret_456",
    })
    def test_returns_params_with_both_keys(self):
        params = get_google_drive_params()
        assert params is not None
        assert isinstance(params, dict)
        assert params["command"] == "npx"
        assert "@isaacphi/mcp-gdrive" in params["args"]
        assert params["env"]["GOOGLE_CLIENT_ID"] == "client_id_123"
        assert params["env"]["GOOGLE_CLIENT_SECRET"] == "client_secret_456"

    @patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "id_only"}, clear=True)
    def test_returns_none_without_secret(self):
        params = get_google_drive_params()
        assert params is None

    @patch.dict("os.environ", {"GOOGLE_CLIENT_SECRET": "secret_only"}, clear=True)
    def test_returns_none_without_id(self):
        params = get_google_drive_params()
        assert params is None

    @patch.dict("os.environ", {}, clear=True)
    def test_returns_none_without_any(self):
        params = get_google_drive_params()
        assert params is None

    @patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "", "GOOGLE_CLIENT_SECRET": "secret"})
    def test_returns_none_with_empty_id(self):
        params = get_google_drive_params()
        assert params is None


class TestGetAllMcpParams:
    @patch.dict("os.environ", {}, clear=True)
    def test_empty_when_no_env(self):
        params = get_all_mcp_params()
        assert params == []

    @patch.dict("os.environ", {"NOTION_API_KEY": "ntn_key"})
    def test_returns_name_and_params_tuple(self):
        params = get_all_mcp_params()
        assert len(params) >= 1
        name, server_params = params[0]
        assert isinstance(name, str)
        assert isinstance(server_params, dict)

    @patch.dict("os.environ", {
        "NOTION_API_KEY": "ntn_key",
        "GITHUB_TOKEN": "ghp_token",
        "GOOGLE_CLIENT_ID": "g_id",
        "GOOGLE_CLIENT_SECRET": "g_secret",
    })
    def test_returns_all_configured(self):
        params = get_all_mcp_params()
        assert len(params) == 3
        names = [name for name, _ in params]
        assert "notion" in names
        assert "github" in names
        assert "google_drive" in names

    @patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_token"}, clear=True)
    def test_returns_only_github(self):
        params = get_all_mcp_params()
        names = [name for name, _ in params]
        assert "github" in names
        assert "notion" not in names

    @patch.dict("os.environ", {}, clear=True)
    def test_return_type_is_list(self):
        params = get_all_mcp_params()
        assert isinstance(params, list)
