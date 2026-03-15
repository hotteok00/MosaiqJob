"""Claude Code CLI를 통한 LLM 호출.

구독 기반으로 추가 API 비용 없이 Claude를 사용한다.
"""

import json
import os
import re
import subprocess

# MCP 도구 허용 목록 (claude -p 비대화형 모드에서 권한 승인 불가하므로 미리 허용)
MCP_ALLOWED_TOOLS = [
    # Notion (커스텀 MCP)
    "mcp__notion__search",
    "mcp__notion__read_page",
    "mcp__notion__query_database",
    # GitHub (커스텀 MCP)
    "mcp__github__search_repos",
    "mcp__github__search_code",
    "mcp__github__get_file",
    "mcp__github__list_commits",
    # Google Drive (커스텀 MCP)
    "mcp__google-drive__search",
    "mcp__google-drive__read_file",
    # OneDrive (커스텀 MCP)
    "mcp__onedrive__search",
    "mcp__onedrive__read_file",
    "mcp__onedrive__list_files",
]

DEFAULT_MODEL = "sonnet"


def ask_claude(
    prompt: str,
    timeout: int = 300,
    use_mcp: bool = False,
    model: str = DEFAULT_MODEL,
) -> str:
    """Claude Code CLI로 프롬프트를 전송하고 응답을 반환한다.

    Args:
        prompt: LLM에 전달할 프롬프트 텍스트
        timeout: 응답 대기 최대 시간(초)
        use_mcp: MCP 도구 사용 허용 여부
        model: 사용할 모델 (sonnet, opus, haiku)

    Returns:
        Claude의 응답 텍스트

    Raises:
        RuntimeError: CLI 실행 실패 시
        TimeoutError: 응답 시간 초과 시
    """
    cmd = ["claude", "-p", "--output-format", "json", "--model", model]

    if use_mcp:
        cmd += ["--allowedTools"] + MCP_ALLOWED_TOOLS

    # ANTHROPIC_API_KEY가 설정되어 있으면 CLI가 API 모드로 전환되므로 제거
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(f"Claude CLI 응답 시간 초과 ({timeout}초)") from e

    if result.returncode != 0:
        # returncode=1이지만 stdout에 결과가 있는 경우 처리
        if result.stdout:
            try:
                response = json.loads(result.stdout)
                if response.get("is_error"):
                    raise RuntimeError(f"Claude CLI 오류: {response.get('result', 'unknown error')}")
                return response["result"]
            except (json.JSONDecodeError, KeyError):
                pass
        raise RuntimeError(f"Claude CLI 오류: {result.stderr.strip()}")

    try:
        response = json.loads(result.stdout)
        if response.get("is_error"):
            raise RuntimeError(f"Claude CLI 오류: {response.get('result', 'unknown error')}")
        return response["result"]
    except (json.JSONDecodeError, KeyError) as e:
        raise RuntimeError(f"Claude CLI 응답 파싱 실패: {result.stdout[:200]}") from e


def extract_json(response: str) -> str:
    """LLM 응답에서 JSON 부분만 추출한다.

    - ```json ... ``` 코드블록 마커를 제거
    - JSON 객체 ({ ~ })를 추출
    - JSON이 없으면 원본 그대로 반환 (fallback)
    """
    # 코드블록 내부 추출 시도
    block_match = re.search(r"```(?:json)?\s*\n?(.*?)```", response, re.DOTALL)
    if block_match:
        candidate = block_match.group(1).strip()
        if candidate.startswith("{"):
            return candidate

    # JSON 객체 추출 시도
    obj_match = re.search(r"\{.*\}", response, re.DOTALL)
    if obj_match:
        return obj_match.group(0)

    # fallback: 원본 반환
    return response
