import json
import re
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from agents.enrich import enrich_resume, enrich_portfolio, enrich_cover, _load_registry
from agents.llm import ask_claude, extract_json
from agents.qa import validate_resume, validate_portfolio, validate_cover

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

RESUME_PROMPT = (PROMPTS_DIR / "writer_resume.md").read_text()
PORTFOLIO_PROMPT = (PROMPTS_DIR / "writer_portfolio.md").read_text()
COVER_PROMPT = (PROMPTS_DIR / "writer_cover.md").read_text()

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=False,
)


def _render_template(template_name: str, data_json: str) -> str:
    """JSON 문자열을 파싱하여 Jinja2 템플릿으로 렌더링한다."""
    data = json.loads(data_json)
    template = _jinja_env.get_template(template_name)
    return template.render(**data)


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
    result = ask_claude(prompt, timeout=600)
    try:
        json_str = extract_json(result)
        data = json.loads(json_str)
        data = enrich_resume(data)
        warnings = validate_resume(data)
        if warnings:
            sys.stderr.write(f"[QA] 이력서 경고: {warnings}\n")
        return _render_template("resume.html", json.dumps(data, ensure_ascii=False))
    except (json.JSONDecodeError, Exception):
        return _extract_html(result)


def write_portfolio(strategy: str, source_data: str, resume_html: str) -> str:
    """포트폴리오 HTML을 생성한다."""
    prompt = f"{PORTFOLIO_PROMPT}\n\n## 전략\n{strategy}\n\n## 소스 데이터\n{source_data}\n\n## 이력서 (참조용, 내용 반복 금지)\n{resume_html}"
    result = ask_claude(prompt, timeout=600)
    try:
        json_str = extract_json(result)
        data = json.loads(json_str)
        data = enrich_portfolio(data, _load_registry())
        warnings = validate_portfolio(data)
        if warnings:
            sys.stderr.write(f"[QA] 포트폴리오 경고: {warnings}\n")
        return _render_template("portfolio.html", json.dumps(data, ensure_ascii=False))
    except (json.JSONDecodeError, Exception):
        return _extract_html(result)


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
    result = ask_claude(prompt, timeout=600)
    try:
        json_str = extract_json(result)
        data = json.loads(json_str)
        data = enrich_cover(data)
        warnings = validate_cover(data)
        if warnings:
            sys.stderr.write(f"[QA] 자기소개서 경고: {warnings}\n")
        return _render_template("cover_letter.html", json.dumps(data, ensure_ascii=False))
    except (json.JSONDecodeError, Exception):
        return _extract_html(result)
