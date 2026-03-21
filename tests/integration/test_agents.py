"""Agent 함수 테스트.

Claude CLI 호출은 conftest의 mock_claude_cli로 자동 mock된다.
각 함수가 올바른 프롬프트를 구성하고 ask_claude를 호출하는지 검증한다.
프롬프트는 subprocess.run의 input= 키워드 인자로 전달된다.
"""

import pytest
from unittest.mock import MagicMock

from agents import analyst, source, strategist, writer, reviewer
from agents import profiler as profiler_agent
from agents import coach as coach_agent
from tests.conftest import (
    MOCK_RESUME_JSON, MOCK_PORTFOLIO_JSON, MOCK_COVER_JSON,
    MOCK_PROFILE_JSON, MOCK_BLUEPRINT_JSON, MOCK_COACH_JSON,
    make_writer_stdout,
)


def _get_prompt(mock_cli):
    """mock된 subprocess.run 호출에서 stdin으로 전달된 프롬프트를 추출한다."""
    return mock_cli.call_args[1]["input"]


class TestAnalyst:
    def test_analyze_jd_returns_response(self):
        result = analyst.analyze_jd("백엔드 개발자 채용공고")
        assert "mocked" in result or "status" in result

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
        assert "mocked" in result or "status" in result

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
        assert "mocked" in result or "status" in result

    def test_strategize_includes_both_inputs(self, mock_claude_cli):
        strategist.strategize("JD 분석 결과", "소스 데이터")
        prompt = _get_prompt(mock_claude_cli)
        assert "JD 분석 결과" in prompt
        assert "소스 데이터" in prompt


class TestWriter:
    @pytest.fixture(autouse=True)
    def _set_writer_mock(self, mock_claude_cli):
        """writer 테스트에서는 유효한 JSON을 반환하도록 mock 오버라이드."""
        responses = [MOCK_RESUME_JSON, MOCK_PORTFOLIO_JSON, MOCK_COVER_JSON]
        call_count = {"n": 0}

        def _side_effect(*args, **kwargs):
            idx = call_count["n"] % len(responses)
            call_count["n"] += 1
            return MagicMock(
                returncode=0,
                stdout=make_writer_stdout(responses[idx]),
                stderr="",
            )

        mock_claude_cli.side_effect = _side_effect

    def test_write_resume(self):
        result = writer.write_resume("전략", "소스", "JD")
        assert "테스트" in result

    def test_write_resume_includes_all_inputs(self, mock_claude_cli):
        writer.write_resume("전략 내용", "소스 내용", "JD 내용")
        # 첫 번째 호출의 prompt 확인 (Layer 2 수정 호출이 뒤따를 수 있으므로)
        first_call = mock_claude_cli.call_args_list[0]
        prompt = first_call[1]["input"]
        assert "전략 내용" in prompt
        assert "소스 내용" in prompt
        assert "JD 내용" in prompt

    def test_write_portfolio(self):
        result = writer.write_portfolio("전략", "소스", "<h1>이력서</h1>")
        assert "테스트" in result or "<html" in result.lower()

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
        assert "mocked" in result or "status" in result

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


# ── V2 에이전트 테스트 ───────────────────────────────────────


class TestProfiler:
    def test_profile_candidate_returns_response(self):
        result = profiler_agent.profile_candidate("소스 데이터")
        assert "mocked" in result or "status" in result

    def test_profile_candidate_includes_source(self, mock_claude_cli):
        profiler_agent.profile_candidate("테스트 소스 데이터")
        prompt = _get_prompt(mock_claude_cli)
        assert "테스트 소스 데이터" in prompt


class TestAnalystV2:
    def test_analyze_jd_deep_returns_response(self):
        result = analyst.analyze_jd_deep("로봇 SW 엔지니어 채용")
        assert "mocked" in result or "status" in result

    def test_analyze_jd_deep_includes_jd(self, mock_claude_cli):
        analyst.analyze_jd_deep("ROS2 경험 필수")
        prompt = _get_prompt(mock_claude_cli)
        assert "ROS2 경험 필수" in prompt
        assert "심사자" in prompt or "서류" in prompt  # V2 프롬프트에 심사자 분석 포함


