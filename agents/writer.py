import re
from pathlib import Path

from agents.llm import ask_claude

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
RESUME_PROMPT = (PROMPTS_DIR / "writer_resume.md").read_text()
PORTFOLIO_PROMPT = (PROMPTS_DIR / "writer_portfolio.md").read_text()
COVER_PROMPT = (PROMPTS_DIR / "writer_cover.md").read_text()


def _extract_html(response: str) -> str:
    """LLM 응답에서 순수 HTML만 추출한다.

    - ```html ... ``` 코드블록 마커를 제거한다.
    - <!DOCTYPE html> 또는 <html 부터 </html> 까지만 추출한다.
    - HTML 태그가 없으면 원본 그대로 반환한다 (fallback).
    """
    # 1) ```html ... ``` 코드블록 마커 제거
    text = re.sub(r"```html\s*\n?", "", response)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)

    # 2) <!DOCTYPE html> 또는 <html 부터 </html> 까지 추출
    match = re.search(
        r"(<!DOCTYPE\s+html\b[^>]*>.*?</html>|<html\b[^>]*>.*?</html>)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        return match.group(0).strip()

    # 3) fallback: HTML 태그가 없으면 원본 그대로
    return response


def write_resume(strategy: str, source_data: str, jd_analysis: str) -> str:
    """이력서 HTML을 생성한다."""
    prompt = f"{RESUME_PROMPT}\n\n## 전략\n{strategy}\n\n## 소스 데이터\n{source_data}\n\n## JD 분석\n{jd_analysis}"
    return _extract_html(ask_claude(prompt, timeout=600))


def write_portfolio(strategy: str, source_data: str, resume_html: str) -> str:
    """포트폴리오 HTML을 생성한다."""
    prompt = f"{PORTFOLIO_PROMPT}\n\n## 전략\n{strategy}\n\n## 소스 데이터\n{source_data}\n\n## 이력서 (참조용, 내용 반복 금지)\n{resume_html}"
    return _extract_html(ask_claude(prompt, timeout=600))


def write_cover(
    strategy: str,
    jd_analysis: str,
    resume_html: str,
    portfolio_html: str,
    questions: list[str],
) -> str:
    """자기소개서 HTML을 생성한다."""
    questions_str = "\n".join(f"- {q}" for q in questions) if questions else "자유형 (문항 없음)"
    prompt = (
        f"{COVER_PROMPT}\n\n## 전략\n{strategy}\n\n## JD 분석\n{jd_analysis}\n\n"
        f"## 자소서 문항\n{questions_str}\n\n"
        f"## 이력서 (참조용, 내용 반복 금지)\n{resume_html}\n\n"
        f"## 포트폴리오 (참조용, 내용 반복 금지)\n{portfolio_html}"
    )
    return _extract_html(ask_claude(prompt, timeout=600))
