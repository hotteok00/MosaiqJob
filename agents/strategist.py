from pathlib import Path

from agents.llm import ask_claude, extract_json

PROMPT = (Path(__file__).parent.parent / "prompts" / "strategist.md").read_text()


def strategize(jd_analysis: str, source_data: str) -> str:
    """JD 분석 결과와 소스 데이터를 매칭하여 전략 JSON을 반환한다."""
    prompt = f"{PROMPT}\n\n## JD 분석 결과\n{jd_analysis}\n\n## 사용자 소스 데이터\n{source_data}"
    return extract_json(ask_claude(prompt))