class TestSourceV2:
    def test_collect_full_profile_returns_response(self):
        result = source.collect_full_profile()
        assert "mocked" in result or "status" in result

    def test_collect_full_profile_no_keywords(self, mock_claude_cli):
        source.collect_full_profile()
        prompt = _get_prompt(mock_claude_cli)
        assert "전수 수집" in prompt or "전체 프로필" in prompt


class TestStrategistV2:
    def test_strategize_v2_returns_response(self):
        result = strategist.strategize_v2("프로필", "JD 분석", "소스")
        assert "mocked" in result or "status" in result

    def test_strategize_v2_includes_all_inputs(self, mock_claude_cli):
        strategist.strategize_v2("후보자 프로필", "JD 심층 분석", "소스 원본")
        prompt = _get_prompt(mock_claude_cli)
        assert "후보자 프로필" in prompt
        assert "JD 심층 분석" in prompt
        assert "소스 원본" in prompt


class TestWriterV2:
    @pytest.fixture(autouse=True)
    def _set_writer_mock(self, mock_claude_cli):
        responses = [MOCK_RESUME_JSON, MOCK_PORTFOLIO_JSON, MOCK_COVER_JSON]
        call_count = {"n": 0}

        def _side_effect(*args, **kwargs):
            idx = call_count["n"] % len(responses)
            call_count["n"] += 1
            return MagicMock(
                returncode=0,
                stdout=make_writer_stdout(responses[idx]),
                stderr="",
            )

        mock_claude_cli.side_effect = _side_effect

    def test_generate_resume_v2_uses_blueprint(self, mock_claude_cli):
        writer.generate_resume_v2(MOCK_BLUEPRINT_JSON, "소스", "JD")
        first_call = mock_claude_cli.call_args_list[0]
        prompt = first_call[1]["input"]
        assert "블루프린트" in prompt
        assert "소스" in prompt

    def test_generate_portfolio_v2_no_resume_html(self, mock_claude_cli):
        writer.generate_portfolio_v2(MOCK_BLUEPRINT_JSON, "소스")
        first_call = mock_claude_cli.call_args_list[0]
        prompt = first_call[1]["input"]
        assert "블루프린트" in prompt
        assert "참조용, 내용 반복 금지" not in prompt  # v1의 이력서 HTML 참조 패턴 없음

    def test_generate_cover_v2_no_doc_dep(self, mock_claude_cli):
        writer.generate_cover_v2(MOCK_BLUEPRINT_JSON, "소스", "JD", ["지원 동기"])
        first_call = mock_claude_cli.call_args_list[0]
        prompt = first_call[1]["input"]
        assert "블루프린트" in prompt
        assert "지원 동기" in prompt


class TestCoach:
    @pytest.fixture(autouse=True)
    def _set_coach_mock(self, mock_claude_cli):
        """코치는 review + fix 2회 호출 가능. 첫 번째는 코칭 결과, 두 번째는 수정."""
        mock_claude_cli.return_value = MagicMock(
            returncode=0,
            stdout=make_writer_stdout(MOCK_COACH_JSON),
            stderr="",
        )

    def test_coach_review_returns_feedbacks(self):
        r, p, c, feedbacks, overall, risks = coach_agent.coach_review(
            "JD", MOCK_BLUEPRINT_JSON,
            {"person": {"name": "t"}}, {"person": {"name": "t"}},
            {"person": {"name": "t"}, "target": {"company": "A", "position": "B"}, "sections": [], "date": "2026"},
            [],
        )
        assert isinstance(feedbacks, list)
        assert isinstance(risks, list)
        assert overall.get("hr_screener_pass") is True
