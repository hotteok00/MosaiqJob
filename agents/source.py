from pathlib import Path

from agents.llm import ask_claude

PROMPT = (Path(__file__).parent.parent / "prompts" / "source.md").read_text()


def analyze_source(keywords: list[str]) -> str:
    """사용자 소스 데이터를 수집한다. 키워드는 우선 탐색용 힌트로 전달."""
    keywords_str = ", ".join(keywords)
    prompt = f"{PROMPT}\n\n## 우선 탐색 키워드 (참고용)\n{keywords_str}"
    return ask_claude(prompt, use_mcp=True, timeout=900)


def collect_full_profile() -> str:
    """JD 무관하게 사용자의 전체 프로필 데이터를 수집한다."""
    return ask_claude(PROMPT, use_mcp=True, timeout=900)
