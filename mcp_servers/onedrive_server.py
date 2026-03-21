"""OneDrive MCP 서버.

Microsoft Graph API를 통해 OneDrive 파일을 검색, 읽기, 목록 조회한다.
"""

import os
from urllib.parse import quote

import requests

try:
    from mcp_servers.base import MCPServer
except ImportError:
    from base import MCPServer

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
SCOPE = "Files.Read.All offline_access"

server = MCPServer("onedrive", "1.0.0")

_access_token: str | None = None


def _get_access_token() -> str:
    """access_token을 반환한다. 첫 호출 시 refresh_token으로 갱신한다."""
    global _access_token
    if _access_token:
        return _access_token

    client_id = os.environ.get("MICROSOFT_CLIENT_ID", "")
    refresh_token = os.environ.get("MICROSOFT_REFRESH_TOKEN", "")

    if not refresh_token:
        raise RuntimeError(
            "MICROSOFT_REFRESH_TOKEN 환경변수가 설정되지 않았습니다.\n"
            "Device Code Flow로 토큰을 발급받으세요:\n"
            "  1. POST https://login.microsoftonline.com/common/oauth2/v2.0/devicecode\n"
            "     body: client_id=<YOUR_CLIENT_ID>&scope=Files.Read.All offline_access\n"
            "  2. 응답의 verification_uri에 접속하여 user_code를 입력\n"
            "  3. POST https://login.microsoftonline.com/common/oauth2/v2.0/token\n"
            "     body: client_id=<YOUR_CLIENT_ID>&grant_type=urn:ietf:params:oauth:grant-type:device_code&device_code=<DEVICE_CODE>\n"
            "  4. 응답의 refresh_token을 MICROSOFT_REFRESH_TOKEN 환경변수에 설정"
        )

    if not client_id:
        raise RuntimeError("MICROSOFT_CLIENT_ID 환경변수가 설정되지 않았습니다.")

    resp = requests.post(TOKEN_URL, data={
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": SCOPE,
    }, timeout=30)

    if resp.status_code != 200:
        raise RuntimeError(f"토큰 갱신 실패 ({resp.status_code}): {resp.text}")

    data = resp.json()
    _access_token = data.get("access_token")
    if not _access_token:
        raise RuntimeError("토큰 응답에 access_token이 없습니다.")

    # refresh_token이 갱신되었으면 메모리에 반영 (다음 갱신에 사용)
    new_refresh = data.get("refresh_token")
    if new_refresh:
        os.environ["MICROSOFT_REFRESH_TOKEN"] = new_refresh

    # 갱신된 토큰으로 서버 헤더 설정
    server.set_headers({"Authorization": f"Bearer {_access_token}"})

    return _access_token


def _ensure_auth() -> None:
    """인증이 완료되었는지 확인하고, 필요 시 토큰을 갱신한다."""
    _get_access_token()


def _format_file_item(item: dict) -> str:
    """Graph API 파일/폴더 항목을 읽기 좋은 텍스트로 포맷한다."""
    name = item.get("name", "(이름 없음)")
    item_id = item.get("id", "")
    size = item.get("size", 0)
    modified = item.get("lastModifiedDateTime", "")
    is_folder = "folder" in item
    kind = "폴더" if is_folder else "파일"

    size_str = MCPServer.format_size(size)
    lines = [
        f"  [{kind}] {name}",
        f"    ID: {item_id}",
        f"    크기: {size_str}",
        f"    수정일: {modified}",
    ]

    if is_folder:
        child_count = item.get("folder", {}).get("childCount", 0)
        lines.append(f"    하위 항목: {child_count}개")

    web_url = item.get("webUrl")
    if web_url:
        lines.append(f"    URL: {web_url}")

    return "\n".join(lines)


def _is_text_mime(mime_type: str) -> bool:
    """텍스트 기반 MIME 타입인지 판별한다."""
    if not mime_type:
        return False
    text_prefixes = ("text/", "application/json", "application/xml", "application/javascript")
    return any(mime_type.startswith(p) for p in text_prefixes)


# --- 도구 등록 ---

