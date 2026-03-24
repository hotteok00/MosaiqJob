import json
import logging
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from agents.enrich import enrich_resume, enrich_portfolio, enrich_cover, _load_registry, shrink_portfolio_highlight
from agents.llm import ask_claude, extract_json
from agents.qa import (
    QAResult,
    validate_resume, validate_portfolio, validate_cover,
    validate_content_resume, validate_content_portfolio, validate_content_cover,
    has_errors, format_errors,
)
from renderer.pdf import html_to_pdf_bytes, count_pages_from_bytes

logger = logging.getLogger("mosaiq.writer")

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

RESUME_PROMPT = (PROMPTS_DIR / "writer_resume.md").read_text()
PORTFOLIO_PROMPT = (PROMPTS_DIR / "writer_portfolio.md").read_text()
COVER_PROMPT = (PROMPTS_DIR / "writer_cover.md").read_text()

# V2 별칭 (하위 호환)
RESUME_V2_PROMPT = RESUME_PROMPT
PORTFOLIO_V2_PROMPT = PORTFOLIO_PROMPT
COVER_V2_PROMPT = COVER_PROMPT

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True,
)

_MAX_STRUCTURE_RETRIES = 3   # Layer 1: 구조 오류 시 전체 재생성
_MAX_CONTENT_RETRIES = 2     # Layer 2: 내용 오류 시 부분 수정


def render_template(template_name: str, data: dict) -> str:
    """dict를 Jinja2 템플릿으로 렌더링한다."""
    template = _jinja_env.get_template(template_name)
    return template.render(**data)


