"""Claude가 반환한 JSON 데이터를 보정하는 후처리 모듈.

agents/writer.py에서 Jinja2 렌더링 전에 호출하여
누락된 에셋 URL을 자동 매칭하고, 데이터를 정규화한다.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

import requests

logger = logging.getLogger("mosaiq.enrich")

REGISTRY_PATH = Path(__file__).parent.parent / "assets" / "registry.json"


# ── OneDrive 이미지 URL 갱신 ──────────────────────────────


_onedrive_token: str | None = None


def _get_onedrive_token() -> str | None:
    """OneDrive access token을 반환한다. 실패 시 None."""
    global _onedrive_token
    if _onedrive_token:
        return _onedrive_token

    client_id = os.environ.get("MICROSOFT_CLIENT_ID", "")
    refresh_token = os.environ.get("MICROSOFT_REFRESH_TOKEN", "")
    if not client_id or not refresh_token:
        return None

    try:
        resp = requests.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "client_id": client_id,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": "Files.Read.All offline_access",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning("OneDrive 토큰 갱신 실패 (HTTP %d)", resp.status_code)
            return None
        token = resp.json().get("access_token")
        if not token:
            logger.warning("OneDrive 토큰 응답에 access_token 없음")
            return None
        _onedrive_token = token
        return _onedrive_token
    except (requests.RequestException, ValueError) as e:
        logger.warning("OneDrive 토큰 갱신 실패: %s", e)
    return None


def _resolve_onedrive_download_url(item_id: str) -> str | None:
    """OneDrive item ID → 임시 download URL을 반환한다."""
    token = _get_onedrive_token()
    if not token:
        return None

    try:
        resp = requests.get(
            f"https://graph.microsoft.com/v1.0/me/drive/items/{item_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if resp.status_code == 200:
            url = resp.json().get("@microsoft.graph.downloadUrl")
            if url:
                logger.info("OneDrive download URL 획득: %s → %s", item_id, url[:80])
                return url
    except (requests.RequestException, ValueError) as e:
        logger.warning("OneDrive URL 갱신 실패 (%s): %s", item_id, e)
    return None


# ── 내부 유틸 ──────────────────────────────────────────────


_registry_cache: dict | None = None


def _load_registry() -> dict:
    """assets/registry.json을 로드한다. 파일 없으면 빈 dict 반환. 결과를 캐싱한다."""
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache
    try:
        _registry_cache = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        _registry_cache = {}
    return _registry_cache


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


def _find_registry_project(registry: dict, project_name: str) -> tuple[dict | None, str | None]:
    """registry에서 프로젝트 이름으로 매칭한다. (매칭 결과, 매칭된 키) 반환.

    매칭 전략 (우선순위):
    1. 정확 매칭 (대소문자 무시)
    2. 부분 매칭: 레지스트리 키가 프로젝트명에 포함되거나 그 반대
    """
    projects = registry.get("projects", {})
    if not project_name:
        return None, None

    name_lower = project_name.lower().strip()

    # 1) 정확 매칭
    for key, val in projects.items():
        if key.lower() == name_lower:
            return val, key

    # 2) 부분 매칭: 레지스트리 키가 프로젝트명에 포함
    for key, val in projects.items():
        key_lower = key.lower()
        if key_lower in name_lower or name_lower in key_lower:
            return val, key

    return None, None


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
        reg_entry, matched_key = _find_registry_project(registry, project_name)

        if reg_entry:
            logger.info("레지스트리 매칭: '%s' → '%s'", project_name, matched_key)

            # diagram_img: GitHub URL 우선 (만료 없음), OneDrive는 보조
            reg_diagram = reg_entry.get("architecture") or reg_entry.get("flowchart")
            if reg_diagram and _is_url(reg_diagram):
                project["diagram_img"] = reg_diagram
            else:
                # GitHub URL이 없으면 OneDrive 시도
                onedrive_arch_id = reg_entry.get("onedrive_architecture_id")
                if onedrive_arch_id:
                    dl_url = _resolve_onedrive_download_url(onedrive_arch_id)
                    if dl_url:
                        project["diagram_img"] = dl_url

            # demo_img: OneDrive → YouTube 썸네일 순으로 주입
            onedrive_demo_id = reg_entry.get("onedrive_demo_id")
            if onedrive_demo_id:
                dl_url = _resolve_onedrive_download_url(onedrive_demo_id)
                if dl_url:
                    project["demo_img"] = dl_url

            # youtube_url 추출
            yt_url = (
                reg_entry.get("youtube")
                or reg_entry.get("youtube_week1")
                or reg_entry.get("youtube_week2")
            )

            # demo_img 유튜브 썸네일 폴백 (OneDrive 실패 시)
            if not _is_url(project.get("demo_img", "")):
                vid = _youtube_video_id(yt_url) if yt_url else None
                if vid:
                    project["demo_img"] = (
                        f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg"
                    )

            # youtube_url: 강제 주입
            if yt_url:
                project["youtube_url"] = yt_url

            # github_url: 강제 주입
            gh = reg_entry.get("github")
            if gh:
                project["github_url"] = gh
        else:
            logger.warning("레지스트리 매칭 실패: '%s'", project_name)

        # 최종 검증: 이미지 URL이 비었으면 경고
        if not _is_url(project.get("diagram_img", "")):
            logger.warning("'%s': diagram_img 없음 — 레지스트리에 에셋 추가 필요", project_name)
        if not _is_url(project.get("demo_img", "")):
            logger.warning("'%s': demo_img 없음 — 레지스트리에 에셋 추가 필요", project_name)

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


def shrink_portfolio_highlight(highlight: dict, level: int) -> dict:
    """강조 프로젝트 데이터를 축소한다. level이 높을수록 더 많이 축소.

    이미지(diagram_img, demo_img)는 절대 제거하지 않는다.
    텍스트만 줄여서 페이지를 맞춘다.

    level 1: STAR bullet 2개로
    level 2: STAR bullet 1개
    level 3: STAR bullet 1개, 기여도 설명 제거
    """
    import copy
    h = copy.deepcopy(highlight)

    if level >= 1:
        for key in ("situation", "decision", "action", "result"):
            if isinstance(h.get(key), list) and len(h[key]) > 2:
                h[key] = h[key][:2]

    if level >= 2:
        for key in ("situation", "decision", "action", "result"):
            if isinstance(h.get(key), list) and len(h[key]) > 1:
                h[key] = h[key][:1]

    if level >= 3:
        h["contribution_desc"] = ""

    return h