@server.tool(
    name="search",
    description="OneDrive에서 파일을 검색합니다.",
    parameters={
        "properties": {
            "query": {
                "type": "string",
                "description": "검색어",
            },
        },
        "required": ["query"],
    },
)
def search(query: str) -> str:
    _ensure_auth()
    items = server.api_get(
        f"{GRAPH_BASE}/me/drive/search(q='{quote(query)}')",
    ).json().get("value", [])

    if not items:
        return f"'{query}' 검색 결과가 없습니다."

    lines = [f"검색 결과: '{query}' ({len(items)}건)"]
    lines.append("-" * 40)
    for item in items:
        lines.append(_format_file_item(item))
    return "\n".join(lines)


@server.tool(
    name="read_file",
    description="OneDrive 파일의 내용을 읽습니다. 텍스트 파일만 내용을 반환하고, 바이너리 파일은 메타데이터만 반환합니다.",
    parameters={
        "properties": {
            "item_id": {
                "type": "string",
                "description": "파일의 OneDrive item ID",
            },
        },
        "required": ["item_id"],
    },
)
def read_file(item_id: str) -> str:
    _ensure_auth()

    # 먼저 메타데이터 조회
    meta = server.api_get(
        f"{GRAPH_BASE}/me/drive/items/{item_id}",
    ).json()

    name = meta.get("name", "(이름 없음)")
    mime_type = meta.get("file", {}).get("mimeType", "")
    size = meta.get("size", 0)

    # 폴더인 경우
    if "folder" in meta:
        return f"'{name}'은(는) 폴더입니다. read_file은 파일만 지원합니다."

    # 바이너리 파일인 경우 메타데이터만 반환
    if not _is_text_mime(mime_type):
        lines = [
            "바이너리 파일이므로 내용을 표시할 수 없습니다.",
            "",
            "파일 메타데이터:",
            f"  이름: {name}",
            f"  ID: {item_id}",
            f"  MIME: {mime_type}",
            f"  크기: {MCPServer.format_size(size)}",
            f"  수정일: {meta.get('lastModifiedDateTime', '')}",
        ]
        web_url = meta.get("webUrl")
        if web_url:
            lines.append(f"  URL: {web_url}")
        return "\n".join(lines)

    # 텍스트 파일 내용 읽기
    content_resp = server.api_get(
        f"{GRAPH_BASE}/me/drive/items/{item_id}/content",
    )

    text = content_resp.text
    lines = [
        f"파일: {name} ({MCPServer.format_size(size)})",
        "=" * 40,
        text,
    ]
    return "\n".join(lines)


@server.tool(
    name="list_files",
    description="OneDrive 루트 폴더의 파일 및 폴더 목록을 조회합니다.",
    parameters={
        "properties": {},
        "required": [],
    },
)
def list_files() -> str:
    _ensure_auth()
    items = server.api_get(
        f"{GRAPH_BASE}/me/drive/root/children",
    ).json().get("value", [])

    if not items:
        return "루트 폴더가 비어 있습니다."

    lines = [f"OneDrive 루트 폴더 ({len(items)}개 항목)"]
    lines.append("-" * 40)
    for item in items:
        lines.append(_format_file_item(item))
    return "\n".join(lines)


@server.tool(
    name="list_children",
    description="OneDrive 폴더 경로를 지정하여 하위 파일/폴더 목록을 조회합니다. 경로 예: '바탕화면/새 폴더/진로'",
    parameters={
        "properties": {
            "path": {
                "type": "string",
                "description": "폴더 경로 (루트부터 슬래시 구분, 예: '바탕화면/새 폴더/진로')",
            },
        },
        "required": ["path"],
    },
)
def list_children(path: str) -> str:
    _ensure_auth()
    # Graph API 경로 기반 조회: /me/drive/root:/{path}:/children
    encoded_path = path.strip("/")
    resp = server.api_get(
        f"{GRAPH_BASE}/me/drive/root:/{encoded_path}:/children",
    ).json()
    items = resp.get("value", [])

    if not items:
        return f"'{path}' 폴더가 비어 있거나 존재하지 않습니다."

    lines = [f"'{path}' ({len(items)}개 항목)"]
    lines.append("-" * 40)
    for item in items:
        lines.append(_format_file_item(item))
    return "\n".join(lines)


if __name__ == "__main__":
    server.run()
