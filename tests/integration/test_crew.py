"""파이프라인 전체 흐름 통합 테스트.

에이전트 함수를 순차 호출하여 전체 파이프라인이 동작하는지 검증한다.
Claude CLI 호출은 conftest의 mock_claude_cli로 자동 mock된다.
"""

from unittest.mock import MagicMock

from agents import analyst, source, strategist, writer, reviewer


class TestPipelineSequence:
    """파이프라인 전체 흐름을 순차적으로 실행."""

    def test_full_pipeline_flow(self, mock_claude_cli):
        # 각 step마다 다른 응답 반환
        responses = [
            '{"result": "jd_analysis_result"}',
            '{"result": "source_data_result"}',
            '{"result": "strategy_result"}',
            '{"result": "resume_html"}',
            '{"result": "portfolio_html"}',
            '{"result": "cover_html"}',
            '{"result": "review_result"}',
        ]
        mock_claude_cli.side_effect = [
            MagicMock(returncode=0, stdout=r, stderr="") for r in responses
        ]

        jd = analyst.analyze_jd("채용공고")
        assert jd == "jd_analysis_result"

        src = source.analyze_source(["Python"])
        assert src == "source_data_result"

        strat = strategist.strategize(jd, src)
        assert strat == "strategy_result"

        resume = writer.write_resume(strat, src, jd)
        assert resume == "resume_html"

        portfolio = writer.write_portfolio(strat, src, resume)
        assert portfolio == "portfolio_html"

        cover = writer.write_cover(strat, jd, resume, portfolio, [])
        assert cover == "cover_html"

        review_result = reviewer.review(jd, resume, portfolio, cover, [])
        assert review_result == "review_result"

        assert mock_claude_cli.call_count == 7
