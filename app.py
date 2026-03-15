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
from renderer.pdf import html_to_pdf

load_dotenv()

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


def _extract_company_name(jd_analysis: str) -> str:
    """JD 분석 결과에서 기업명을 재귀 탐색한다."""
    text = re.sub(r"```(?:json)?\s*\n?", "", jd_analysis)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)

    def _find(obj):
        if isinstance(obj, dict):
            for key in ("company_name", "company"):
                val = obj.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
            for v in obj.values():
                found = _find(v)
                if found:
                    return found
        return None

    try:
        data = json.loads(text) if text.strip().startswith("{") else {}
        name = _find(data)
        if name:
            return re.sub(r'[\\/*?:"<>|]', "_", name)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return "unknown"


def _make_output_dir(company_name: str) -> Path:
    """output/기업명_timestamp 디렉토리를 생성한다."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_ROOT / f"{company_name}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def run_pipeline(jd_text: str, questions: list[str], auto: bool = False) -> None:
    """파이프라인 전체를 실행한다."""

    # Step 1: JD + 기업 분석
    with console.status("[bold cyan]1/7 JD + 기업 분석 중..."):
        jd_analysis = analyst.analyze_jd(jd_text)
    console.print("[green]1/7[/green] JD + 기업 분석 완료")

    # 기업명 기반 출력 디렉토리 생성
    company_name = _extract_company_name(jd_analysis)
    output_dir = _make_output_dir(company_name)

    keywords = extract_keywords(jd_analysis, jd_text)

    # Step 2: 소스 수집
    with console.status("[bold cyan]2/7 소스 수집 중 (Notion/GitHub)..."):
        source_data = source.analyze_source(keywords)
    console.print("[green]2/7[/green] 소스 수집 완료")

    # Step 3: 전략 수립
    with console.status("[bold cyan]3/7 전략 수립 중..."):
        strategy_result = strategist.strategize(jd_analysis, source_data)
    console.print("[green]3/7[/green] 전략 수립 완료")

    # Step 4: 사용자 승인
    console.print()
    console.print(Panel(strategy_result, title="전략 수립 결과", border_style="yellow"))
    if not auto:
        answer = input("\n진행할까요? (Y/n): ").strip().lower()
        if answer in ("n", "no", "아니", "ㄴㄴ"):
            console.print("[red]취소됨[/red]")
            return
    console.print()

    # Step 5: 이력서 생성
    with console.status("[bold cyan]4/7 이력서 생성 중..."):
        resume_html = writer.write_resume(strategy_result, source_data, jd_analysis)
    (output_dir / "이력서.html").write_text(resume_html, encoding="utf-8")
    html_to_pdf(resume_html, output_dir / "이력서.pdf")
    console.print("[green]4/7[/green] 이력서 생성 완료")

    # Step 6: 포트폴리오 생성
    with console.status("[bold cyan]5/7 포트폴리오 생성 중..."):
        portfolio_html = writer.write_portfolio(strategy_result, source_data, resume_html)
    (output_dir / "포트폴리오.html").write_text(portfolio_html, encoding="utf-8")
    html_to_pdf(portfolio_html, output_dir / "포트폴리오.pdf")
    console.print("[green]5/7[/green] 포트폴리오 생성 완료")

    # Step 7: 자소서 생성
    with console.status("[bold cyan]6/7 자소서 생성 중..."):
        cover_html = writer.write_cover(
            strategy_result, jd_analysis, resume_html, portfolio_html, questions
        )
    (output_dir / "자소서.html").write_text(cover_html, encoding="utf-8")
    html_to_pdf(cover_html, output_dir / "자소서.pdf")
    console.print("[green]6/7[/green] 자소서 생성 완료")

    # Step 8: 크로스체크
    with console.status("[bold cyan]7/7 크로스체크 중..."):
        review_result = reviewer.review(
            jd_analysis, resume_html, portfolio_html, cover_html, questions
        )
    console.print("[green]7/7[/green] 크로스체크 완료")

    # 결과 표시
    console.print()
    console.print(Panel(review_result, title="크로스체크 결과", border_style="cyan"))
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
    args = parser.parse_args()

    # JD 텍스트 읽기
    if args.jd:
        jd_path = Path(args.jd)
        if not jd_path.exists():
            console.print(f"[red]파일을 찾을 수 없습니다: {jd_path}[/red]")
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

    # 출력 디렉토리 (-o 지정 시 자동 생성 대신 해당 경로 사용)
    global OUTPUT_ROOT
    if args.output:
        OUTPUT_ROOT = Path(args.output)

    console.print(Panel("MosaiqJob - 취업 문서 자동화 파이프라인", style="bold blue"))
    console.print()

    run_pipeline(jd_text, questions, auto=args.auto)


if __name__ == "__main__":
    main()
