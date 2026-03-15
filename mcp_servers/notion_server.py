"""Notion MCP 서버.

Notion API를 호출하여 페이지 검색, 읽기, 데이터베이스 쿼리를 수행한다.
"""

import os
import requests
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from base import MCPServer

server = MCPServer(name="notion", version="1.0.0")

NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "")
NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


# ── 블록 텍스트 추출 헬퍼 ──────────────────────────────────────────


def _rich_text_to_str(rich_texts: list) -> str:
    """Notion rich_text 배열을 평문 문자열로 변환한다."""
    return "".join(rt.get("plain_text", "") for rt in rich_texts)


def _format_block(block: dict, indent: int = 0) -> str:
    """단일 블록을 읽기 좋은 텍스트로 변환한다."""
    btype = block.get("type", "")
    prefix = "  " * indent
    data = block.get(btype, {})

    if btype in (
        "paragraph", "heading_1", "heading_2", "heading_3",
        "bulleted_list_item", "numbered_list_item", "quote",
        "callout", "toggle",
    ):
        text = _rich_text_to_str(data.get("rich_text", []))
        markers = {
            "heading_1": "# ",
            "heading_2": "## ",
            "heading_3": "### ",
            "bulleted_list_item": "- ",
            "numbered_list_item": "1. ",
            "quote": "> ",
        }
        marker = markers.get(btype, "")
        return f"{prefix}{marker}{text}"

    if btype == "to_do":
        text = _rich_text_to_str(data.get("rich_text", []))
        checked = "[x]" if data.get("checked") else "[ ]"
        return f"{prefix}{checked} {text}"

    if btype == "code":
        text = _rich_text_to_str(data.get("rich_text", []))
        lang = data.get("language", "")
        return f"{prefix}```{lang}\n{prefix}{text}\n{prefix}```"

    if btype == "divider":
        return f"{prefix}---"

    if btype == "image":
        img = data.get("file", data.get("external", {}))
        url = img.get("url", "")
        return f"{prefix}[image: {url}]"

    if btype == "table_row":
        cells = data.get("cells", [])
        row = " | ".join(_rich_text_to_str(cell) for cell in cells)
        return f"{prefix}| {row} |"

    # 기타 블록은 타입만 표시
    return f"{prefix}[{btype}]"


