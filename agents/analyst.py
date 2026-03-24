from pathlib import Path

from agents.llm import ask_claude, extract_json

PROMPT = (Path(__file__).parent.parent / "prompts" / "analyst.md").read_text()


def analyze_jd(jd_text: str) -> str:
    """JD를 분석하여 구조화된 JSON을 반환한다."""
    prompt = f"{PROMPT}\n\n## 채용공고 원문\n{jd_text}"
    return extract_json(ask_claude(prompt, timeout=600))


def analyze_jd_deep(jd_text: str) -> str:
    """JD + 기업 심층 분석 (analyze_jd와 동일, 하위 호환용 별칭)."""
    return analyze_jd(jd_text)
