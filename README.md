# 세무법인 지율 — 소개용 원페이지 랜딩

반응형 원페이지 랜딩 + 고객 문의 폼 + 서버 측 리드(상담 신청) 저장.
브라우저 localStorage / sessionStorage는 사용하지 않으며, 모든 문의 데이터는 서버의 SQLite DB에 저장됩니다.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `index.html` | 랜딩 페이지 (헤더·히어로·소개·서비스·FAQ·문의폼·푸터, 개인정보 처리방침/이용약관 모달, JSON-LD·OG 태그) |
| `assets/styles.css` | 전체 스타일 (블루&화이트, 1024 / 768~1023 / 767 이하 반응형) |
| `assets/app.js` | 헤더·메뉴·아코디언·폼 검증·모달 + **`submitLead(payload)`** 저장 어댑터 |
| `server.py` | Python 표준 라이브러리만 사용하는 웹/API 서버 (외부 패키지 설치 불필요) |
| `schema.sql` | `leads` 테이블 스키마 |
| `data/leads.db` | 실행 시 자동 생성되는 SQLite 데이터베이스 |
| `assets/images/` | 교체 가능한 이미지 슬롯 (`hero.jpg`, `profile.jpg`, `og.jpg`) |

## 실행 방법

```bash
python server.py
```

브라우저에서 `http://127.0.0.1:8080` 접속. 포트를 바꾸려면 `python server.py 9000`.

## 리드 조회 (관리용)

관리 API는 토큰을 설정해야 열립니다. PowerShell 기준:

```bash
$env:JIYUL_ADMIN_TOKEN = "원하는_긴_토큰"; python server.py
```

| 엔드포인트 | 설명 |
|---|---|
| `POST /api/leads` | 문의 접수 (페이지 폼이 호출) |
| `GET /api/leads?token=...&status=신규&limit=200` | 리드 목록 (JSON) |
| `GET /api/leads.csv?token=...` | 리드 목록 CSV 내려받기 (엑셀용 UTF-8 BOM) |
| `PATCH /api/leads/<id>` | `status` / `assignee` / `memo` 수정 (헤더 `X-Admin-Token`) |

`status` 허용값: `신규`(기본값) / `연락완료` / `상담진행` / `수임` / `보류`

SQLite 파일을 직접 열어 봐도 됩니다.

```bash
python -c "import sqlite3;c=sqlite3.connect('data/leads.db');[print(dict(r)) for r in [dict(zip([d[0] for d in c.execute('select * from leads limit 0').description], row)) for row in c.execute('select * from leads order by id desc')]]"
```

## 저장 로직 교체

저장은 `assets/app.js` 상단의 **`submitLead(payload)` 함수 하나**로 분리되어 있습니다.
다른 시스템(외부 CRM, 구글 시트, 메일 발송 API 등)으로 옮길 때 이 함수 내부만 바꾸면 됩니다.

```js
payload = {
  name, company, phone, email, inquiry_type, message,
  privacy_agreed, agreed_at, source
}
// 성공: { receiptNo: 'YY-MMDD-###' } 반환
// 실패: Error throw  →  화면에 "일시적인 오류가 발생했습니다..." 표시
```

`id`, `created_at`, `receipt_no`, `status`(기본 `신규`)는 서버에서 부여합니다.
접수번호는 `YY-MMDD-###` 형식이며 `###`는 당일 접수 순번입니다.

## 이미지 슬롯

`assets/images/`에 아래 파일을 넣으면 자동 적용되고, 없으면 네이비 그라데이션 + 이니셜 모노그램으로 대체 렌더링됩니다.

| 파일 | 위치 | 권장 크기 |
|---|---|---|
| `hero.jpg` | 히어로 우측 (모바일 하단) | 1200×900 (4:3) |
| `profile.jpg` | 대표 세무사 프로필 | 600×800 (3:4) |
| `og.png` | 카카오톡·SNS 공유 미리보기 | 1200×630 (기본 제공, 교체 가능) |

이미지는 **성공적으로 로드될 때만** 슬롯에 표시되고, 없으면 네이비 그라데이션 + 모노그램으로 자동 대체됩니다.
기본 공유 이미지는 `python make_og.py`로 언제든 다시 생성할 수 있습니다.

### 공유 미리보기(og)가 안 뜰 때

카카오톡·SNS 미리보기는 아래 3가지가 **모두** 충족돼야 표시됩니다.

1. `assets/images/og.png` 존재 (기본 제공됨)
2. `index.html`의 `[사이트 주소 입력]`을 실제 도메인(`https://...`)으로 교체 → `og:image`가 절대 URL로 완성
3. 사이트가 외부 접근 가능한 **공개 https 주소**로 배포 (localhost·도메인 미입력 상태에서는 미리보기 불가)

