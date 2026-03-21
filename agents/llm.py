"""LLM 호출 모듈.

기본 백엔드는 Claude Code CLI(구독 기반, 추가 API 비용 없음).
set_backend()로 테스트 mock이나 다른 백엔드로 교체할 수 있다.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from typing import Protocol

logger = logging.getLogger("mosaiq.llm")

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


# ── LLM 백엔드 프로토콜 ──────────────────────────────────────


class LLMBackend(Protocol):
    """LLM 호출 인터페이스. 새 백엔드 추가 시 이 프로토콜만 구현."""

    def __call__(
        self,
        prompt: str,
        timeout: int = 300,
        use_mcp: bool = False,
        model: str = DEFAULT_MODEL,
    ) -> str: ...


# ── Claude CLI 백엔드 ────────────────────────────────────────


class ClaudeCLIBackend:
    """Claude Code CLI 기반 백엔드."""

    _ENV_WHITELIST = {
        "PATH", "HOME", "USER", "LANG", "LC_ALL",
        "TERM", "SHELL", "TMPDIR", "XDG_CONFIG_HOME",
    }

    def __call__(
        self,
        prompt: str,
        timeout: int = 300,
        use_mcp: bool = False,
        model: str = DEFAULT_MODEL,
    ) -> str:
        cmd = ["claude", "-p", "--output-format", "json", "--model", model]

        if use_mcp:
            cmd += ["--allowedTools"] + MCP_ALLOWED_TOOLS

        env = {k: v for k, v in os.environ.items() if k in self._ENV_WHITELIST}

        logger.debug("Claude CLI 호출: model=%s, mcp=%s, timeout=%d", model, use_mcp, timeout)

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

        # stdout 파싱 시도 (returncode 관계없이 stdout에 결과가 있을 수 있음)
        if result.stdout:
            try:
                response = json.loads(result.stdout)
                if response.get("is_error"):
                    raise RuntimeError(
                        f"Claude CLI 오류: {response.get('result', 'unknown error')}"
                    )
                return response["result"]
            except (json.JSONDecodeError, KeyError):
                if result.returncode != 0:
                    raise RuntimeError(f"Claude CLI 오류: {result.stderr.strip()}")
                raise RuntimeError(
                    f"Claude CLI 응답 파싱 실패: {result.stdout[:200]}"
                )

        raise RuntimeError(f"Claude CLI 오류: {result.stderr.strip()}")


# ── 모듈 레벨 API (기존 호환) ────────────────────────────────


_backend: LLMBackend = ClaudeCLIBackend()


def ask_claude(
    prompt: str,
    timeout: int = 300,
    use_mcp: bool = False,
    model: str = DEFAULT_MODEL,
) -> str:
    """LLM에 프롬프트를 전송하고 응답을 반환한다.

    내부적으로 _backend에 위임한다. set_backend()로 교체 가능.

    Raises:
        RuntimeError: LLM 실행 실패 시
        TimeoutError: 응답 시간 초과 시
    """
    return _backend(prompt, timeout=timeout, use_mcp=use_mcp, model=model)


def set_backend(backend: LLMBackend) -> None:
    """LLM 백엔드를 교체한다. 테스트나 API 모드 전환에 사용."""
    global _backend
    _backend = backend


def extract_json(response: str) -> str:
    """LLM 응답에서 JSON 부분만 추출한다.

    - ```json ... ``` 코드블록 마커를 제거
    - JSON 객체 ({ ~ })를 추출

    Raises:
        ValueError: JSON 객체를 찾지 못한 경우
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

    raise ValueError(
        f"LLM 응답에서 JSON을 찾을 수 없습니다: {response[:200]}"
    )
