"""MosaiqJob CLI - 취업 문서 자동화 파이프라인."""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from agents import analyst, source, strategist, writer, reviewer
from agents import profiler as profiler_agent
from agents import coach as coach_agent
from agents.log import setup_logging
from renderer.pdf import html_to_pdf

load_dotenv()
setup_logging()

console = Console()
OUTPUT_ROOT = Path(__file__).parent / "output"


def parse_input(text: str) -> tuple[str, list[str]]:
    """JD 텍스트와 자소서 문항을 분리한다. 구분자: ---"""
    if "---" in text:
        parts = text.split("---", 1)
        jd_text = parts[0].strip()
        questions = [q.strip() for q in parts[1].strip().split("\n") if q.strip()]
    else:
        jd_text = text.strip()
        questions = []
    return jd_text, questions


def extract_keywords(jd_analysis: str, jd_text: str) -> list[str]:
    """JD 분석 결과에서 키워드를 추출한다."""
    try:
        data = json.loads(jd_analysis)
        return data.get("keywords", [])
    except (json.JSONDecodeError, TypeError):
        return [w for w in jd_text.split() if len(w) > 2][:10]


def _extract_company_name(*json_sources: str) -> str:
    """여러 JSON 소스에서 기업명을 재귀 탐색한다. 첫 번째로 찾은 값을 반환."""

    _COMPANY_KEYS = ("company_name", "company", "target_company", "회사명", "기업명")

    def _find(obj):
        if isinstance(obj, dict):
            for key in _COMPANY_KEYS:
                val = obj.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
                # target: {company: "..."} 같은 중첩 구조도 탐색
                if isinstance(val, dict):
                    found = _find(val)
                    if found:
                        return found
            for v in obj.values():
                found = _find(v)
                if found:
                    return found
        if isinstance(obj, list):
            for item in obj:
                found = _find(item)
                if found:
                    return found
        return None

    for source in json_sources:
        if not source:
            continue
        text = re.sub(r"```(?:json)?\s*\n?", "", source)
        text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
        try:
            data = json.loads(text) if text.strip().startswith("{") else {}
            name = _find(data)
            if name:
                name = re.sub(r'[\\/*?:"<>|]', "_", name)
                name = name.replace("..", "_")
                return name.strip("._")
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return "unknown"


