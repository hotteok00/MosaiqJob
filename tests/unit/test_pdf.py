"""PDF 렌더링 테스트."""

import pytest

from renderer.pdf import render_html, render_pdf, html_to_pdf

# Jinja2 템플릿용 더미 데이터
_RESUME_DATA = {
    "person": {"name": "홍길동", "title": "Engineer", "phone": "", "email": "", "github": "", "location": ""},
    "summary": "테스트 요약",
    "careers": [],
    "projects": [],
    "skills": {},
    "education": [],
    "certifications": [],
    "activities": [],
}

_PORTFOLIO_DATA = {
    "person": {"name": "홍길동", "title": "Engineer", "phone": "", "email": "", "github": "", "company": ""},
    "summary": "포트폴리오 요약",
    "competencies": [],
    "project_table": [],
    "highlights": [],
    "other_projects": [],
    "additional": [],
}

_COVER_DATA = {
    "person": {"name": "홍길동", "phone": "", "email": "", "github": ""},
    "target": {"company": "테스트 기업", "position": "엔지니어"},
    "doc_label": "COVER LETTER",
    "sections": [{"label": "자유형", "content": "<p>자소서 테스트</p>"}],
    "date": "2026. 03",
}


class TestRenderHtml:
    def test_resume_template(self):
        html = render_html("resume.html", _RESUME_DATA)
        assert "홍길동" in html
        assert "<!DOCTYPE html>" in html

    def test_portfolio_template(self):
        html = render_html("portfolio.html", _PORTFOLIO_DATA)
        assert "홍길동" in html

    def test_cover_letter_template(self):
        html = render_html("cover_letter.html", _COVER_DATA)
        assert "자소서 테스트" in html

    def test_nonexistent_template(self):
        with pytest.raises(Exception):
            render_html("nonexistent.html", {})


class TestRenderPdf:
    def test_generates_pdf_bytes(self):
        pdf_bytes = render_pdf("resume.html", _RESUME_DATA)
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"

    def test_portfolio_pdf(self):
        pdf_bytes = render_pdf("portfolio.html", _PORTFOLIO_DATA)
        assert pdf_bytes[:5] == b"%PDF-"

    def test_cover_letter_pdf(self):
        pdf_bytes = render_pdf("cover_letter.html", _COVER_DATA)
        assert pdf_bytes[:5] == b"%PDF-"


class TestHtmlToPdf:
    def test_writes_pdf_file(self, tmp_path):
        output_path = tmp_path / "test.pdf"
        html_to_pdf("<h1>테스트</h1>", output_path)
        assert output_path.exists()
        assert output_path.read_bytes()[:5] == b"%PDF-"

    def test_overwrites_existing(self, tmp_path):
        output_path = tmp_path / "test.pdf"
        html_to_pdf("<h1>첫번째</h1>", output_path)
        html_to_pdf("<h1>두번째</h1><p>더 긴 내용</p>", output_path)
        assert output_path.exists()

    def test_creates_in_nested_dir(self, tmp_path):
        output_path = tmp_path / "sub" / "dir" / "test.pdf"
        output_path.parent.mkdir(parents=True)
        html_to_pdf("<p>테스트</p>", output_path)
        assert output_path.exists()
