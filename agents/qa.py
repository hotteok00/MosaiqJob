"""QA agent – Claude가 반환한 JSON 데이터의 구조를 검증하고 경고 목록을 반환한다."""

from __future__ import annotations

_PLACEHOLDER_KEYWORDS = ["[", "직접 기재"]


def _check_person_name(data: dict, warnings: list[str]) -> None:
    """person.name 공통 검증."""
    name = (data.get("person") or {}).get("name", "")
    if not name:
        warnings.append("person.name이 비어 있습니다.")
    else:
        for kw in _PLACEHOLDER_KEYWORDS:
            if kw in name:
                warnings.append(
                    f"person.name에 플레이스홀더가 포함되어 있습니다: '{kw}'"
                )
                break


def validate_resume(data: dict) -> list[str]:
    """이력서 JSON 구조를 검증한다."""
    warnings: list[str] = []

    _check_person_name(data, warnings)

    if not data.get("summary"):
        warnings.append("summary가 비어 있습니다.")

    if not data.get("careers"):
        warnings.append("careers가 비어 있습니다.")

    if not data.get("projects"):
        warnings.append("projects가 비어 있습니다.")

    education = data.get("education")
    if not education:
        warnings.append("education이 비어 있습니다.")
    elif isinstance(education, list):
        for i, edu in enumerate(education):
            if not edu.get("school"):
                warnings.append(f"education[{i}]: 학교명이 누락되었습니다.")

    if not data.get("skills"):
        warnings.append("skills가 비어 있습니다.")

    return warnings


def validate_portfolio(data: dict) -> list[str]:
    """포트폴리오 JSON 구조를 검증한다."""
    warnings: list[str] = []

    _check_person_name(data, warnings)

    if not data.get("summary"):
        warnings.append("summary가 비어 있습니다.")

    competencies = data.get("competencies") or []
    if len(competencies) < 3:
        warnings.append(
            f"competencies가 3개 미만입니다. (현재 {len(competencies)}개)"
        )

    highlights = data.get("highlights") or []
    if not highlights:
        warnings.append("highlights가 비어 있습니다.")

    for i, hl in enumerate(highlights):
        for field in ("situation", "decision", "action", "result"):
            if not hl.get(field):
                warnings.append(f"highlights[{i}]: {field}이(가) 비어 있습니다.")

        if hl.get("contribution_pct", 0) == 0:
            warnings.append(f"highlights[{i}]: contribution_pct가 0입니다.")

        if not hl.get("tags"):
            warnings.append(f"highlights[{i}]: tags가 비어 있습니다.")

    return warnings


def validate_cover(data: dict) -> list[str]:
    """자기소개서 JSON 구조를 검증한다."""
    warnings: list[str] = []

    target = data.get("target") or {}
    if not target.get("company"):
        warnings.append("target.company가 비어 있습니다.")
    if not target.get("position"):
        warnings.append("target.position이 비어 있습니다.")

    sections = data.get("sections") or []
    if not sections:
        warnings.append("sections가 비어 있습니다.")

    for i, sec in enumerate(sections):
        content = sec.get("content", "")
        if len(content) < 100:
            warnings.append(f"sections[{i}]: 내용이 너무 짧습니다. ({len(content)}자)")

        for key in ("person", "target"):
            if f'"{key}"' in content or f"'{key}'" in content:
                warnings.append(
                    f"sections[{i}]: JSON 원문이 content에 포함되어 있습니다. ('{key}')"
                )

    return warnings


def validate_all(
    resume_data: dict,
    portfolio_data: dict,
    cover_data: dict,
) -> dict[str, list[str]]:
    """이력서·포트폴리오·자기소개서를 한꺼번에 검증한다."""
    return {
        "resume": validate_resume(resume_data),
        "portfolio": validate_portfolio(portfolio_data),
        "cover": validate_cover(cover_data),
    }
