# MosaiqJob

채용공고(JD)를 입력하면 **이력서, 포트폴리오, 자기소개서** PDF 3종을 자동 생성하는 CLI 도구.

Claude Code CLI + MCP(Notion/GitHub)를 활용해 소스 수집부터 문서 생성, 교차 검증까지 전 과정을 자동화합니다.

## 파이프라인

```
JD 입력 → ① JD분석 → ② 소스수집(MCP) → ③ 전략수립 → ④ 사용자승인
         → ⑤ 이력서 → ⑥ 포트폴리오 → ⑦ 자소서 → ⑧ 교차검증 → ⑨ PDF출력
```

## 사용법

```bash
# 설치
pip install weasyprint jinja2 pydantic python-dotenv rich

# JD 파일로 실행
python3 app.py jd.txt

# 자소서 문항 포함
python3 app.py jd.txt -q questions.txt

# 승인 없이 자동 진행
python3 app.py jd.txt --auto

# 출력 디렉토리 지정
python3 app.py jd.txt -o ~/Documents/지원서/
```

JD 파일 안에서 `---` 구분선 뒤에 자소서 문항을 넣을 수도 있습니다.

## 출력 구조

```
output/
└── 삼성전자_20260315_174458/
    ├── 이력서.html
    ├── 이력서.pdf
    ├── 포트폴리오.html
    ├── 포트폴리오.pdf
    ├── 자소서.html
    └── 자소서.pdf
```

기업명과 타임스탬프로 자동 분류됩니다.

## 사전 요구사항

- **Claude Code CLI** 설치 + 구독 로그인 (`claude --version`으로 확인)
- **MCP 서버 등록** (선택): `claude mcp add`로 Notion/GitHub 연결
- **WeasyPrint** 시스템 의존성: [설치 가이드](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html)

### 환경변수 (`.env`)

```bash
# MCP - 필요한 것만 설정
NOTION_API_KEY=ntn_...
GITHUB_TOKEN=ghp_...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

LLM API 키는 불필요합니다. Claude Code 구독으로 동작합니다.

## 기술 스택

| 구분 | 기술 |
|------|------|
| LLM | Claude Code CLI (`claude -p`, 구독 기반) |
| 외부 연동 | MCP (Notion, GitHub, Google Drive) |
| PDF 렌더링 | WeasyPrint + Jinja2 |
| CLI | argparse + rich |
| 데이터 모델 | Pydantic v2 |

## 프로젝트 구조

```
MosaiqJob/
├── app.py                  # CLI 엔트리포인트
├── agents/
│   ├── llm.py              # Claude CLI 래퍼 (ask_claude, extract_json)
│   ├── analyst.py           # JD + 기업 분석
│   ├── source.py            # MCP 소스 수집
│   ├── strategist.py        # 전략 수립
│   ├── writer.py            # 이력서/포트폴리오/자소서 HTML 생성
│   └── reviewer.py          # 교차 검증
├── prompts/                 # 에이전트별 프롬프트 템플릿
├── models/schemas.py        # Pydantic 데이터 모델
├── renderer/pdf.py          # WeasyPrint PDF 렌더링
├── output_example/          # 예시 출력물 (HTML + PDF)
└── tests/                   # pytest (101 tests)
```

## 서술 원칙

- 성과 수치가 아닌 **의사결정 근거** 중심 서술
- 솔직 담백, 과장 없이, AI스럽지 않은 진솔한 톤
- **"이런 상황에서, 이런 이유로, 이렇게 했다, 그래서 이런 결과가 나왔다"**
- 이력서(팩트) / 포트폴리오(기술 깊이) / 자소서(동기·맥락) — 세 문서가 각각 다른 역할

## 예시 출력물

[`output_example/`](output_example/) 디렉토리에서 확인할 수 있습니다.

## 테스트

```bash
python3 -m pytest tests/ -v
```
