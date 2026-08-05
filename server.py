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


def init_db():
    os.makedirs(LEADS_DIR, exist_ok=True)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as fp:
        schema = fp.read()
    conn = get_conn()
    try:
        conn.executescript(schema)
        conn.commit()
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


def _render_post_cards(posts, views):
    out = []
    for p in posts:
        slug = p.get("slug", "")
        href = "post.html?slug=" + quote(slug, safe="")
        tags = "".join(
            '<span class="post-card__tag">' + _esc_html(t) + "</span>"
            for t in (p.get("tags") or [])
        )
        v = int(views.get(slug, 0) or 0)
        out.append(
            '<li class="post-card"><a class="post-card__link" href="' + href + '">'
            + (('<div class="post-card__tags">' + tags + "</div>") if tags else "")
            + '<h3 class="post-card__title">' + _esc_html(p.get("title")) + "</h3>"
            + '<p class="post-card__summary">' + _esc_html(p.get("summary")) + "</p>"
            + '<div class="post-card__meta"><span class="post-card__meta-left">'
            + '<time datetime="' + _esc_html(p.get("date")) + '">' + _fmt_date(p.get("date")) + "</time>"
            + '<span class="post-card__views" title="조회수">조회 ' + format(v, ",d") + "</span></span>"
            + '<span class="post-card__go">읽기 <span aria-hidden="true">→</span></span></div></a></li>'
        )
    return "".join(out)


def _render_quick_items(posts):
    """제목+상세링크만 담은 깔끔한 순서목록(크롤러가 목록으로 명확히 추출하도록)."""
    out = []
    for i, p in enumerate(posts, 1):
        href = "post.html?slug=" + quote(p.get("slug", ""), safe="")
        out.append(
            '<li class="quick-list__item"><a class="quick-list__link" href="' + href + '">'
            + '<span class="quick-list__no">' + str(i) + "</span>"
            + '<span class="quick-list__text">' + _esc_html(p.get("title")) + "</span>"
            + '<span class="quick-list__arrow" aria-hidden="true">→</span></a></li>'
        )
    return "".join(out)


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
    # 2) 제목+링크 목록(퀵리스트)을 채우고 노출(hidden 제거) — 크롤러의 명확한 목록 추출용
    html = html.replace(
        '<div class="quick-list" id="quickList" hidden>',
        '<div class="quick-list" id="quickList">',
        1,
    )
    html = html.replace(
        '<ol class="quick-list__items" id="quickTitles"></ol>',
        '<ol class="quick-list__items" id="quickTitles">' + _render_quick_items(posts) + "</ol>",
        1,
    )
    # 3) 숨김 처리된 '아직 등록된 칼럼이 없습니다.' 문구 제거
    #    (hidden 속성만으로는 텍스트 크롤러가 본문으로 읽어감. 칼럼이 있으므로 비운다)
    html = html.replace(">아직 등록된 칼럼이 없습니다.</p>", "></p>", 1)
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


def _render_article(p):
    slug_source = p.get("source")
    tags = "".join(
        '<a class="post-card__tag" href="index.html">' + _esc_html(t) + "</a>"
        for t in (p.get("tags") or [])
    )
    date = p.get("date")
    return (
        '<nav class="article__back"><a href="index.html">← 칼럼 목록</a></nav>'
        + '<header class="article__head">'
        + (('<div class="post-card__tags">' + tags + "</div>") if tags else "")
        + '<h1 class="article__title">' + _esc_html(p.get("title")) + "</h1>"
        + '<div class="article__meta"><time datetime="' + _esc_html(date) + '">' + _fmt_date(date) + "</time>"
        + '<span class="article__author">세무법인 지율 · 손창용 세무사</span></div>'
        + "</header>"
        + '<div class="article__body prose">' + (p.get("content_html") or "") + "</div>"
        + '<footer class="article__foot">'
        + '<a class="btn btn--outline btn--sm" href="index.html">← 칼럼 목록으로 바로 가기</a> '
        + (
            (
                '<a class="btn btn--outline btn--sm" href="' + _esc_html(slug_source)
                + '" target="_blank" rel="noopener noreferrer">네이버 블로그에서 더 보기</a> '
            )
            if slug_source
            else ""
        )
        + '<a class="btn btn--primary btn--sm" href="contact.html">상담 문의하기</a>'
        + "</footer>"
    )


def _render_post_html(slug):
    """post.html 템플릿에 해당 칼럼의 제목·메타·본문·구조화데이터를 심어 반환."""
    html = _read_text(POST_TEMPLATE_PATH)
    post = None
    for p in load_posts().get("posts", []):
        if p.get("slug") == slug:
            post = p
            break
    if not post:
        return html  # 알 수 없는 slug: 템플릿 그대로(브라우저 JS가 안내 메시지 표시)

    title = post.get("title") or "세무 칼럼"
    summary = post.get("summary") or "세무법인 지율 손창용 세무사의 세무 칼럼."
    canonical = SITE_ORIGIN + "/post.html?slug=" + quote(slug, safe="")
    desc = _esc_html(summary)
    full_title = _esc_html(title) + " | 세무 칼럼 · 세무법인 지율"

    replacements = [
        ("<title>세무 칼럼 | 세무법인 지율</title>", "<title>" + full_title + "</title>"),
        (
            '<meta name="description" content="세무법인 지율 손창용 세무사의 세무 칼럼." />',
            '<meta name="description" content="' + desc + '" />',
        ),
        (
            '<link rel="canonical" href="https://taxin4u.com/index.html" id="canonicalLink" />',
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
            '<meta property="og:url" content="https://taxin4u.com/index.html" id="ogUrl" />',
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
        "image": SITE_ORIGIN + "/assets/images/og.png?v=3",
    }
    if post.get("date"):
        ld["datePublished"] = post["date"]
    ld_tag = '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False) + "</script>\n</head>"
    html = html.replace("</head>", ld_tag, 1)

    marker = '<p class="article__loading" id="articleLoading">칼럼을 불러오는 중입니다…</p>'
    return html.replace(marker, _render_article(post), 1)


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

    def _client_ip(self):
        return self.client_address[0] if self.client_address else "unknown"

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
        if parsed.path == "/post.html":
            slug = (query.get("slug", [""])[0] or "").strip()
            if slug:
                try:
                    self._send_html(_render_post_html(slug))
                    return
                except Exception as exc:  # noqa: BLE001
                    self.log_error("SSR post failed: %s", exc)
        if parsed.path == "/resources.html":
            try:
                self._send_html(_render_resources_html())
                return
            except Exception as exc:  # noqa: BLE001
                self.log_error("SSR resources failed: %s", exc)

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
