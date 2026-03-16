import io
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from PyPDF2 import PdfReader
from weasyprint import HTML

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def render_pdf(template_name: str, data: dict) -> bytes:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template(template_name)
    html_string = template.render(**data)
    return HTML(string=html_string, base_url=str(TEMPLATES_DIR)).write_pdf()


def render_html(template_name: str, data: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template(template_name)
    return template.render(**data)


_PAGE_CSS = """
<style>
@page {
    size: A4 !important;
    margin: 12mm 14mm 12mm 14mm !important;
}
html, body {
    width: auto !important;
    max-width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
}
.page, .container, main, article {
    width: auto !important;
    max-width: 100% !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
}
</style>
"""


def _inject_page_css(html_string: str) -> str:
    """@page 마진을 강제 삽입하여 좌우 잘림 방지."""
    if "<head>" in html_string:
        return html_string.replace("<head>", f"<head>{_PAGE_CSS}", 1)
    elif "<html" in html_string:
        return html_string.replace("<html", f"<html><head>{_PAGE_CSS}</head", 1)
    return f"{_PAGE_CSS}{html_string}"


def html_to_pdf(html_string: str, output_path: Path) -> None:
    html_string = _inject_page_css(html_string)
    HTML(string=html_string, base_url=str(TEMPLATES_DIR)).write_pdf(str(output_path))


def count_pdf_pages(pdf_path: Path) -> int:
    """PDF 파일의 페이지 수를 반환한다."""
    return len(PdfReader(str(pdf_path)).pages)


def html_to_pdf_bytes(html_string: str) -> bytes:
    """HTML을 PDF 바이트로 변환한다 (파일 저장 없이)."""
    html_string = _inject_page_css(html_string)
    return HTML(string=html_string, base_url=str(TEMPLATES_DIR)).write_pdf()


def count_pages_from_bytes(pdf_bytes: bytes) -> int:
    """PDF 바이트에서 페이지 수를 반환한다."""
    return len(PdfReader(io.BytesIO(pdf_bytes)).pages)
