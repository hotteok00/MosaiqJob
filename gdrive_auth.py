"""Google Drive OAuth 인증 스크립트. 1회만 실행하면 됩니다."""

import json
import os
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI = "http://localhost:8080"
SCOPE = "https://www.googleapis.com/auth/drive.readonly"

auth_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        auth_code = parse_qs(urlparse(self.path).query).get("code", [""])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("<h1>인증 성공!</h1><p>이 탭을 닫아도 됩니다.</p>".encode())

    def log_message(self, format, *args):
        pass  # 로그 숨김


def main():
    global auth_code

    params = urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    })
    auth_url = f"https://accounts.google.com/o/oauth2/auth?{params}"

    print(f"\n브라우저가 열리지 않으면 아래 URL을 직접 열어주세요:\n\n{auth_url}\n")
    webbrowser.open(auth_url)

    print("Google 로그인 대기 중...")
    HTTPServer(("localhost", 8080), CallbackHandler).handle_request()

    if not auth_code:
        print("인증 코드를 받지 못했습니다.")
        return

    print(f"\n인증 코드 수신 완료!")

    # 코드 → refresh token 교환
    import urllib.request
    data = urlencode({
        "code": auth_code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()

    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    resp = urllib.request.urlopen(req, timeout=30)
    tokens = json.loads(resp.read())

    refresh_token = tokens.get("refresh_token")
    if refresh_token:
        print(f"\nRefresh Token 획득 성공!")
        print(f"GOOGLE_REFRESH_TOKEN={refresh_token}")

        # .env에 추가
        env_path = Path(__file__).parent / ".env"
        env_content = env_path.read_text()
        if "GOOGLE_REFRESH_TOKEN" not in env_content:
            env_path.write_text(env_content + f"\nGOOGLE_REFRESH_TOKEN={refresh_token}\n")
            print(".env에 GOOGLE_REFRESH_TOKEN 추가 완료!")
        print("\n이제 Google Drive MCP를 사용할 수 있습니다.")
    else:
        print("Refresh token을 받지 못했습니다:", tokens)


if __name__ == "__main__":
    main()
