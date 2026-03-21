"""파이프라인 전체 흐름 통합 테스트.

에이전트 함수를 순차 호출하여 전체 파이프라인이 동작하는지 검증한다.
Claude CLI 호출은 conftest의 mock_claude_cli로 자동 mock된다.
"""

from unittest.mock import MagicMock

from agents import analyst, source, strategist, writer, reviewer
from tests.conftest import MOCK_RESUME_JSON, MOCK_PORTFOLIO_JSON, MOCK_COVER_JSON, make_writer_stdout


class TestPipelineSequence:
    """파이프라인 전체 흐름을 순차적으로 실행."""

    def test_full_pipeline_flow(self, mock_claude_cli):
        # writer는 JSON 파싱이 필요하므로 유효한 JSON 응답을 제공
        # Layer 2 content fix 호출까지 고려하여 충분한 응답 제공
        # extract_json이 JSON을 찾을 수 있도록 result를 JSON 형태로 설정
        _jd_json = '{"company_name": "테스트", "position": "개발자"}'
        _src_json = '{"experiences": [], "projects": []}'
        _strat_json = '{"match_rate": 80, "storyline": "테스트"}'
        _review_json = '{"issues": []}'
        responses = [
            make_writer_stdout(_jd_json),                        # analyst
            '{"result": "' + _src_json.replace('"', '\\"') + '"}',  # source (no extract_json)
            make_writer_stdout(_strat_json),                     # strategist
            make_writer_stdout(MOCK_RESUME_JSON),                # writer resume
            make_writer_stdout(MOCK_RESUME_JSON),                # writer resume content fix (if needed)
            make_writer_stdout(MOCK_PORTFOLIO_JSON),             # writer portfolio
            make_writer_stdout(MOCK_PORTFOLIO_JSON),             # writer portfolio content fix (if needed)
            make_writer_stdout(MOCK_COVER_JSON),                 # writer cover
            make_writer_stdout(MOCK_COVER_JSON),                 # writer cover content fix (if needed)
            make_writer_stdout(_review_json),                    # reviewer
        ]
        mock_claude_cli.side_effect = [
            MagicMock(returncode=0, stdout=r, stderr="") for r in responses
        ]

        jd = analyst.analyze_jd("채용공고")
        assert "company_name" in jd or "테스트" in jd

        src = source.analyze_source(["Python"])
        assert "experiences" in src

        strat = strategist.strategize(jd, src)
        assert "match_rate" in strat or "storyline" in strat

        resume = writer.write_resume(strat, src, jd)
        assert "테스트" in resume  # HTML 렌더링 결과에 테스트 데이터 포함

        portfolio = writer.write_portfolio(strat, src, resume)
        assert "테스트" in portfolio or "<html" in portfolio.lower()

        cover = writer.write_cover(strat, jd, resume, portfolio, [])
        assert "테스트" in cover or "<html" in cover.lower()

        # reviewer는 기존대로
        review_result = reviewer.review(jd, resume, portfolio, cover, [])
        assert review_result  # 비어있지 않으면 OK
