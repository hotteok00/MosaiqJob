# MCP 서버 인증/인가 설정 가이드

## 1. 개요

MosaiqJob은 Claude Code CLI와 연동되는 **커스텀 MCP(Model Context Protocol) 서버**를 사용하여 외부 서비스의 데이터를 가져온다. 모든 MCP 서버는 `mcp_servers/base.py`의 `MCPServer` 클래스를 상속하며, **stdin/stdout JSON-RPC 2.0** 프로토콜로 Claude Code와 통신한다.

### 서버 목록

| 서버 이름 | 파일 | 역할 |
|-----------|------|------|
| `notion` | `mcp_servers/notion_server.py` | Notion 페이지/데이터베이스 검색 및 읽기 |
| `github` | `mcp_servers/github_server.py` | GitHub 저장소/코드 검색, 파일 조회, 커밋 목록 |
| `google-drive` | `mcp_servers/gdrive_server.py` | Google Drive 파일 검색 및 읽기 |
| `onedrive` | `mcp_servers/onedrive_server.py` | OneDrive 파일 검색, 읽기, 목록 조회 |

### 인증 구조

각 서버는 시작 시 `.env` 파일의 환경변수에서 인증 정보를 읽어온다. Notion과 GitHub는 API 키/토큰 방식이고, Google Drive와 OneDrive는 OAuth 2.0 기반의 refresh token 방식을 사용한다.

```
.env (환경변수)
  ├── NOTION_API_KEY          → Notion 서버가 직접 사용
  ├── GITHUB_TOKEN            → GitHub 서버가 직접 사용
  ├── GOOGLE_CLIENT_ID        ┐
  ├── GOOGLE_CLIENT_SECRET    ├→ Google Drive 서버가 Credentials 객체 생성
  ├── GOOGLE_REFRESH_TOKEN    ┘
  ├── MICROSOFT_CLIENT_ID     ┐
  └── MICROSOFT_REFRESH_TOKEN ┘→ OneDrive 서버가 access_token 갱신
```

---

## 2. 사전 요구사항

### 시스템 환경

- **Python 3.10+**
- **Claude Code CLI** 설치 및 구독 (LLM 호출에 사용)
- **pip** 패키지 관리자

### Python 패키지

```bash
pip install requests google-api-python-client google-auth python-dotenv
```

| 패키지 | 용도 |
|--------|------|
| `requests` | Notion, GitHub, OneDrive API HTTP 호출 |
| `google-api-python-client` | Google Drive API 서비스 객체 빌드 |
| `google-auth` | Google OAuth 2.0 인증 처리 |
| `python-dotenv` | `.env` 파일 로드 (gdrive_auth.py에서 사용) |

### 프로젝트 구조

```
MosaiqJob/
├── .env                              # 인증 정보 (gitignore 대상)
├── gdrive_auth.py                    # Google Drive OAuth 인증 스크립트
└── mcp_servers/
    ├── base.py                       # MCP 서버 공통 프레임워크
    ├── notion_server.py
    ├── github_server.py
    ├── gdrive_server.py
    └── onedrive_server.py
```

---

## 3. 각 MCP 서버 인증 가이드

### 3.1 Notion

Notion은 **Internal Integration** 방식으로 API 키를 발급받아 사용한다.

#### 1단계: Integration 생성

