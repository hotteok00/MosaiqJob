from pathlib import Path

from agents.llm import ask_claude

PROMPT = (Path(__file__).parent.parent / "prompts" / "source.md").read_text()


def analyze_source(keywords: list[str]) -> str:
    """사용자 소스 데이터를 분석하여 JSON을 반환한다."""
    keywords_str = ", ".join(keywords)
    prompt = f"{PROMPT}\n\n## 우선 탐색 키워드\n{keywords_str}"
    return ask_claude(prompt, use_mcp=True, timeout=900)
