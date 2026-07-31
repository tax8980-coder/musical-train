#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
노션 '세무법인 지율 · 세무칼럼' → 홈페이지 세무칼럼 자동 미러링
(Python 표준 라이브러리만 사용)

'세무칼럼' 페이지 아래의 모든 하위 글을 조건 없이(무조건) 가져와
content/*.md 로 저장하고 data/posts.json 을 다시 생성합니다.
→ 홈페이지(루트)의 세무 칼럼이 노션과 동일해집니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
■ 최초 1회 설정 (토큰)
  1) https://www.notion.so/my-integrations → 새 '내부 통합' 생성 → 토큰 복사
  2) 노션에서 '세무법인 지율 · 세무칼럼' 페이지 우상단 ⋯ → 연결(Connections)
     → 위에서 만든 통합을 추가(공유)
  3) 토큰을 시스템 환경변수로 저장 (관리자 PowerShell):
       setx NOTION_TOKEN "secret_xxxxxxxx"
     (창을 새로 열어야 반영됩니다)

■ 수동 실행
     python sync_notion.py

■ 자동 실행 (권장)
     install_sync_task.ps1 을 실행하면 Windows 작업 스케줄러에
     30분마다 도는 작업이 등록됩니다. 이후 노션에 글을 올리면
     자동으로 홈페이지에 반영됩니다.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

주의: content/ 폴더는 이 스크립트가 관리합니다(노션 미러). 직접 손으로
      편집한 .md 는 다음 동기화 때 노션 내용으로 대체될 수 있습니다.
"""
import glob
import json
import os
import re
import sys
import unicodedata
import urllib.request
import urllib.error

NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "").strip()
NOTION_VERSION = os.environ.get("NOTION_VERSION", "2022-06-28")
# 기본 소스 = '세무법인 지율 · 세무칼럼' 페이지
COLUMN_PAGE_ID = os.environ.get(
    "NOTION_COLUMN_PAGE_ID", "3ad868d0-d82c-819d-8b25-d189e0cb4963"
).strip()
DEFAULT_SOURCE = os.environ.get("NOTION_DEFAULT_SOURCE", "https://blog.naver.com/taxin4u")
API = "https://api.notion.com/v1"

# 한 번에 발행하는 칼럼 최대 개수(최신순). 0 이하면 제한 없음.
MAX_POSTS = int(os.environ.get("NOTION_MAX_POSTS", "3"))

# 기존 글의 주소(slug)를 안정적으로 유지: 노션 page id(대시 제거·소문자) → slug
# (매핑에 없는 새 글은 제목 기반 slug 자동 생성)
SLUG_MAP = {
    "3ad868d0d82c8189ab22efebcabcdcb1": "employment-credit-fulltime-worker-2026",
    "3ad868d0d82c81c2b5def9a0a4af2961": "e-filing-tax-credit-agent-2026",
    "3ad868d0d82c8115b73df48a8eeba63c": "tax-credit-carryover-merger-conversion",
    "3ad868d0d82c8145a458c87ba7ae13a0": "bad-debt-vat-credit-2year",
    "3ae868d0d82c8156a519f86bb4dfd099": "temp-2house-3house-sell-one-2024du55426",
    "3ae868d0d82c813884f8d42743be9587": "presale-right-acquisition-date-2024du54560",
}

# 모든 칼럼 상단에 넣는 공통 안내 콜아웃(노션 글에 없으면 자동 삽입)
DISCLAIMER = (
    '<callout icon="ℹ️" color="gray_bg">\n'
    '본 글은 세무법인 지율 손창용 세무사가 작성한 **참고용 일반정보**입니다. '
    '실제 의사결정 시에는 반드시 관련 세법·국세청 해석 등 공식 자료를 추가로 확인하시기 바라며, '
    '본 글만을 근거로 한 조치에 대해 작성자 및 세무법인은 책임지지 않습니다.\n'
    '</callout>'
)

BASE = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(BASE, "content")

# 세목 태그 자동 추출용 키워드(우선순위 순)
TAG_KEYWORDS = [
    "법인세", "소득세", "부가가치세", "상속세", "증여세", "양도소득세",
    "조세특례제한법", "국세기본법", "지방세", "원천세", "연말정산", "4대보험", "노동법",
]

COLOR_MAP = {
    "blue_background": "blue_bg", "gray_background": "gray_bg", "grey_background": "gray_bg",
    "green_background": "green_bg", "red_background": "red_bg",
    "yellow_background": "yellow_bg", "orange_background": "orange_bg",
    "brown_background": "gray_bg", "purple_background": "blue_bg", "pink_background": "red_bg",
    "default": "gray_bg",
}


# ---------------- HTTP ----------------
def api(method, path, body=None):
    url = path if path.startswith("http") else (API + path)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + NOTION_TOKEN)
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_children(block_id):
    out, cursor = [], None
    while True:
        q = "/blocks/%s/children?page_size=100" % block_id
        if cursor:
            q += "&start_cursor=" + cursor
        page = api("GET", q)
        out.extend(page.get("results", []))
        cursor = page.get("next_cursor")
        if not cursor:
            break
    return out


# ---------------- 리치 텍스트 / 블록 → 마크다운 ----------------
def rich_to_md(rich):
    parts = []
    for r in rich or []:
        t = r.get("plain_text", "")
        if not t:
            continue
        ann = r.get("annotations", {})
        href = r.get("href")
        if ann.get("code"):
            t = "`%s`" % t
        elif ann.get("bold"):
            t = "**%s**" % t
        if href:
            t = "[%s](%s)" % (r.get("plain_text", t), href)
        parts.append(t)
    return "".join(parts).replace("\n", " ").strip()


def plain_text(rich):
    return "".join(r.get("plain_text", "") for r in (rich or []))


def blocks_to_md(blocks):
    lines = []
    for b in blocks:
        t = b.get("type")
        d = b.get(t, {}) if t else {}

        if t == "heading_1":
            lines.append("# " + rich_to_md(d.get("rich_text")))
        elif t == "heading_2":
            lines.append("## " + rich_to_md(d.get("rich_text")))
        elif t == "heading_3":
            lines.append("### " + rich_to_md(d.get("rich_text")))
        elif t == "paragraph":
            lines.append(rich_to_md(d.get("rich_text")))
        elif t == "bulleted_list_item":
            lines.append("- " + rich_to_md(d.get("rich_text")))
        elif t == "numbered_list_item":
            lines.append("1. " + rich_to_md(d.get("rich_text")))
        elif t == "to_do":
            lines.append("- [%s] %s" % ("x" if d.get("checked") else " ", rich_to_md(d.get("rich_text"))))
        elif t == "quote":
            lines.append('<callout icon="" color="gray_bg">')
            lines.append(rich_to_md(d.get("rich_text")))
            lines.append("</callout>")
        elif t == "callout":
            icon = ""
            ic = d.get("icon") or {}
            if ic.get("type") == "emoji":
                icon = ic.get("emoji", "")
            color = COLOR_MAP.get(d.get("color", "default"), "gray_bg")
            lines.append('<callout icon="%s" color="%s">' % (icon, color))
            lines.append(rich_to_md(d.get("rich_text")))
            if b.get("has_children"):
                for c in get_children(b["id"]):
                    ct = c.get("type")
                    cd = c.get(ct, {})
                    prefix = "- " if ct in ("bulleted_list_item", "numbered_list_item") else ""
                    lines.append(prefix + rich_to_md(cd.get("rich_text")))
            lines.append("</callout>")
        elif t == "divider":
            lines.append("---")
        elif t == "code":
            lines.append('<callout icon="💻" color="gray_bg">')
            for ln in rich_to_md(d.get("rich_text")).split("\n"):
                lines.append(("`%s`" % ln) if ln else "")
            lines.append("</callout>")
        elif t == "table":
            header = d.get("has_column_header", False)
            rows = get_children(b["id"]) if b.get("has_children") else []
            lines.append('<table header-row="%s">' % ("true" if header else "false"))
            for row in rows:
                if row.get("type") != "table_row":
                    continue
                cells = row["table_row"].get("cells", [])
                lines.append("<tr>" + "".join("<td>%s</td>" % rich_to_md(c) for c in cells) + "</tr>")
            lines.append("</table>")
        elif t in ("image", "embed", "bookmark", "file"):
            url = ""
            if d.get("type") in ("external", "file"):
                url = d.get(d["type"], {}).get("url", "")
            url = url or d.get("url", "")
            cap = rich_to_md(d.get("caption")) or url
            if url:
                lines.append("[%s](%s)" % (cap, url))
        else:
            txt = rich_to_md(d.get("rich_text")) if isinstance(d, dict) else ""
            if txt:
                lines.append(txt)
        lines.append("")

    # 연속 목록 항목 사이 빈 줄 제거
    def is_list(s):
        return bool(re.match(r"^(- \[|- |\d+\. )", s))

    cleaned = []
    for i, ln in enumerate(lines):
        if ln.strip() == "":
            prev = cleaned[-1] if cleaned else ""
            nxt = next((lines[j] for j in range(i + 1, len(lines)) if lines[j].strip()), "")
            if is_list(prev) and is_list(nxt):
                continue
        cleaned.append(ln)
    return "\n".join(cleaned)


# ---------------- 메타 추출 ----------------
def derive_tags(title, blocks):
    text = title + " " + " ".join(
        plain_text(b.get(b.get("type"), {}).get("rich_text"))
        for b in blocks if isinstance(b.get(b.get("type")), dict)
    )
    tags = [kw for kw in TAG_KEYWORDS if kw in text]
    # 조특법/세액공제 언급 시 조세특례제한법 보강
    if "조세특례제한법" not in tags and ("조특" in text or "세액공제" in text):
        tags.append("조세특례제한법")
    return tags[:4]


def derive_summary(blocks, limit=140):
    for b in blocks:
        if b.get("type") == "paragraph":
            txt = plain_text(b["paragraph"].get("rich_text")).strip()
            if len(txt) >= 20:
                return (txt[:limit] + "…") if len(txt) > limit else txt
    return ""


def slugify(title, page_id):
    base = re.sub(r"[^A-Za-z0-9가-힣]+", "-", unicodedata.normalize("NFKD", title)).strip("-").lower()
    return (base[:40] or "post") + "-" + page_id.replace("-", "")[:8]


def choose_slug(title, page_id):
    """기존 글은 고정 slug 유지, 새 글은 자동 생성."""
    key = page_id.replace("-", "").lower()
    return SLUG_MAP.get(key) or slugify(title, page_id)


# ---------------- 동기화 (server.py에서도 import 하여 호출) ----------------
def sync():
    """노션 세무칼럼 → content/*.md → posts.json. 성공 시 글 수(int) 반환.
    문제 시 RuntimeError 를 던지며, 이 경우 기존 content 는 그대로 보존됩니다."""
    if not NOTION_TOKEN:
        raise RuntimeError(
            "환경변수 NOTION_TOKEN 이 설정되지 않았습니다. "
            "(로컬: setx NOTION_TOKEN \"...\" / Render: 환경변수 NOTION_TOKEN 등록)"
        )

    print("세무칼럼 페이지 하위 글 수집: %s" % COLUMN_PAGE_ID)
    try:
        top = get_children(COLUMN_PAGE_ID)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise RuntimeError(
            "노션 API 오류 %s: %s "
            "→ 통합 토큰이 맞는지, '세무칼럼' 페이지를 통합과 '연결(공유)'했는지 확인하세요." % (e.code, detail)
        )
    except urllib.error.URLError as e:
        raise RuntimeError("네트워크 오류: %s" % e)

    child_pages = [b for b in top if b.get("type") == "child_page"]
    print("하위 글 %d건 발견" % len(child_pages))

    # 먼저 메모리에 전부 변환 (실패 시 기존 content 보존)
    posts = []
    for b in child_pages:
        page_id = b["id"]
        title = b["child_page"].get("title", "제목 없음")
        try:
            body_blocks = get_children(page_id)
        except urllib.error.HTTPError as e:
            print("  · 건너뜀(조회 실패) %s" % title[:36])
            continue
        md = blocks_to_md(body_blocks)
        if "참고용 일반정보" not in md:
            md = DISCLAIMER + "\n" + md
        posts.append({
            "slug": choose_slug(title, page_id),
            "notion_id": page_id,
            "title": title,
            "summary": derive_summary(body_blocks),
            "tags": derive_tags(title, body_blocks),
            "date": (b.get("created_time", "") or "")[:10],
            "source": DEFAULT_SOURCE,
            "md": md,
        })
        print("  · OK  %s" % title[:40])

    if not posts:
        raise RuntimeError(
            "하위 글을 찾지 못했습니다. 안전을 위해 기존 content 를 변경하지 않고 종료합니다. "
            "→ '세무칼럼' 페이지에 하위 글이 있는지, 통합 공유가 되었는지 확인하세요."
        )

    # 최신순 정렬 후 최대 MAX_POSTS 개만 발행
    posts.sort(key=lambda p: p.get("date", ""), reverse=True)
    if MAX_POSTS > 0 and len(posts) > MAX_POSTS:
        print("  · 최신 %d건만 발행(전체 %d건 중)" % (MAX_POSTS, len(posts)))
        posts = posts[:MAX_POSTS]

    # 노션 미러: 기존 .md 제거 후 재생성
    os.makedirs(CONTENT_DIR, exist_ok=True)
    for old in glob.glob(os.path.join(CONTENT_DIR, "*.md")):
        if os.path.basename(old).startswith("_"):
            continue  # 템플릿 등 밑줄 파일은 보존
        os.remove(old)

    for p in posts:
        front = [
            "---",
            "slug: %s" % p["slug"],
            "notion_id: %s" % p["notion_id"],
            "title: %s" % p["title"],
            "summary: %s" % p["summary"],
            "tags: %s" % ", ".join(p["tags"]),
            "date: %s" % p["date"],
            "source: %s" % p["source"],
            "---",
        ]
        with open(os.path.join(CONTENT_DIR, p["slug"] + ".md"), "w", encoding="utf-8") as fp:
            fp.write("\n".join(front) + "\n" + p["md"] + "\n")

    print("content/ 재생성 완료 (%d건)." % len(posts))

    import build_posts
    build_posts.build()
    print("동기화 완료 — 홈페이지 새로고침 시 반영됩니다.")
    return len(posts)


def main():
    try:
        sync()
    except RuntimeError as e:
        raise SystemExit(str(e))


if __name__ == "__main__":
    main()
