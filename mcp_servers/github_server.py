"""GitHub MCP 서버.

GitHub API를 호출하여 저장소 검색, 코드 검색, 파일 조회, 커밋 목록 등을 제공한다.
"""

import base64
import os

import requests

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from base import MCPServer

server = MCPServer(name="github", version="1.0.0")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
API_BASE = "https://api.github.com"


def _headers() -> dict:
    """GitHub API 요청 헤더를 반환한다."""
    h = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def _get(url: str, params: dict | None = None) -> dict:
    """GitHub API GET 요청을 보내고 JSON을 반환한다."""
    resp = requests.get(url, headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ── 도구 등록 ──────────────────────────────────────────────


@server.tool(
    name="search_repos",
    description="GitHub 저장소를 검색한다. 키워드로 관련 저장소를 찾을 수 있다.",
    parameters={
        "properties": {
            "q": {
                "type": "string",
                "description": "검색 쿼리 (예: 'robotics language:python')",
            },
        },
        "required": ["q"],
    },
)
def search_repos(q: str) -> str:
    data = _get(f"{API_BASE}/search/repositories", params={"q": q})
    total = data.get("total_count", 0)
    items = data.get("items", [])[:10]

    lines = [f"총 {total}개 저장소 검색됨 (상위 {len(items)}개 표시)\n"]
    for i, repo in enumerate(items, 1):
        stars = repo.get("stargazers_count", 0)
        lang = repo.get("language") or "N/A"
        desc = repo.get("description") or ""
        lines.append(
            f"{i}. {repo['full_name']}  ⭐ {stars}  [{lang}]\n"
            f"   {desc}\n"
            f"   {repo['html_url']}\n"
        )
    return "\n".join(lines)


@server.tool(
    name="search_code",
    description="GitHub에서 코드를 검색한다. 특정 코드 패턴이나 파일을 찾을 수 있다.",
    parameters={
        "properties": {
            "q": {
                "type": "string",
                "description": "코드 검색 쿼리 (예: 'def main repo:owner/repo')",
            },
        },
        "required": ["q"],
    },
)
def search_code(q: str) -> str:
    data = _get(f"{API_BASE}/search/code", params={"q": q})
    total = data.get("total_count", 0)
    items = data.get("items", [])[:10]

    lines = [f"총 {total}개 코드 결과 (상위 {len(items)}개 표시)\n"]
    for i, item in enumerate(items, 1):
        repo_name = item.get("repository", {}).get("full_name", "")
        path = item.get("path", "")
        lines.append(
            f"{i}. {repo_name}/{path}\n"
            f"   {item.get('html_url', '')}\n"
        )
    return "\n".join(lines)


@server.tool(
    name="get_file",
    description="GitHub 저장소의 파일 내용을 가져온다. base64 디코딩하여 텍스트로 반환한다.",
    parameters={
        "properties": {
            "owner": {
                "type": "string",
                "description": "저장소 소유자 (예: 'octocat')",
            },
            "repo": {
                "type": "string",
                "description": "저장소 이름 (예: 'hello-world')",
            },
            "path": {
                "type": "string",
                "description": "파일 경로 (예: 'src/main.py')",
            },
        },
        "required": ["owner", "repo", "path"],
    },
)
def get_file(owner: str, repo: str, path: str) -> str:
    data = _get(f"{API_BASE}/repos/{owner}/{repo}/contents/{path}")

    if isinstance(data, list):
        # 디렉터리인 경우 파일 목록 반환
        lines = [f"디렉터리: {path} ({len(data)}개 항목)\n"]
        for item in data:
            kind = "📁" if item["type"] == "dir" else "📄"
            lines.append(f"  {kind} {item['name']}")
        return "\n".join(lines)

    # 파일인 경우 내용 디코딩
    name = data.get("name", path)
    size = data.get("size", 0)
    content_b64 = data.get("content", "")
    content = base64.b64decode(content_b64).decode("utf-8", errors="replace")

    return (
        f"파일: {name} ({size} bytes)\n"
        f"{'=' * 60}\n"
        f"{content}"
    )


@server.tool(
    name="list_commits",
    description="GitHub 저장소의 최근 커밋 목록을 조회한다 (최대 10개).",
    parameters={
        "properties": {
            "owner": {
                "type": "string",
                "description": "저장소 소유자 (예: 'octocat')",
            },
            "repo": {
                "type": "string",
                "description": "저장소 이름 (예: 'hello-world')",
            },
        },
        "required": ["owner", "repo"],
    },
)
def list_commits(owner: str, repo: str) -> str:
    data = _get(
        f"{API_BASE}/repos/{owner}/{repo}/commits", params={"per_page": 10}
    )

    lines = [f"{owner}/{repo} 최근 커밋 ({len(data)}개)\n"]
    for i, commit_data in enumerate(items := data[:10], 1):
        sha = commit_data["sha"][:7]
        commit = commit_data.get("commit", {})
        message = commit.get("message", "").split("\n")[0]
        author = commit.get("author", {}).get("name", "unknown")
        date = commit.get("author", {}).get("date", "")[:10]
        lines.append(f"{i}. [{sha}] {message}  — {author} ({date})")

    return "\n".join(lines)


# ── 엔트리포인트 ───────────────────────────────────────────

if __name__ == "__main__":
    server.run()
