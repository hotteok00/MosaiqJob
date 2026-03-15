"""Claude CLI 래퍼 함수 테스트."""

import json
from unittest.mock import MagicMock, patch

import pytest

from agents.llm import ask_claude


class TestAskClaude:
    def test_returns_result(self, mock_claude_cli):
        result = ask_claude("테스트 프롬프트")
        assert result == "mocked claude response"

    def test_passes_prompt_to_cli(self, mock_claude_cli):
        ask_claude("안녕하세요")
        args = mock_claude_cli.call_args
        cmd = args[0][0]
        assert cmd[0] == "claude"
        assert cmd[1] == "-p"
        assert "--output-format" in cmd
        assert "json" in cmd
        # 프롬프트는 stdin으로 전달됨
        assert args[1]["input"] == "안녕하세요"

    def test_uses_timeout(self, mock_claude_cli):
        ask_claude("프롬프트", timeout=60)
        args = mock_claude_cli.call_args
        assert args[1]["timeout"] == 60

    def test_default_timeout(self, mock_claude_cli):
        ask_claude("프롬프트")
        args = mock_claude_cli.call_args
        assert args[1]["timeout"] == 300

    def test_raises_on_nonzero_exit(self, mock_claude_cli):
        mock_claude_cli.return_value = MagicMock(
            returncode=1,
            stderr="command not found",
            stdout="",
        )
        with pytest.raises(RuntimeError, match="Claude CLI 오류"):
            ask_claude("프롬프트")

    def test_raises_on_timeout(self, mock_claude_cli):
        import subprocess
        mock_claude_cli.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=300)
        with pytest.raises(TimeoutError, match="시간 초과"):
            ask_claude("프롬프트")

    def test_raises_on_invalid_json(self, mock_claude_cli):
        mock_claude_cli.return_value = MagicMock(
            returncode=0,
            stdout="not json",
            stderr="",
        )
        with pytest.raises(RuntimeError, match="파싱 실패"):
            ask_claude("프롬프트")

    def test_raises_on_missing_result_key(self, mock_claude_cli):
        mock_claude_cli.return_value = MagicMock(
            returncode=0,
            stdout='{"type": "error"}',
            stderr="",
        )
        with pytest.raises(RuntimeError, match="파싱 실패"):
            ask_claude("프롬프트")

    def test_complex_response(self, mock_claude_cli):
        complex_result = json.dumps({
            "result": '{"company_name": "테크", "position": "개발자"}',
            "type": "result",
        })
        mock_claude_cli.return_value = MagicMock(
            returncode=0,
            stdout=complex_result,
            stderr="",
        )
        result = ask_claude("JD 분석해줘")
        parsed = json.loads(result)
        assert parsed["company_name"] == "테크"