1. [Notion My Integrations](https://www.notion.so/my-integrations) 페이지에 접속
2. **"새 API 통합"** 클릭
3. 이름 입력 (예: `MosaiqJob`)
4. 연결할 워크스페이스 선택
5. **유형**: Internal Integration
6. **기능**: "콘텐츠 읽기" 권한 활성화
7. **제출** 클릭

#### 2단계: API 키 복사

생성 완료 후 표시되는 **Internal Integration Secret**을 복사한다. `ntn_` 또는 `secret_`으로 시작하는 문자열이다.

#### 3단계: 워크스페이스에 Integration 연결

Notion에서 MosaiqJob이 접근해야 할 페이지/데이터베이스에 가서:

1. 페이지 우측 상단 **"..."** 메뉴 클릭
2. **"연결 추가"** 선택
3. 방금 만든 Integration(`MosaiqJob`) 선택

> 주의: Integration을 연결하지 않으면 해당 페이지에 API로 접근할 수 없다.

#### 4단계: `.env` 설정

```bash
NOTION_API_KEY=ntn_여기에_발급받은_키를_붙여넣기
```

#### 5단계: Claude Code에 MCP 서버 등록

```bash
claude mcp add notion \
  -e NOTION_API_KEY \
  -- python3 -u /절대경로/MosaiqJob/mcp_servers/notion_server.py
```

- `-e NOTION_API_KEY`: `.env`의 환경변수를 서버 프로세스에 전달
- `-u`: Python stdout 버퍼링을 비활성화 (MCP 통신에 필수)

---

### 3.2 GitHub

GitHub는 **Personal Access Token (PAT)** 으로 인증한다.

#### 1단계: Personal Access Token 발급

1. [GitHub Token 설정](https://github.com/settings/tokens) 페이지 접속
2. **"Generate new token (classic)"** 클릭
3. Note에 용도 입력 (예: `MosaiqJob`)
4. 필요한 scope 선택:
   - `repo` : 저장소 전체 접근 (private 포함)
   - `read:user` : 사용자 프로필 읽기
5. **"Generate token"** 클릭
6. 표시된 토큰(`ghp_`으로 시작)을 즉시 복사

> 주의: 토큰은 생성 직후에만 표시된다. 분실 시 새로 발급해야 한다.

#### 2단계: `.env` 설정

```bash
GITHUB_TOKEN=ghp_여기에_발급받은_토큰을_붙여넣기
```

#### 3단계: Claude Code에 MCP 서버 등록

```bash
claude mcp add github \
  -e GITHUB_TOKEN \
  -- python3 -u /절대경로/MosaiqJob/mcp_servers/github_server.py
```

---

### 3.3 Google Drive

Google Drive는 **OAuth 2.0** 인증을 사용한다. 최초 1회 브라우저 인증이 필요하며, 이후에는 refresh token으로 자동 갱신된다.

#### 1단계: Google Cloud Console 프로젝트 생성

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 상단 프로젝트 선택 드롭다운에서 **"새 프로젝트"** 클릭
3. 프로젝트 이름 입력 (예: `MosaiqJob`) 후 생성

#### 2단계: Google Drive API 활성화

1. 좌측 메뉴 **"API 및 서비스"** > **"라이브러리"**
2. "Google Drive API" 검색 후 **"사용"** 클릭

#### 3단계: OAuth 동의 화면 설정

1. **"API 및 서비스"** > **"OAuth 동의 화면"**
2. User Type: **외부** 선택
3. 앱 이름, 사용자 지원 이메일, 개발자 연락처 이메일 입력
4. 범위 추가: `https://www.googleapis.com/auth/drive.readonly`
5. **테스트 사용자 추가**: 본인의 Google 계정 이메일 등록

> 주의: 앱이 "테스트" 상태이므로, 테스트 사용자로 등록된 계정만 인증 가능하다.

#### 4단계: OAuth 클라이언트 ID 생성

1. **"API 및 서비스"** > **"사용자 인증 정보"**
2. **"사용자 인증 정보 만들기"** > **"OAuth 클라이언트 ID"**
3. 애플리케이션 유형: **데스크톱 앱**
4. 이름 입력 후 **"만들기"**
5. **클라이언트 ID**와 **클라이언트 보안 비밀번호** 복사

#### 5단계: `.env`에 클라이언트 정보 설정

```bash
GOOGLE_CLIENT_ID=여기에_클라이언트_ID
GOOGLE_CLIENT_SECRET=여기에_클라이언트_시크릿
```

#### 6단계: Refresh Token 발급

프로젝트 루트에서 `gdrive_auth.py`를 실행한다:

```bash
python3 gdrive_auth.py
```

실행하면:
1. 브라우저가 자동으로 열리며 Google 로그인 페이지가 표시됨
2. 테스트 사용자로 등록한 계정으로 로그인
3. "이 앱은 확인되지 않았습니다" 경고가 뜨면 **"고급"** > **"(앱 이름)(으)로 이동"** 클릭
4. Drive 읽기 권한 허용
5. "인증 성공!" 메시지가 표시되면 브라우저 탭을 닫아도 됨
6. 터미널에 `GOOGLE_REFRESH_TOKEN=...` 값이 출력됨
7. `.env` 파일에 자동으로 추가됨

> 스크립트는 `localhost:8080`에서 OAuth 콜백을 수신한다. 해당 포트가 사용 중이면 먼저 해제해야 한다.

#### 7단계: Claude Code에 MCP 서버 등록

```bash
claude mcp add google-drive \
  -e GOOGLE_CLIENT_ID \
  -e GOOGLE_CLIENT_SECRET \
  -e GOOGLE_REFRESH_TOKEN \
  -- python3 -u /절대경로/MosaiqJob/mcp_servers/gdrive_server.py
```

---

### 3.4 OneDrive

OneDrive는 **Microsoft Graph API**를 사용하며, **Device Code Flow**로 인증한다. 브라우저가 없는 환경에서도 인증이 가능하다.

#### 1단계: Azure Portal에서 앱 등록

1. [Azure Portal - 앱 등록](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade) 접속
2. **"새 등록"** 클릭
3. 설정:
   - 이름: `MosaiqJob`
   - 지원되는 계정 유형: **모든 조직 디렉터리의 계정 및 개인 Microsoft 계정**
   - 리디렉션 URI: 비워둠
4. **"등록"** 클릭
5. **애플리케이션(클라이언트) ID** 복사

#### 2단계: 퍼블릭 클라이언트 흐름 허용

1. 등록한 앱의 **"인증"** 메뉴 이동
2. 하단 **"고급 설정"** 섹션에서
3. **"퍼블릭 클라이언트 흐름 허용"** → **"예"** 선택
4. **"저장"**

#### 3단계: API 권한 설정

1. **"API 사용 권한"** 메뉴 이동
2. **"권한 추가"** > **"Microsoft Graph"** > **"위임된 권한"**
3. `Files.Read.All` 검색 후 체크
4. `offline_access` 검색 후 체크 (refresh token 발급에 필요)
5. **"권한 추가"** 클릭

#### 4단계: Device Code Flow로 토큰 발급

아래 Python 스크립트를 실행하여 refresh token을 발급받는다:

```python
"""OneDrive Device Code Flow 인증 스크립트."""
import requests
import time

CLIENT_ID = "여기에_애플리케이션_클라이언트_ID"
SCOPE = "Files.Read.All offline_access"

# 1. Device code 요청
resp = requests.post(
    "https://login.microsoftonline.com/common/oauth2/v2.0/devicecode",
    data={"client_id": CLIENT_ID, "scope": SCOPE},
)
data = resp.json()

print(f"\n아래 URL에 접속하여 코드를 입력하세요:")
print(f"  URL:  {data['verification_uri']}")
print(f"  코드: {data['user_code']}\n")

# 2. 사용자 인증 대기 (폴링)
interval = data.get("interval", 5)
device_code = data["device_code"]

while True:
    time.sleep(interval)
    token_resp = requests.post(
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
        },
    )
    token_data = token_resp.json()

    if "refresh_token" in token_data:
        print("인증 성공!")
        print(f"\nMICROSOFT_REFRESH_TOKEN={token_data['refresh_token']}")
        break
    elif token_data.get("error") == "authorization_pending":
        print("인증 대기 중...")
        continue
    else:
        print(f"오류: {token_data.get('error_description', token_data)}")
        break
```

실행 흐름:
1. 스크립트가 표시하는 URL(`https://microsoft.com/devicelogin`)에 접속
2. 화면에 표시된 코드를 입력
3. Microsoft 계정으로 로그인 및 권한 승인
4. 터미널에 `MICROSOFT_REFRESH_TOKEN=...` 값이 출력됨

#### 5단계: `.env` 설정

```bash
MICROSOFT_CLIENT_ID=여기에_애플리케이션_클라이언트_ID
MICROSOFT_REFRESH_TOKEN=여기에_발급받은_리프레시_토큰
```

#### 6단계: Claude Code에 MCP 서버 등록

```bash
claude mcp add onedrive \
  -e MICROSOFT_CLIENT_ID \
  -e MICROSOFT_REFRESH_TOKEN \
  -- python3 -u /절대경로/MosaiqJob/mcp_servers/onedrive_server.py
```

---

## 4. 전체 MCP 등록 스크립트

4개 서버를 한번에 등록하는 쉘 스크립트이다. 프로젝트 루트 경로를 수정하여 사용한다.

```bash
#!/bin/bash
# MosaiqJob MCP 서버 일괄 등록 스크립트
# 사용법: bash register_mcp.sh

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== MosaiqJob MCP 서버 등록 ==="
echo "프로젝트 경로: $PROJECT_DIR"
echo ""

# .env 파일 존재 확인
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "오류: .env 파일이 없습니다. .env 파일을 먼저 생성하세요."
    exit 1
fi

# Notion
echo "[1/4] Notion MCP 서버 등록..."
claude mcp add notion \
  -e NOTION_API_KEY \
  -- python3 -u "$PROJECT_DIR/mcp_servers/notion_server.py"

# GitHub
echo "[2/4] GitHub MCP 서버 등록..."
claude mcp add github \
  -e GITHUB_TOKEN \
  -- python3 -u "$PROJECT_DIR/mcp_servers/github_server.py"

# Google Drive
echo "[3/4] Google Drive MCP 서버 등록..."
claude mcp add google-drive \
  -e GOOGLE_CLIENT_ID \
  -e GOOGLE_CLIENT_SECRET \
  -e GOOGLE_REFRESH_TOKEN \
  -- python3 -u "$PROJECT_DIR/mcp_servers/gdrive_server.py"

# OneDrive
echo "[4/4] OneDrive MCP 서버 등록..."
claude mcp add onedrive \
  -e MICROSOFT_CLIENT_ID \
  -e MICROSOFT_REFRESH_TOKEN \
  -- python3 -u "$PROJECT_DIR/mcp_servers/onedrive_server.py"

echo ""
echo "=== 등록 완료! ==="
echo "서버 상태 확인: claude mcp list"
```

---

## 5. 문제 해결

### `python3 -u` 플래그가 필요한 이유

MCP 프로토콜은 stdin/stdout을 통해 JSON-RPC 메시지를 주고받는다. Python은 기본적으로 stdout을 **버퍼링**하기 때문에, `-u` (unbuffered) 플래그 없이 실행하면 응답이 버퍼에 머물러 Claude Code가 메시지를 수신하지 못한다.

```bash
# 잘못된 실행 (버퍼링으로 인해 통신 불가)
python3 mcp_servers/notion_server.py

# 올바른 실행
python3 -u mcp_servers/notion_server.py
```

### 자주 발생하는 에러

| 에러 메시지 | 원인 | 해결 방법 |
|-------------|------|-----------|
| `401 Unauthorized` (Notion) | API 키가 잘못되었거나 만료됨 | `.env`의 `NOTION_API_KEY` 확인 후 재발급 |
| `403 Forbidden` (Notion) | 페이지에 Integration이 연결되지 않음 | Notion 페이지에서 "연결 추가"로 Integration 연결 |
| `401 Bad credentials` (GitHub) | PAT가 만료되었거나 잘못됨 | GitHub에서 토큰 재발급 |
| `GOOGLE_CLIENT_ID` KeyError | 환경변수 미설정 | `.env`에 `GOOGLE_CLIENT_ID` 추가 |
| `invalid_grant` (Google) | Refresh token 만료 또는 무효화 | `gdrive_auth.py` 재실행하여 토큰 재발급 |
| `MICROSOFT_REFRESH_TOKEN 환경변수가 설정되지 않았습니다` | OneDrive 토큰 미설정 | Device Code Flow 스크립트로 토큰 발급 |
| `토큰 갱신 실패 (400)` (OneDrive) | Microsoft refresh token 만료 | Device Code Flow를 다시 실행하여 토큰 재발급 |
| `MCP server not connected` | 서버 프로세스가 시작되지 않음 | `claude mcp list`로 상태 확인 후 재등록 |

### 토큰 갱신 방법

#### Notion / GitHub

- Notion API 키와 GitHub PAT는 만료되지 않는 한 계속 사용 가능하다.
- GitHub PAT는 생성 시 만료 기간을 설정한다. 만료 시 GitHub Settings에서 재발급한다.

#### Google Drive

- Refresh token은 일반적으로 만료되지 않지만, 다음 경우 무효화된다:
  - 사용자가 앱 접근 권한을 취소한 경우
  - 6개월간 사용하지 않은 경우
  - Google Cloud 프로젝트가 "테스트" 상태이고 7일이 경과한 경우
- 무효화 시 `gdrive_auth.py`를 재실행하면 새 토큰이 발급된다.

#### OneDrive

- Microsoft refresh token은 **90일간** 비활성 상태면 만료된다.
- 정상 사용 시에는 토큰 갱신 때마다 새 refresh token이 자동 발급된다.
- OneDrive 서버 코드(`onedrive_server.py`)는 갱신된 refresh token을 메모리에 반영하지만, `.env` 파일에는 자동 저장하지 않는다. 장기간 사용 시 `.env`의 토큰을 수동 갱신하는 것을 권장한다.
- 만료 시 Device Code Flow 스크립트를 다시 실행한다.

### MCP 서버 상태 확인

```bash
# 등록된 서버 목록 및 연결 상태 확인
claude mcp list

# 특정 서버 재등록 (기존 서버를 먼저 제거 후 다시 추가)
claude mcp remove notion
claude mcp add notion -e NOTION_API_KEY -- python3 -u /절대경로/mcp_servers/notion_server.py
```
