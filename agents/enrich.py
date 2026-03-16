"""Claude가 반환한 JSON 데이터를 보정하는 후처리 모듈.

agents/writer.py에서 Jinja2 렌더링 전에 호출하여
누락된 에셋 URL을 자동 매칭하고, 데이터를 정규화한다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

REGISTRY_PATH = Path(__file__).parent.parent / "assets" / "registry.json"


# ── 내부 유틸 ──────────────────────────────────────────────


def _load_registry() -> dict:
    """assets/registry.json을 로드한다. 파일 없으면 빈 dict 반환."""
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _normalize_github(url: str) -> str:
    """GitHub URL에서 username만 추출한다.

    Examples:
        "https://github.com/hotteok00" → "hotteok00"
        "github.com/hotteok00"         → "hotteok00"
        "hotteok00"                    → "hotteok00"
    """
    if not url:
        return url
    url = url.strip().rstrip("/")
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"^github\.com/", "", url)
    return url


def _youtube_video_id(url: str) -> str | None:
    """YouTube URL에서 VIDEO_ID를 추출한다."""
    if not url:
        return None
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]+)",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def _is_url(s: str) -> bool:
    """문자열이 http(s) URL인지 간단히 판별한다."""
    if not s:
        return False
    return s.strip().startswith(("http://", "https://"))


def _find_registry_project(registry: dict, project_name: str) -> dict | None:
    """registry에서 프로젝트 이름으로 매칭한다 (대소문자 무시)."""
    projects = registry.get("projects", {})
    name_lower = project_name.lower()
    for key, val in projects.items():
        if key.lower() == name_lower:
            return val
    return None


# ── 공개 함수 ──────────────────────────────────────────────


def enrich_resume(data: dict) -> dict:
    """이력서 JSON을 보정한다.

    - person.github URL 정규화
    - 빈 섹션 제거 (빈 리스트는 유지)
    """
    person = data.get("person", {})
    if person.get("github"):
        person["github"] = _normalize_github(person["github"])

    # 빈 섹션 제거: 값이 None이거나 빈 문자열이면 삭제, 빈 리스트는 유지
    keys_to_delete = [
        k
        for k, v in data.items()
        if v is None or (isinstance(v, str) and not v.strip())
    ]
    for k in keys_to_delete:
        del data[k]

    return data


def enrich_portfolio(data: dict, registry: dict | None = None) -> dict:
    """포트폴리오 JSON을 보정한다.

    - highlights 프로젝트별 에셋 자동 매칭
    - person.github URL 정규화
    - STAR bullet 트리밍 (최대 3개)
    """
    if registry is None:
        registry = _load_registry()

    # person.github 정규화
    person = data.get("person", {})
    if person.get("github"):
        person["github"] = _normalize_github(person["github"])

    highlights = data.get("highlights", [])
    for project in highlights:
        project_name = project.get("name", "") or project.get("title", "")
        reg_entry = _find_registry_project(registry, project_name)

        if reg_entry:
            # diagram_img: 비어있거나 URL이 아니면 registry에서 매칭
            if not _is_url(project.get("diagram_img", "")):
                img = reg_entry.get("architecture") or reg_entry.get("flowchart")
                if img:
                    project["diagram_img"] = img

            # demo_img: 비어있거나 URL이 아니면 YouTube 썸네일 생성
            if not _is_url(project.get("demo_img", "")):
                yt_url = (
                    reg_entry.get("youtube")
                    or reg_entry.get("youtube_week1")
                    or reg_entry.get("youtube_week2")
                )
                vid = _youtube_video_id(yt_url) if yt_url else None
                if vid:
                    project["demo_img"] = (
                        f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg"
                    )

            # youtube_url
            if not project.get("youtube_url"):
                yt = (
                    reg_entry.get("youtube")
                    or reg_entry.get("youtube_week1")
                    or reg_entry.get("youtube_week2")
                )
                if yt:
                    project["youtube_url"] = yt

            # github_url
            if not project.get("github_url"):
                gh = reg_entry.get("github")
                if gh:
                    project["github_url"] = gh

        # STAR 항목 트리밍: 각 최대 3개 bullet
        star = project.get("star", {})
        for key in ("situation", "decision", "action", "result"):
            bullets = star.get(key)
            if isinstance(bullets, list) and len(bullets) > 3:
                star[key] = bullets[:3]

    return data


def enrich_cover(data: dict) -> dict:
    """자기소개서 JSON을 보정한다.

    - sections content에 <p> 태그 없으면 단락을 <p>로 감싸기
    - person.github URL 정규화
    """
    # person.github 정규화
    person = data.get("person", {})
    if person.get("github"):
        person["github"] = _normalize_github(person["github"])

    # sections content를 <p>로 감싸기
    sections = data.get("sections", [])
    for section in sections:
        content = section.get("content", "")
        if not content:
            continue
        if "<p>" not in content and "<p " not in content:
            # 빈 줄 기준으로 단락 분리 후 각각 <p>로 감싸기
            paragraphs = re.split(r"\n\s*\n", content.strip())
            wrapped = "\n".join(f"<p>{p.strip()}</p>" for p in paragraphs if p.strip())
            section["content"] = wrapped

    return data
