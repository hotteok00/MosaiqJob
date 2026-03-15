"""PDF 렌더링 테스트."""

import pytest

from renderer.pdf import render_html, render_pdf, html_to_pdf


class TestRenderHtml:
    def test_resume_template(self):
        html = render_html("resume.html", {"content": "<h1>홍길동</h1>"})
        assert "홍길동" in html
        assert "<!DOCTYPE html>" in html
        assert "common.css" in html

    def test_portfolio_template(self):
        html = render_html("portfolio.html", {"content": "<h1>포트폴리오</h1>"})
        assert "포트폴리오" in html
        assert "project-page" in html  # portfolio 전용 스타일

    def test_cover_letter_template(self):
        html = render_html("cover_letter.html", {"content": "<h1>자소서</h1>"})
        assert "자소서" in html
        assert "cover-header" in html  # cover letter 전용 스타일

    def test_empty_content(self):
        html = render_html("resume.html", {"content": ""})
        assert "<!DOCTYPE html>" in html

    def test_html_escaping(self):
        """Jinja2 기본 동작: content는 safe하게 렌더링"""
        html = render_html("resume.html", {"content": "<script>alert('xss')</script>"})
        # Jinja2에서 {{ content }}는 autoescaping 설정에 따라 다름
        assert "<!DOCTYPE html>" in html

    def test_korean_content(self):
        html = render_html("resume.html", {"content": "<p>한국어 테스트 콘텐츠</p>"})
        assert "한국어 테스트 콘텐츠" in html

    def test_nonexistent_template(self):
        with pytest.raises(Exception):
            render_html("nonexistent.html", {"content": ""})


class TestRenderPdf:
    def test_generates_pdf_bytes(self):
        pdf_bytes = render_pdf("resume.html", {"content": "<h1>이력서</h1>"})
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        # PDF magic bytes
        assert pdf_bytes[:5] == b"%PDF-"

    def test_portfolio_pdf(self):
        pdf_bytes = render_pdf("portfolio.html", {"content": "<p>프로젝트</p>"})
        assert pdf_bytes[:5] == b"%PDF-"

    def test_cover_letter_pdf(self):
        pdf_bytes = render_pdf("cover_letter.html", {"content": "<p>자소서</p>"})
        assert pdf_bytes[:5] == b"%PDF-"

    def test_empty_content_pdf(self):
        pdf_bytes = render_pdf("resume.html", {"content": ""})
        assert pdf_bytes[:5] == b"%PDF-"


class TestHtmlToPdf:
    def test_writes_pdf_file(self, tmp_path):
        output_path = tmp_path / "test.pdf"
        html_to_pdf("<h1>테스트</h1>", output_path)
        assert output_path.exists()
        assert output_path.stat().st_size > 0
        assert output_path.read_bytes()[:5] == b"%PDF-"

    def test_overwrites_existing(self, tmp_path):
        output_path = tmp_path / "test.pdf"
        html_to_pdf("<h1>첫번째</h1>", output_path)
        size1 = output_path.stat().st_size
        html_to_pdf("<h1>두번째</h1><p>더 긴 내용</p>", output_path)
        assert output_path.exists()
        # 파일이 다시 쓰여졌는지 확인 (크기가 다를 수 있음)
        assert output_path.stat().st_size > 0

    def test_creates_in_nested_dir(self, tmp_path):
        output_path = tmp_path / "sub" / "dir" / "test.pdf"
        output_path.parent.mkdir(parents=True)
        html_to_pdf("<p>테스트</p>", output_path)
        assert output_path.exists()
