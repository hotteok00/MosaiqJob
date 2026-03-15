"""Pydantic 모델 유효성 검증 테스트."""

import pytest
from pydantic import ValidationError

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


class TestCompanyInfo:
    def test_default_values(self):
        info = CompanyInfo()
        assert info.industry == ""
        assert info.recent_news == []
        assert info.tech_stack == []
        assert info.culture == ""
        assert info.hiring_context == ""
        assert info.salary_info == ""

    def test_with_values(self, sample_company_info):
        assert sample_company_info.industry == "IT/소프트웨어"
        assert len(sample_company_info.recent_news) == 2
        assert "Python" in sample_company_info.tech_stack


class TestJDAnalysis:
    def test_required_fields(self):
        with pytest.raises(ValidationError):
            JDAnalysis()  # company_name, position 필수

    def test_minimal(self):
        jd = JDAnalysis(company_name="회사", position="개발자")
        assert jd.company_name == "회사"
        assert jd.requirements == []
        assert isinstance(jd.company_info, CompanyInfo)

    def test_full(self, sample_jd_analysis):
        assert sample_jd_analysis.company_name == "테크스타트업"
        assert len(sample_jd_analysis.requirements) == 2
        assert sample_jd_analysis.company_info.industry == "IT/소프트웨어"

    def test_serialization_roundtrip(self, sample_jd_analysis):
        data = sample_jd_analysis.model_dump()
        restored = JDAnalysis(**data)
        assert restored == sample_jd_analysis

    def test_json_roundtrip(self, sample_jd_analysis):
        json_str = sample_jd_analysis.model_dump_json()
        restored = JDAnalysis.model_validate_json(json_str)
        assert restored == sample_jd_analysis


class TestExperience:
    def test_default_values(self):
        exp = Experience()
        assert exp.company == ""
        assert exp.role == ""

    def test_with_values(self, sample_experience):
        assert sample_experience.company == "이전회사"
        assert sample_experience.period == "2022.01 ~ 2024.06"


class TestProject:
    def test_required_fields(self):
        with pytest.raises(ValidationError):
            Project()  # name 필수

    def test_minimal(self):
        proj = Project(name="테스트 프로젝트")
        assert proj.name == "테스트 프로젝트"
        assert proj.tech_stack == []

    def test_full(self, sample_project):
        assert sample_project.name == "주문 시스템 리팩토링"
        assert "Python" in sample_project.tech_stack
        assert sample_project.result == "응답 속도 40% 개선"


class TestEducation:
    def test_required_fields(self):
        with pytest.raises(ValidationError):
            Education()  # school 필수

    def test_minimal(self):
        edu = Education(school="서울대학교")
        assert edu.major == ""

    def test_full(self, sample_education):
        assert sample_education.degree == "학사"


class TestSourceData:
    def test_default_empty(self):
        sd = SourceData()
        assert sd.experiences == []
        assert sd.projects == []
        assert sd.skills == []

    def test_with_data(self, sample_source_data):
        assert len(sample_source_data.experiences) == 1
        assert len(sample_source_data.projects) == 1
        assert "Python" in sample_source_data.skills
        assert "정보처리기사" in sample_source_data.certifications


class TestStrategy:
    def test_default_values(self):
        s = Strategy()
        assert s.match_rate == 0.0
        assert s.highlight_projects == []

    def test_match_rate_range(self, sample_strategy):
        assert 0 <= sample_strategy.match_rate <= 100

    def test_with_values(self, sample_strategy):
        assert sample_strategy.match_rate == 82.0
        assert len(sample_strategy.requirement_mapping) == 1
        assert sample_strategy.requirement_mapping[0]["status"] == "충족"


class TestDocuments:
    def test_default_empty(self):
        docs = Documents()
        assert docs.resume_html == ""
        assert docs.portfolio_html == ""
        assert docs.cover_letter_html == ""

    def test_with_html(self, sample_documents):
        assert "<h1>" in sample_documents.resume_html


class TestCrossCheckResult:
    def test_default_pass(self):
        result = CrossCheckResult()
        assert result.overall_pass is True
        assert result.char_count_ok is True
        assert result.ai_detection_risk == "low"
        assert result.consistency_issues == []

    def test_with_issues(self):
        result = CrossCheckResult(
            consistency_issues=["날짜 불일치"],
            overall_pass=False,
            ai_detection_risk="high",
        )
        assert result.overall_pass is False
        assert len(result.consistency_issues) == 1


class TestPipelineState:
    def test_default_empty(self):
        state = PipelineState()
        assert state.jd_text == ""
        assert state.jd_analysis is None
        assert state.source_data is None

    def test_full_state(self, sample_pipeline_state):
        assert sample_pipeline_state.jd_analysis is not None
        assert sample_pipeline_state.source_data is not None
        assert sample_pipeline_state.strategy is not None
        assert sample_pipeline_state.documents is not None
        assert sample_pipeline_state.cross_check is not None

    def test_partial_state(self, sample_jd_analysis):
        state = PipelineState(
            jd_text="채용공고",
            jd_analysis=sample_jd_analysis,
        )
        assert state.jd_analysis is not None
        assert state.source_data is None

    def test_serialization_roundtrip(self, sample_pipeline_state):
        data = sample_pipeline_state.model_dump()
        restored = PipelineState(**data)
        assert restored == sample_pipeline_state
