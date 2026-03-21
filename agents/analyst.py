from pathlib import Path

from agents.llm import ask_claude, extract_json

PROMPT = (Path(__file__).parent.parent / "prompts" / "analyst.md").read_text()
DEEP_PROMPT = (Path(__file__).parent.parent / "prompts" / "analyst_v2.md").read_text()


def analyze_jd(jd_text: str) -> str:
    """JD를 분석하여 구조화된 JSON을 반환한다 (v1)."""
    prompt = f"{PROMPT}\n\n## 채용공고 원문\n{jd_text}"
    return extract_json(ask_claude(prompt))


def analyze_jd_deep(jd_text: str) -> str:
    """JD + 기업 심층 분석: 심사자 추론, 숨은 요구사항, 경쟁자 프로필 포함 (v2)."""
    prompt = f"{DEEP_PROMPT}\n\n## 채용공고 원문\n{jd_text}"
    return extract_json(ask_claude(prompt, timeout=600))
