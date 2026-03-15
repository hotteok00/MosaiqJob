"""Agent 함수 테스트.

Claude CLI 호출은 conftest의 mock_claude_cli로 자동 mock된다.
각 함수가 올바른 프롬프트를 구성하고 ask_claude를 호출하는지 검증한다.
프롬프트는 subprocess.run의 input= 키워드 인자로 전달된다.
"""

import pytest

from agents import analyst, source, strategist, writer, reviewer


def _get_prompt(mock_cli):
    """mock된 subprocess.run 호출에서 stdin으로 전달된 프롬프트를 추출한다."""
    return mock_cli.call_args[1]["input"]


class TestAnalyst:
    def test_analyze_jd_returns_response(self):
        result = analyst.analyze_jd("백엔드 개발자 채용공고")
        assert result == "mocked claude response"

    def test_analyze_jd_includes_jd_in_prompt(self, mock_claude_cli):
        analyst.analyze_jd("Python 3년 이상 필수")
        prompt = _get_prompt(mock_claude_cli)
        assert "Python 3년 이상 필수" in prompt

    def test_analyze_jd_includes_prompt_template(self, mock_claude_cli):
        analyst.analyze_jd("JD")
        prompt = _get_prompt(mock_claude_cli)
        assert len(prompt) > len("JD")  # 프롬프트 템플릿이 포함됨


class TestSource:
    def test_analyze_source_returns_response(self):
        result = source.analyze_source(["Python", "FastAPI"])
        assert result == "mocked claude response"

    def test_analyze_source_includes_keywords(self, mock_claude_cli):
        source.analyze_source(["Python", "FastAPI"])
        prompt = _get_prompt(mock_claude_cli)
        assert "Python" in prompt
        assert "FastAPI" in prompt

    def test_analyze_source_empty_keywords(self, mock_claude_cli):
        source.analyze_source([])
        prompt = _get_prompt(mock_claude_cli)
        assert "우선 탐색 키워드" in prompt


class TestStrategist:
    def test_strategize_returns_response(self):
        result = strategist.strategize("JD 분석 결과", "소스 데이터")
        assert result == "mocked claude response"

    def test_strategize_includes_both_inputs(self, mock_claude_cli):
        strategist.strategize("JD 분석 결과", "소스 데이터")
        prompt = _get_prompt(mock_claude_cli)
        assert "JD 분석 결과" in prompt
        assert "소스 데이터" in prompt


class TestWriter:
    def test_write_resume(self):
        result = writer.write_resume("전략", "소스", "JD")
        assert result == "mocked claude response"

    def test_write_resume_includes_all_inputs(self, mock_claude_cli):
        writer.write_resume("전략 내용", "소스 내용", "JD 내용")
        prompt = _get_prompt(mock_claude_cli)
        assert "전략 내용" in prompt
        assert "소스 내용" in prompt
        assert "JD 내용" in prompt

    def test_write_portfolio(self):
        result = writer.write_portfolio("전략", "소스", "<h1>이력서</h1>")
        assert result == "mocked claude response"

    def test_write_portfolio_includes_resume_ref(self, mock_claude_cli):
        writer.write_portfolio("전략", "소스", "<h1>이력서</h1>")
        prompt = _get_prompt(mock_claude_cli)
        assert "이력서" in prompt
        assert "내용 반복 금지" in prompt

    def test_write_cover_with_questions(self, mock_claude_cli):
        writer.write_cover("전략", "JD", "<h1>이력서</h1>", "<h1>포폴</h1>",
                           ["지원 동기 (500자)", "강점 (1000자)"])
        prompt = _get_prompt(mock_claude_cli)
        assert "지원 동기" in prompt
        assert "강점" in prompt

    def test_write_cover_no_questions(self, mock_claude_cli):
        writer.write_cover("전략", "JD", "<h1>이력서</h1>", "<h1>포폴</h1>", [])
        prompt = _get_prompt(mock_claude_cli)
        assert "자유형" in prompt


class TestReviewer:
    def test_review_returns_response(self):
        result = reviewer.review("JD", "<h1>이력서</h1>", "<h1>포폴</h1>", "<h1>자소서</h1>", ["질문"])
        assert result == "mocked claude response"

    def test_review_includes_all_docs(self, mock_claude_cli):
        reviewer.review("JD 분석", "<h1>이력서</h1>", "<h1>포폴</h1>", "<h1>자소서</h1>", ["지원 동기"])
        prompt = _get_prompt(mock_claude_cli)
        assert "이력서" in prompt
        assert "포폴" in prompt
        assert "자소서" in prompt
        assert "지원 동기" in prompt

    def test_review_no_questions(self, mock_claude_cli):
        reviewer.review("JD", "<h1>이력서</h1>", "<h1>포폴</h1>", "<h1>자소서</h1>", [])
        prompt = _get_prompt(mock_claude_cli)
        assert "자유형" in prompt