def _fetch_blocks(block_id: str, indent: int = 0) -> list[str]:
    """block_id 하위의 모든 블록을 재귀적으로 수집하여 텍스트 리스트로 반환한다."""
    lines: list[str] = []
    url = f"{BASE_URL}/blocks/{block_id}/children"
    has_more = True
    start_cursor = None

    while has_more:
        params: dict = {"page_size": 100}
        if start_cursor:
            params["start_cursor"] = start_cursor

        resp = requests.get(url, headers=_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()

        for block in data.get("results", []):
            lines.append(_format_block(block, indent))
            if block.get("has_children"):
                lines.extend(_fetch_blocks(block["id"], indent + 1))

        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return lines


# ── 검색 결과 포맷 헬퍼 ─────────────────────────────────────────


def _format_search_result(obj: dict) -> str:
    """검색 결과 하나를 한 줄 요약 텍스트로 변환한다."""
    obj_type = obj.get("object", "")
    obj_id = obj.get("id", "")

    title = ""
    if obj_type == "page":
        props = obj.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                title = _rich_text_to_str(prop.get("title", []))
                break
        if not title:
            title = "(제목 없음)"
        return f"[page] {title}  (id: {obj_id})"

    if obj_type == "database":
        title_parts = obj.get("title", [])
        title = _rich_text_to_str(title_parts) if title_parts else "(제목 없음)"
        return f"[database] {title}  (id: {obj_id})"

    return f"[{obj_type}] id: {obj_id}"


# ── 데이터베이스 행 포맷 헬퍼 ────────────────────────────────────


def _format_property_value(prop: dict) -> str:
    """데이터베이스 프로퍼티 값을 평문으로 변환한다."""
    ptype = prop.get("type", "")

    if ptype == "title":
        return _rich_text_to_str(prop.get("title", []))
    if ptype == "rich_text":
        return _rich_text_to_str(prop.get("rich_text", []))
    if ptype == "number":
        val = prop.get("number")
        return str(val) if val is not None else ""
    if ptype == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""
    if ptype == "multi_select":
        return ", ".join(s.get("name", "") for s in prop.get("multi_select", []))
    if ptype == "status":
        st = prop.get("status")
        return st.get("name", "") if st else ""
    if ptype == "date":
        d = prop.get("date")
        if not d:
            return ""
        start = d.get("start", "")
        end = d.get("end", "")
        return f"{start} ~ {end}" if end else start
    if ptype == "checkbox":
        return "Yes" if prop.get("checkbox") else "No"
    if ptype == "url":
        return prop.get("url", "") or ""
    if ptype == "email":
        return prop.get("email", "") or ""
    if ptype == "phone_number":
        return prop.get("phone_number", "") or ""
    if ptype == "people":
        return ", ".join(p.get("name", p.get("id", "")) for p in prop.get("people", []))
    if ptype == "relation":
        return ", ".join(r.get("id", "") for r in prop.get("relation", []))
    if ptype == "formula":
        f = prop.get("formula", {})
        ftype = f.get("type", "")
        return str(f.get(ftype, ""))
    if ptype == "rollup":
        r = prop.get("rollup", {})
        rtype = r.get("type", "")
        return str(r.get(rtype, ""))
    if ptype == "files":
        files = prop.get("files", [])
        return ", ".join(f.get("name", "") for f in files)
    if ptype == "created_time":
        return prop.get("created_time", "")
    if ptype == "last_edited_time":
        return prop.get("last_edited_time", "")

    return str(prop.get(ptype, ""))


def _format_db_row(page: dict) -> str:
    """데이터베이스 쿼리 결과의 한 행을 텍스트로 변환한다."""
    props = page.get("properties", {})
    parts: list[str] = []
    for name, prop in props.items():
        value = _format_property_value(prop)
        if value:
            parts.append(f"  {name}: {value}")
    page_id = page.get("id", "")
    header = f"--- (id: {page_id}) ---"
    return header + "\n" + "\n".join(parts) if parts else header


# ── 도구 등록 ─────────────────────────────────────────────────────


@server.tool(
    name="search",
    description="Notion 워크스페이스에서 페이지와 데이터베이스를 검색한다.",
    parameters={
        "properties": {
            "query": {
                "type": "string",
                "description": "검색 키워드",
            },
        },
        "required": ["query"],
    },
)
def search(query: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/search",
        headers=_headers(),
        json={"query": query, "page_size": 20},
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])

    if not results:
        return "검색 결과가 없습니다."

    lines = [f"검색 결과 ({len(results)}건):", ""]
    for obj in results:
        lines.append(_format_search_result(obj))
    return "\n".join(lines)


@server.tool(
    name="read_page",
    description="Notion 페이지의 속성과 본문 블록을 읽는다.",
    parameters={
        "properties": {
            "page_id": {
                "type": "string",
                "description": "Notion 페이지 ID",
            },
        },
        "required": ["page_id"],
    },
)
def read_page(page_id: str) -> str:
    # 1) 페이지 속성 조회
    resp = requests.get(f"{BASE_URL}/pages/{page_id}", headers=_headers())
    resp.raise_for_status()
    page = resp.json()

    # 제목 추출
    title = ""
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            title = _rich_text_to_str(prop.get("title", []))
            break

    lines: list[str] = []
    lines.append(f"=== {title or '(제목 없음)'} ===")
    lines.append(f"ID: {page.get('id', '')}")
    lines.append(f"URL: {page.get('url', '')}")
    lines.append(f"생성: {page.get('created_time', '')}")
    lines.append(f"수정: {page.get('last_edited_time', '')}")
    lines.append("")

    # 속성 표시
    props = page.get("properties", {})
    for name, prop in props.items():
        if prop.get("type") == "title":
            continue
        value = _format_property_value(prop)
        if value:
            lines.append(f"{name}: {value}")

    lines.append("")
    lines.append("── 본문 ──")
    lines.append("")

    # 2) 블록 내용 재귀 수집
    body_lines = _fetch_blocks(page_id)
    lines.extend(body_lines)

    return "\n".join(lines)


@server.tool(
    name="query_database",
    description="Notion 데이터베이스를 쿼리하여 항목 목록을 가져온다.",
    parameters={
        "properties": {
            "database_id": {
                "type": "string",
                "description": "Notion 데이터베이스 ID",
            },
        },
        "required": ["database_id"],
    },
)
def query_database(database_id: str) -> str:
    results: list[dict] = []
    has_more = True
    start_cursor = None

    while has_more:
        body: dict = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor

        resp = requests.post(
            f"{BASE_URL}/databases/{database_id}/query",
            headers=_headers(),
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    if not results:
        return "데이터베이스에 항목이 없습니다."

    lines = [f"데이터베이스 쿼리 결과 ({len(results)}건):", ""]
    for page in results:
        lines.append(_format_db_row(page))
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    server.run()