def _make_output_dir(company_name: str) -> Path:
    """output/기업명_timestamp 디렉토리를 생성한다."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_ROOT / f"{company_name}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _render_and_save(
    output_dir: Path,
    resume_data: dict,
    portfolio_data: dict,
    cover_data: dict,
) -> None:
    """3개 문서를 HTML + PDF로 렌더링하여 output_dir에 저장한다."""
    # 이력서
    resume_html = writer.render_template("resume.html", resume_data)
    (output_dir / "이력서.html").write_text(resume_html, encoding="utf-8")
    html_to_pdf(resume_html, output_dir / "이력서.pdf")

    # 포트폴리오 (페이지 축소 포함)
    portfolio_html, portfolio_pdf_bytes = writer.render_portfolio_with_shrink(portfolio_data)
    (output_dir / "포트폴리오.html").write_text(portfolio_html, encoding="utf-8")
    (output_dir / "포트폴리오.pdf").write_bytes(portfolio_pdf_bytes)

    # 자소서
    cover_html = writer.render_template("cover_letter.html", cover_data)
    (output_dir / "자소서.html").write_text(cover_html, encoding="utf-8")
    html_to_pdf(cover_html, output_dir / "자소서.pdf")


def _format_issues_panel(issues: list) -> str:
    """ReviewIssue 리스트를 읽기 좋은 텍스트로 변환한다."""
    if not issues:
        return "문제 없음"

    lines = []
    for issue in issues:
        icon = "[red]ERROR[/red]" if issue.severity == "error" else "[yellow]WARN[/yellow]"
        lines.append(f"  {icon} [{issue.doc}] {issue.category}: {issue.description}")
        if issue.fix_suggestion:
            lines.append(f"        → {issue.fix_suggestion}")
    return "\n".join(lines)


def run_pipeline(jd_text: str, questions: list[str], auto: bool = False) -> None:
    """파이프라인 전체를 실행한다."""

    # Step 1: JD + 기업 분석
    with console.status("[bold cyan]1/8 JD + 기업 분석 중..."):
        jd_analysis = analyst.analyze_jd(jd_text)
    console.print("[green]1/8[/green] JD + 기업 분석 완료")

    keywords = extract_keywords(jd_analysis, jd_text)

    # Step 2: 소스 수집
    with console.status("[bold cyan]2/8 소스 수집 중 (Notion/GitHub)..."):
        source_data = source.analyze_source(keywords)
    console.print("[green]2/8[/green] 소스 수집 완료")

    # Step 3: 전략 수립
    with console.status("[bold cyan]3/8 전략 수립 중..."):
        strategy_result = strategist.strategize(jd_analysis, source_data)
    console.print("[green]3/8[/green] 전략 수립 완료")

    # 기업명 기반 출력 디렉토리 생성 (analyst + strategist 양쪽에서 탐색)
    company_name = _extract_company_name(jd_analysis, strategy_result)
    output_dir = _make_output_dir(company_name)

    # Step 4: 사용자 승인
    console.print()
    console.print(Panel(strategy_result, title="전략 수립 결과", border_style="yellow"))
    if not auto:
        answer = input("\n진행할까요? (Y/n): ").strip().lower()
        if answer in ("n", "no", "아니", "ㄴㄴ"):
            console.print("[red]취소됨[/red]")
            return
    console.print()

    # Step 5: 이력서 생성 (Layer 1 구조 + Layer 2 내용 검증)
    with console.status("[bold cyan]4/8 이력서 생성 중 (구조+내용 검증)..."):
        resume_data = writer.generate_resume(strategy_result, source_data, jd_analysis)
    console.print("[green]4/8[/green] 이력서 생성 완료")

    # Step 6: 포트폴리오 생성 (Layer 1 + Layer 2 + 페이지 축소)
    with console.status("[bold cyan]5/8 포트폴리오 생성 중 (구조+내용 검증)..."):
        portfolio_data = writer.generate_portfolio(strategy_result, source_data, resume_data)
    console.print("[green]5/8[/green] 포트폴리오 생성 완료")

    # Step 7: 자소서 생성 (Layer 1 + Layer 2)
    with console.status("[bold cyan]6/8 자소서 생성 중 (구조+내용 검증)..."):
        cover_data = writer.generate_cover(
            strategy_result, jd_analysis, resume_data, portfolio_data, questions
        )
    console.print("[green]6/8[/green] 자소서 생성 완료")

    # Step 8: 크로스체크 + 자동 수정 (Layer 3)
    with console.status("[bold cyan]7/8 크로스체크 + 자동 수정 중..."):
        resume_data, portfolio_data, cover_data, issues = reviewer.review_and_fix(
            jd_analysis, resume_data, portfolio_data, cover_data, questions
        )
    console.print("[green]7/8[/green] 크로스체크 완료")

    # 크로스체크 결과 표시
    if issues:
        console.print()
        console.print(Panel(
            _format_issues_panel(issues),
            title="크로스체크 결과",
            border_style="cyan",
        ))

    # Step 9: 최종 렌더 + 파일 저장
    with console.status("[bold cyan]8/8 최종 렌더링 + PDF 생성 중..."):
        _render_and_save(output_dir, resume_data, portfolio_data, cover_data)

    console.print("[green]8/8[/green] 최종 렌더링 완료")

    # 결과 표시
    console.print()
    console.print(f"[bold green]완료![/bold green] {output_dir} 에 생성됨:")
    for f in sorted(output_dir.iterdir()):
        console.print(f"  - {f.name}")
    console.print()
    console.print("[dim]검토 가이드:[/dim]")
    console.print("  - 이력서 상단 요약문이 본인 느낌과 맞는지 확인하세요")
    console.print("  - 자소서 첫 문장이 마음에 드시나요?")
    console.print("  - 포폴에서 강조한 프로젝트가 적절한가요?")
    console.print("  - 전체적인 톤이 본인답게 느껴지나요?")


def _display_blueprint(blueprint_json: str) -> None:
    """블루프린트를 Rich Panel로 시각화한다."""
    try:
        bp = json.loads(blueprint_json)
    except (json.JSONDecodeError, TypeError):
        console.print(Panel(blueprint_json, title="블루프린트", border_style="yellow"))
        return

    lines = []

    # 포지셔닝
    pos = bp.get("positioning", {})
    lines.append(f"[bold]포지셔닝:[/bold] {pos.get('one_liner', '-')}")
    lines.append(f"[bold]차별점:[/bold] {pos.get('competitive_advantage', '-')}")
    lines.append("")

    # 갭 매트릭스
    lines.append("[bold]갭 매트릭스:[/bold]")
    for gap in bp.get("gap_matrix", []):
        status = gap.get("status", "?")
        icon = "[green]MET[/green]" if status == "met" else "[yellow]PARTIAL[/yellow]" if status == "partial" else "[red]GAP[/red]"
        strategy = f" ({gap['weakness_strategy']})" if gap.get("weakness_strategy") else ""
        lines.append(f"  {icon} {gap.get('requirement', '?')}: {gap.get('my_evidence', '-')}{strategy}")
    lines.append("")

    # 경험 배분
    dist = bp.get("blueprint", {}).get("experience_distribution", {})
    if dist:
        lines.append("[bold]경험 배분:[/bold]")
        for doc, items in dist.items():
            doc_label = {"resume": "이력서", "portfolio": "포폴", "cover": "자소서"}.get(doc, doc)
            lines.append(f"  [cyan]{doc_label}:[/cyan] {', '.join(items) if isinstance(items, list) else items}")
        lines.append("")

    # 감정 흐름
    arc = bp.get("blueprint", {}).get("emotional_arc", {})
    if arc:
        lines.append("[bold]감정 흐름:[/bold]")
        for doc, desc in arc.items():
            doc_label = {"resume": "이력서", "portfolio": "포폴", "cover": "자소서"}.get(doc, doc)
            lines.append(f"  {doc_label}: {desc}")
        lines.append("")

    # 매칭률 + 스토리라인
    lines.append(f"[bold]매칭률:[/bold] {bp.get('match_rate', '?')}%")
    lines.append(f"[bold]스토리라인:[/bold] {bp.get('storyline', '-')}")
    lines.append(f"[bold]강조 프로젝트:[/bold] {', '.join(bp.get('highlight_projects', []))}")

    console.print(Panel("\n".join(lines), title="V2 블루프린트", border_style="yellow"))


def _format_coach_panel(feedbacks: list, overall: dict) -> str:
    """코칭 피드백을 읽기 좋은 텍스트로 변환한다."""
    lines = []

    # 종합 점수
    if overall:
        hr = "[green]PASS[/green]" if overall.get("hr_screener_pass") else "[red]FAIL[/red]"
        tl = overall.get("team_lead_interview_want", "?")
        hm = overall.get("hiring_manager_meet_want", "?")
        lines.append(f"  HR 스크리닝: {hr} | 팀리더 면접의향: {tl}/5 | 채용결정자 관심도: {hm}/5")
        lines.append("")

    if not feedbacks:
        lines.append("  문제 없음")
        return "\n".join(lines)

    for fb in feedbacks:
        icon = "[red]ERROR[/red]" if fb.severity == "error" else "[yellow]WARN[/yellow]"
        lines.append(f"  {icon} [{fb.doc}] {fb.persona}/{fb.category}: {fb.description}")
        if fb.fix_suggestion:
            lines.append(f"        → {fb.fix_suggestion}")

    return "\n".join(lines)


def _format_interview_risks(risks: list) -> str:
    """면접 리스크를 읽기 좋은 텍스트로 변환한다."""
    if not risks:
        return "  면접 리스크 없음"

    lines = []
    for r in risks:
        icon = {"high": "[red]HIGH[/red]", "medium": "[yellow]MED[/yellow]", "low": "[green]LOW[/green]"}.get(r.risk_level, "[dim]?[/dim]")
        lines.append(f"  {icon} Q: {r.predicted_question}")
        lines.append(f"       전략: {r.defense_strategy}")
        if r.sample_answer:
            lines.append(f"       예시: {r.sample_answer[:100]}{'...' if len(r.sample_answer) > 100 else ''}")
        lines.append("")
    return "\n".join(lines)


def run_pipeline_v2(jd_text: str, questions: list[str], auto: bool = False) -> None:
    """V2 파이프라인: 후보자 중심 진단 → 전략 심화 → 병렬 작성 → 설득력 코칭."""
    from concurrent.futures import ThreadPoolExecutor

    # Phase 1: 진단
    # 1/7 소스 전수 수집
    with console.status("[bold cyan]1/7 소스 전체 수집 중 (Notion/GitHub/Drive/OneDrive)..."):
        source_data = source.collect_full_profile()
    console.print("[green]1/7[/green] 소스 전체 수집 완료")

    # 2/7 프로파일링 + JD 심층분석 (병렬)
    with console.status("[bold cyan]2/7 후보자 프로파일링 + JD 심층 분석 중..."):
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_profile = pool.submit(profiler_agent.profile_candidate, source_data)
            f_jd = pool.submit(analyst.analyze_jd_deep, jd_text)
            candidate_profile = f_profile.result()
            jd_analysis = f_jd.result()
    console.print("[green]2/7[/green] 프로파일링 + JD 분석 완료")

    # Phase 2: 전략
    # 3/7 블루프린트 생성
    with console.status("[bold cyan]3/7 갭 분석 + 포지셔닝 + 블루프린트 수립 중..."):
        blueprint = strategist.strategize_v2(candidate_profile, jd_analysis, source_data)
    console.print("[green]3/7[/green] 블루프린트 수립 완료")

    # 기업명 기반 출력 디렉토리 생성 (analyst + blueprint 양쪽에서 탐색)
    company_name = _extract_company_name(jd_analysis, blueprint)
    output_dir = _make_output_dir(company_name)

    # 사용자 승인 (블루프린트 시각화)
    console.print()
    _display_blueprint(blueprint)
    if not auto:
        answer = input("\n진행할까요? (Y/n): ").strip().lower()
        if answer in ("n", "no", "아니", "ㄴㄴ"):
            console.print("[red]취소됨[/red]")
            return
    console.print()

    # Phase 3: 병렬 작성
    # 4/7 이력서 + 포트폴리오 + 자소서 동시 생성
    with console.status("[bold cyan]4/7 이력서 + 포트폴리오 + 자소서 병렬 생성 중..."):
        with ThreadPoolExecutor(max_workers=3) as pool:
            f_resume = pool.submit(writer.generate_resume_v2, blueprint, source_data, jd_analysis)
            f_portfolio = pool.submit(writer.generate_portfolio_v2, blueprint, source_data)
            f_cover = pool.submit(writer.generate_cover_v2, blueprint, source_data, jd_analysis, questions)
            resume_data = f_resume.result()
            portfolio_data = f_portfolio.result()
            cover_data = f_cover.result()
    console.print("[green]4/7[/green] 3개 문서 병렬 생성 완료")

    # Phase 4: 코칭
    # 5/7 설득력 코칭 + 면접 리스크
    with console.status("[bold cyan]5/7 설득력 코칭 + 면접 리스크 분석 중..."):
        resume_data, portfolio_data, cover_data, feedbacks, overall, risks = coach_agent.coach_review(
            jd_analysis, blueprint, resume_data, portfolio_data, cover_data, questions
        )
    console.print("[green]5/7[/green] 설득력 코칭 완료")

    # 코칭 결과 표시
    if feedbacks or overall:
        console.print()
        console.print(Panel(
            _format_coach_panel(feedbacks, overall),
            title="설득력 코칭 결과",
            border_style="cyan",
        ))

    # 면접 리스크 표시
    if risks:
        console.print()
        console.print(Panel(
            _format_interview_risks(risks),
            title="면접 예상 질문 + 방어 전략",
            border_style="magenta",
        ))

    # 6/7 최종 렌더 + 파일 저장
    with console.status("[bold cyan]6/7 최종 렌더링 + PDF 생성 중..."):
        _render_and_save(output_dir, resume_data, portfolio_data, cover_data)

        # 면접 준비 가이드
        if risks:
            interview_data = {
                "overall_scores": overall,
                "interview_risks": [
                    {
                        "predicted_question": r.predicted_question,
                        "source": r.source,
                        "risk_level": r.risk_level,
                        "defense_strategy": r.defense_strategy,
                        "sample_answer": r.sample_answer,
                    }
                    for r in risks
                ],
            }
            (output_dir / "면접준비.json").write_text(
                json.dumps(interview_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    console.print("[green]6/7[/green] 최종 렌더링 완료")

    # 7/7 결과 표시
    console.print()
    console.print(f"[bold green]완료![/bold green] {output_dir} 에 생성됨:")
    for f in sorted(output_dir.iterdir()):
        console.print(f"  - {f.name}")
    console.print()
    console.print("[dim]검토 가이드:[/dim]")
    console.print("  - 이력서 상단 요약문이 포지셔닝과 맞는지 확인하세요")
    console.print("  - 자소서 첫 문장이 마음에 드시나요?")
    console.print("  - 포폴에서 강조한 프로젝트가 적절한가요?")
    console.print("  - 3개 문서를 순서대로 읽었을 때 서사가 이어지나요?")
    console.print("  - 면접준비.json으로 예상 질문을 미리 연습하세요")


def serve_output(port: int = 8080, output_path: Path | None = None) -> None:
    """output 폴더를 브라우저에서 볼 수 있도록 HTTP 서버를 실행한다."""
    import http.server
    import socket
    import socketserver
    import urllib.parse
    from functools import partial

    serve_dir = output_path or OUTPUT_ROOT

    if not serve_dir.exists():
        console.print(f"[red]출력 디렉토리가 없습니다: {serve_dir}[/red]")
        sys.exit(1)

    class OutputHandler(http.server.SimpleHTTPRequestHandler):
        """output 디렉토리 전용 핸들러. / 요청 시 동적 인덱스를 생성한다."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(serve_dir), **kwargs)

        def do_GET(self):
            # / 요청이면 동적 인덱스 생성
            if self.path in ("/", "/index.html"):
                self._serve_index()
                return
            # /viewer 요청이면 PDF 뷰어
            if self.path.startswith("/viewer"):
                self._serve_viewer()
                return
            super().do_GET()

        def _serve_index(self):
            folders = []
            for d in sorted(serve_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                if not d.is_dir():
                    continue
                filenames = {f.name for f in d.iterdir() if f.is_file()}
                folders.append({"name": d.name, "files": filenames})

            html = _build_index_html(folders)
            self._send_html(html)

        def _serve_viewer(self):
            html = _build_viewer_html()
            self._send_html(html)

        def _send_html(self, html: str):
            encoded = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format, *args):
            # 로그 억제 (너무 많이 찍힘)
            pass

    # 로컬 IP 얻기
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "localhost"

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", port), OutputHandler) as httpd:
        console.print(Panel(
            f"[bold]http://{local_ip}:{port}[/bold]\n"
            f"[dim]output 디렉토리: {serve_dir}[/dim]\n"
            f"[dim]Ctrl+C로 종료[/dim]",
            title="Output Browser",
            border_style="green",
        ))
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            console.print("\n[yellow]서버 종료[/yellow]")


