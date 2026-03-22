"""Layer 3: 크로스체크 + 자동 수정.

3개 문서(이력서/포트폴리오/자소서)를 LLM 기반으로 교차 검증하고,
ERROR 급 문제가 발견되면 해당 문서만 targeted 수정을 요청한다.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from agents.llm import ask_claude, extract_json, build_fix_prompt

logger = logging.getLogger("mosaiq.reviewer")

PROMPT = (Path(__file__).parent.parent / "prompts" / "reviewer.md").read_text()


@dataclass
class ReviewIssue:
    doc: str            # "resume" | "portfolio" | "cover"
    category: str       # "일관성" | "중복" | "JD커버리지" | ...
    description: str
    fix_suggestion: str
    severity: str       # "error" | "warning"


def review(
    jd_analysis: str,
    resume_html: str,
    portfolio_html: str,
    cover_letter_html: str,
    questions: list[str],
) -> str:
    """3개 문서를 크로스체크하여 검수 결과 JSON을 반환한다 (하위 호환)."""
    questions_str = "\n".join(f"- {q}" for q in questions) if questions else "자유형"
    prompt = (
        f"{PROMPT}\n\n## JD 분석\n{jd_analysis}\n\n"
        f"## 자소서 문항 및 글자수\n{questions_str}\n\n"
        f"## 이력서\n{resume_html}\n\n"
        f"## 포트폴리오\n{portfolio_html}\n\n"
        f"## 자기소개서\n{cover_letter_html}"
    )
    return extract_json(ask_claude(prompt, timeout=900))


def _parse_review_issues(review_json: str) -> list[ReviewIssue]:
    """reviewer LLM 응답을 ReviewIssue 리스트로 파싱한다."""
    try:
        data = json.loads(review_json)
    except json.JSONDecodeError:
        logger.error("크로스체크 결과 JSON 파싱 실패")
        return []

    issues: list[ReviewIssue] = []

    # reviewer 응답이 다양한 구조일 수 있으므로 유연하게 파싱
    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        # {"issues": [...]} 또는 카테고리별 dict
        if "issues" in data:
            items = data["issues"]
        else:
            for category, entries in data.items():
                if isinstance(entries, list):
                    for entry in entries:
                        if isinstance(entry, dict):
                            entry.setdefault("category", category)
                            items.append(entry)
                elif isinstance(entries, dict):
                    # {"통과": true} 같은 단순 판정은 건너뜀
                    status = entries.get("status") or entries.get("통과") or entries.get("result")
                    if status in (True, "통과", "pass", "ok"):
                        continue
                    entries.setdefault("category", category)
                    items.append(entries)

    for item in items:
        if not isinstance(item, dict):
            continue

        severity = str(item.get("severity", item.get("등급", "warning"))).lower()
        if severity not in ("error", "warning"):
            # "위반", "violation" → error 취급
            severity = "error" if severity in ("위반", "violation", "fail") else "warning"

        doc = item.get("doc", item.get("문서", ""))
        if not doc:
            # 카테고리명에서 문서 추론
            cat = item.get("category", "")
            if "이력서" in cat or "resume" in cat.lower():
                doc = "resume"
            elif "포트폴리오" in cat or "portfolio" in cat.lower():
                doc = "portfolio"
            elif "자소서" in cat or "cover" in cat.lower():
                doc = "cover"

        issues.append(ReviewIssue(
            doc=doc,
            category=item.get("category", item.get("카테고리", "")),
            description=item.get("description", item.get("설명", item.get("message", str(item)))),
            fix_suggestion=item.get("fix_suggestion", item.get("수정제안", item.get("suggestion", ""))),
            severity=severity,
        ))

    return issues


def review_and_fix(
    jd_analysis: str,
    resume_data: dict,
    portfolio_data: dict,
    cover_data: dict,
    questions: list[str],
) -> tuple[dict, dict, dict, list[ReviewIssue]]:
    """Layer 3: 크로스체크 후 ERROR 급 문제는 자동 수정한다.

    Returns:
        (resume_data, portfolio_data, cover_data, issues)
        수정된 데이터와 발견된 이슈 리스트를 반환한다.
    """
    from agents.writer import render_template

    # 렌더링하여 reviewer에 전달 (reviewer는 HTML을 보고 판단)
    resume_html = render_template("resume.html", resume_data)
    portfolio_html = render_template("portfolio.html", portfolio_data)
    cover_html = render_template("cover_letter.html", cover_data)

    # 1단계: 문제 탐지
    review_json = review(jd_analysis, resume_html, portfolio_html, cover_html, questions)
    issues = _parse_review_issues(review_json)

    for issue in issues:
        level = logger.error if issue.severity == "error" else logger.warning
        level("[크로스체크] %s/%s: %s", issue.doc, issue.category, issue.description)

    errors = [i for i in issues if i.severity == "error" and i.doc]
    if not errors:
        logger.info("크로스체크 통과: ERROR 없음 (%d WARNING)", len(issues))
        return resume_data, portfolio_data, cover_data, issues

    # 2단계: targeted 수정 (1회만)
    logger.warning("크로스체크 ERROR %d건 → targeted 수정 시도", len(errors))
    fix_prompt = build_fix_prompt(errors, resume_data, portfolio_data, cover_data, context_label="크로스체크")

    try:
        fixed_response = ask_claude(fix_prompt, timeout=600)
        fixed_json = extract_json(fixed_response)
        fixed_data = json.loads(fixed_json)

        affected_docs = {i.doc for i in errors}
        if "resume" in affected_docs and "resume" in fixed_data:
            resume_data = fixed_data["resume"]
            logger.info("이력서 크로스체크 수정 적용")
        if "portfolio" in affected_docs and "portfolio" in fixed_data:
            portfolio_data = fixed_data["portfolio"]
            logger.info("포트폴리오 크로스체크 수정 적용")
        if "cover" in affected_docs and "cover" in fixed_data:
            cover_data = fixed_data["cover"]
            logger.info("자소서 크로스체크 수정 적용")

    except (json.JSONDecodeError, RuntimeError, KeyError) as e:
        logger.error("크로스체크 수정 실패: %s — 원본 유지", e)

    return resume_data, portfolio_data, cover_data, issues