배포 후에도 갱신이 안 되면 [카카오 공유 디버거](https://developers.kakao.com/tool/debugger/sharing) 또는 [페이스북 디버거](https://developers.facebook.com/tools/debug/)에서 URL을 다시 긁어 캐시를 초기화하세요.

## 검증 규칙 (프런트 + 서버 양쪽 적용)

- 성함 2자 이상 / 연락처 숫자 9~11자리(자동 하이픈) / 이메일 형식
- 문의 유형은 지정된 7개 값만 허용
- 문의 내용 10~1,000자
- 개인정보 수집·이용 동의 필수 (미동의 시 접수 차단)
- 동일 IP 기준 10분 내 5건 초과 접수 차단(간단한 스팸 방어)

## 세무 칼럼 (노션 연동 블로그)

노션 '세무칼럼'에 정리한 글을 홈페이지에 블로그처럼 노출합니다.

### 페이지 구조 (세무칼럼이 첫 화면)

| URL | 파일 | 역할 |
|---|---|---|
| `/` | `index.html` | **세무 칼럼 랜딩(첫 화면)** — 태그 필터 + 글 목록, 상단 CTA로 상담/소개 연결 |
| `/intro.html` | `intro.html` | 사무소 소개 one-pager — 히어로, 소개·업무분야(병합), FAQ, 상담 폼 |
| `/post.html?slug=...` | `post.html` | 칼럼 본문 |

| 구성 | 파일 |
|---|---|
| 목록·본문 API | `server.py` → `/api/posts`, `/api/posts/<slug>` |
| 목록/본문 렌더 스크립트 | `assets/blog.js` |
| 소개 페이지 스크립트(폼·최신칼럼 카드) | `assets/app.js` |
| 글 원고(마크다운) | `content/*.md` |
| 렌더링된 글 데이터 | `data/posts.json` |

### 글을 추가/수정하는 두 가지 방법

**A. 파일로 직접 (토큰 불필요)**
`content/` 폴더에 아래 형식의 `.md` 파일을 추가한 뒤 빌드합니다.

```
---
slug: 영문-식별자
title: 글 제목
summary: 목록에 보일 한 줄 요약
tags: 법인세, 조세특례제한법
date: 2026-07-30
source: https://blog.naver.com/taxin4u
---
(본문: 노션에서 복사한 표/콜아웃/체크리스트 그대로 붙여넣기)
```

```bash
python build_posts.py
```

**B. 노션 자동 미러링 (권장, `sync_notion.py`)**
노션 **‘세무법인 지율 · 세무칼럼’ 페이지의 하위 글 전체**를 조건 없이 내려받아
`content/`를 노션과 동일하게 맞추고 `posts.json`을 다시 만듭니다. (제목→title,
본문 첫 문단→요약, 본문 키워드→세목 태그 자동 추출)

**최초 1회 설정 (토큰)**
1. https://www.notion.so/my-integrations → **내부 통합** 생성 → 토큰 복사
2. 노션에서 **‘세무법인 지율 · 세무칼럼’ 페이지 ⋯ → 연결(Connections)** 에 그 통합 추가(공유)
3. 토큰 저장 (관리자 PowerShell):
   ```bash
   setx NOTION_TOKEN "secret_xxxxxxxx"
   ```
   (창을 새로 열어야 반영됨)

**자동 실행 등록 (30분 주기)**
```bash
./install_sync_task.ps1
```
→ Windows 작업 스케줄러에 `JiyulNotionColumnSync` 작업이 등록되어, 이후 노션 세무칼럼에
글을 올리거나 수정하면 **다음 주기에 자동으로 홈페이지에 반영**됩니다.
(제거: `./install_sync_task.ps1 -Remove` / 즉시 1회: `python sync_notion.py`)

- 소스 페이지를 바꾸려면 `NOTION_COLUMN_PAGE_ID` 환경변수로 지정합니다.
- `content/` 폴더는 이 스크립트가 관리합니다(노션 미러). 하위 글이 0건이면 안전을 위해 기존 내용을 지우지 않고 중단합니다.

> ⚠️ **개인정보/공개 주의**: ‘세무칼럼’ 페이지에는 **외부 공개해도 되는(익명화된) 글만** 두십시오. 이 페이지의 하위 글은 조건 없이 그대로 홈페이지에 반영됩니다. 원본 상담기록(고객 실명·연락처)이 있는 페이지를 이 아래로 옮기지 마십시오.

## 초안 안내

본 산출물은 초안이며 실서비스 전환 시 HTTPS 적용, 전송·저장 구간 암호화, 접근권한 통제 및 접속기록 보관,
보유기간 경과 자료 파기, 개인정보 처리방침 게시, 스팸·봇 차단 등 개인정보 보호법상 안전성 확보조치를
별도 검토해야 합니다. 개발용 서버(`server.py`)는 `127.0.0.1`에만 바인딩되며 그대로 외부에 공개하지 마십시오.
