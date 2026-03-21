"""QA agent – Claude가 반환한 JSON 데이터를 검증한다.

Layer 1 (구조 검증): 필수 필드 존재, 플레이스홀더, 포맷 검사
Layer 2 (내용 검증): 잘림 감지, 톤 일관성, 최소 길이, 날짜 형식 등

Severity:
    ERROR   — writer에서 재생성/수정을 트리거한다.
    WARNING — 로그에 기록하고 진행한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class QAResult:
    severity: Severity
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.value}] {self.message}"


_PLACEHOLDER_RE = re.compile(
    r"\[.*?\]|<.*?>|TODO|FIXME|입력\s*필요|작성\s*필요|직접\s*기재",
    re.IGNORECASE,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^[\d\-+()\s]{9,}$")


# ── 공통 헬퍼 ──────────────────────────────────────────────


def _has_placeholder(text: str) -> bool:
    """텍스트에 플레이스홀더 패턴이 있는지 확인한다."""
    if not text:
        return False
    # HTML 태그는 제외 (<p>, <br> 등)
    clean = re.sub(r"<(?:p|br|div|span|strong|em|ul|ol|li|h[1-6]|a|img)[^>]*>", "", text)
    clean = re.sub(r"</(?:p|br|div|span|strong|em|ul|ol|li|h[1-6]|a)>", "", clean)
    return bool(_PLACEHOLDER_RE.search(clean))


def _check_person(data: dict, results: list[QAResult], required_fields: list[str]) -> None:
    """person 필드 공통 검증."""
    person = data.get("person") or {}

    name = person.get("name", "")
    if not name:
        results.append(QAResult(Severity.ERROR, "person.name이 비어 있습니다."))
    elif _has_placeholder(name):
        results.append(QAResult(Severity.ERROR, f"person.name에 플레이스홀더 포함: '{name}'"))

    for field in required_fields:
        if field == "name":
            continue
        val = person.get(field, "")
        if not val:
            results.append(QAResult(Severity.ERROR, f"person.{field}이(가) 비어 있습니다."))

    # 이메일 형식 검증
    email = person.get("email", "")
    if email and not _EMAIL_RE.match(email):
        results.append(QAResult(Severity.ERROR, f"person.email 형식 오류: '{email}'"))

    # 전화번호 형식 검증
    phone = person.get("phone", "")
    if phone and not _PHONE_RE.match(phone):
        results.append(QAResult(Severity.ERROR, f"person.phone 형식 오류: '{phone}'"))


def has_errors(results: list[QAResult]) -> bool:
    """결과에 ERROR가 있는지 확인한다."""
    return any(r.severity == Severity.ERROR for r in results)


def format_errors(results: list[QAResult]) -> str:
    """ERROR만 추출하여 피드백 문자열로 변환한다."""
    errors = [r for r in results if r.severity == Severity.ERROR]
    return "\n".join(f"- {r.message}" for r in errors)


# ── Layer 2 공통: 내용 품질 헬퍼 ─────────────────────────────


def _is_truncated(text: str) -> bool:
    """텍스트가 잘려 있는지 감지한다.

    "…" (U+2026)은 거의 항상 잘림. "..."은 의도적 줄임표일 수 있으므로 제외.
    """
    if not text or len(text) < 10:
        return False
    stripped = text.rstrip()
    return stripped.endswith("…")


def _check_truncation(obj, path: str, results: list[QAResult]) -> None:
    """재귀적으로 모든 문자열 필드에서 잘림(…) 감지."""
    if isinstance(obj, str):
        if obj.rstrip().endswith("…") and len(obj) > 20:
            results.append(QAResult(
                Severity.ERROR,
                f"{path}: 텍스트가 잘려 있습니다 ('…{obj[-40:]}')",
            ))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _check_truncation(v, f"{path}.{k}" if path else k, results)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _check_truncation(v, f"{path}[{i}]", results)


def _check_sentence_ending(text: str) -> bool:
    """한국어 문장이 자연스럽게 끝나는지 확인한다."""
    if not text:
        return True
    stripped = text.rstrip()
    # 한국어 문장 종결 패턴
    return bool(re.search(r"[.다요음됨함임니까세]$", stripped))


def _check_tone_consistency(sections: list[dict], results: list[QAResult]) -> None:
    """합쇼체(습니다/입니다)와 해요체(해요/에요) 혼용 감지."""
    all_text = " ".join(s.get("content", "") for s in sections)
    plain = re.sub(r"<[^>]+>", "", all_text)

    formal = len(re.findall(r"[가-힣](?:습니다|ㅂ니다)", plain))
    casual = len(re.findall(r"[가-힣](?:어요|아요|에요|예요|여요|죠)", plain))

    if formal > 0 and casual > 0:
        results.append(QAResult(
            Severity.ERROR,
            f"톤 불일치: 합쇼체 {formal}회 + 해요체 {casual}회 혼용",
        ))


# ── Layer 1: 이력서 구조 검증 ─────────────────────────────────


def validate_resume(data: dict) -> list[QAResult]:
    """이력서 JSON 구조를 검증한다."""
    results: list[QAResult] = []

    _check_person(data, results, ["name", "phone", "email"])

    if not data.get("summary"):
        results.append(QAResult(Severity.ERROR, "summary가 비어 있습니다."))

    if not data.get("careers"):
        results.append(QAResult(Severity.ERROR, "careers가 비어 있습니다."))

    if not data.get("projects"):
        results.append(QAResult(Severity.ERROR, "projects가 비어 있습니다."))

    education = data.get("education")
    if not education:
        results.append(QAResult(Severity.ERROR, "education이 비어 있습니다."))
    elif isinstance(education, list):
        for i, edu in enumerate(education):
            if not edu.get("school"):
                results.append(QAResult(Severity.ERROR, f"education[{i}]: 학교명이 누락되었습니다."))
            school = edu.get("school", "")
            if _has_placeholder(school):
                results.append(QAResult(Severity.ERROR, f"education[{i}]: 학교명에 플레이스홀더 포함: '{school}'"))

    if not data.get("skills"):
        results.append(QAResult(Severity.ERROR, "skills가 비어 있습니다."))

    # WARNING: 개인 프로젝트 포함 여부
    projects = data.get("projects") or []
    has_personal = any(p.get("is_personal") for p in projects)
    if projects and not has_personal:
        results.append(QAResult(Severity.WARNING, "개인 프로젝트가 없습니다. 자발성 증명을 위해 포함을 권장합니다."))

    return results


# ── Layer 1: 포트폴리오 구조 검증 ─────────────────────────────


def validate_portfolio(data: dict) -> list[QAResult]:
    """포트폴리오 JSON 구조를 검증한다."""
    results: list[QAResult] = []

    _check_person(data, results, ["name"])

    if not data.get("summary"):
        results.append(QAResult(Severity.ERROR, "summary가 비어 있습니다."))

    competencies = data.get("competencies") or []
    if len(competencies) < 3:
        results.append(QAResult(Severity.ERROR, f"competencies가 3개 미만입니다. (현재 {len(competencies)}개)"))

    highlights = data.get("highlights") or []
    if not highlights:
        results.append(QAResult(Severity.ERROR, "highlights가 비어 있습니다."))

    for i, hl in enumerate(highlights):
        for field in ("situation", "decision", "action", "result"):
            if not hl.get(field):
                results.append(QAResult(Severity.ERROR, f"highlights[{i}]: {field}이(가) 비어 있습니다."))

        if hl.get("contribution_pct", 0) == 0:
            results.append(QAResult(Severity.ERROR, f"highlights[{i}]: contribution_pct가 0입니다."))

        if not hl.get("tags"):
            results.append(QAResult(Severity.ERROR, f"highlights[{i}]: tags가 비어 있습니다."))

        # 이미지 에셋 존재 여부 (enrich 후 검증) — ERROR로 상향
        name = hl.get("name", f"highlights[{i}]")
        if not hl.get("diagram_img"):
            results.append(QAResult(Severity.ERROR, f"{name}: diagram_img가 없습니다. 레지스트리에 에셋이 있는 프로젝트를 강조 프로젝트로 선정하세요."))
        if not hl.get("demo_img"):
            results.append(QAResult(Severity.WARNING, f"{name}: demo_img가 없습니다. (유튜브 썸네일 생성 실패 가능)"))

    # WARNING: other_projects 개수
    other_projects = data.get("other_projects") or []
    if len(other_projects) < 3:
        results.append(QAResult(Severity.WARNING, f"other_projects가 3개 미만입니다. (현재 {len(other_projects)}개)"))

    return results


# ── Layer 1: 자소서 구조 검증 ─────────────────────────────────


def validate_cover(data: dict) -> list[QAResult]:
    """자기소개서 JSON 구조를 검증한다."""
    results: list[QAResult] = []

    target = data.get("target") or {}
    if not target.get("company"):
        results.append(QAResult(Severity.ERROR, "target.company가 비어 있습니다."))
    if not target.get("position"):
        results.append(QAResult(Severity.ERROR, "target.position이 비어 있습니다."))

    sections = data.get("sections") or []
    if not sections:
        results.append(QAResult(Severity.ERROR, "sections가 비어 있습니다."))

    total_chars = 0
    for i, sec in enumerate(sections):
        content = sec.get("content", "")
        if len(content) < 100:
            results.append(QAResult(Severity.ERROR, f"sections[{i}]: 내용이 너무 짧습니다. ({len(content)}자)"))

        for key in ("person", "target"):
            if f'"{key}"' in content or f"'{key}'" in content:
                results.append(QAResult(Severity.ERROR, f"sections[{i}]: JSON 원문이 content에 혼입되었습니다."))

        # HTML 태그 제거 후 순수 텍스트 길이 계산
        plain = re.sub(r"<[^>]+>", "", content)
        total_chars += len(plain.strip())

    # WARNING: 자유형 글자수 범위
    if sections and total_chars > 0:
        if total_chars < 800:
            results.append(QAResult(Severity.WARNING, f"자소서 전체 {total_chars}자 — 800자 미만으로 짧습니다."))
        elif total_chars > 1200:
            results.append(QAResult(Severity.WARNING, f"자소서 전체 {total_chars}자 — 1200자 초과입니다."))

    return results


# ── Layer 2: 이력서 내용 검증 ─────────────────────────────────


def validate_content_resume(data: dict) -> list[QAResult]:
    """이력서 내용 품질을 검증한다 (규칙 기반, LLM 호출 없음)."""
    results: list[QAResult] = []

    # 1. 잘림 감지
    _check_truncation(data, "", results)

    # 2. 요약문 최소 길이
    summary = data.get("summary", "")
    plain_summary = re.sub(r"<[^>]+>", "", summary)
    if plain_summary and len(plain_summary) < 30:
        results.append(QAResult(Severity.ERROR, f"summary가 너무 짧습니다. ({len(plain_summary)}자)"))

    # 3. 프로젝트 tags 누락
    for i, proj in enumerate(data.get("projects", [])):
        if not proj.get("tags"):
            results.append(QAResult(Severity.WARNING, f"projects[{i}] '{proj.get('name', '')}': tags 누락"))

    # 4. 플레이스홀더 심층 검사 (모든 문자열 필드)
    _check_placeholder_deep(data, "", results)

    return results


# ── Layer 2: 포트폴리오 내용 검증 ─────────────────────────────


def validate_content_portfolio(data: dict) -> list[QAResult]:
    """포트폴리오 내용 품질을 검증한다."""
    results: list[QAResult] = []

    # 1. 잘림 감지 (전체)
    _check_truncation(data, "", results)

    for i, hl in enumerate(data.get("highlights", [])):
        name = hl.get("name", f"highlights[{i}]")

        # 2. overview 완성도
        ov = hl.get("overview", "")
        if ov and not _check_sentence_ending(ov):
            results.append(QAResult(
                Severity.ERROR,
                f"'{name}' overview가 문장으로 끝나지 않습니다: '{ov[-30:]}'",
            ))

        # 3. STAR bullet 최소 개수 (action, result는 반드시 2개 이상)
        for field in ("action", "result"):
            bullets = hl.get(field, [])
            if isinstance(bullets, list) and len(bullets) < 2:
                results.append(QAResult(
                    Severity.ERROR,
                    f"'{name}' {field}이 {len(bullets)}개뿐입니다. 최소 2개 bullet을 작성해야 합니다.",
                ))

        # 4. STAR bullet 최소 길이
        for field in ("situation", "decision", "action", "result"):
            bullets = hl.get(field, [])
            if isinstance(bullets, list):
                for j, b in enumerate(bullets):
                    if isinstance(b, str) and 0 < len(b) < 10:
                        results.append(QAResult(
                            Severity.WARNING,
                            f"'{name}' {field}[{j}] 너무 짧음 ({len(b)}자): '{b}'",
                        ))

    # 5. project_table 개수 제한 (7개 초과 시 1페이지 overflow)
    project_table = data.get("project_table", [])
    if len(project_table) > 7:
        results.append(QAResult(
            Severity.ERROR,
            f"project_table이 {len(project_table)}개입니다. 1페이지에 맞추려면 최대 7개여야 합니다.",
        ))

    # 6. overview 최소 길이 (잘린 게 아니라 원래 너무 짧은 경우)
    for i, hl in enumerate(data.get("highlights", [])):
        ov = hl.get("overview", "")
        if ov and len(ov) < 40:
            results.append(QAResult(
                Severity.WARNING,
                f"'{hl.get('name', '')}' overview가 너무 짧습니다 ({len(ov)}자). 2줄 이상 권장.",
            ))

    # 7. 플레이스홀더 심층 검사
    _check_placeholder_deep(data, "", results)

    return results


# ── Layer 2: 자소서 내용 검증 ─────────────────────────────────


def validate_content_cover(data: dict) -> list[QAResult]:
    """자소서 내용 품질을 검증한다."""
    results: list[QAResult] = []

    sections = data.get("sections", [])

    # 1. 잘림 감지
    for i, sec in enumerate(sections):
        content = sec.get("content", "")
        if content.rstrip().endswith("…"):
            results.append(QAResult(Severity.ERROR, f"sections[{i}]: 내용이 잘려 있습니다"))

    # 2. 톤 일관성
    _check_tone_consistency(sections, results)

    # 3. "~하겠습니다" 과다 사용
    all_text = " ".join(s.get("content", "") for s in sections)
    plain = re.sub(r"<[^>]+>", "", all_text)
    future_count = len(re.findall(r"하겠습니다", plain))
    if future_count > 3:
        results.append(QAResult(
            Severity.WARNING,
            f"'하겠습니다' {future_count}회 사용 — 미래 다짐보다 과거 행동 중심 권장",
        ))

    # 4. AI투 표현 감지
    ai_patterns = [
        (r"깊은\s*관심을\s*가지고", "깊은 관심을 가지고"),
        (r"큰\s*매력을\s*느꼈", "큰 매력을 느꼈"),
        (r"마음을\s*굳혔습니다", "마음을 굳혔습니다"),
        (r"그때\s*깨달았습니다", "그때 깨달았습니다"),
        (r"이바지", "이바지"),
        (r"역량을\s*함양", "역량을 함양"),
        (r"전문성을\s*배양", "전문성을 배양"),
        (r"시너지", "시너지"),
        (r"패러다임", "패러다임"),
        (r"열정적으로|적극적으로|끊임없이|능동적으로", "과도한 부사"),
    ]
    ai_found = []
    for pattern, label in ai_patterns:
        if re.search(pattern, plain):
            ai_found.append(label)
    if ai_found:
        results.append(QAResult(
            Severity.ERROR,
            f"AI투 표현 감지: {', '.join(ai_found)} — 자연스러운 서사체로 수정 필요",
        ))

    # 4. 플레이스홀더 심층 검사
    _check_placeholder_deep(data, "", results)

    return results


def _check_placeholder_deep(obj, path: str, results: list[QAResult]) -> None:
    """재귀적으로 모든 문자열 필드에서 플레이스홀더를 감지한다."""
    if isinstance(obj, str):
        if _has_placeholder(obj) and len(obj) < 200:
            results.append(QAResult(
                Severity.ERROR,
                f"{path}: 플레이스홀더 감지 ('{obj[:60]}')",
            ))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _check_placeholder_deep(v, f"{path}.{k}" if path else k, results)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _check_placeholder_deep(v, f"{path}[{i}]", results)


# ── 블루프린트 검증 (V2) ─────────────────────────────────────


def validate_blueprint(data: dict) -> list[QAResult]:
    """V2 블루프린트 구조를 검증한다."""
    results: list[QAResult] = []

    if not data.get("gap_matrix"):
        results.append(QAResult(Severity.ERROR, "gap_matrix가 비어 있습니다."))

    positioning = data.get("positioning", {})
    if not positioning.get("one_liner"):
        results.append(QAResult(Severity.ERROR, "positioning.one_liner가 비어 있습니다."))
    key_msgs = positioning.get("key_messages", [])
    if len(key_msgs) < 3:
        results.append(QAResult(Severity.WARNING, f"positioning.key_messages가 3개 미만입니다 ({len(key_msgs)}개)."))

    blueprint = data.get("blueprint", {})
    dist = blueprint.get("experience_distribution", {})
    for doc in ("resume", "portfolio", "cover"):
        if not dist.get(doc):
            results.append(QAResult(Severity.ERROR, f"blueprint.experience_distribution.{doc}가 비어 있습니다."))

    if not blueprint.get("emotional_arc"):
        results.append(QAResult(Severity.WARNING, "blueprint.emotional_arc가 비어 있습니다."))
    if not blueprint.get("per_document_role"):
        results.append(QAResult(Severity.WARNING, "blueprint.per_document_role이 비어 있습니다."))

    if not data.get("highlight_projects"):
        results.append(QAResult(Severity.ERROR, "highlight_projects가 비어 있습니다."))
    if not data.get("storyline"):
        results.append(QAResult(Severity.ERROR, "storyline이 비어 있습니다."))

    match_rate = data.get("match_rate")
    if match_rate is not None and not (0 <= match_rate <= 100):
        results.append(QAResult(Severity.WARNING, f"match_rate가 0~100 범위 밖입니다: {match_rate}"))

    return results


# ── 통합 검증 ──────────────────────────────────────────────


def validate_all(
    resume_data: dict,
    portfolio_data: dict,
    cover_data: dict,
) -> dict[str, list[QAResult]]:
    """이력서·포트폴리오·자기소개서를 한꺼번에 검증한다."""
    return {
        "resume": validate_resume(resume_data),
        "portfolio": validate_portfolio(portfolio_data),
        "cover": validate_cover(cover_data),
    }
