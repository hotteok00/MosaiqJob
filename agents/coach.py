"""V2 설득력 코칭 에이전트.

3개 문서를 HR/팀리더/채용결정자 관점에서 시뮬레이션 검토하고,
면접 리스크를 분석한다. ERROR 급 문제는 자동 수정한다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from agents.llm import ask_claude, extract_json

logger = logging.getLogger("mosaiq.coach")

PROMPT = (Path(__file__).parent.parent / "prompts" / "coach.md").read_text()


@dataclass
class CoachFeedback:
    doc: str            # "resume" | "portfolio" | "cover"
    persona: str        # "HR_screener" | "team_lead" | "hiring_manager" | "cross_check"
    category: str       # "설득력" | "차별화" | "감정흐름" | "일관성" | ...
    score: int          # 1-5 (해당 없으면 0)
    description: str
    fix_suggestion: str
    severity: str       # "error" | "warning"


@dataclass
class InterviewRisk:
    predicted_question: str
    source: str
    risk_level: str     # "high" | "medium" | "low"
    defense_strategy: str
    sample_answer: str


def _parse_coach_result(raw_json: str) -> tuple[list[CoachFeedback], dict, list[InterviewRisk]]:
    """코치 LLM 응답을 파싱한다."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        logger.error("코칭 결과 JSON 파싱 실패")
        return [], {}, []

    feedbacks: list[CoachFeedback] = []
    for item in data.get("feedbacks", []):
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity", "warning")).lower()
        if severity not in ("error", "warning"):
            severity = "error" if severity in ("위반", "violation", "fail") else "warning"
        feedbacks.append(CoachFeedback(
            doc=item.get("doc", ""),
            persona=item.get("persona", ""),
            category=item.get("category", ""),
            score=int(item.get("score", 0)),
            description=item.get("description", str(item)),
            fix_suggestion=item.get("fix_suggestion", ""),
            severity=severity,
        ))

    overall = data.get("overall_scores", {})

    risks: list[InterviewRisk] = []
    for item in data.get("interview_risks", []):
        if not isinstance(item, dict):
            continue
        risks.append(InterviewRisk(
            predicted_question=item.get("predicted_question", ""),
            source=item.get("source", ""),
            risk_level=item.get("risk_level", "medium"),
            defense_strategy=item.get("defense_strategy", ""),
            sample_answer=item.get("sample_answer", ""),
        ))

    return feedbacks, overall, risks


def _build_fix_prompt(
    errors: list[CoachFeedback],
    resume_data: dict,
    portfolio_data: dict,
    cover_data: dict,
) -> str:
    """ERROR 급 피드백에 대한 targeted fix 프롬프트를 생성한다."""
    affected_docs = {f.doc for f in errors if f.doc}

    error_lines = []
    for fb in errors:
        error_lines.append(f"- [{fb.doc}] {fb.persona}/{fb.category}: {fb.description}")
        if fb.fix_suggestion:
            error_lines.append(f"  수정 제안: {fb.fix_suggestion}")
    errors_text = "\n".join(error_lines)

    parts = [
        "아래 설득력 코칭에서 발견된 오류를 수정하세요.",
        "수정이 필요한 문서의 JSON만 수정하여 반환하세요.",
        "수정 대상이 아닌 문서는 포함하지 마세요.",
        "나머지 내용은 절대 변경하지 마세요.",
        "",
        "## 발견된 오류",
        errors_text,
        "",
    ]

    if "resume" in affected_docs:
        parts.append("## 이력서 JSON")
        parts.append(json.dumps(resume_data, ensure_ascii=False))
        parts.append("")
    if "portfolio" in affected_docs:
        parts.append("## 포트폴리오 JSON")
        parts.append(json.dumps(portfolio_data, ensure_ascii=False))
        parts.append("")
    if "cover" in affected_docs:
        parts.append("## 자소서 JSON")
        parts.append(json.dumps(cover_data, ensure_ascii=False))
        parts.append("")

    parts.append(
        '수정된 JSON을 다음 형식으로 반환하세요: {"resume": {...}, "portfolio": {...}, "cover": {...}}'
        " (수정한 문서만 포함). 코드블록 마커(```)를 사용하지 마세요."
    )

    return "\n".join(parts)


def coach_review(
    jd_analysis: str,
    blueprint: str,
    resume_data: dict,
    portfolio_data: dict,
    cover_data: dict,
    questions: list[str],
) -> tuple[dict, dict, dict, list[CoachFeedback], dict, list[InterviewRisk]]:
    """설득력 코칭 + 면접 리스크 분석.

    Returns:
        (resume_data, portfolio_data, cover_data, feedbacks, overall_scores, interview_risks)
    """
    from agents.writer import render_template

    resume_html = render_template("resume.html", resume_data)
    portfolio_html = render_template("portfolio.html", portfolio_data)
    cover_html = render_template("cover_letter.html", cover_data)

    questions_str = "\n".join(f"- {q}" for q in questions) if questions else "자유형"
    prompt = (
        f"{PROMPT}\n\n"
        f"## 블루프린트\n{blueprint}\n\n"
        f"## JD 분석\n{jd_analysis}\n\n"
        f"## 자소서 문항\n{questions_str}\n\n"
        f"## 이력서\n{resume_html}\n\n"
        f"## 포트폴리오\n{portfolio_html}\n\n"
        f"## 자기소개서\n{cover_html}"
    )

    raw = extract_json(ask_claude(prompt, timeout=900))
    feedbacks, overall, risks = _parse_coach_result(raw)

    for fb in feedbacks:
        level = logger.error if fb.severity == "error" else logger.warning
        level("[코칭] %s/%s/%s: %s", fb.doc, fb.persona, fb.category, fb.description)

    # ERROR 급 이슈 자동 수정 (1회)
    errors = [f for f in feedbacks if f.severity == "error" and f.doc]
    if not errors:
        logger.info("코칭 통과: ERROR 없음 (%d WARNING)", len(feedbacks))
        return resume_data, portfolio_data, cover_data, feedbacks, overall, risks

    logger.warning("코칭 ERROR %d건 → targeted 수정 시도", len(errors))
    fix_prompt = _build_fix_prompt(errors, resume_data, portfolio_data, cover_data)

    try:
        fixed_response = ask_claude(fix_prompt, timeout=600)
        fixed_json = extract_json(fixed_response)
        fixed_data = json.loads(fixed_json)

        affected_docs = {f.doc for f in errors}
        if "resume" in affected_docs and "resume" in fixed_data:
            resume_data = fixed_data["resume"]
            logger.info("이력서 코칭 수정 적용")
        if "portfolio" in affected_docs and "portfolio" in fixed_data:
            portfolio_data = fixed_data["portfolio"]
            logger.info("포트폴리오 코칭 수정 적용")
        if "cover" in affected_docs and "cover" in fixed_data:
            cover_data = fixed_data["cover"]
            logger.info("자소서 코칭 수정 적용")

    except (json.JSONDecodeError, RuntimeError, KeyError) as e:
        logger.error("코칭 수정 실패: %s — 원본 유지", e)

    return resume_data, portfolio_data, cover_data, feedbacks, overall, risks
