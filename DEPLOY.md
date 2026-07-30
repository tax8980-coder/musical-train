# 공개 배포 가이드 (관리형 플랫폼 · 임시 주소)

관리형 플랫폼 **Render** 에 올려 `https://<이름>.onrender.com` 임시 주소로 공개하는 방법입니다.
(파이썬 서버를 그대로 돌리므로 상담 폼·칼럼·API가 모두 작동합니다.)

## 1. 코드를 GitHub 저장소에 올리기
Render는 GitHub/GitLab 저장소를 연결해 배포합니다.

```bash
git init
git add .
git commit -m "세무법인 지율 홈페이지"
# GitHub에서 빈 저장소를 만든 뒤:
git remote add origin https://github.com/<계정>/jiyul-landing.git
git branch -M main
git push -u origin main
```
> `data/leads.db`(리드 개인정보)와 `__pycache__`는 `.gitignore`로 제외됩니다. `data/posts.json`(칼럼)은 포함됩니다.

## 2. Render 웹 서비스 생성
1. https://render.com 가입 → **New +** → **Web Service** → 위 GitHub 저장소 선택
2. 설정(대부분 자동 인식):
   - Runtime: **Python**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python server.py`
   - Instance Type: **Free**
3. **Environment(환경변수)** 에 추가:
   | Key | Value |
   |---|---|
   | `HOST` | `0.0.0.0` |
   | `PYTHON_VERSION` | `3.12.8` |
   | `JIYUL_ADMIN_TOKEN` | (원하는 긴 무작위 문자열 — 리드 조회용) |
4. **Create Web Service** → 몇 분 후 `https://jiyul-landing-xxxx.onrender.com` 발급

> 저장소에 `render.yaml`이 있어, Render **Blueprint** 로 만들면 위 설정이 자동 적용됩니다.

## 3. 확인
- `https://<주소>/` → 세무 칼럼 랜딩(첫 화면)
- `https://<주소>/intro.html` → 회사 소개 + 상담 폼
- 리드 조회: `https://<주소>/api/leads?token=<JIYUL_ADMIN_TOKEN>`
- 페이지의 `[사이트 주소 입력]`(og·canonical)을 발급된 주소로 바꾸면 공유 미리보기가 완성됩니다.

## ⚠️ 무료 플랜 주의 (실서비스 전 반드시 확인)
1. **절전(Cold start)**: 무료는 일정 시간 미접속 시 잠들었다가 첫 접속에 수십 초 걸립니다.
2. **리드 유실**: 무료는 디스크가 재배포·재시작 시 초기화됩니다 → `data/leads.db`의 상담 접수가 사라질 수 있습니다.
   - 해결: Render **유료 디스크**를 붙이고(`/var/data`), 환경변수 `JIYUL_DATA_DIR=/var/data` 설정 (render.yaml 주석 참고). 또는 접수 즉시 이메일 통보 방식 추가(요청 주세요).
3. **개인정보 보호법 안전성 확보조치**: 상담 폼이 실명·연락처를 받으므로, 실제 홍보 전 HTTPS(플랫폼 제공)·접근권한 통제·접속기록·보유기간 파기·개인정보 처리방침 게시·스팸/봇 차단을 갖춰야 합니다. (페이지 하단 안내 참고)
   - 임시 공개 동안에는 폼을 홍보에 널리 쓰지 마시고, 도메인 연결 + 위 조치 완료 후 정식 오픈을 권장합니다.

## 4. 노션 칼럼 자동 동기화(선택)
`sync_notion.py` + `install_sync_task.ps1` 는 **내 PC(로컬)** 에서 도는 자동화입니다. 클라우드에서 자동 동기화하려면 Render **Cron Job**(유료) 또는 로컬 스케줄러로 동기화 후 `git push`(자동 재배포) 방식을 쓰면 됩니다. 필요 시 구성해 드리겠습니다.

## 대안
- **국내 보관이 필요하면**(개인정보 국내 저장) 네이버클라우드/카페24/가비아 VPS + Caddy(자동 HTTPS)로 전환할 수 있습니다. 이 경우 `Dockerfile`/`Caddyfile`을 준비해 드립니다.