def _build_index_html(folders: list[dict]) -> str:
    """output 폴더 목록을 동적으로 HTML 인덱스 페이지로 생성한다."""
    import html as html_mod
    import re as re_mod
    import urllib.parse

    rows = []
    for folder in folders:
        name = folder["name"]
        files = folder["files"]
        enc = urllib.parse.quote(name)

        # 타임스탬프 파싱
        m = re_mod.search(r"_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$", name)
        if m:
            time_str = f"{m[1]}-{m[2]}-{m[3]} {m[4]}:{m[5]}"
            display_name = name[:m.start()]
        else:
            time_str = ""
            display_name = name

        links = []
        for doc in ("이력서", "자소서", "포트폴리오"):
            doc_enc = urllib.parse.quote(doc)
            if f"{doc}.pdf" in files:
                links.append(f'<a class="pdf-link" href="/viewer?file={enc}/{doc_enc}.pdf">{doc}</a>')

        rows.append(f"""
        <div class="folder">
            <div class="folder-name">{html_mod.escape(display_name)}</div>
            <div class="folder-time">{time_str}</div>
            <div class="links">{' '.join(links)}</div>
        </div>""")

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MosaiqJob Output</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, sans-serif; background: #f5f5f5; padding: 16px; }}
  h1 {{ font-size: 1.4em; margin-bottom: 16px; color: #333; }}
  .folder {{ background: #fff; border-radius: 8px; margin-bottom: 12px; padding: 14px;
             box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .folder-name {{ font-weight: 600; font-size: 1em; margin-bottom: 4px; color: #222; }}
  .folder-time {{ font-size: 0.8em; color: #888; margin-bottom: 8px; }}
  .links {{ display: flex; gap: 8px; flex-wrap: wrap; }}
  .links a {{ display: inline-block; padding: 6px 14px; border-radius: 6px;
              text-decoration: none; font-size: 0.85em; font-weight: 500; }}
  .html-link {{ background: #e3f2fd; color: #1565c0; }}
  .pdf-link {{ background: #fce4ec; color: #c62828; }}
  .html-link:active {{ background: #bbdefb; }}
  .pdf-link:active {{ background: #f8bbd0; }}
</style>
</head>
<body>
<h1>MosaiqJob Output</h1>
{''.join(rows) if rows else '<p style="color:#888">출력 폴더가 없습니다.</p>'}
</body>
</html>"""


def _build_viewer_html() -> str:
    """PDF.js 기반 PDF 뷰어 페이지를 반환한다."""
    return """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PDF Viewer</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #333; }
  .top-bar { position: fixed; top: 0; left: 0; right: 0; z-index: 10;
    background: rgba(0,0,0,0.85); color: #fff; padding: 10px 16px;
    display: flex; align-items: center; justify-content: space-between; font-size: 14px; }
  .top-bar a { color: #90caf9; text-decoration: none; font-size: 14px; }
  #pages { padding-top: 50px; display: flex; flex-direction: column; align-items: center;
           gap: 8px; padding-bottom: 20px; }
  canvas { display: block; width: 100%; max-width: 800px; height: auto; }
  .loading { color: #fff; text-align: center; padding-top: 80px; font-size: 16px; }
</style>
</head>
<body>
<div class="top-bar">
  <a href="/">&larr; 목록</a>
  <span id="info"></span>
</div>
<div id="pages"><div class="loading">로딩 중...</div></div>
<script>
  pdfjsLib.GlobalWorkerOptions.workerSrc =
    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
  const params = new URLSearchParams(location.search);
  const file = params.get('file');
  document.getElementById('info').textContent = decodeURIComponent(file || '').split('/').pop();
  if (file) {
    pdfjsLib.getDocument(file).promise.then(pdf => {
      const container = document.getElementById('pages');
      container.innerHTML = '';
      for (let i = 1; i <= pdf.numPages; i++) {
        pdf.getPage(i).then(page => {
          const vp = page.getViewport({ scale: 3 });
          const canvas = document.createElement('canvas');
          canvas.width = vp.width;
          canvas.height = vp.height;
          container.appendChild(canvas);
          page.render({ canvasContext: canvas.getContext('2d'), viewport: vp });
        });
      }
    }).catch(e => {
      document.getElementById('pages').innerHTML =
        '<div class="loading">PDF 로드 실패: ' + e.message + '</div>';
    });
  }
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(
        prog="mosaiq",
        description="MosaiqJob - 취업 문서 자동화 파이프라인",
    )
    parser.add_argument(
        "jd",
        nargs="?",
        help="JD 파일 경로 (없으면 stdin에서 읽음)",
    )
    parser.add_argument(
        "-q", "--questions",
        help="자소서 문항 파일 경로",
    )
    parser.add_argument(
        "-o", "--output",
        help="출력 디렉토리 (기본: ./output)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="전략 승인 없이 자동 진행",
    )
    parser.add_argument(
        "--v2",
        action="store_true",
        help="V2 파이프라인 (후보자 중심 + 병렬 작성 + 설득력 코칭)",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="output 폴더를 브라우저에서 볼 수 있도록 HTTP 서버 실행",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="서버 포트 (기본: 8080)",
    )
    args = parser.parse_args()

    global OUTPUT_ROOT
    if args.output:
        OUTPUT_ROOT = Path(args.output)

    # --serve 모드: 파이프라인 없이 서버만 실행
    if args.serve:
        serve_output(port=args.port, output_path=OUTPUT_ROOT)
        return

    # JD 텍스트 읽기
    if args.jd:
        jd_path = Path(args.jd).resolve()
        if not jd_path.exists():
            console.print(f"[red]파일을 찾을 수 없습니다: {jd_path}[/red]")
            sys.exit(1)
        if not jd_path.is_file():
            console.print(f"[red]파일이 아닙니다: {jd_path}[/red]")
            sys.exit(1)
        text = jd_path.read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        console.print("[yellow]JD 텍스트를 붙여넣으세요 (Ctrl+D로 입력 종료):[/yellow]")
        text = sys.stdin.read()

    if not text.strip():
        console.print("[red]JD 텍스트가 비어 있습니다.[/red]")
        sys.exit(1)

    # 자소서 문항 읽기
    jd_text, inline_questions = parse_input(text)
    if args.questions:
        q_path = Path(args.questions)
        if not q_path.exists():
            console.print(f"[red]문항 파일을 찾을 수 없습니다: {q_path}[/red]")
            sys.exit(1)
        questions = [q.strip() for q in q_path.read_text(encoding="utf-8").split("\n") if q.strip()]
    else:
        questions = inline_questions

    if args.v2:
        console.print(Panel("MosaiqJob V2 - 후보자 중심 취업 문서 자동화", style="bold magenta"))
    else:
        console.print(Panel("MosaiqJob - 취업 문서 자동화 파이프라인", style="bold blue"))
    console.print()

    if args.v2:
        run_pipeline_v2(jd_text, questions, auto=args.auto)
    else:
        run_pipeline(jd_text, questions, auto=args.auto)


if __name__ == "__main__":
    main()
