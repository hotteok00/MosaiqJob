"""Jinja2 템플릿 더미 데이터 렌더링 테스트."""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from renderer.pdf import html_to_pdf

TEMPLATES_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = Path(__file__).parent / "output" / "template_test"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

# ── 공통 person ──
person = {
    "name": "홍길동",
    "title": "Robot Software Engineer · ROS2 / MoveIt2 / SLAM",
    "phone": "010-1234-5678",
    "email": "gildong@example.com",
    "github": "github.com/example-user",
    "location": "서울특별시 강남구",
    "company": "VisionSpace · Robot AI Developer (재직 중)",
}

# ── 이력서 ──
resume_data = {
    "person": person,
    "summary": (
        "ROS2·MoveIt2·SLAM을 부트캠프(845시간)와 현직에서 직접 구현한 주니어 로봇 SW 엔지니어입니다.<br>"
        "음성→LLM→로봇 동작 엔드투엔드 파이프라인 설계와 Octomap 기반 실시간 장애물 회피 경로 생성을 주도했으며,<br>"
        "현재 VisionSpace에서 AGV·코봇 ROS2 포팅과 Unreal Engine 디지털 트윈 연동을 담당하고 있습니다."
    ),
    "careers": [
        {
            "company": "VisionSpace",
            "position": "Robot AI Developer",
            "period": "2025.10 ~ 현재 (재직 중)",
            "bullets": [
                "Elephant Robotics MyAGV·MyCobot의 ROS2 Foxy → Jazzy 포팅",
                "Unreal Engine 디지털 트윈 환경과 ROS2(MoveIt2, Gazebo) 연동",
                "Robot Learning Platform 개발 참여",
            ],
        },
        {
            "company": "AITRON",
            "position": "Front-End Developer (외주)",
            "period": "2023.08 ~ 2023.10",
            "bullets": ["식당 사업주용 내부 백오피스 개발"],
        },
    ],
    "projects": [
        {
            "name": "MEDICREW",
            "subtitle": "중앙공급실 자동화 — 음성 명령 기반 협동 로봇",
            "period": "2025.06 · 팀 4명",
            "team": "4인 팀",
            "role_desc": "음성→LLM→MoveIt2 엔드투엔드 파이프라인 설계. Octomap 실시간 장애물 회피 구현.",
            "tags": ["ROS2 Humble", "MoveIt2", "Octomap", "YOLO", "LangChain"],
            "is_personal": False,
            "github_url": "",
        },
        {
            "name": "CODA",
            "subtitle": "교통사고 현장 보존 자율주행 로봇",
            "period": "2025.05 · 팀 7명",
            "team": "7인 팀",
            "role_desc": "메인 서버 시스템 구조 설계. AutoSLAM + Nav2 자율주행 파이프라인 연결.",
            "tags": ["ROS2 Humble", "AutoSLAM", "Nav2", "YOLO", "TF"],
            "is_personal": False,
            "github_url": "",
        },
        {
            "name": "robot_control_bridge",
            "subtitle": "DSR MoveIt–Gazebo 연동 실습",
            "period": "개인 프로젝트",
            "team": "",
            "role_desc": "MoveIt 플래너 출력을 Gazebo 제어 토픽에 브리지하는 노드 작성.",
            "tags": ["ROS2", "MoveIt", "Gazebo", "Python"],
            "is_personal": True,
            "github_url": "https://github.com/example-user/robot_control_bridge",
        },
    ],
    "skills": {
        "로보틱스": "ROS2 (Humble / Jazzy), MoveIt2, SLAM, Nav2, TF, Octomap, Gazebo",
        "언어": "Python, C++",
        "AI / 비전": "YOLO, OpenCV, LangChain, PyTorch",
        "하드웨어": "LiDAR, RGB-D Camera, Jetson Orin Nano",
    },
    "education": [
        {"school": "OO대학교 컴퓨터공학 학사", "detail": "GPA 3.9 / 4.5", "period": "2019.03 ~ 2025.02"},
    ],
    "certifications": [
        {"name": "정보처리기사", "date": "2024.06"},
        {"name": "SQLD", "date": "2024.12"},
        {"name": "OPIc IM2", "date": "2024.09"},
    ],
    "activities": [
        {"label": "Doosan Rokey Boot Camp 3기", "desc": "로봇 SW 부트캠프 845시간 수료", "period": "2025.01 ~ 2025.07"},
        {"label": "RoCo Challenge @ AAAI 2026", "desc": "국제 로봇 경진대회 참가", "period": "2025.11 ~ 2026.01"},
        {"label": "학생우수논문상", "desc": "KIICE 춘계학술대회", "period": "2024.05"},
    ],
}

