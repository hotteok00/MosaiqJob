"""Google Drive MCP 서버.

Google Drive 파일 검색 및 읽기 기능을 제공한다.
"""

import io
import os

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from base import MCPServer

server = MCPServer("google-drive", "1.0.0")

# Lazy-init 용 전역 변수
_service = None


def _get_service():
    """Google Drive API 서비스 객체를 lazy init으로 반환한다."""
    global _service
    if _service is not None:
        return _service

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    client_id = os.environ["GOOGLE_CLIENT_ID"]
    client_secret = os.environ["GOOGLE_CLIENT_SECRET"]
    refresh_token = os.environ["GOOGLE_REFRESH_TOKEN"]

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
    )

    _service = build("drive", "v3", credentials=creds)
    return _service


@server.tool(
    name="search",
    description="Google Drive에서 파일을 검색한다.",
    parameters={
        "properties": {
            "query": {
                "type": "string",
                "description": "검색할 키워드",
            },
        },
        "required": ["query"],
    },
)
def search(query: str) -> str:
    service = _get_service()

    results = (
        service.files()
        .list(
            q=f"fullText contains '{query}'",
            pageSize=20,
            fields="files(id, name, mimeType, modifiedTime, size)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )

    files = results.get("files", [])
    if not files:
        return f"'{query}' 검색 결과가 없습니다."

    lines = [f"검색 결과: {len(files)}건\n"]
    for i, f in enumerate(files, 1):
        size = f.get("size", "-")
        if size != "-":
            size = _format_size(int(size))
        lines.append(
            f"{i}. {f['name']}\n"
            f"   ID: {f['id']}\n"
            f"   유형: {f.get('mimeType', 'unknown')}\n"
            f"   수정일: {f.get('modifiedTime', '-')}\n"
            f"   크기: {size}"
        )
    return "\n".join(lines)


@server.tool(
    name="read_file",
    description="파일 ID로 Google Drive 파일 내용을 읽는다.",
    parameters={
        "properties": {
            "file_id": {
                "type": "string",
                "description": "Google Drive 파일 ID",
            },
        },
        "required": ["file_id"],
    },
)
def read_file(file_id: str) -> str:
    from googleapiclient.http import MediaIoBaseDownload

    service = _get_service()

    # 파일 메타데이터 조회
    meta = (
        service.files()
        .get(fileId=file_id, fields="id, name, mimeType, size")
        .execute()
    )
    mime_type = meta.get("mimeType", "")
    name = meta.get("name", "unknown")

    # Google Docs/Sheets/Slides는 export, 일반 파일은 media download
    google_export_types = {
        "application/vnd.google-apps.document": "text/plain",
        "application/vnd.google-apps.spreadsheet": "text/csv",
        "application/vnd.google-apps.presentation": "text/plain",
    }

    buf = io.BytesIO()

    if mime_type in google_export_types:
        export_mime = google_export_types[mime_type]
        request = service.files().export_media(
            fileId=file_id, mimeType=export_mime
        )
    else:
        request = service.files().get_media(fileId=file_id)

    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    content = buf.getvalue().decode("utf-8", errors="replace")

    header = f"=== {name} ===\n유형: {mime_type}\n{'=' * 40}\n"
    return header + content


def _format_size(size_bytes: int) -> str:
    """바이트 수를 사람이 읽기 좋은 단위로 변환한다."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


if __name__ == "__main__":
    server.run()
