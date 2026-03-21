from pathlib import Path

from agents.llm import ask_claude

PROMPT = (Path(__file__).parent.parent / "prompts" / "source.md").read_text()
FULL_PROMPT = (Path(__file__).parent.parent / "prompts" / "source_full.md").read_text()


def analyze_source(keywords: list[str]) -> str:
    """사용자 소스 데이터를 분석하여 JSON을 반환한다 (v1: 키워드 기반)."""
    keywords_str = ", ".join(keywords)
    prompt = f"{PROMPT}\n\n## 우선 탐색 키워드\n{keywords_str}"
    return ask_claude(prompt, use_mcp=True, timeout=900)


def collect_full_profile() -> str:
    """JD 무관하게 사용자의 전체 프로필 데이터를 수집한다 (v2: 전수 수집)."""
    return ask_claude(FULL_PROMPT, use_mcp=True, timeout=900)
