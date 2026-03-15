"""MCP 서버 연결 및 도구 관리.

Claude CLI가 .mcp.json을 자동 인식하므로,
프로젝트 루트에 .mcp.json 파일을 생성/업데이트하여 MCP 서버를 연결한다.
"""

import json
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
MCP_CONFIG_PATH = PROJECT_ROOT / ".mcp.json"


def get_notion_params() -> dict | None:
    api_key = os.getenv("NOTION_API_KEY")
    if not api_key:
        return None
    return {
        "command": "npx",
        "args": ["-y", "@suekou/mcp-notion-server"],
        "env": {"NOTION_API_TOKEN": api_key},
    }


def get_github_params() -> dict | None:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return None
    return {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": token},
    }


def get_google_drive_params() -> dict | None:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    return {
        "command": "npx",
        "args": ["-y", "@isaacphi/mcp-gdrive"],
        "env": {"GOOGLE_CLIENT_ID": client_id, "GOOGLE_CLIENT_SECRET": client_secret},
    }


MCP_SERVERS = {
    "notion": get_notion_params,
    "github": get_github_params,
    "google_drive": get_google_drive_params,
}


def get_all_mcp_params() -> list[tuple[str, dict]]:
    """설정된 MCP 서버 파라미터를 (이름, params) 튜플로 반환."""
    result = []
    for name, getter in MCP_SERVERS.items():
        p = getter()
        if p:
            result.append((name, p))
    return result


def write_mcp_config() -> Path:
    """환경변수 기반으로 .mcp.json 파일을 생성/업데이트한다.

    Claude CLI는 프로젝트 루트의 .mcp.json을 자동 인식하므로,
    이 파일만 만들면 claude -p 호출 시 MCP 도구가 자동 연결된다.

    Returns:
        생성된 .mcp.json 파일 경로
    """
    servers = {}

    notion_key = os.getenv("NOTION_API_KEY")
    if notion_key:
        servers["notion"] = {
            "command": "npx",
            "args": ["-y", "@suekou/mcp-notion-server"],
            "env": {"NOTION_API_TOKEN": notion_key},
        }

    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        servers["github"] = {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": github_token},
        }

    google_id = os.getenv("GOOGLE_CLIENT_ID")
    google_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if google_id and google_secret:
        servers["google_drive"] = {
            "command": "npx",
            "args": ["-y", "@isaacphi/mcp-gdrive"],
            "env": {"GOOGLE_CLIENT_ID": google_id, "GOOGLE_CLIENT_SECRET": google_secret},
        }

    config = {"mcpServers": servers}
    MCP_CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    logger.info(f".mcp.json 생성: {list(servers.keys())}")
    return MCP_CONFIG_PATH


def remove_mcp_config() -> None:
    """MCP 설정 파일을 제거한다."""
    if MCP_CONFIG_PATH.exists():
        MCP_CONFIG_PATH.unlink()
        logger.info(".mcp.json 제거")
