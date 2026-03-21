import os
from unittest.mock import MagicMock, patch

import pytest

from models.schemas import (
    CompanyInfo,
    CrossCheckResult,
    Documents,
    Education,
    Experience,
    JDAnalysis,
    PipelineState,
    Project,
    SourceData,
    Strategy,
)


@pytest.fixture(autouse=True)
def mock_claude_cli():
    """Claude CLI 호출을 mock하여 실제 subprocess 실행을 방지한다."""
    with patch("agents.llm.subprocess.run") as mock_run:
        # extract_json이 JSON을 찾을 수 있도록 기본 응답을 JSON 형태로 설정
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"result": "{\\"status\\": \\"mocked\\"}"}',
            stderr="",
        )
        yield mock_run


# writer 테스트용 유효 JSON 응답
# writer 테스트용: ask_claude는 response["result"] (문자열)을 반환하므로
# mock stdout의 "result"도 문자열이어야 함 (JSON 문자열을 이스케이프하여 감싸기)
import json as _json

_resume_obj = {"person":{"name":"테스트","phone":"010-0000-0000","email":"t@t.com","github":"test"},"summary":"테스트 요약","careers":[{"company":"A사","position":"개발자","period":"2024","bullets":["업무"]}],"projects":[{"name":"P1","subtitle":"설명","period":"2024","team":"3인","role_desc":"역할","tags":["Python"],"is_personal":False,"github_url":""}],"skills":{"언어":"Python"},"education":[{"school":"테스트대","detail":"CS","period":"2020~2024"}]}
_portfolio_obj = {"person":{"name":"테스트"},"summary":"포폴 요약","competencies":[{"number":"01","keyword":"A","description":"a"},{"number":"02","keyword":"B","description":"b"},{"number":"03","keyword":"C","description":"c"}],"project_table":[],"highlights":[{"order":1,"name":"P1","subtitle":"설명","period":"2024","team":"3인","role":"개발","overview":"프로젝트 개요입니다. 두 줄 이상의 설명을 작성합니다.","situation":["상황1","상황2"],"decision":["판단1","판단2"],"action":["행동1","행동2"],"result":["결과1","결과2"],"contribution_pct":80,"contribution_desc":"기여","tags":["Python"],"github_url":"","diagram_img":"https://example.com/diagram.png","demo_img":"https://example.com/demo.png","youtube_url":""}],"other_projects":[{"name":"O1","subtitle":"","description":"기타","tags":["A"],"period":"2024","team":""}]}
_cover_obj = {"person":{"name":"테스트","phone":"010-0000-0000","email":"t@t.com","github":"test"},"target":{"company":"A사","position":"개발자"},"doc_label":"자기소개서","sections":[{"label":"자유형","content":"<p>" + "테스트 내용입니다. " * 20 + "</p>"}],"date":"2026.03"}

# result 값은 문자열이어야 함 (ask_claude가 response["result"]를 str로 반환)
MOCK_RESUME_JSON = _json.dumps(_resume_obj, ensure_ascii=False)
MOCK_PORTFOLIO_JSON = _json.dumps(_portfolio_obj, ensure_ascii=False)
MOCK_COVER_JSON = _json.dumps(_cover_obj, ensure_ascii=False)

# V2 mock 데이터
_profile_obj = {
    "career_narrative": "로봇 SW 엔지니어 지망, 부트캠프 출신",
    "career_turning_points": ["부트캠프 입학"],
    "career_gaps": [],
    "strengths": [
        {"area": "기술적 강점", "evidence": "ROS2 프로젝트 3건", "uniqueness": "HW-SW 통합"},
        {"area": "행동 패턴", "evidence": "개인 프로젝트 자발적 수행", "uniqueness": "자기 주도"},
        {"area": "희소 가치", "evidence": "로봇+비전 융합", "uniqueness": "융합 역량"},
    ],
    "weaknesses": [
        {"area": "실무 경력 부족", "impact": "경력직 대비 불리", "mitigation_hint": "밀도 전환"},
    ],
    "persona": "HW-SW 융합 관점의 빠르게 성장하는 엔지니어",
    "persona_fit": "로봇/자동화 스타트업, 연구소",
    "transferable_skills": ["임베디드 시스템 이해", "팀 리더십"],
    "project_depth_ranking": ["P1", "P2"],
}
_blueprint_obj = {
    "gap_matrix": [{"requirement": "ROS2", "my_evidence": "6개월", "status": "partial", "weakness_strategy": "reframe_as_intensity"}],
    "weakness_strategies": {"short_exp": {"pattern": "reframe_as_intensity", "message": "6개월 5개 프로젝트"}},
    "positioning": {"one_liner": "테스트 포지셔닝", "competitive_advantage": "차별점", "key_messages": ["이력서msg", "포폴msg", "자소서msg"]},
    "blueprint": {
        "experience_distribution": {"resume": ["P1: 팩트"], "portfolio": ["P1: 깊이"], "cover": ["P1: 동기"]},
        "emotional_arc": {"resume": "신뢰", "portfolio": "깊이", "cover": "진심"},
        "per_document_role": {"resume": "스크리닝", "portfolio": "면접유도", "cover": "설득"},
        "cover_question_plan": [],
    },
    "match_rate": 72,
    "storyline": "테스트 스토리라인",
    "highlight_projects": ["P1"],
    "highlight_reasons": ["JD 관련"],
}
_coach_obj = {
    "feedbacks": [],
    "overall_scores": {"hr_screener_pass": True, "team_lead_interview_want": 4, "hiring_manager_meet_want": 4},
    "interview_risks": [
        {"predicted_question": "경력이 짧은데?", "source": "resume.careers", "risk_level": "high", "defense_strategy": "밀도 강조", "sample_answer": "6개월 5개 프로젝트"},
    ],
}