def _extract_html(response: str) -> str:
    """LLM 응답에서 순수 HTML만 추출한다."""
    text = re.sub(r"```html\s*\n?", "", response)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)

    match = re.search(
        r"(<!DOCTYPE\s+html\b[^>]*>.*?</html>|<html\b[^>]*>.*?</html>)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        return match.group(0).strip()

    return response


def _log_qa_results(doc_name: str, results: list[QAResult]) -> None:
    """QA 결과를 severity별로 로깅한다."""
    for r in results:
        if r.severity.value == "error":
            logger.error("[QA] %s: %s", doc_name, r.message)
        else:
            logger.warning("[QA] %s: %s", doc_name, r.message)


def _request_content_fix(original_data: dict, content_errors: str, doc_type: str) -> dict:
    """내용 품질 오류에 대해 부분 수정만 요청한다. 전체 재생성이 아닌 targeted fix."""
    prompt = f"""다음 {doc_type} JSON에서 아래 품질 문제만 수정하세요.
나머지 내용은 절대 변경하지 마세요.

## 수정 필요 사항
{content_errors}

## 원본 JSON
{json.dumps(original_data, ensure_ascii=False)}

수정된 완전한 JSON만 반환하세요. 코드블록 마커(```)를 사용하지 마세요."""

    result = ask_claude(prompt, timeout=300)
    json_str = extract_json(result)
    return json.loads(json_str)


def _generate_doc_with_qa(
    base_prompt: str,
    doc_name: str,
    enrich_fn,
    validate_structure_fn,
    validate_content_fn,
) -> dict:
    """공통 문서 생성 루프: Layer 1 (구조 검증) + Layer 2 (내용 검증).

    Args:
        base_prompt: LLM에 전달할 기본 프롬프트
        doc_name: 로그용 문서 이름 (예: "이력서", "포트폴리오", "자소서")
        enrich_fn: JSON 보정 함수 (dict → dict)
        validate_structure_fn: Layer 1 구조 검증 함수
        validate_content_fn: Layer 2 내용 검증 함수

    Returns:
        검증 및 보정된 문서 JSON dict
    """
    data = None
    error_feedback = ""

    # Layer 1: 구조 검증 루프
    for attempt in range(_MAX_STRUCTURE_RETRIES + 1):
        prompt = base_prompt
        if attempt > 0:
            prompt += f"\n\n## 수정 필요 사항 (이전 생성에서 발견된 오류)\n{error_feedback}"

        result = ask_claude(prompt, timeout=600)
        try:
            json_str = extract_json(result)
            data = json.loads(json_str)
            data = enrich_fn(data)
            qa_results = validate_structure_fn(data)
            _log_qa_results(f"{doc_name}/구조", qa_results)

            if has_errors(qa_results) and attempt < _MAX_STRUCTURE_RETRIES:
                error_feedback = format_errors(qa_results)
                logger.warning(
                    "%s 구조 오류 %d건 → 재생성 %d/%d",
                    doc_name,
                    len([r for r in qa_results if r.severity.value == "error"]),
                    attempt + 1, _MAX_STRUCTURE_RETRIES,
                )
                continue
            break
        except json.JSONDecodeError:
            logger.error("%s JSON 파싱 실패 (시도 %d/%d)", doc_name, attempt + 1, _MAX_STRUCTURE_RETRIES + 1)
            if attempt == _MAX_STRUCTURE_RETRIES:
                raise RuntimeError(f"{doc_name} JSON 파싱 실패: 최대 재시도 초과")
            continue

    # Layer 2: 내용 검증 루프
    for fix_attempt in range(_MAX_CONTENT_RETRIES + 1):
        content_results = validate_content_fn(data)
        _log_qa_results(f"{doc_name}/내용", content_results)

        if not has_errors(content_results):
            break
        if fix_attempt == _MAX_CONTENT_RETRIES:
            logger.warning("%s 내용 오류 수정 한도 초과, 현재 상태로 진행", doc_name)
            break

        error_feedback = format_errors(content_results)
        logger.warning(
            "%s 내용 오류 %d건 → 부분 수정 %d/%d",
            doc_name,
            len([r for r in content_results if r.severity.value == "error"]),
            fix_attempt + 1, _MAX_CONTENT_RETRIES,
        )
        try:
            data = _request_content_fix(data, error_feedback, doc_name)
            data = enrich_fn(data)
        except (json.JSONDecodeError, RuntimeError) as e:
            logger.error("%s 내용 수정 실패: %s", doc_name, e)
            break

    return data


# ── 이력서 ────────────────────────────────────────────────


def generate_resume(strategy: str, source_data: str, jd_analysis: str) -> dict:
    """이력서 JSON 데이터를 생성한다. Layer 1 + Layer 2 검증."""
    base_prompt = f"{RESUME_PROMPT}\n\n## 전략\n{strategy}\n\n## 소스 데이터\n{source_data}\n\n## JD 분석\n{jd_analysis}"
    return _generate_doc_with_qa(
        base_prompt=base_prompt,
        doc_name="이력서",
        enrich_fn=enrich_resume,
        validate_structure_fn=validate_resume,
        validate_content_fn=validate_content_resume,
    )


def write_resume(strategy: str, source_data: str, jd_analysis: str) -> str:
    """이력서 HTML을 생성한다 (하위 호환용)."""
    data = generate_resume(strategy, source_data, jd_analysis)
    return render_template("resume.html", data)


# ── 포트폴리오 ────────────────────────────────────────────


def generate_portfolio(strategy: str, source_data: str, resume_data: dict) -> dict:
    """포트폴리오 JSON 데이터를 생성한다. Layer 1 + Layer 2 검증."""
    resume_html = render_template("resume.html", resume_data)
    base_prompt = f"{PORTFOLIO_PROMPT}\n\n## 전략\n{strategy}\n\n## 소스 데이터\n{source_data}\n\n## 이력서 (참조용, 내용 반복 금지)\n{resume_html}"
    return _generate_doc_with_qa(
        base_prompt=base_prompt,
        doc_name="포트폴리오",
        enrich_fn=lambda d: enrich_portfolio(d, _load_registry()),
        validate_structure_fn=validate_portfolio,
        validate_content_fn=validate_content_portfolio,
    )


def render_portfolio_with_shrink(data: dict) -> tuple[str, bytes]:
    """포트폴리오를 렌더링하고 페이지 초과 시 자동 축소한다. (html, pdf_bytes) 반환."""
    expected_pages = 2 + len(data.get("highlights", []))
    max_shrink = 3

    html = ""
    pdf_bytes = b""
    for level in range(max_shrink + 1):
        html = render_template("portfolio.html", data)
        pdf_bytes = html_to_pdf_bytes(html)
        actual_pages = count_pages_from_bytes(pdf_bytes)

        if actual_pages <= expected_pages:
            break

        logger.warning(
            "포트폴리오 페이지 초과: %dp > %dp → 축소 level %d",
            actual_pages, expected_pages, level + 1,
        )
        data["highlights"] = [
            shrink_portfolio_highlight(h, level + 1)
            for h in data.get("highlights", [])
        ]

    return html, pdf_bytes


def write_portfolio(strategy: str, source_data: str, resume_html: str) -> str:
    """포트폴리오 HTML을 생성한다 (하위 호환용).

    내부적으로 generate_portfolio + render_portfolio_with_shrink에 위임한다.
    resume_html을 받지만, generate_portfolio는 resume_data(dict)를 받으므로
    프롬프트에 HTML을 직접 주입하는 간이 경로를 사용한다.
    """
    # resume_html → 임시 dict로 감싸서 generate_portfolio 호환
    # generate_portfolio 내부에서 resume_data → resume_html 렌더링하므로
    # 여기선 이미 렌더링된 HTML을 _resume_html 키로 우회
    data = _generate_doc_with_qa(
        base_prompt=f"{PORTFOLIO_PROMPT}\n\n## 전략\n{strategy}\n\n## 소스 데이터\n{source_data}\n\n## 이력서 (참조용, 내용 반복 금지)\n{resume_html}",
        doc_name="포트폴리오",
        enrich_fn=lambda d: enrich_portfolio(d, _load_registry()),
        validate_structure_fn=validate_portfolio,
        validate_content_fn=validate_content_portfolio,
    )
    html, _ = render_portfolio_with_shrink(data)
    return html


# ── 자소서 ────────────────────────────────────────────────


def generate_cover(
    strategy: str,
    jd_analysis: str,
    resume_data: dict,
    portfolio_data: dict,
    questions: list[str],
) -> dict:
    """자소서 JSON 데이터를 생성한다. Layer 1 + Layer 2 검증."""
    resume_html = render_template("resume.html", resume_data)
    portfolio_html = render_template("portfolio.html", portfolio_data)
    questions_str = "\n".join(f"- {q}" for q in questions) if questions else "자유형 (문항 없음)"
    base_prompt = (
        f"{COVER_PROMPT}\n\n## 전략\n{strategy}\n\n## JD 분석\n{jd_analysis}\n\n"
        f"## 자소서 문항\n{questions_str}\n\n"
        f"## 이력서 (참조용, 내용 반복 금지)\n{resume_html}\n\n"
        f"## 포트폴리오 (참조용, 내용 반복 금지)\n{portfolio_html}"
    )
    return _generate_doc_with_qa(
        base_prompt=base_prompt,
        doc_name="자소서",
        enrich_fn=enrich_cover,
        validate_structure_fn=validate_cover,
        validate_content_fn=validate_content_cover,
    )


def write_cover(
    strategy: str,
    jd_analysis: str,
    resume_html: str,
    portfolio_html: str,
    questions: list[str],
) -> str:
    """자소서 HTML을 생성한다 (하위 호환용).

    내부적으로 _generate_doc_with_qa + render_template에 위임한다.
    """
    questions_str = "\n".join(f"- {q}" for q in questions) if questions else "자유형 (문항 없음)"
    data = _generate_doc_with_qa(
        base_prompt=(
            f"{COVER_PROMPT}\n\n## 전략\n{strategy}\n\n## JD 분석\n{jd_analysis}\n\n"
            f"## 자소서 문항\n{questions_str}\n\n"
            f"## 이력서 (참조용, 내용 반복 금지)\n{resume_html}\n\n"
            f"## 포트폴리오 (참조용, 내용 반복 금지)\n{portfolio_html}"
        ),
        doc_name="자소서",
        enrich_fn=enrich_cover,
        validate_structure_fn=validate_cover,
        validate_content_fn=validate_content_cover,
    )
    return render_template("cover_letter.html", data)


# ── V2: 블루프린트 기반 병렬 생성 ───────────────────────────


def _extract_blueprint_section(blueprint: str, doc_type: str) -> str:
    """블루프린트에서 특정 문서에 관련된 섹션만 추출한다."""
    try:
        data = json.loads(blueprint)
        section = {
            "positioning": data.get("positioning", {}),
            "distribution": data.get("blueprint", {}).get("experience_distribution", {}).get(doc_type, []),
            "emotional_arc": data.get("blueprint", {}).get("emotional_arc", {}).get(doc_type, ""),
            "document_role": data.get("blueprint", {}).get("per_document_role", {}).get(doc_type, ""),
            "weakness_strategies": data.get("weakness_strategies", {}),
            "gap_matrix": data.get("gap_matrix", []),
            "storyline": data.get("storyline", ""),
            "highlight_projects": data.get("highlight_projects", []),
            "highlight_reasons": data.get("highlight_reasons", []),
            "match_rate": data.get("match_rate", 0),
        }
        if doc_type == "cover":
            section["cover_question_plan"] = data.get("blueprint", {}).get("cover_question_plan", [])
        return json.dumps(section, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        return blueprint


def generate_resume_v2(blueprint: str, source_data: str, jd_analysis: str) -> dict:
    """블루프린트 기반 이력서 생성 (V2). 다른 문서 참조 불필요."""
    bp_section = _extract_blueprint_section(blueprint, "resume")
    base_prompt = (
        f"{RESUME_V2_PROMPT}\n\n"
        f"## 블루프린트 (이력서)\n{bp_section}\n\n"
        f"## 소스 데이터\n{source_data}\n\n"
        f"## JD 분석\n{jd_analysis}"
    )
    return _generate_doc_with_qa(
        base_prompt=base_prompt,
        doc_name="이력서",
        enrich_fn=enrich_resume,
        validate_structure_fn=validate_resume,
        validate_content_fn=validate_content_resume,
    )


def generate_portfolio_v2(blueprint: str, source_data: str) -> dict:
    """블루프린트 기반 포트폴리오 생성 (V2). 이력서 참조 불필요."""
    bp_section = _extract_blueprint_section(blueprint, "portfolio")
    base_prompt = (
        f"{PORTFOLIO_V2_PROMPT}\n\n"
        f"## 블루프린트 (포트폴리오)\n{bp_section}\n\n"
        f"## 소스 데이터\n{source_data}"
    )
    return _generate_doc_with_qa(
        base_prompt=base_prompt,
        doc_name="포트폴리오",
        enrich_fn=lambda d: enrich_portfolio(d, _load_registry()),
        validate_structure_fn=validate_portfolio,
        validate_content_fn=validate_content_portfolio,
    )


def generate_cover_v2(
    blueprint: str,
    source_data: str,
    jd_analysis: str,
    questions: list[str],
) -> dict:
    """블루프린트 기반 자소서 생성 (V2). 이력서/포폴 참조 불필요."""
    bp_section = _extract_blueprint_section(blueprint, "cover")
    questions_str = "\n".join(f"- {q}" for q in questions) if questions else "자유형 (문항 없음)"
    base_prompt = (
        f"{COVER_V2_PROMPT}\n\n"
        f"## 블루프린트 (자소서)\n{bp_section}\n\n"
        f"## 소스 데이터\n{source_data}\n\n"
        f"## JD 분석\n{jd_analysis}\n\n"
        f"## 자소서 문항\n{questions_str}"
    )
    return _generate_doc_with_qa(
        base_prompt=base_prompt,
        doc_name="자소서",
        enrich_fn=enrich_cover,
        validate_structure_fn=validate_cover,
        validate_content_fn=validate_content_cover,
    )
