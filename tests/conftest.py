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
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"result": "mocked claude response"}',
            stderr="",
        )
        yield mock_run


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
