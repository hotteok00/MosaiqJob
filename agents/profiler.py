"""후보자 프로파일링 에이전트.

소스 데이터를 기반으로 JD와 무관하게 지원자의 커리어 서사,
강점/약점, 인상, 전이 가능 기술을 진단한다.
"""

from pathlib import Path

from agents.llm import ask_claude, extract_json

PROMPT = (Path(__file__).parent.parent / "prompts" / "profiler.md").read_text()


def profile_candidate(source_data: str) -> str:
    """소스 데이터를 기반으로 지원자 프로필을 진단한다."""
    prompt = f"{PROMPT}\n\n## 수집된 소스 데이터\n{source_data}"
    return extract_json(ask_claude(prompt, timeout=600))
