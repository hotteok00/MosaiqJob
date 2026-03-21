from pydantic import BaseModel


class CompanyInfo(BaseModel):
    industry: str = ""
    recent_news: list[str] = []
    tech_stack: list[str] = []
    culture: str = ""
    hiring_context: str = ""  # 충원/신설/확장
    salary_info: str = ""


class JDAnalysis(BaseModel):
    company_name: str
    position: str
    requirements: list[str] = []
    preferred: list[str] = []
    keywords: list[str] = []
    company_info: CompanyInfo = CompanyInfo()


class Experience(BaseModel):
    company: str = ""
    department: str = ""
    role: str = ""
    period: str = ""
    description: str = ""


class Project(BaseModel):
    name: str
    description: str = ""
    tech_stack: list[str] = []
    situation: str = ""
    decision_reason: str = ""
    action: str = ""
    result: str = ""
    contribution: str = ""
    period: str = ""


class Education(BaseModel):
    school: str
    major: str = ""
    degree: str = ""
    period: str = ""


class SourceData(BaseModel):
    experiences: list[Experience] = []
    projects: list[Project] = []
    skills: list[str] = []
    education: list[Education] = []
    certifications: list[str] = []


class Strategy(BaseModel):
    match_rate: float = 0.0
    match_comment: str = ""
    storyline: str = ""
    requirement_mapping: list[dict] = []  # [{requirement, my_experience, status}]
    highlight_projects: list[str] = []  # project names
    highlight_reasons: list[str] = []


class Documents(BaseModel):
    resume_html: str = ""
    portfolio_html: str = ""
    cover_letter_html: str = ""


class CrossCheckResult(BaseModel):
    consistency_issues: list[str] = []
    uncovered_requirements: list[str] = []
    duplicate_expressions: list[str] = []
    spelling_issues: list[str] = []
    char_count_ok: bool = True
    ai_detection_risk: str = "low"
    overall_pass: bool = True


class PipelineState(BaseModel):
    jd_text: str = ""
    cover_letter_questions: list[str] = []
    jd_analysis: JDAnalysis | None = None
    source_data: SourceData | None = None
    strategy: Strategy | None = None
    documents: Documents | None = None
    cross_check: CrossCheckResult | None = None


# ── V2 모델 ────────────────────────────────────────────────


class Strength(BaseModel):
    area: str
    evidence: str = ""
    uniqueness: str = ""


class Weakness(BaseModel):
    area: str
    impact: str = ""
    mitigation_hint: str = ""


class CandidateProfile(BaseModel):
    career_narrative: str = ""
    career_turning_points: list[str] = []
    career_gaps: list[str] = []
    strengths: list[Strength] = []
    weaknesses: list[Weakness] = []
    persona: str = ""
    persona_fit: str = ""
    transferable_skills: list[str] = []
    project_depth_ranking: list[str] = []


class GapEntry(BaseModel):
    requirement: str
    my_evidence: str = ""
    status: str = "gap"  # "met" | "partial" | "gap"
    weakness_strategy: str | None = None


class WeaknessStrategy(BaseModel):
    pattern: str = ""
    message: str = ""


class Positioning(BaseModel):
    one_liner: str = ""
    competitive_advantage: str = ""
    key_messages: list[str] = []


class DocumentDistribution(BaseModel):
    resume: list[str] = []
    portfolio: list[str] = []
    cover: list[str] = []


class EmotionalArc(BaseModel):
    resume: str = ""
    portfolio: str = ""
    cover: str = ""


class CoverQuestionPlan(BaseModel):
    question: str = ""
    core_message: str = ""
    evidence_projects: list[str] = []
    angle: str = ""


class BlueprintDetail(BaseModel):
    experience_distribution: DocumentDistribution = DocumentDistribution()
    emotional_arc: EmotionalArc = EmotionalArc()
    per_document_role: dict[str, str] = {}
    cover_question_plan: list[CoverQuestionPlan] = []


class Blueprint(BaseModel):
    gap_matrix: list[GapEntry] = []
    weakness_strategies: dict[str, WeaknessStrategy] = {}
    positioning: Positioning = Positioning()
    blueprint: BlueprintDetail = BlueprintDetail()
    match_rate: float = 0.0
    storyline: str = ""
    highlight_projects: list[str] = []
    highlight_reasons: list[str] = []


class InterviewRisk(BaseModel):
    predicted_question: str = ""
    source: str = ""
    risk_level: str = "medium"  # "high" | "medium" | "low"
    defense_strategy: str = ""
    sample_answer: str = ""


class CoachResult(BaseModel):
    overall_scores: dict[str, object] = {}
    interview_risks: list[InterviewRisk] = []