# ── 포트폴리오 ──
portfolio_data = {
    "person": person,
    "summary": (
        "로봇을 움직이기 위해 선택한 설계 결정들 — Octomap으로 정적 경로의 한계를 넘고, "
        "중앙 서버 아키텍처로 다노드 타이밍 문제를 해결하고, LLM 파이프라인으로 음성에서 "
        "로봇 동작까지 엔드투엔드로 연결했습니다."
    ),
    "competencies": [
        {"number": "01", "keyword": "Motion Planning", "description": "MoveIt2 + Octomap 연동, 실시간 충돌 회피 경로 생성."},
        {"number": "02", "keyword": "SLAM · Navigation", "description": "AutoSLAM 맵 생성, Nav2 파라미터 튜닝, 동적 장애물 회피."},
        {"number": "03", "keyword": "System Architecture", "description": "ROS2 노드 인터페이스 설계, 중앙 서버 상태 관리."},
    ],
    "project_table": [
        {"name": "MEDICREW", "subtitle": "협동로봇 작업 어시스턴트", "description": "음성→LLM→MoveIt2 엔드투엔드", "tags": ["ROS2", "MoveIt2", "Octomap"], "period": "2025.06", "is_highlighted": True},
        {"name": "CODA", "subtitle": "자율주행 사고현장 보존", "description": "AutoSLAM + Nav2 기반 자동화", "tags": ["ROS2", "SLAM", "Nav2"], "period": "2025.05", "is_highlighted": True},
        {"name": "ROADY", "subtitle": "도로 낙하물 수거 로봇", "description": "ArUco + MoveIt 매니퓰레이터", "tags": ["ROS2", "MoveIt"], "period": "2025.07", "is_highlighted": False},
    ],
    "highlights": [
        {
            "order": 1,
            "name": "MEDICREW",
            "subtitle": "AI 기반 협동 로봇 작업 어시스턴트",
            "period": "2025.06.09 – 06.20 (12일)",
            "team": "4인 팀",
            "role": "ROS2 제어 구조 설계 · 모션 플래닝 · Octomap 연동",
            "overview": "병원 중앙공급실에서 협동로봇이 물품을 자동 수거하는 시스템.",
            "situation": ["협동로봇이 고정 경로만 사용 시 동적 장애물에 충돌 위험", "음성 명령을 로봇 동작으로 변환하는 인터페이스 필요"],
            "decision": ["정적 경로 대신 Octomap 실시간 환경 맵 선택", "LangChain 기반 의도 파싱으로 자연어 명령 처리"],
            "action": ["ROS2 노드 구조 설계: speech→llm→action→moveit", "Octomap Server를 MoveIt2 Planning Scene에 연동"],
            "result": ["음성 명령 → 물품 수거 엔드투엔드 동작 확인", "장애물 배치 시 경로 재계획으로 충돌 없이 우회"],
            "contribution_pct": 75,
            "contribution_desc": "ROS2 구조 설계 · Octomap 연동 · 모션 플래닝 담당",
            "tags": ["ROS2 Humble", "MoveIt2", "Octomap", "YOLO", "LangChain", "MongoDB"],
            "github_url": "https://github.com/example/collaboration-2",
        },
        {
            "order": 2,
            "name": "CODA",
            "subtitle": "SLAM 기반 교통사고 현장 보존 로봇",
            "period": "2025.05.16 – 05.22 (7일)",
            "team": "7인 팀",
            "role": "메인 서버 시스템 설계 · 개별 노드 구현",
            "overview": "교통사고 현장에 자율주행 로봇이 자동 촬영, 증거 수집, 보고서 생성.",
            "situation": ["7개 노드가 독립 실행 시 타이밍 충돌로 데이터 정합성 문제", "AutoSLAM 맵 품질이 자율 이동 성공률 직결"],
            "decision": ["분산 노드 대신 중앙 서버 상태 머신 아키텍처 선택", "AutoSLAM 파라미터 직접 튜닝"],
            "action": ["6단계 상태 머신 설계: IDLE→DETECT→NAVIGATE→CAPTURE→CONTROL→REPORT", "Nav2 DWB 플래너 로컬 코스트맵 파라미터 튜닝"],
            "result": ["사고 감지→이동→촬영→리포트 전 과정 자동 실행 확인", "중앙 서버로 7개 노드 실행 순서 충돌 없이 안정 동작"],
            "contribution_pct": 40,
            "contribution_desc": "메인 서버 아키텍처 + 노드 인터페이스 설계 담당 (7인 팀)",
            "tags": ["ROS2 Humble", "AutoSLAM", "Nav2", "TF", "LiDAR", "YOLO"],
            "github_url": "",
        },
    ],
    "other_projects": [
        {"name": "ROADY", "subtitle": "도로 낙하물 자동 수거 로봇", "description": "ArUco 마커 인식 + MoveIt Pick&Place + FSM 상태 관리", "tags": ["ROS2", "MoveIt", "OpenCV"], "period": "2025.07", "team": "4인"},
        {"name": "DrawBot", "subtitle": "로봇팔 드로잉 자동화", "description": "Force Control 기반 정밀 접촉 감지 드로잉", "tags": ["ROS2", "Force Control", "DRL"], "period": "2025.05–06", "team": "4인"},
    ],
    "additional": [
        {
            "section": "현재 재직 · 교육",
            "entries": [
                {"title": "VisionSpace", "detail": "Robot AI Developer", "period": "2025.10 – 현재"},
                {"title": "Doosan Rokey Boot Camp 3기", "detail": "로봇 SW 845시간", "period": "2025.01 – 07"},
            ],
        },
        {
            "section": "자격증 · 수상",
            "entries": [
                {"title": "정보처리기사 · SQLD", "detail": "", "period": "2024"},
                {"title": "학생우수논문상", "detail": "KIICE", "period": "2024.05"},
            ],
        },
    ],
}

