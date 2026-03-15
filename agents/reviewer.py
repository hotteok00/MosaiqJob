from pathlib import Path

from agents.llm import ask_claude, extract_json

PROMPT = (Path(__file__).parent.parent / "prompts" / "reviewer.md").read_text()


def review(
    jd_analysis: str,
    resume_html: str,
    portfolio_html: str,
    cover_letter_html: str,
    questions: list[str],
) -> str:
    """3개 문서를 크로스체크하여 검수 결과 JSON을 반환한다."""
    questions_str = "\n".join(f"- {q}" for q in questions) if questions else "자유형"
    prompt = (
        f"{PROMPT}\n\n## JD 분석\n{jd_analysis}\n\n"
        f"## 자소서 문항 및 글자수\n{questions_str}\n\n"
        f"## 이력서\n{resume_html}\n\n"
        f"## 포트폴리오\n{portfolio_html}\n\n"
        f"## 자기소개서\n{cover_letter_html}"
    )
    return extract_json(ask_claude(prompt, timeout=900))
