"""app.py의 parse_input 및 UI 관련 테스트.

Chainlit UI 자체는 mock하고, 순수 로직만 테스트한다.
실제 LLM 호출이 필요한 E2E 테스트는 @pytest.mark.e2e로 표시한다.
"""

import pytest

from app import parse_input


class TestParseInput:
    def test_jd_only(self):
        jd, questions = parse_input("백엔드 개발자 모집합니다.")
        assert jd == "백엔드 개발자 모집합니다."
        assert questions == []

    def test_jd_with_questions(self):
        text = "백엔드 개발자 모집\n---\n1. 지원 동기 (500자)\n2. 강점 (1000자)"
        jd, questions = parse_input(text)
        assert jd == "백엔드 개발자 모집"
        assert len(questions) == 2
        assert "지원 동기" in questions[0]
        assert "강점" in questions[1]

    def test_multiple_separators(self):
        text = "JD 내용\n---\n질문1\n---\n이건 질문의 일부"
        jd, questions = parse_input(text)
        assert jd == "JD 내용"
        # 첫 번째 --- 기준으로 분리, 나머지는 질문 영역
        assert any("질문1" in q for q in questions)

    def test_empty_questions(self):
        text = "JD 내용\n---\n"
        jd, questions = parse_input(text)
        assert jd == "JD 내용"
        assert questions == []

    def test_whitespace_handling(self):
        text = "  JD 내용  \n---\n  질문1  \n\n  질문2  \n"
        jd, questions = parse_input(text)
        assert jd == "JD 내용"
        assert len(questions) == 2
        assert questions[0] == "질문1"
        assert questions[1] == "질문2"

    def test_no_separator(self):
        text = "전체가 JD입니다\n추가 내용도 있습니다"
        jd, questions = parse_input(text)
        assert "전체가 JD입니다" in jd
        assert "추가 내용도 있습니다" in jd
        assert questions == []

    def test_empty_input(self):
        jd, questions = parse_input("")
        assert jd == ""
        assert questions == []

    def test_korean_multiline_jd(self):
        text = (
            "[채용공고]\n"
            "회사: 테크스타트업\n"
            "포지션: 백엔드 개발자\n"
            "요구사항:\n"
            "- Python 3년 이상\n"
            "---\n"
            "1. 지원 동기를 작성하세요. (500자 이내)"
        )
        jd, questions = parse_input(text)
        assert "테크스타트업" in jd
        assert "Python" in jd
        assert len(questions) == 1
        assert "500자" in questions[0]