# ── 자소서 ──
cover_data = {
    "person": person,
    "target": {"company": "삼성전자 미래로봇추진단", "position": "로봇 소프트웨어 엔지니어"},
    "doc_label": "COVER LETTER · 자기소개서",
    "sections": [
        {
            "label": "자유형",
            "content": (
                "<p>삼성전자 미래로봇추진단이 눈에 들어온 건 기업 규모 때문이 아닙니다. "
                "레인보우로보틱스 인수 직후 조선소 파일럿 테스트를 진행하고, 2028년 상용화 로드맵을 공개적으로 "
                "제시하는 조직은 지금이 '아키텍처를 결정하는 단계'라는 뜻입니다.</p>"
                "<p>MEDICREW 프로젝트에서 가장 오래 붙잡고 있던 문제는 좌표 불일치였습니다. "
                "YOLO가 물체를 정확히 탐지해도 로봇이 허공을 집는 상황이 반복됐습니다. "
                "Octomap을 선택한 건 기술 트렌드 때문이 아니었습니다. 3차원 매니퓰레이터 운동 공간을 "
                "2D 격자 맵으로 커버하는 것이 물리적으로 불가능했기 때문입니다.</p>"
                "<p>C++과 시뮬레이션 환경은 아직 부족합니다. 솔직하게 인정합니다. "
                "그럼에도 지금 지원하는 이유는, 신설 조직에서 소프트웨어 스택을 빠르게 쌓아야 하는 국면에 "
                "ROS2 파이프라인을 실하드웨어에서 직접 구현하고 디버깅한 경험이 필요하다고 판단했기 때문입니다.</p>"
            ),
        },
    ],
    "date": "2026. 03",
}

# ── 렌더링 ──
for name, template_file, data in [
    ("이력서", "resume.html", resume_data),
    ("포트폴리오", "portfolio.html", portfolio_data),
    ("자소서", "cover_letter.html", cover_data),
]:
    try:
        template = env.get_template(template_file)
        html = template.render(**data)
        html_path = OUTPUT_DIR / f"{name}.html"
        pdf_path = OUTPUT_DIR / f"{name}.pdf"
        html_path.write_text(html, encoding="utf-8")
        html_to_pdf(html, pdf_path)
        print(f"✓ {name} 생성 완료 → {pdf_path}")
    except Exception as e:
        print(f"✗ {name} 실패: {e}")