MOCK_PROFILE_JSON = _json.dumps(_profile_obj, ensure_ascii=False)
MOCK_BLUEPRINT_JSON = _json.dumps(_blueprint_obj, ensure_ascii=False)
MOCK_COACH_JSON = _json.dumps(_coach_obj, ensure_ascii=False)

def make_writer_stdout(json_str: str) -> str:
    """writer 테스트용 mock stdout을 생성한다. result가 문자열이어야 함."""
    return _json.dumps({"result": json_str})


@pytest.fixture
def sample_company_info() -> CompanyInfo:
    return CompanyInfo(
        industry="IT/소프트웨어",
        recent_news=["시리즈B 투자 유치", "신규 서비스 출시"],
        tech_stack=["Python", "FastAPI", "React"],
        culture="자율과 책임",
        hiring_context="팀 확장",
        salary_info="5000~7000만원",
    )


@pytest.fixture
def sample_jd_analysis(sample_company_info) -> JDAnalysis:
    return JDAnalysis(
        company_name="테크스타트업",
        position="백엔드 개발자",
        requirements=["Python 3년 이상", "REST API 설계"],
        preferred=["FastAPI 경험", "Docker/K8s"],
        keywords=["Python", "FastAPI", "백엔드"],
        company_info=sample_company_info,
    )


@pytest.fixture
def sample_experience() -> Experience:
    return Experience(
        company="이전회사",
        department="개발팀",
        role="백엔드 개발자",
        period="2022.01 ~ 2024.06",
        description="REST API 설계 및 개발",
    )


@pytest.fixture
def sample_project() -> Project:
    return Project(
        name="주문 시스템 리팩토링",
        description="레거시 주문 시스템을 MSA로 전환",
        tech_stack=["Python", "FastAPI", "PostgreSQL"],
        situation="레거시 모놀리스 시스템의 성능 한계",
        decision_reason="서비스별 독립 배포 필요",
        action="도메인 분리 및 이벤트 기반 통신 도입",
        result="응답 속도 40% 개선",
        contribution="설계 및 구현 주도",
        period="2023.03 ~ 2023.09",
    )


@pytest.fixture
def sample_education() -> Education:
    return Education(
        school="서울대학교",
        major="컴퓨터공학",
        degree="학사",
        period="2018.03 ~ 2022.02",
    )


@pytest.fixture
def sample_source_data(sample_experience, sample_project, sample_education) -> SourceData:
    return SourceData(
        experiences=[sample_experience],
        projects=[sample_project],
        skills=["Python", "FastAPI", "Docker"],
        education=[sample_education],
        certifications=["정보처리기사"],
    )


@pytest.fixture
def sample_strategy() -> Strategy:
    return Strategy(
        match_rate=82.0,
        match_comment="주요 요구사항 대부분 충족",
        storyline="실무 경험 기반의 문제 해결 능력",
        requirement_mapping=[
            {"requirement": "Python 3년 이상", "my_experience": "Python 4년", "status": "충족"},
        ],
        highlight_projects=["주문 시스템 리팩토링"],
        highlight_reasons=["MSA 전환 경험이 JD와 직접 연관"],
    )


@pytest.fixture
def sample_documents() -> Documents:
    return Documents(
        resume_html="<h1>이력서</h1>",
        portfolio_html="<h1>포트폴리오</h1>",
        cover_letter_html="<h1>자소서</h1>",
    )


@pytest.fixture
def sample_cross_check() -> CrossCheckResult:
    return CrossCheckResult(
        consistency_issues=[],
        uncovered_requirements=[],
        duplicate_expressions=[],
        spelling_issues=[],
        char_count_ok=True,
        ai_detection_risk="low",
        overall_pass=True,
    )


@pytest.fixture
def sample_pipeline_state(
    sample_jd_analysis,
    sample_source_data,
    sample_strategy,
    sample_documents,
    sample_cross_check,
) -> PipelineState:
    return PipelineState(
        jd_text="백엔드 개발자 채용",
        cover_letter_questions=["지원 동기를 작성하세요."],
        jd_analysis=sample_jd_analysis,
        source_data=sample_source_data,
        strategy=sample_strategy,
        documents=sample_documents,
        cross_check=sample_cross_check,
    )
