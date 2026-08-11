#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jiyul Tax Corp - landing page server (Python standard library only)

- Serves the static landing page (index.html, assets/)
- POST /api/leads      : stores an inquiry into the server-side SQLite `leads` table
- GET  /api/leads      : lead list (JSON)  [admin token required]
- GET  /api/leads.csv  : lead list (CSV, UTF-8 BOM for Excel) [admin token required]
- PATCH /api/leads/<id>: update status / assignee / memo        [admin token required]

Run:
    python server.py            # http://127.0.0.1:8080
    python server.py 9000       # custom port

Admin endpoints:
    set the JIYUL_ADMIN_TOKEN environment variable, then send it as
    the X-Admin-Token header (or ?token=... query string).

NOTE: this is a draft. See the disclaimer at the bottom of the landing page
      before running it as a production service.
"""

import csv
import hashlib
import http.cookies
import io
import json
import os
import re
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote, unquote

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
# 리드 DB 저장 위치. 클라우드에서는 재시작에도 남도록 영속 디스크 경로를
# JIYUL_DATA_DIR 로 지정하세요(예: /var/data). 미지정 시 프로젝트의 data/ 사용.
LEADS_DIR = os.environ.get("JIYUL_DATA_DIR", DATA_DIR)
DB_PATH = os.path.join(LEADS_DIR, "leads.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

KST = timezone(timedelta(hours=9))

# 공개 조회수 노출 시작일(KST). 이 시점 전까지는 서버에서 조회수를 계속 누적만 하고
# 화면(칼럼 카드·본문)에는 숨긴다. 이후 자동으로 노출된다. blog.js에도 동일 기준 존재.
PUBLIC_VIEWS_START = datetime(2026, 11, 1, tzinfo=KST)


def public_views_visible():
    """공개 화면에 조회수를 표시할지 여부(2026-11-01 KST부터 True)."""
    return datetime.now(KST) >= PUBLIC_VIEWS_START


ADMIN_TOKEN = os.environ.get("JIYUL_ADMIN_TOKEN", "").strip()

# 대표 도메인 정규화: 아래 호스트로 접속하면 CANONICAL_URL 로 301 리다이렉트.
# (여기에 없는 호스트 — 예: onrender.com, localhost, taxin4u.com 자신 — 은 그대로 서비스)
CANONICAL_URL = os.environ.get("JIYUL_CANONICAL_URL", "https://taxin4u.com").rstrip("/")
REDIRECT_HOSTS = {
    h.strip().lower()
    for h in os.environ.get(
        "JIYUL_REDIRECT_HOSTS", "www.taxin4u.com,taxin4u.co.kr,www.taxin4u.co.kr"
    ).split(",")
    if h.strip()
}

MAX_BODY_BYTES = 64 * 1024
ALLOWED_STATUS = ("신규", "연락완료", "상담진행", "수임", "보류")
DEFAULT_STATUS = "신규"

# must match the <option value="..."> list in index.html
ALLOWED_INQUIRY_TYPES = (
    "법인 세무·기장",
    "개인 종합소득세·양도소득세",
    "상속·증여·가업승계",
    "세액공제·경정청구",
    "세무조사·조세불복",
    "강의·집필 문의",
    "기타",
)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[A-Za-z]{2,}$")

POSTS_PATH = os.path.join(BASE_DIR, "data", "posts.json")
_posts_cache = {"mtime": None, "data": {"posts": []}}

# 조회수 스냅샷: 저장소에 커밋되는 파일. 컨테이너 임시 DB가 재배포로 초기화돼도
# 부팅 시 이 값으로 조회수를 복원한다. (스케줄 워크플로가 주기적으로 갱신·커밋)
VIEWS_JSON_PATH = os.path.join(BASE_DIR, "data", "views.json")

# 방문 통계 스냅샷(집계값). 조회수와 동일하게 재배포에도 보존.
STATS_JSON_PATH = os.path.join(BASE_DIR, "data", "stats.json")
STATS_SALT = os.environ.get("JIYUL_STATS_SALT", "jiyul-stats-2026")

# User-Agent 분류 시그니처(소문자 부분일치). AI를 먼저 검사(예: applebot-extended → AI).
_AI_BOT_SIGS = [
    ("gptbot", "GPTBot"), ("chatgpt-user", "ChatGPT-User"), ("oai-searchbot", "OAI-SearchBot"),
    ("claudebot", "ClaudeBot"), ("claude-web", "Claude-Web"), ("anthropic-ai", "anthropic-ai"),
    ("perplexity", "PerplexityBot"), ("google-extended", "Google-Extended"),
    ("bytespider", "Bytespider"), ("ccbot", "CCBot"), ("amazonbot", "Amazonbot"),
    ("applebot-extended", "Applebot-Extended"), ("meta-external", "Meta-ExternalAgent"),
    ("cohere", "cohere-ai"), ("diffbot", "Diffbot"), ("youbot", "YouBot"),
    ("imagesift", "ImagesiftBot"), ("timpibot", "Timpibot"), ("omgili", "omgili"),
    ("petalbot", "PetalBot"), ("gemini", "Google-Gemini"),
]
_SEARCH_BOT_SIGS = [
    ("googlebot", "Googlebot"), ("bingbot", "Bingbot"), ("yeti", "Naver-Yeti"),
    ("daum", "Daum"), ("yandex", "YandexBot"), ("duckduckbot", "DuckDuckBot"),
    ("applebot", "Applebot"), ("seznambot", "SeznamBot"), ("baiduspider", "Baiduspider"),
    ("facebookexternalhit", "facebook"), ("twitterbot", "Twitterbot"),
    ("slackbot", "Slackbot"), ("kakao", "Kakao"), ("naver", "Naver"),
]
_GENERIC_BOT_KEYS = ("bot", "crawler", "spider", "slurp", "python-requests",
                     "curl", "wget", "scan", "http-client", "go-http", "okhttp", "headless")

ADMIN_COOKIE = "jiyul_admin"


def _admin_cookie_value():
    """관리자 로그인 쿠키 값(토큰 원문 대신 해시). 토큰 변경 시 기존 로그인 무효화."""
    return hashlib.sha256(("admin-auth|" + ADMIN_TOKEN + "|" + STATS_SALT).encode("utf-8")).hexdigest()


def render_login_html(error=False):
    """관리자 로그인 페이지."""
    err = ('<p class="err">비밀번호가 올바르지 않습니다.</p>' if error else "")
    return (
        "<!doctype html><html lang=ko><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width, initial-scale=1'>"
        "<meta name=robots content='noindex, nofollow'><title>관리자 로그인 · 세무법인 지율</title><style>"
        "body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;"
        "font-family:Pretendard,system-ui,sans-serif;background:#F7F9FC;color:#1F2937;padding:20px}"
        ".box{background:#fff;border:1px solid #E2E8F0;border-radius:14px;padding:28px 26px;width:100%;max-width:360px;box-shadow:0 6px 24px rgba(30,58,95,.06)}"
        "h1{font-size:18px;margin:0 0 4px;color:#1E3A5F}.sub{color:#5B6B7F;font-size:13px;margin:0 0 18px}"
        "label{display:block;font-size:13px;color:#5B6B7F;margin-bottom:6px}"
        "input{width:100%;box-sizing:border-box;padding:11px 12px;font-size:15px;border:1px solid #CBD5E1;border-radius:9px;margin-bottom:14px}"
        "input:focus{outline:none;border-color:#3B82F6;box-shadow:0 0 0 3px rgba(59,130,246,.15)}"
        "button{width:100%;padding:11px;font-size:15px;font-weight:700;color:#fff;background:#3B82F6;border:0;border-radius:9px;cursor:pointer}"
        "button:hover{background:#2F6FE0}.err{color:#dc2626;font-size:13px;margin:0 0 12px}"
        "</style></head><body><form class=box method=post action='/admin/login'>"
        "<h1>관리자 로그인</h1><p class=sub>세무법인 지율 · 방문 통계</p>" + err +
        "<label for=pw>비밀번호</label>"
        "<input id=pw type=password name=password autocomplete=current-password autofocus required>"
        "<button type=submit>로그인</button></form></body></html>"
    )


_REF_SEARCH = [  # (host 부분일치, 라벨)  — 검색엔진
    ("google", "구글"), ("search.naver", "네이버"), ("m.search.naver", "네이버"),
    ("bing", "빙"), ("search.daum", "다음"), ("yahoo", "야후"),
    ("duckduckgo", "DuckDuckGo"), ("yandex", "Yandex"), ("zum.", "ZUM"),
]
_REF_SNS = [  # SNS·외부 매체
    ("blog.naver", "네이버블로그"), ("cafe.naver", "네이버카페"), ("m.blog.naver", "네이버블로그"),
    ("facebook", "페이스북"), ("instagram", "인스타그램"), ("threads", "스레드"),
    ("youtube", "유튜브"), ("youtu.be", "유튜브"), ("t.co", "X(트위터)"), ("twitter", "X(트위터)"),
    ("x.com", "X(트위터)"), ("kakao", "카카오"), ("band.us", "밴드"), ("t.me", "텔레그램"),
    ("linkedin", "링크드인"),
]
_REF_QUERY_KEYS = ("q", "query", "wd", "keyword", "kw", "p", "text")


def classify_ref(ref):
    """Referer → (type, site, keyword). type: '검색'|'SNS'|'직접'|'기타'|'내부'."""
    if not ref:
        return ("직접", "직접 유입/앱/북마크", None)
    try:
        u = urlparse(ref)
        host = (u.hostname or "").lower()
        qs = parse_qs(u.query)
    except Exception:  # noqa: BLE001
        return ("기타", "기타", None)
    if not host:
        return ("기타", "기타", None)
    if "taxin4u" in host:
        return ("내부", None, None)  # 내부 이동은 집계 제외
    for key, label in _REF_SNS:
        if key in host:
            return ("SNS", label, None)
    for key, label in _REF_SEARCH:
        if key in host:
            kw = None
            for qk in _REF_QUERY_KEYS:
                if qk in qs and qs[qk][0].strip():
                    kw = qs[qk][0].strip()[:80]
                    break
            return ("검색", label, kw)
    return ("기타", host[:60], None)


def classify_ua(ua):
    """User-Agent → (category, name). category: 'ai'|'search'|'bot'|'human'."""
    u = (ua or "").lower()
    if not u:
        return ("bot", "empty-ua")
    for sig, name in _AI_BOT_SIGS:
        if sig in u:
            return ("ai", name)
    for sig, name in _SEARCH_BOT_SIGS:
        if sig in u:
            return ("search", name)
    for k in _GENERIC_BOT_KEYS:
        if k in u:
            return ("bot", "generic")
    return ("human", None)


def record_visit(path, ip, ua, ref=""):
    """컨텐츠 페이지 GET 1건을 일자별 집계에 반영. 실패는 조용히 무시(서비스 영향 없음)."""
    try:
        day = datetime.now(KST).strftime("%Y-%m-%d")
        cat, bot = classify_ua(ua)
        conn = get_conn()
        try:
            def bump(category, name, n=1):
                conn.execute(
                    "INSERT INTO stat_counts (day, category, name, hits) VALUES (?,?,?,?) "
                    "ON CONFLICT(day,category,name) DO UPDATE SET hits = hits + ?",
                    (day, category, name, n, n),
                )
            if cat == "human":
                bump("pv", "total")
                bump("page", path[:120])
                vhash = hashlib.sha256(
                    (STATS_SALT + "|" + day + "|" + (ip or "")).encode("utf-8")
                ).hexdigest()[:16]
                cur = conn.execute(
                    "INSERT OR IGNORE INTO visitor_seen (day, vhash) VALUES (?,?)", (day, vhash)
                )
                if cur.rowcount:
                    bump("visitor", "unique")
                # 유입 경로/검색어 (사람 방문만)
                rtype, rsite, kw = classify_ref(ref)
                if rtype != "내부":
                    bump("reftype", rtype)
                    if rsite:
                        bump("refsite", rtype + " · " + rsite)
                    if kw:
                        bump("kw", kw)
            elif cat == "ai":
                bump("ai", bot)
                bump("ai", "__total__")
            elif cat == "search":
                bump("search", bot)
                bump("search", "__total__")
            else:
                bump("bot", bot or "unknown")
            conn.commit()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        pass


def _seed_stats_from_snapshot(conn):
    """재배포로 DB가 초기화돼도 data/stats.json 집계로 방문 통계를 복원(값별 MAX)."""
    try:
        with open(STATS_JSON_PATH, encoding="utf-8") as fp:
            snap = json.load(fp)
    except (OSError, ValueError):
        return
    rows = snap.get("rows") if isinstance(snap, dict) else None
    if not isinstance(rows, list):
        return
    for r in rows:
        try:
            day, cat, name, hits = r["day"], r["category"], r["name"], int(r["hits"])
        except (KeyError, TypeError, ValueError):
            continue
        conn.execute(
            "INSERT INTO stat_counts (day, category, name, hits) VALUES (?,?,?,?) "
            "ON CONFLICT(day,category,name) DO UPDATE SET hits = MAX(stat_counts.hits, excluded.hits)",
            (day, cat, name, hits),
        )
    conn.commit()


def export_stats():
    """전체 집계를 리스트로 내보내기(스냅샷 백업용)."""
    try:
        conn = get_conn()
        try:
            rows = [
                {"day": r["day"], "category": r["category"], "name": r["name"], "hits": int(r["hits"])}
                for r in conn.execute("SELECT day, category, name, hits FROM stat_counts")
            ]
            return {"rows": rows}
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        return {"rows": []}


_STATIC_PAGE_LABELS = {
    "/": "홈 · 세무칼럼 목록",
    "/index.html": "홈 · 세무칼럼 목록",
    "/intro.html": "업무분야(세무사·업무소개)",
    "/resources.html": "자료실",
    "/faq.html": "자주 묻는 질문",
    "/contact.html": "상담 문의",
    "/post.html": "칼럼(구 주소)",
}

# 옛 자동생성 slug → 정리된 slug. /column/<옛slug> 요청은 새 주소로 301 이동한다.
# (자동동기화가 SLUG_MAP 없이 만든 임시 slug를 사람이 읽기 좋은 주소로 정리한 뒤 링크·색인 보존)
SLUG_REDIRECTS = {
    "ot-2026-2026-4-9-3b5868d0": "inclusive-wage-fixed-ot-2026",
    "post-3b6868d0": "financial-income-comprehensive-tax-refund",
    "2-127-10-3b6868d0": "two-workplaces-separate-accounting-127-10",
    "2024-67238-3b8868d0": "onerous-gift-acquisition-tax-2024du67238",
    "post-3b8868d0": "support-conditioned-gift-civil-vs-tax",
}

# ---------------- 세목별 허브(대표) 페이지 ----------------
# 하이브리드(C): 각 허브는 대표 태그로 자동 채우되, include로 특정 칼럼을 강제 포함,
# exclude로 태그가 걸려도 제외할 수 있다. posts.json 은 최신순 정렬이라 그 순서를 유지.
HUBS = [
    {
        "slug": "corporate-tax",
        "title": "법인세 이야기",
        "lead": "법인세 신고·세무조정, 적격합병·이월결손금·세액공제 승계 등 법인 세무의 실무 쟁점을 법령과 판례에 근거해 풀어 쓴 칼럼을 모았습니다.",
        "desc": "법인세 신고·세무조정·적격합병·세액공제 등 법인 세무 실무를 법령과 판례로 정리한 세무법인 지율 손창용 세무사의 칼럼 모음.",
        "tags": ["법인세"], "include": [], "exclude": [],
    },
    {
        "slug": "income-tax",
        "title": "소득세 이야기",
        "lead": "종합소득세·근로소득·금융소득종합과세·사업소득 등 개인 소득세의 신고와 절세 쟁점을 법령과 예규로 풀어 쓴 칼럼을 모았습니다.",
        "desc": "종합소득세·근로소득·금융소득종합과세·사업소득 등 개인 소득세 실무를 정리한 세무법인 지율 손창용 세무사의 칼럼 모음.",
        "tags": ["소득세"], "include": [], "exclude": [],
    },
    {
        "slug": "vat",
        "title": "부가가치세 이야기",
        "lead": "부가가치세 신고·매입세액공제·세금계산서·대손세액공제 등 부가세 실무 쟁점을 정리한 칼럼을 모았습니다.",
        "desc": "부가가치세 신고·매입세액공제·세금계산서·대손세액공제 등 부가세 실무를 정리한 세무법인 지율 손창용 세무사의 칼럼 모음.",
        "tags": ["부가가치세"], "include": [], "exclude": [],
    },
    {
        "slug": "tax-credit",
        "title": "세액공제·감면 이야기",
        "lead": "통합고용세액공제·통합투자세액공제·연구인력개발비(R&D)·창업중소기업감면·중소기업특별세액감면 등 조세특례제한법상 세액공제·감면을 다룬 칼럼을 모았습니다.",
        "desc": "통합고용·통합투자·R&D·창업중소기업감면 등 조세특례제한법 세액공제·감면을 정리한 세무법인 지율 손창용 세무사의 칼럼 모음.",
        "tags": ["조세특례제한법"], "include": [], "exclude": [],
    },
    {
        "slug": "transfer-inheritance-gift",
        "title": "양도·상속·증여세 이야기",
        "lead": "양도소득세 비과세·중과·취득시기와 상속·증여세 신고·절세, 가업승계·유류분·신탁 등 재산의 처분과 이전에 관한 쟁점을 모았습니다.",
        "desc": "양도소득세와 상속·증여세, 가업승계·유류분·신탁 등 재산의 처분·이전 쟁점을 정리한 세무법인 지율 손창용 세무사의 칼럼 모음.",
        "tags": ["양도소득세", "상속세", "증여세"], "include": [], "exclude": [],
    },
    {
        "slug": "acquisition-tax",
        "title": "취득세 이야기",
        "lead": "부동산·주식 등 자산 취득에 따른 취득세와 관련 지방세 쟁점을 정리한 칼럼을 모았습니다.",
        "desc": "자산 취득에 따른 취득세와 관련 지방세 쟁점을 정리한 세무법인 지율 손창용 세무사의 칼럼 모음.",
        "tags": ["취득세"], "include": ["testamentary-trust-not-tax-saving"], "exclude": [],
    },
]
HUB_BY_SLUG = {h["slug"]: h for h in HUBS}

# 통합·정리로 사라진 옛 허브 slug → 새 허브. /<옛slug> 요청은 301로 새 주소로 이동.
HUB_REDIRECTS = {
    "capital-gains": "transfer-inheritance-gift",
    "inheritance-gift": "transfer-inheritance-gift",
}


def _post_in_hub(post, hub):
    slug = post.get("slug", "")
    if slug in hub.get("exclude", []):
        return False
    if slug in hub.get("include", []):
        return True
    return bool(set(hub.get("tags", [])) & set(post.get("tags") or []))


def _hub_posts(hub, posts):
    return [p for p in posts if _post_in_hub(p, hub)]


def _primary_hub_for(post):
    for h in HUBS:
        if _post_in_hub(post, h):
            return h
    return None


# 허브 칩·브레드크럼·홈 섹션 공용 스타일(styles.css 버전과 무관하게 인라인 주입).
HUB_INLINE_CSS = (
    "<style>"
    ".hub-chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px}"
    ".hub-chip{display:inline-block;padding:7px 14px;border-radius:999px;font-size:.92rem;font-weight:600;"
    "color:#1E3A5F;background:#EAF1FA;border:1px solid #D3E0F0;text-decoration:none;transition:background .15s,border-color .15s}"
    ".hub-chip:hover{background:#D8E6F7;border-color:#B9D0EC}"
    ".hub-chip.is-active{background:#1E3A5F;color:#fff;border-color:#1E3A5F}"
    ".hub-chip__n{opacity:.6;font-weight:700;margin-left:3px}"
    ".hub-chip.is-active .hub-chip__n{opacity:.9}"
    ".hub-breadcrumb{font-size:.9rem;color:#5b6b7f;margin:0 0 12px}"
    ".hub-breadcrumb a{color:#2A5A9A;text-decoration:none}.hub-breadcrumb a:hover{text-decoration:underline}"
    ".hub-home{margin:2px 0 20px}"
    ".hub-home__title{font-size:1rem;font-weight:700;color:#1E3A5F;margin:0 0 10px}"
    ".related{margin:34px 0 6px;padding-top:22px;border-top:1px solid #e5e7eb}"
    ".related__title{font-size:23px;font-weight:700;line-height:1.4;letter-spacing:-.01em;color:#1E3A5F;margin:0 0 14px}"
    "@media (max-width:767px){.related__title{font-size:20px}}"
    ".related__list{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:11px}"
    ".related__link{color:#1E3A5F;font-weight:600;text-decoration:none}"
    ".related__link:hover{text-decoration:underline}"
    ".related__tags{display:block;margin-top:3px;font-size:.85rem;color:#5b6b7f}"
    ".related__blog{margin-top:6px}"
    ".related__blog a{color:#2A5A9A;font-weight:600;text-decoration:none}"
    ".related__blog a:hover{text-decoration:underline}"
    "@media print{.related{display:none !important}}"
    ".post-list{list-style:none;padding:0;margin:0;display:flex;flex-direction:column}"
    ".post-row{border-top:1px solid #eef1f5}"
    ".post-row:last-child{border-bottom:1px solid #eef1f5}"
    ".post-row__link{display:block;padding:15px 4px;text-decoration:none}"
    ".post-row__title{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;font-size:18px;font-weight:700;line-height:1.45;color:#1E3A5F}"
    ".post-row__link:hover .post-row__title{color:#2A5A9A}"
    ".post-row__emoji{margin-right:7px}"
    ".post-row__meta{display:flex;flex-wrap:wrap;align-items:center;gap:4px 12px;margin-top:7px;font-size:.86rem}"
    ".post-row__tags{color:#2A5A9A;font-weight:600}"
    ".post-row__date{color:#5b6b7f}"
    "@media (max-width:767px){.post-row__title{font-size:16px}.post-row__link{padding:14px 2px}}"
    "</style>"
)


def _page_label(path, title_map):
    """방문 통계 경로 → 사람이 읽는 한글 라벨."""
    if path in _STATIC_PAGE_LABELS:
        return _STATIC_PAGE_LABELS[path]
    m = re.match(r"^/column/([A-Za-z0-9\-_]+)$", path)
    if m:
        return title_map.get(m.group(1), path)
    hp = path.strip("/")
    if hp in HUB_BY_SLUG:
        return "세목별 · " + HUB_BY_SLUG[hp]["title"]
    return path


def build_stats(days=30):
    """관리자 대시보드용 집계 요약. 최근 N일."""
    since = (datetime.now(KST) - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    out = {
        "days": days, "since": since,
        "pv": 0, "visitors": 0, "ai": 0, "search": 0, "bot": 0,
        "ai_by_bot": [], "search_by_bot": [], "top_pages": [], "daily": [],
        "ref_types": [], "ref_sites": [], "keywords": [],
    }
    try:
        conn = get_conn()
    except Exception:  # noqa: BLE001
        return out
    try:
        def q(sql, args=()):
            return conn.execute(sql, args).fetchall()

        out["pv"] = (q("SELECT COALESCE(SUM(hits),0) s FROM stat_counts WHERE category='pv' AND day>=?", (since,))[0]["s"])
        out["visitors"] = (q("SELECT COALESCE(SUM(hits),0) s FROM stat_counts WHERE category='visitor' AND day>=?", (since,))[0]["s"])
        out["ai"] = (q("SELECT COALESCE(SUM(hits),0) s FROM stat_counts WHERE category='ai' AND name='__total__' AND day>=?", (since,))[0]["s"])
        out["search"] = (q("SELECT COALESCE(SUM(hits),0) s FROM stat_counts WHERE category='search' AND name='__total__' AND day>=?", (since,))[0]["s"])
        out["bot"] = (q("SELECT COALESCE(SUM(hits),0) s FROM stat_counts WHERE category='bot' AND day>=?", (since,))[0]["s"])
        out["ai_by_bot"] = [(r["name"], r["s"]) for r in q(
            "SELECT name, SUM(hits) s FROM stat_counts WHERE category='ai' AND name!='__total__' AND day>=? GROUP BY name ORDER BY s DESC", (since,))]
        out["search_by_bot"] = [(r["name"], r["s"]) for r in q(
            "SELECT name, SUM(hits) s FROM stat_counts WHERE category='search' AND name!='__total__' AND day>=? GROUP BY name ORDER BY s DESC", (since,))]
        title_map = {p.get("slug"): p.get("title") for p in load_posts().get("posts", [])}
        out["top_pages"] = [(_page_label(r["name"], title_map), r["s"]) for r in q(
            "SELECT name, SUM(hits) s FROM stat_counts WHERE category='page' AND day>=? GROUP BY name ORDER BY s DESC LIMIT 15", (since,))]
        out["ref_types"] = [(r["name"], r["s"]) for r in q(
            "SELECT name, SUM(hits) s FROM stat_counts WHERE category='reftype' AND day>=? GROUP BY name ORDER BY s DESC", (since,))]
        out["ref_sites"] = [(r["name"], r["s"]) for r in q(
            "SELECT name, SUM(hits) s FROM stat_counts WHERE category='refsite' AND day>=? GROUP BY name ORDER BY s DESC LIMIT 15", (since,))]
        out["keywords"] = [(r["name"], r["s"]) for r in q(
            "SELECT name, SUM(hits) s FROM stat_counts WHERE category='kw' AND day>=? GROUP BY name ORDER BY s DESC LIMIT 20", (since,))]
        daily = {}
        for r in q("SELECT day, category, name, hits FROM stat_counts WHERE day>=?", (since,)):
            d = daily.setdefault(r["day"], {"pv": 0, "visitor": 0, "ai": 0, "search": 0})
            if r["category"] == "pv":
                d["pv"] += r["hits"]
            elif r["category"] == "visitor":
                d["visitor"] += r["hits"]
            elif r["category"] == "ai" and r["name"] == "__total__":
                d["ai"] += r["hits"]
            elif r["category"] == "search" and r["name"] == "__total__":
                d["search"] += r["hits"]
        out["daily"] = sorted(([day] + [v["pv"], v["visitor"], v["ai"], v["search"]] for day, v in daily.items()), reverse=True)[:14]
    finally:
        conn.close()
    return out


def render_stats_html(s):
    """관리자 통계 대시보드(자체 완결 HTML)."""
    def rows_html(pairs, empty="데이터 없음"):
        if not pairs:
            return '<tr><td colspan="2" class="empty">' + empty + "</td></tr>"
        return "".join(
            "<tr><td>" + _esc_html(n) + '</td><td class="num">' + format(int(h), ",d") + "</td></tr>"
            for n, h in pairs
        )

    daily_rows = "".join(
        "<tr><td>" + _esc_html(r[0]) + "</td>"
        + '<td class="num">' + format(int(r[1]), ",d") + "</td>"
        + '<td class="num">' + format(int(r[2]), ",d") + "</td>"
        + '<td class="num">' + format(int(r[3]), ",d") + "</td>"
        + '<td class="num">' + format(int(r[4]), ",d") + "</td></tr>"
        for r in s["daily"]
    ) or '<tr><td colspan="5" class="empty">데이터 없음</td></tr>'

    return (
        "<!doctype html><html lang=ko><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width, initial-scale=1'>"
        "<meta name=robots content='noindex, nofollow'>"
        "<title>방문 통계 · 세무법인 지율</title><style>"
        ":root{--navy:#1E3A5F;--blue:#3B82F6;--line:#E2E8F0;--sub:#5B6B7F}"
        "*{box-sizing:border-box}body{margin:0;font-family:Pretendard,system-ui,sans-serif;background:#F7F9FC;color:#1F2937;padding:20px}"
        ".wrap{max-width:960px;margin:0 auto}h1{font-size:20px;margin:0 0 4px}.meta{color:var(--sub);font-size:13px;margin-bottom:18px}"
        ".cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:22px}"
        "@media(max-width:640px){.cards{grid-template-columns:repeat(2,1fr)}}"
        ".card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px}"
        ".card .k{color:var(--sub);font-size:13px}.card .v{font-size:26px;font-weight:800;color:var(--navy);margin-top:4px}"
        ".card.ai .v{color:var(--blue)}"
        "section{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:16px}"
        "h2{font-size:15px;margin:0 0 10px;color:var(--navy)}"
        "table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line)}"
        "th{color:var(--sub);font-weight:600;font-size:12px}td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}"
        ".empty{color:var(--sub);text-align:center;padding:14px}.note{color:var(--sub);font-size:12px;line-height:1.7}"
        "a.logout{font-size:13px;color:var(--sub);text-decoration:none;border:1px solid var(--line);padding:6px 12px;border-radius:8px}"
        "a.logout:hover{background:#fff}"
        "</style></head><body><div class=wrap>"
        "<div style='display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap'>"
        "<h1>방문 통계 <span style='font-weight:500;color:var(--sub);font-size:14px'>· 세무법인 지율</span></h1>"
        "<a class=logout href='/admin/logout'>로그아웃</a></div>"
        "<p class=meta>최근 " + str(s["days"]) + "일 (" + _esc_html(s["since"]) + " ~) · 서버 기준 집계</p>"
        "<div class=cards>"
        "<div class=card><div class=k>페이지뷰(사람)</div><div class=v>" + format(int(s["pv"]), ",d") + "</div></div>"
        "<div class=card><div class=k>순 방문자(추정)</div><div class=v>" + format(int(s["visitors"]), ",d") + "</div></div>"
        "<div class='card ai'><div class=k>AI 크롤러 조회</div><div class=v>" + format(int(s["ai"]), ",d") + "</div></div>"
        "<div class=card><div class=k>검색 크롤러 조회</div><div class=v>" + format(int(s["search"]), ",d") + "</div></div>"
        "</div>"
        "<section><h2>AI 크롤러별 조회 (GPTBot·ClaudeBot·PerplexityBot 등)</h2>"
        "<table><thead><tr><th>봇</th><th class=num>조회수</th></tr></thead><tbody>" + rows_html(s["ai_by_bot"], "아직 AI 크롤러 방문 없음") + "</tbody></table></section>"
        "<section><h2>검색 크롤러별 조회 (Googlebot·Naver Yeti·Bingbot 등)</h2>"
        "<table><thead><tr><th>봇</th><th class=num>조회수</th></tr></thead><tbody>" + rows_html(s["search_by_bot"]) + "</tbody></table></section>"
        "<section><h2>인기 페이지 (사람 방문)</h2>"
        "<table><thead><tr><th>페이지</th><th class=num>페이지뷰</th></tr></thead><tbody>" + rows_html(s["top_pages"]) + "</tbody></table></section>"
        "<section><h2>유입 경로 (사람 방문)</h2>"
        "<table><thead><tr><th>구분</th><th class=num>방문</th></tr></thead><tbody>" + rows_html(s["ref_types"]) + "</tbody></table></section>"
        "<section><h2>유입 매체별 (검색엔진·SNS)</h2>"
        "<table><thead><tr><th>매체</th><th class=num>방문</th></tr></thead><tbody>" + rows_html(s["ref_sites"]) + "</tbody></table></section>"
        "<section><h2>검색어 (유입 키워드)</h2>"
        "<table><thead><tr><th>검색어</th><th class=num>유입</th></tr></thead><tbody>" + rows_html(s["keywords"], "집계된 검색어 없음") + "</tbody></table>"
        "<p class=note style='margin-top:10px'>※ 구글·네이버는 개인정보 보호로 검색어를 사이트에 넘기지 않아, 여기엔 일부(빙·다음 등)만 잡힙니다. <b>전체 검색어</b>는 구글 서치콘솔(실적→검색어)·네이버 서치어드바이저(리포트→검색어)에서 확인하세요.</p></section>"
        "<section><h2>일자별 추이 (최근 14일)</h2>"
        "<table><thead><tr><th>날짜</th><th class=num>페이지뷰</th><th class=num>순방문</th><th class=num>AI</th><th class=num>검색</th></tr></thead><tbody>" + daily_rows + "</tbody></table></section>"
        "<p class=note>· 페이지뷰/순방문은 사람(브라우저) 방문 기준, AI·검색은 크롤러 User-Agent 기준입니다.<br>"
        "· AI 크롤러 조회는 서버에서만 집계됩니다(구글 애널리틱스 등 JS 분석은 크롤러를 못 잡음).<br>"
        "· 순 방문자는 당일 IP 해시로 추정하며, IP 원문은 저장하지 않습니다. 재배포 후 당일 순방문은 일시적으로 과다 집계될 수 있습니다.<br>"
        "· 데이터는 스냅샷(data/stats.json)으로 재배포에도 보존됩니다.</p>"
        "</div></body></html>"
    )

# 자료실: 세무 서식 등 다운로드 파일 폴더 (git 저장소에 포함 → 영구 보존)
FILES_DIR = os.path.join(BASE_DIR, "files")


def _human_size(num):
    num = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024.0 or unit == "GB":
            return "%d B" % int(num) if unit == "B" else "%.1f %s" % (num, unit)
        num /= 1024.0
    return "%.1f GB" % num


def list_files():
    """files/ 폴더의 다운로드 파일 목록(가나다/이름순). 숨김(.)·시스템(_) 파일 및 README 제외."""
    out = []
    try:
        names = os.listdir(FILES_DIR)
    except OSError:
        return out
    for name in names:
        if name.startswith(".") or name.startswith("_") or name.upper().startswith("README"):
            continue
        path = os.path.join(FILES_DIR, name)
        if not os.path.isfile(path):
            continue
        try:
            st = os.stat(path)
        except OSError:
            continue
        base, ext = os.path.splitext(name)
        out.append({
            "name": name,
            "title": base,
            "ext": ext.lstrip(".").lower(),
            "size": st.st_size,
            "size_text": _human_size(st.st_size),
            "modified": datetime.fromtimestamp(st.st_mtime, KST).isoformat(timespec="seconds"),
        })
    out.sort(key=lambda f: f["name"].lower())
    return out


MEDIA_JSON = os.path.join(BASE_DIR, "data", "media.json")


def _youtube_id(url):
    """유튜브 URL에서 11자리 영상 ID 추출(watch/youtu.be/embed/shorts)."""
    m = re.search(r"(?:v=|youtu\.be/|embed/|shorts/|/live/)([A-Za-z0-9_-]{11})", url or "")
    return m.group(1) if m else ""


def load_media():
    """data/media.json → 언론·강의 영상 목록(유튜브 썸네일 자동 생성). 없으면 빈 목록."""
    try:
        with open(MEDIA_JSON, encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, ValueError):
        return []
    out = []
    for m in (data.get("media") or []):
        if not m.get("url") or not m.get("title"):
            continue
        vid = _youtube_id(m.get("url", ""))
        item = dict(m)
        item["youtube_id"] = vid
        # 지정 thumb(비유튜브: KBS 등 og:image) 우선, 없으면 유튜브 ID로 자동 생성
        item["thumb"] = m.get("thumb") or (("https://img.youtube.com/vi/" + vid + "/hqdefault.jpg") if vid else "")
        out.append(item)
    out.sort(key=lambda x: x.get("date") or "", reverse=True)   # 최신순(날짜 없는 항목은 뒤로)
    return out


def load_posts():
    """data/posts.json 을 mtime 기준으로 캐싱해 로드. 없으면 빈 목록."""
    try:
        mtime = os.path.getmtime(POSTS_PATH)
    except OSError:
        return {"posts": []}
    if _posts_cache["mtime"] != mtime:
        try:
            with open(POSTS_PATH, encoding="utf-8") as fp:
                _posts_cache["data"] = json.load(fp)
            _posts_cache["mtime"] = mtime
        except (OSError, ValueError):
            return {"posts": []}
    return _posts_cache["data"]

_receipt_lock = threading.Lock()

# very simple in-memory throttle: max N submissions per IP per window
_rate_lock = threading.Lock()
_rate_log = {}
RATE_LIMIT = 5
RATE_WINDOW_SEC = 600

# 세무칼럼 조회수 중복 집계 방지: 같은 IP+slug는 이 시간(초) 안에서 1회만 카운트
_view_lock = threading.Lock()
_view_seen = {}
VIEW_DEDUP_SEC = 3600


# ---------------------------------------------------------------- database
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _seed_views_from_snapshot(conn):
    """재배포로 DB가 초기화돼도 저장소의 data/views.json 값으로 조회수를 복원.
    기존 값보다 큰 경우에만 반영해, 살아있는(더 최신) 카운트를 낮추지 않는다."""
    try:
        with open(VIEWS_JSON_PATH, encoding="utf-8") as fp:
            snap = json.load(fp)
    except (OSError, ValueError):
        return
    if not isinstance(snap, dict):
        return
    now = datetime.now(KST).isoformat(timespec="seconds")
    for slug, views in snap.items():
        try:
            v = int(views)
        except (TypeError, ValueError):
            continue
        if v <= 0:
            continue
        conn.execute(
            "INSERT INTO post_views (slug, views, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(slug) DO UPDATE SET "
            "views = MAX(post_views.views, excluded.views), updated_at = excluded.updated_at",
            (slug, v, now),
        )
    conn.commit()


def init_db():
    os.makedirs(LEADS_DIR, exist_ok=True)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as fp:
        schema = fp.read()
    conn = get_conn()
    try:
        conn.executescript(schema)
        conn.commit()
        _seed_views_from_snapshot(conn)
        _seed_stats_from_snapshot(conn)
    finally:
        conn.close()


def next_receipt_no(conn, now_kst):
    """YY-MMDD-### : ### is a per-day sequence, zero padded to 3 digits."""
    prefix = now_kst.strftime("%y-%m%d")
    row = conn.execute(
        "SELECT receipt_no FROM leads WHERE receipt_no LIKE ? ORDER BY receipt_no DESC LIMIT 1",
        (prefix + "-%",),
    ).fetchone()
    seq = 1
    if row:
        try:
            seq = int(str(row["receipt_no"]).rsplit("-", 1)[1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return "%s-%03d" % (prefix, seq)


def insert_lead(fields):
    """Insert one lead, returning its receipt number. Retries on receipt collision."""
    now_kst = datetime.now(KST)
    created_at = now_kst.isoformat(timespec="seconds")

    with _receipt_lock:
        conn = get_conn()
        try:
            for _ in range(20):
                receipt_no = next_receipt_no(conn, now_kst)
                try:
                    conn.execute(
                        """
                        INSERT INTO leads
                            (created_at, receipt_no, name, company, phone, email,
                             inquiry_type, message, privacy_agreed, agreed_at,
                             status, assignee, memo, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            created_at,
                            receipt_no,
                            fields["name"],
                            fields["company"],
                            fields["phone"],
                            fields["email"],
                            fields["inquiry_type"],
                            fields["message"],
                            1 if fields["privacy_agreed"] else 0,
                            fields["agreed_at"],
                            DEFAULT_STATUS,          # status
                            None,                    # assignee
                            None,                    # memo
                            fields["source"],
                        ),
                    )
                    conn.commit()
                    return receipt_no
                except sqlite3.IntegrityError:
                    conn.rollback()
                    continue
            raise RuntimeError("receipt number allocation failed")
        finally:
            conn.close()


# ---------------------------------------------------------------- validation
def _clean(value, limit):
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    value = value.replace("\x00", "").strip()
    return value[:limit]


def validate_payload(payload):
    """Server side validation. Returns (fields, errors)."""
    errors = {}

    name = _clean(payload.get("name"), 80)
    company = _clean(payload.get("company"), 120)
    phone_raw = _clean(payload.get("phone"), 20)
    email = _clean(payload.get("email"), 190)
    inquiry_type = _clean(payload.get("inquiry_type"), 60)
    message = _clean(payload.get("message"), 1000)
    agreed = payload.get("privacy_agreed")
    agreed_at = _clean(payload.get("agreed_at"), 40)
    source = _clean(payload.get("source"), 60) or "website-landing"

    digits = re.sub(r"\D", "", phone_raw)

    if len(name) < 2:
        errors["name"] = "name_too_short"
    if not (9 <= len(digits) <= 11):
        errors["phone"] = "phone_invalid"
    if not EMAIL_RE.match(email):
        errors["email"] = "email_invalid"
    if inquiry_type not in ALLOWED_INQUIRY_TYPES:
        errors["inquiry_type"] = "inquiry_type_invalid"
    if not (10 <= len(message) <= 1000):
        errors["message"] = "message_length_invalid"
    if agreed is not True and str(agreed).lower() not in ("true", "1", "on", "yes"):
        errors["privacy_agreed"] = "privacy_not_agreed"

    if not agreed_at:
        agreed_at = datetime.now(KST).isoformat(timespec="seconds")

    fields = {
        "name": name,
        "company": company or None,
        "phone": phone_raw,
        "email": email,
        "inquiry_type": inquiry_type,
        "message": message,
        "privacy_agreed": True,
        "agreed_at": agreed_at,
        "source": source,
    }
    return fields, errors


def rate_limited(ip):
    now = time.time()
    with _rate_lock:
        hits = [t for t in _rate_log.get(ip, []) if now - t < RATE_WINDOW_SEC]
        if len(hits) >= RATE_LIMIT:
            _rate_log[ip] = hits
            return True
        hits.append(now)
        _rate_log[ip] = hits
        # opportunistic cleanup
        if len(_rate_log) > 2000:
            for key in list(_rate_log.keys()):
                if all(now - t >= RATE_WINDOW_SEC for t in _rate_log[key]):
                    _rate_log.pop(key, None)
    return False


# ---------------------------------------------------------------- 조회수
def _slug_exists(slug):
    """posts.json 에 존재하는 slug 인지 검증(임의 slug 로 테이블 오염 방지)."""
    for p in load_posts().get("posts", []):
        if p.get("slug") == slug:
            return True
    return False


def get_views_map():
    """{slug: views} 전체 맵. DB 오류 시 빈 dict."""
    try:
        conn = get_conn()
        try:
            return {r["slug"]: r["views"] for r in conn.execute("SELECT slug, views FROM post_views")}
        finally:
            conn.close()
    except Exception:
        return {}


def get_post_views(slug):
    """slug 하나의 조회수. 없거나 오류면 0."""
    try:
        conn = get_conn()
        try:
            row = conn.execute("SELECT views FROM post_views WHERE slug = ?", (slug,)).fetchone()
            return int(row["views"]) if row else 0
        finally:
            conn.close()
    except Exception:
        return 0


def bump_post_views(slug):
    """조회수 +1 후 새 값을 반환. 실패 시 현재값(또는 0)."""
    now = datetime.now(KST).isoformat(timespec="seconds")
    try:
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO post_views (slug, views, updated_at) VALUES (?, 1, ?) "
                "ON CONFLICT(slug) DO UPDATE SET views = views + 1, updated_at = excluded.updated_at",
                (slug, now),
            )
            conn.commit()
            row = conn.execute("SELECT views FROM post_views WHERE slug = ?", (slug,)).fetchone()
            return int(row["views"]) if row else 0
        finally:
            conn.close()
    except Exception:
        return get_post_views(slug)


def view_recently_counted(ip, slug):
    """최근 창 안에서 이미 집계했으면 True(이번엔 카운트 생략). 오래된 항목은 정리."""
    key = (ip or "unknown") + "|" + slug
    now = time.time()
    with _view_lock:
        last = _view_seen.get(key, 0)
        if now - last < VIEW_DEDUP_SEC:
            return True
        _view_seen[key] = now
        if len(_view_seen) > 5000:
            for k in [k for k, t in list(_view_seen.items()) if now - t >= VIEW_DEDUP_SEC]:
                _view_seen.pop(k, None)
    return False


# ------------------------------------------------ SSR (크롤러 대비 서버 렌더링)
# 홈(index.html)의 칼럼 목록과 본문(post.html)은 원래 자바스크립트로 그려져,
# JS를 실행하지 않는 크롤러(특히 네이버 Yeti)는 빈 페이지로 인식한다.
# 아래 함수들은 posts.json 내용을 HTML에 미리 심어 크롤러도 읽게 한다.
# (브라우저에서는 blog.js가 같은 내용을 다시 그려 검색·필터 기능이 그대로 동작한다.)
INDEX_PATH = os.path.join(BASE_DIR, "index.html")
POST_TEMPLATE_PATH = os.path.join(BASE_DIR, "post.html")
RESOURCES_PATH = os.path.join(BASE_DIR, "resources.html")
SITE_ORIGIN = CANONICAL_URL


def _read_text(path):
    with open(path, encoding="utf-8") as fp:
        return fp.read()


def _esc_html(s):
    return (
        str("" if s is None else s)
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;").replace("'", "&#39;")
    )


def _fmt_date(iso):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(iso or ""))
    return (m.group(1) + "." + m.group(2) + "." + m.group(3) + ".") if m else _esc_html(iso)


# 세목(첫 태그) → 제목 앞 이모지. blog.js 의 TAG_EMOJI 와 동일하게 유지할 것.
POST_TAG_EMOJI = {
    "법인세": "🏢", "소득세": "💰", "부가가치세": "🧾", "조세특례제한법": "🎯",
    "양도소득세": "🏠", "상속세": "👪", "증여세": "🎁", "취득세": "🏗️",
    "원천세": "💵", "연말정산": "🧮", "노동법": "👷", "지방세": "🏛️",
    "국세기본법": "⚖️", "4대보험": "🛡️",
}


def _post_emoji(post):
    for t in (post.get("tags") or []):
        if t in POST_TAG_EMOJI:
            return POST_TAG_EMOJI[t]
    return "📄"


def _render_post_cards(posts, views=None):
    """홈·허브 칼럼 목록(리스트형): 이모지+제목(2~3줄) · 세목 · 작성일자."""
    out = []
    for p in posts:
        href = "/column/" + quote(p.get("slug", ""), safe="")
        tagtxt = " · ".join(p.get("tags") or [])
        out.append(
            '<li class="post-row"><a class="post-row__link" href="' + href + '">'
            + '<span class="post-row__title"><span class="post-row__emoji" aria-hidden="true">'
            + _post_emoji(p) + "</span>" + _esc_html(p.get("title")) + "</span>"
            + '<span class="post-row__meta">'
            + (('<span class="post-row__tags">' + _esc_html(tagtxt) + "</span>") if tagtxt else "")
            + '<time class="post-row__date" datetime="' + _esc_html(p.get("date")) + '">'
            + _fmt_date(p.get("date")) + "</time></span></a></li>"
        )
    return "".join(out)


def _render_hub_chips(active_slug=None, posts=None):
    """세목별 허브로 이동하는 칩 내비게이션(각 칩에 칼럼 수 표기).
    맨 앞 '전체 세무이야기' 칩은 홈 전체 목록(/)으로 연결한다."""
    if posts is None:
        posts = load_posts().get("posts", [])
    parts = ['<nav class="hub-chips" aria-label="세목별 대표 페이지">']
    # 전체 세무이야기(홈 전체 목록). 홈(active_slug=None)에서는 활성 표시.
    all_active = active_slug is None
    parts.append(
        '<a class="hub-chip%s" href="/"%s>전체 세무이야기 <span class="hub-chip__n">%d</span></a>' % (
            " is-active" if all_active else "",
            ' aria-current="page"' if all_active else "",
            len(posts),
        )
    )
    for h in HUBS:
        active = (h["slug"] == active_slug)
        parts.append(
            '<a class="hub-chip%s" href="/%s"%s>%s <span class="hub-chip__n">%d</span></a>' % (
                " is-active" if active else "",
                h["slug"],
                ' aria-current="page"' if active else "",
                _esc_html(h["title"]),
                len(_hub_posts(h, posts)),
            )
        )
    parts.append("</nav>")
    return "".join(parts)


def _render_index_html():
    """홈 HTML의 자리표시자를 실제 칼럼 목록으로 치환해 반환."""
    html = _read_text(INDEX_PATH)
    posts = load_posts().get("posts", [])
    if not posts:
        return html
    views = get_views_map()
    # 1) 메인 카드 그리드
    html = html.replace(
        '<li class="post-grid__loading">칼럼을 불러오는 중입니다…</li>',
        _render_post_cards(posts, views),
        1,
    )
    # 2) 숨김 처리된 '아직 등록된 칼럼이 없습니다.' 문구 제거
    #    (hidden 속성만으로는 텍스트 크롤러가 본문으로 읽어감. 칼럼이 있으므로 비운다)
    html = html.replace(">아직 등록된 칼럼이 없습니다.</p>", "></p>", 1)
    # 3) 세목별 허브 칩 + 공용 스타일 삽입(칼럼 목록 위, 크롤러 내부링크 제공)
    home_hub = (
        '<div class="hub-home"><p class="hub-home__title">세목별로 모아 보기</p>'
        + _render_hub_chips(None, posts) + "</div>"
    )
    html = html.replace(
        '<ul class="post-list" id="blogList"',
        home_hub + '<ul class="post-list" id="blogList"',
        1,
    )
    html = html.replace("</head>", HUB_INLINE_CSS + "</head>", 1)
    return html


def _render_file_items(files):
    out = []
    for f in files:
        ext = (f.get("ext") or "").upper() or "FILE"
        href = "/files/" + quote(f.get("name", ""), safe="")
        meta = " · ".join(x for x in [ext, f.get("size_text"), _fmt_date(f.get("modified"))] if x)
        out.append(
            '<li class="file-item">'
            + '<span class="file-item__ext" aria-hidden="true">' + _esc_html(ext) + "</span>"
            + '<div class="file-item__body">'
            + '<span class="file-item__title">' + _esc_html(f.get("title")) + "</span>"
            + '<span class="file-item__meta">' + _esc_html(meta) + "</span>"
            + "</div>"
            + '<a class="btn btn--primary btn--sm file-item__dl" href="' + href + '" download>다운로드</a>'
            + "</li>"
        )
    return "".join(out)


def _render_resources_html():
    """자료실 HTML의 자리표시자를 실제 파일 목록으로 치환해 반환."""
    html = _read_text(RESOURCES_PATH)
    files = list_files()
    if not files:
        return html
    html = html.replace(
        '<li class="file-list__state" id="fileLoading">자료를 불러오는 중입니다…</li>',
        _render_file_items(files),
        1,
    )
    html = html.replace(">등록된 자료가 없습니다.</p>", "></p>", 1)
    return html


def _file_lastmod(path):
    """파일 수정일(YYYY-MM-DD, KST). 없으면 None."""
    try:
        return datetime.fromtimestamp(os.path.getmtime(path), KST).strftime("%Y-%m-%d")
    except OSError:
        return None


HUB_TEMPLATE_PATH = os.path.join(BASE_DIR, "hub.html")


def _render_hub_html(hub_slug):
    """세목별 허브 페이지: 소개문 + 해당 칼럼 카드 목록 + 고유 SEO 메타·구조화데이터."""
    hub = HUB_BY_SLUG.get(hub_slug)
    if not hub:
        raise KeyError(hub_slug)
    html = _read_text(HUB_TEMPLATE_PATH)
    posts = load_posts().get("posts", [])
    members = _hub_posts(hub, posts)
    views = get_views_map()
    canonical = SITE_ORIGIN + "/" + hub_slug
    full_title = _esc_html(hub["title"]) + " | 세무 칼럼 · 세무법인 지율"
    desc = _esc_html(hub["desc"])
    cards = _render_post_cards(members, views)
    if not members:
        cards = '<li class="post-grid__empty" style="list-style:none;color:#5b6b7f">이 주제의 칼럼을 준비 중입니다.</li>'

    ld_collection = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": hub["title"], "description": hub["desc"], "url": canonical,
        "isPartOf": {"@type": "WebSite", "name": "세무법인 지율", "url": SITE_ORIGIN + "/"},
        "hasPart": [
            {"@type": "Article", "headline": p.get("title"),
             "url": SITE_ORIGIN + "/column/" + quote(p.get("slug", ""), safe="")}
            for p in members
        ],
    }
    ld_bc = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "세무칼럼", "item": SITE_ORIGIN + "/"},
            {"@type": "ListItem", "position": 2, "name": hub["title"], "item": canonical},
        ],
    }
    jsonld = (
        '<script type="application/ld+json">' + json.dumps(ld_collection, ensure_ascii=False) + "</script>"
        + '<script type="application/ld+json">' + json.dumps(ld_bc, ensure_ascii=False) + "</script>"
    )

    for token, value in (
        ("{{HUB_FULL_TITLE}}", full_title),
        ("{{HUB_DESC}}", desc),
        ("{{HUB_CANONICAL}}", _esc_html(canonical)),
        ("{{HUB_TITLE}}", _esc_html(hub["title"])),
        ("{{HUB_LEAD}}", _esc_html(hub["lead"])),
        ("{{HUB_COUNT}}", str(len(members))),
        ("{{HUB_CHIPS}}", _render_hub_chips(hub_slug, posts)),
        ("{{HUB_CARDS}}", cards),
        ("{{HUB_CSS}}", HUB_INLINE_CSS),
        ("{{HUB_JSONLD}}", jsonld),
    ):
        html = html.replace(token, value)
    return html


def _render_sitemap_xml():
    """posts.json 기준으로 sitemap.xml 을 매번 생성(새 칼럼 자동 포함)."""
    o = SITE_ORIGIN
    posts = load_posts().get("posts", [])
    post_dates = [p.get("date") for p in posts if p.get("date")]
    home_mod = max(post_dates) if post_dates else _file_lastmod(INDEX_PATH)

    # 고정 페이지 (loc, changefreq, priority, lastmod)
    entries = [
        (o + "/", "weekly", "1.0", home_mod),
        (o + "/intro.html", "monthly", "0.9", _file_lastmod(os.path.join(BASE_DIR, "intro.html"))),
        (o + "/resources.html", "monthly", "0.7", _file_lastmod(RESOURCES_PATH)),
        (o + "/faq.html", "monthly", "0.7", _file_lastmod(os.path.join(BASE_DIR, "faq.html"))),
        (o + "/contact.html", "monthly", "0.8", _file_lastmod(os.path.join(BASE_DIR, "contact.html"))),
        (o + "/media.html", "monthly", "0.6", _file_lastmod(os.path.join(BASE_DIR, "media.html"))),
    ]
    # 세목별 허브(대표 페이지) — 홈 다음가는 우선순위
    for h in HUBS:
        entries.append((o + "/" + h["slug"], "weekly", "0.8", home_mod))
    # 칼럼(동적)
    for p in posts:
        slug = p.get("slug", "")
        if not slug:
            continue
        entries.append(
            (o + "/column/" + quote(slug, safe=""), "yearly", "0.6", p.get("date"))
        )

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, freq, pri, mod in entries:
        lines.append("  <url>")
        lines.append("    <loc>" + _esc_html(loc) + "</loc>")
        if mod:
            lines.append("    <lastmod>" + _esc_html(mod) + "</lastmod>")
        lines.append("    <changefreq>" + freq + "</changefreq>")
        lines.append("    <priority>" + pri + "</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def _related_posts(post, posts, n=2):
    """태그 공유가 많은 순으로 관련 칼럼 n편(동점·부족 시 최신순)."""
    cur = set(post.get("tags") or [])
    cur_slug = post.get("slug")
    others = [q for q in posts if q.get("slug") != cur_slug]
    others.sort(key=lambda q: (len(cur & set(q.get("tags") or [])), q.get("date", "")), reverse=True)
    return others[:n]


def _render_related(p, posts):
    """칼럼 하단 '함께 읽으면 좋은 칼럼': 관련 칼럼 2편(제목+세목태그) + 네이버 블로그 링크."""
    items = ""
    for r in _related_posts(p, posts, 2):
        rtags = " · ".join(r.get("tags") or [])
        items += (
            '<li class="related__item"><a class="related__link" href="/column/'
            + quote(r.get("slug", ""), safe="") + '">' + _esc_html(r.get("title")) + "</a>"
            + (('<span class="related__tags">' + _esc_html(rtags) + "</span>") if rtags else "")
            + "</li>"
        )
    naver = p.get("source") or "https://blog.naver.com/taxin4u"
    items += (
        '<li class="related__blog"><a href="' + _esc_html(naver)
        + '" target="_blank" rel="noopener noreferrer">네이버 블로그에서 더 많은 세무 칼럼 보기 →</a></li>'
    )
    return (
        '<section class="related" aria-label="함께 읽으면 좋은 칼럼">'
        '<h2 class="related__title">📚 함께 읽으면 좋은 칼럼</h2>'
        '<ul class="related__list">' + items + "</ul></section>"
    )


def _render_article(p, posts=None):
    slug_source = p.get("source")
    tags = "".join(
        '<a class="post-card__tag" href="/">' + _esc_html(t) + "</a>"
        for t in (p.get("tags") or [])
    )
    date = p.get("date")
    hub = _primary_hub_for(p)
    breadcrumb = (
        '<nav class="hub-breadcrumb" aria-label="위치"><a href="/">세무칼럼</a> › '
        '<a href="/' + hub["slug"] + '">' + _esc_html(hub["title"]) + "</a></nav>"
    ) if hub else ""
    related = _render_related(p, posts) if posts else ""
    return (
        '<nav class="article__back"><a href="/">← 칼럼 목록</a></nav>'
        + breadcrumb
        + '<header class="article__head">'
        + (('<div class="post-card__tags">' + tags + "</div>") if tags else "")
        + '<h1 class="article__title">' + _esc_html(p.get("title")) + "</h1>"
        + '<div class="article__meta"><time datetime="' + _esc_html(date) + '">' + _fmt_date(date) + "</time>"
        + '<span class="article__author">세무법인 지율 · 손창용 세무사</span></div>'
        + "</header>"
        + '<div class="article__body prose">' + (p.get("content_html") or "") + "</div>"
        + related
        + '<footer class="article__foot">'
        + '<a class="btn btn--outline btn--sm" href="/">← 칼럼 목록으로 바로 가기</a> '
        + (
            (
                '<a class="btn btn--outline btn--sm" href="' + _esc_html(slug_source)
                + '" target="_blank" rel="noopener noreferrer">네이버 블로그에서 더 보기</a> '
            )
            if slug_source
            else ""
        )
        + '<a class="btn btn--primary btn--sm" href="/contact.html"><span class="only-pc">강의요청 및 상담문의하기</span><span class="only-mo">상담 문의하기</span></a>'
        + "</footer>"
    )


def _render_post_html(slug):
    """post.html 템플릿에 해당 칼럼의 제목·메타·본문·구조화데이터를 심어 반환."""
    html = _read_text(POST_TEMPLATE_PATH)
    all_posts = load_posts().get("posts", [])
    post = None
    for p in all_posts:
        if p.get("slug") == slug:
            post = p
            break
    if not post:
        return html  # 알 수 없는 slug: 템플릿 그대로(브라우저 JS가 안내 메시지 표시)

    title = post.get("title") or "세무 칼럼"
    summary = post.get("summary") or "세무법인 지율 손창용 세무사의 세무 칼럼."
    canonical = SITE_ORIGIN + "/column/" + quote(slug, safe="")
    desc = _esc_html(summary)
    full_title = _esc_html(title) + " | 세무 칼럼 · 세무법인 지율"

    replacements = [
        ("<title>세무 칼럼 | 세무법인 지율</title>", "<title>" + full_title + "</title>"),
        (
            '<meta name="description" content="세무법인 지율 손창용 세무사의 세무 칼럼." />',
            '<meta name="description" content="' + desc + '" />',
        ),
        (
            '<link rel="canonical" href="https://taxin4u.com/post.html" id="canonicalLink" />',
            '<link rel="canonical" href="' + canonical + '" id="canonicalLink" />',
        ),
        (
            '<meta property="og:title" content="세무 칼럼 | 세무법인 지율" id="ogTitle" />',
            '<meta property="og:title" content="' + _esc_html(title) + ' | 세무법인 지율" id="ogTitle" />',
        ),
        (
            '<meta property="og:description" content="세무법인 지율 손창용 세무사의 세무 칼럼." id="ogDesc" />',
            '<meta property="og:description" content="' + desc + '" id="ogDesc" />',
        ),
        (
            '<meta property="og:url" content="https://taxin4u.com/post.html" id="ogUrl" />',
            '<meta property="og:url" content="' + canonical + '" id="ogUrl" />',
        ),
    ]
    for old, new in replacements:
        html = html.replace(old, new, 1)

    ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": summary,
        "author": {"@type": "Person", "name": "손창용", "jobTitle": "대표 세무사"},
        "publisher": {"@type": "Organization", "name": "세무법인 지율"},
        "mainEntityOfPage": canonical,
        "url": canonical,
        "image": SITE_ORIGIN + "/assets/images/og.png?v=4",
    }
    if post.get("date"):
        ld["datePublished"] = post["date"]
    ld_tag = '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False) + "</script>\n</head>"
    html = html.replace("</head>", ld_tag, 1)
    # 브레드크럼 스타일(허브 공용 CSS) 주입
    html = html.replace("</head>", HUB_INLINE_CSS + "</head>", 1)

    marker = '<p class="article__loading" id="articleLoading">칼럼을 불러오는 중입니다…</p>'
    return html.replace(marker, _render_article(post, all_posts), 1)


# ---------------------------------------------------------------- handler
class Handler(SimpleHTTPRequestHandler):
    server_version = "JiyulLanding/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    # ---- helpers
    def _send_json(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_xml(self, xml, status=200):
        body = xml.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None, "bad_length"
        if length <= 0:
            return None, "empty_body"
        if length > MAX_BODY_BYTES:
            return None, "body_too_large"
        raw = self.rfile.read(length)
        try:
            # utf-8-sig: tolerate a leading BOM from some clients
            data = json.loads(raw.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None, "invalid_json"
        if not isinstance(data, dict):
            return None, "invalid_json"
        return data, None

    def _is_admin(self, query):
        if not ADMIN_TOKEN:
            return False
        header_token = (self.headers.get("X-Admin-Token") or "").strip()
        query_token = (query.get("token", [""])[0] or "").strip()
        return header_token == ADMIN_TOKEN or query_token == ADMIN_TOKEN

    def _is_admin_session(self):
        """로그인 쿠키로 관리자 인증."""
        if not ADMIN_TOKEN:
            return False
        raw = self.headers.get("Cookie", "")
        if not raw:
            return False
        try:
            jar = http.cookies.SimpleCookie()
            jar.load(raw)
            m = jar.get(ADMIN_COOKIE)
            return bool(m) and m.value == _admin_cookie_value()
        except Exception:  # noqa: BLE001
            return False

    def _https(self):
        return (self.headers.get("X-Forwarded-Proto", "").lower() == "https")

    def _send_redirect(self, location, set_cookie=None):
        self.send_response(303)
        self.send_header("Location", location)
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _admin_cookie_header(self, logout=False):
        attrs = "; HttpOnly; SameSite=Lax; Path=/"
        if self._https():
            attrs += "; Secure"
        if logout:
            return ADMIN_COOKIE + "=; Max-Age=0" + attrs
        return ADMIN_COOKIE + "=" + _admin_cookie_value() + "; Max-Age=2592000" + attrs

    def _client_ip(self):
        # 프록시(Cloudflare/Cloudtype) 뒤에서는 원 IP가 헤더에 온다.
        for h in ("CF-Connecting-IP", "X-Forwarded-For", "X-Real-IP"):
            v = self.headers.get(h)
            if v:
                return v.split(",")[0].strip()
        return self.client_address[0] if self.client_address else "unknown"

    def _track_visit(self, parsed):
        """컨텐츠 페이지(/, *.html, /column/<slug>) GET만 방문 통계에 집계."""
        p = parsed.path
        is_page = (p == "/" or p.endswith(".html") or re.match(r"^/column/[A-Za-z0-9\-_]+$", p)
                   or p.strip("/") in HUB_BY_SLUG)
        if not is_page:
            return
        record_visit(p, self._client_ip(), self.headers.get("User-Agent", ""),
                     self.headers.get("Referer", ""))

    def _canonical_redirect(self):
        """www / .co.kr 등 비대표 호스트 → 대표 도메인으로 301. 처리 시 True."""
        host = (self.headers.get("Host") or "").split(":")[0].strip().lower()
        if host in REDIRECT_HOSTS:
            self.send_response(301)
            self.send_header("Location", CANONICAL_URL + self.path)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return True
        return False

    def end_headers(self):
        # light hardening for the static responses as well
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        super().end_headers()

    # ---- routes
    def do_POST(self):
        if self._canonical_redirect():
            return
        parsed = urlparse(self.path)

        # ---- 관리자 로그인 (비밀번호 → 쿠키) ----
        if parsed.path == "/admin/login":
            if not ADMIN_TOKEN:
                self._send_redirect("/admin")
                return
            pw = ""
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if 0 < length <= 4096:
                    body = self.rfile.read(length).decode("utf-8", "replace")
                    pw = (parse_qs(body).get("password", [""])[0] or "").strip()
            except Exception:  # noqa: BLE001
                pw = ""
            if pw and pw == ADMIN_TOKEN:
                self._send_redirect("/admin/stats", set_cookie=self._admin_cookie_header())
            else:
                self._send_redirect("/admin?e=1")
            return

        # ---- 세무칼럼 조회수 +1 (공개) ----
        m_view = re.match(r"^/api/posts/([A-Za-z0-9\-_]+)/view$", parsed.path)
        if m_view:
            slug = m_view.group(1)
            if not _slug_exists(slug):
                self._send_json(404, {"ok": False, "error": "post_not_found"})
                return
            if view_recently_counted(self._client_ip(), slug):
                # 최근에 이미 집계 — 현재값만 돌려주고 증가시키지 않음
                self._send_json(200, {"ok": True, "slug": slug, "views": get_post_views(slug), "counted": False})
                return
            self._send_json(200, {"ok": True, "slug": slug, "views": bump_post_views(slug), "counted": True})
            return

        if parsed.path != "/api/leads":
            self._send_json(404, {"ok": False, "error": "not_found"})
            return

        if rate_limited(self._client_ip()):
            self._send_json(429, {"ok": False, "error": "rate_limited"})
            return

        payload, err = self._read_json()
        if err:
            self._send_json(400, {"ok": False, "error": err})
            return

        fields, errors = validate_payload(payload)
        if errors:
            self._send_json(422, {"ok": False, "error": "validation_failed", "fields": errors})
            return

        try:
            receipt_no = insert_lead(fields)
        except Exception as exc:  # noqa: BLE001 - surface as a generic 500
            self.log_error("insert_lead failed: %s", exc)
            self._send_json(500, {"ok": False, "error": "storage_failed"})
            return

        self._send_json(201, {"ok": True, "receipt_no": receipt_no})

    def do_PATCH(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        match = re.match(r"^/api/leads/(\d+)$", parsed.path)
        if not match:
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        if not self._is_admin(query):
            self._send_json(401, {"ok": False, "error": "unauthorized"})
            return

        payload, err = self._read_json()
        if err:
            self._send_json(400, {"ok": False, "error": err})
            return

        sets, values = [], []
        if "status" in payload:
            status = _clean(payload.get("status"), 20)
            if status not in ALLOWED_STATUS:
                self._send_json(422, {"ok": False, "error": "status_invalid"})
                return
            sets.append("status = ?")
            values.append(status)
        if "assignee" in payload:
            sets.append("assignee = ?")
            values.append(_clean(payload.get("assignee"), 80) or None)
        if "memo" in payload:
            sets.append("memo = ?")
            values.append(_clean(payload.get("memo"), 2000) or None)

        if not sets:
            self._send_json(422, {"ok": False, "error": "nothing_to_update"})
            return

        values.append(int(match.group(1)))
        conn = get_conn()
        try:
            cur = conn.execute("UPDATE leads SET " + ", ".join(sets) + " WHERE id = ?", values)
            conn.commit()
        finally:
            conn.close()

        if cur.rowcount == 0:
            self._send_json(404, {"ok": False, "error": "lead_not_found"})
            return
        self._send_json(200, {"ok": True})

    def do_GET(self):
        if self._canonical_redirect():
            return
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        # 방문 통계 집계(컨텐츠 페이지 GET). 서비스에 영향 없이 조용히 기록.
        self._track_visit(parsed)

        # ---- 관리자: 로그인 페이지 / 로그아웃 / 대시보드 ----
        if parsed.path in ("/admin", "/admin/", "/admin/login"):
            if not ADMIN_TOKEN:
                self._send_html(
                    "<!doctype html><meta charset=utf-8><body style='font-family:sans-serif;padding:24px;color:#1F2937'>"
                    "<h2>관리자 페이지 비활성</h2><p>서버에 <code>JIYUL_ADMIN_TOKEN</code> 환경변수를 설정하면 활성화됩니다.</p></body>"
                )
                return
            if self._is_admin_session() or self._is_admin(query):
                self._send_redirect("/admin/stats")
                return
            self._send_html(render_login_html(error=(query.get("e", [""])[0] == "1")))
            return

        if parsed.path == "/admin/logout":
            self._send_redirect("/admin", set_cookie=self._admin_cookie_header(logout=True))
            return

        if parsed.path == "/admin/stats":
            if not ADMIN_TOKEN:
                self._send_html(
                    "<!doctype html><meta charset=utf-8><body style='font-family:sans-serif;padding:24px;color:#1F2937'>"
                    "<h2>관리자 페이지 비활성</h2><p>서버에 <code>JIYUL_ADMIN_TOKEN</code> 환경변수를 설정하면 활성화됩니다.</p></body>"
                )
                return
            # 세션 쿠키 또는 ?token= (기존 방식 호환)
            if not (self._is_admin_session() or self._is_admin(query)):
                self._send_redirect("/admin")
                return
            self._send_html(render_stats_html(build_stats(30)))
            return

        # ---- 방문 통계 내보내기 (토큰 필요, 스냅샷 백업용) ----
        if parsed.path == "/api/stats":
            if not self._is_admin(query):
                self._send_json(401, {"ok": False, "error": "unauthorized"})
                return
            self._send_json(200, {"ok": True, "stats": export_stats()})
            return

        if parsed.path in ("/api/leads", "/api/leads.csv"):
            if not self._is_admin(query):
                self._send_json(401, {"ok": False, "error": "unauthorized"})
                return
            rows = self._fetch_leads(query)
            if parsed.path == "/api/leads":
                self._send_json(200, {"ok": True, "count": len(rows), "leads": rows})
            else:
                self._send_csv(rows)
            return

        # ---- 세무칼럼 (공개) ----
        if parsed.path == "/api/posts":
            data = load_posts()
            try:
                limit = int(query.get("limit", ["0"])[0])
            except ValueError:
                limit = 0
            tag = (query.get("tag", [""])[0] or "").strip()
            items = data.get("posts", [])
            if tag:
                items = [p for p in items if tag in p.get("tags", [])]
            # 목록에서는 본문 HTML 제외 (가벼운 응답)
            listed = [{k: v for k, v in p.items() if k != "content_html"} for p in items]
            if limit > 0:
                listed = listed[:limit]
            views = get_views_map()
            for p in listed:
                p["views"] = int(views.get(p.get("slug"), 0))
            self._send_json(200, {"ok": True, "count": len(listed), "posts": listed})
            return

        m_post = re.match(r"^/api/posts/([A-Za-z0-9\-_]+)$", parsed.path)
        if m_post:
            data = load_posts()
            slug = m_post.group(1)
            for p in data.get("posts", []):
                if p.get("slug") == slug:
                    post = dict(p)  # 캐시 원본 보존
                    post["views"] = get_post_views(slug)
                    self._send_json(200, {"ok": True, "post": post})
                    return
            self._send_json(404, {"ok": False, "error": "post_not_found"})
            return

        # ---- 자료실 파일 목록 (공개) ----
        if parsed.path == "/api/files":
            self._send_json(200, {"ok": True, "files": list_files()})
            return

        # ---- 언론·강의 영상 목록 (공개) ----
        if parsed.path == "/api/media":
            self._send_json(200, {"ok": True, "media": load_media()})
            return

        # ---- 조회수 내보내기 (공개, 이미 카드에 노출되는 비민감 데이터) : 스냅샷 백업용 ----
        if parsed.path == "/api/views":
            self._send_json(200, {"ok": True, "views": get_views_map()})
            return

        if parsed.path.startswith("/api/"):
            self._send_json(404, {"ok": False, "error": "not_found"})
            return

        # ---- 자료실 다운로드 (공개, 첨부 강제 · 경로조작 차단, 목록 노출 금지) ----
        if parsed.path in ("/files", "/files/"):
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        if parsed.path.startswith("/files/"):
            self._serve_download(unquote(parsed.path[len("/files/"):]))
            return

        # ---- 크롤러 대비 서버 렌더링(SSR): 홈 칼럼 목록·칼럼 본문을 HTML에 미리 심어 응답 ----
        # 실패 시에는 정적 파일을 그대로 서빙(브라우저 JS가 렌더)하여 사이트가 끊기지 않게 한다.
        if parsed.path in ("/", "/index.html"):
            try:
                self._send_html(_render_index_html())
                return
            except Exception as exc:  # noqa: BLE001
                self.log_error("SSR index failed: %s", exc)
        # ---- 옛 자동생성 slug → 정리된 slug 301 (링크·색인 보존) ----
        m_alias = re.match(r"^/column/([A-Za-z0-9\-_]+)$", parsed.path)
        if m_alias and m_alias.group(1) in SLUG_REDIRECTS:
            self.send_response(301)
            self.send_header("Location", "/column/" + quote(SLUG_REDIRECTS[m_alias.group(1)], safe=""))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        # ---- 칼럼 본문: 경로형 /column/<slug> (대표 주소) ----
        m_col = re.match(r"^/column/([A-Za-z0-9\-_]+)$", parsed.path)
        if m_col:
            try:
                self._send_html(_render_post_html(m_col.group(1)))
                return
            except Exception as exc:  # noqa: BLE001
                self.log_error("SSR column failed: %s", exc)
        # ---- 옛 주소 /post.html?slug=X → /column/X 301 (기존 색인·링크 보존) ----
        if parsed.path == "/post.html":
            slug = (query.get("slug", [""])[0] or "").strip()
            target = ("/column/" + quote(slug, safe="")) if re.match(r"^[A-Za-z0-9\-_]+$", slug) else "/"
            self.send_response(301)
            self.send_header("Location", target)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if parsed.path == "/resources.html":
            try:
                self._send_html(_render_resources_html())
                return
            except Exception as exc:  # noqa: BLE001
                self.log_error("SSR resources failed: %s", exc)
        # ---- 세목별 허브(대표) 페이지: /corporate-tax, /tax-credit 등 ----
        m_hub = re.match(r"^/([a-z0-9-]+)$", parsed.path)
        if m_hub and m_hub.group(1) in HUB_REDIRECTS:
            self.send_response(301)
            self.send_header("Location", "/" + HUB_REDIRECTS[m_hub.group(1)])
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if m_hub and m_hub.group(1) in HUB_BY_SLUG:
            try:
                self._send_html(_render_hub_html(m_hub.group(1)))
                return
            except Exception as exc:  # noqa: BLE001
                self.log_error("SSR hub failed: %s", exc)
        if parsed.path == "/sitemap.xml":
            try:
                self._send_xml(_render_sitemap_xml())
                return
            except Exception as exc:  # noqa: BLE001
                self.log_error("sitemap generation failed: %s", exc)
                # 실패 시 정적 sitemap.xml 파일로 폴백

        super().do_GET()

    def _serve_download(self, name):
        """files/ 폴더의 파일을 첨부(다운로드)로 전송. 경로 조작 차단."""
        safe = os.path.basename(name)
        if (not safe) or safe != name or safe.startswith(".") or safe.startswith("_"):
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        real = os.path.realpath(os.path.join(FILES_DIR, safe))
        root = os.path.realpath(FILES_DIR)
        if os.path.commonpath([real, root]) != root or not os.path.isfile(real):
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        try:
            with open(real, "rb") as fp:
                data = fp.read()
        except OSError:
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", "attachment; filename*=UTF-8''%s" % quote(safe))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _fetch_leads(self, query):
        status = (query.get("status", [""])[0] or "").strip()
        try:
            limit = min(max(int(query.get("limit", ["200"])[0]), 1), 1000)
        except ValueError:
            limit = 200

        sql = "SELECT * FROM leads"
        args = []
        if status:
            sql += " WHERE status = ?"
            args.append(status)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)

        conn = get_conn()
        try:
            return [dict(r) for r in conn.execute(sql, args).fetchall()]
        finally:
            conn.close()

    def _send_csv(self, rows):
        cols = [
            "id", "created_at", "receipt_no", "name", "company", "phone", "email",
            "inquiry_type", "message", "privacy_agreed", "agreed_at",
            "status", "assignee", "memo", "source",
        ]
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\r\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        body = ("﻿" + buf.getvalue()).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="leads.csv"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # ASCII only, so a cp949 console cannot break logging
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))


# ---------------- 노션 자동 동기화 (매주 월요일 05:00 KST) ----------------
def _seconds_until_monday_5am():
    now = datetime.now(KST)
    days_ahead = (0 - now.weekday()) % 7          # 월요일 = 0
    target = now.replace(hour=5, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
    if target <= now:
        target += timedelta(days=7)
    return (target - now).total_seconds()


def _notion_sync_loop():
    import sync_notion
    while True:
        wait = _seconds_until_monday_5am()
        print("[notion-sync] 다음 동기화까지 %d시간 대기" % int(wait // 3600), flush=True)
        time.sleep(wait)
        try:
            n = sync_notion.sync()
            print("[notion-sync] 완료: 칼럼 %d건 반영" % n, flush=True)
        except Exception as e:                      # 실패해도 서버·기존 글 유지
            print("[notion-sync] 실패(기존 글 유지): %s" % e, flush=True)
        time.sleep(120)                             # 같은 시각 중복 발화 방지


def start_notion_sync():
    """서버측 주간 동기화. 무료 플랜은 서버 절전·디스크 초기화로 불안정하므로 기본 비활성.
    노션 동기화는 GitHub Actions(주간 크론)가 담당한다. JIYUL_SERVER_SYNC=1 이면 활성화."""
    if os.environ.get("JIYUL_SERVER_SYNC", "").strip() != "1":
        print("  sync  : 서버측 동기화 비활성(기본) — 노션 동기화는 GitHub Actions가 처리")
        return
    if not os.environ.get("NOTION_TOKEN", "").strip():
        print("  sync  : disabled (NOTION_TOKEN 미설정)")
        return
    threading.Thread(target=_notion_sync_loop, daemon=True).start()
    print("  sync  : 서버측 주간 동기화 활성화 (JIYUL_SERVER_SYNC=1)")


def main():
    # Windows 콘솔(cp949)에서도 한글 로그가 깨지지 않도록
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    # 로컬 기본은 127.0.0.1(안전). 클라우드 배포 시 HOST=0.0.0.0, PORT 는 플랫폼이 주입.
    host = os.environ.get("HOST", "127.0.0.1")
    # PORT 가 비어있거나 숫자가 아니면 8080 으로 안전하게 대체
    # (일부 플랫폼이 PORT 를 빈 값으로 주입하면 int() 에서 크래시 → 컨테이너 재시작 루프)
    _port_env = (os.environ.get("PORT") or "").strip()
    port = int(_port_env) if _port_env.isdigit() else 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("usage: python server.py [port]")
            return 1

    try:
        init_db()
    except Exception as e:
        # DB 초기화 실패해도 사이트(정적/칼럼)는 정상 서비스. 상담 접수만 제한됨.
        print("  warn  : DB 초기화 실패(상담 접수 기능 제한) — %s" % e, flush=True)
    httpd = ThreadingHTTPServer((host, port), Handler)
    print("Jiyul landing server running")
    print("  bind  : %s:%d" % (host, port))
    print("  page  : http://%s:%d/" % (host, port))
    print("  db    : %s" % DB_PATH)
    if ADMIN_TOKEN:
        print("  admin : /api/leads?token=*** (enabled)")
    else:
        print("  admin : disabled (set JIYUL_ADMIN_TOKEN to enable /api/leads)")
    start_notion_sync()
    print("  stop  : Ctrl+C")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
