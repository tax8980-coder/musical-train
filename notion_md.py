#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
세무법인 지율 — 세무칼럼 마크다운 → 안전한 HTML 변환기 (표준 라이브러리만 사용)

노션 '세무칼럼' 글을 내보낸 확장 마크다운 부분집합을 처리합니다.
지원: 프런트매터, 제목(#/##/###), 구분선(---), 콜아웃, 표(header-row),
      체크리스트(- [ ]/- [x]), 불릿(-), 번호목록(1.), 문단,
      인라인 **굵게** · [텍스트](URL) · `코드`.

핵심 원칙: 사용자 입력 텍스트는 항상 HTML 이스케이프한 뒤,
          우리가 생성하는 태그만 삽입 → XSS/깨짐 방지.
"""
import html
import re


# ---------- 인라인 ----------
_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_CODE_RE = re.compile(r"`([^`]+)`")


def render_inline(text):
    """인라인 서식 처리. 먼저 이스케이프한 뒤 링크/굵게/코드를 토큰 방식으로 복원."""
    text = text.strip()
    tokens = []

    def stash(html_fragment):
        tokens.append(html_fragment)
        return "\x00%d\x00" % (len(tokens) - 1)

    # 링크: [텍스트](url)
    def _link(m):
        label = html.escape(m.group(1))
        url = html.escape(m.group(2), quote=True)
        return stash('<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>' % (url, label))
    text = _LINK_RE.sub(_link, text)

    # 코드: `code`
    def _code(m):
        return stash("<code>%s</code>" % html.escape(m.group(1)))
    text = _CODE_RE.sub(_code, text)

    # 굵게: **bold**
    def _bold(m):
        return stash("<strong>%s</strong>" % html.escape(m.group(1)))
    text = _BOLD_RE.sub(_bold, text)

    # 남은 일반 텍스트 이스케이프
    text = html.escape(text)

    # 토큰 복원
    def _restore(m):
        return tokens[int(m.group(1))]
    text = re.sub(r"\x00(\d+)\x00", _restore, text)
    return text


# ---------- 프런트매터 ----------
def parse_front_matter(raw):
    meta, body = {}, raw
    if raw.startswith("---"):
        end = raw.find("\n---", 3)
        if end != -1:
            header = raw[3:end].strip("\n")
            body = raw[end + 4:].lstrip("\n")
            for line in header.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
    if "tags" in meta:
        meta["tags"] = [t.strip() for t in meta["tags"].split(",") if t.strip()]
    return meta, body


# ---------- 콜아웃 색상 ----------
_CALLOUT_CLASS = {
    "blue_bg": "callout--blue", "gray_bg": "callout--gray", "grey_bg": "callout--gray",
    "green_bg": "callout--green", "red_bg": "callout--red", "yellow_bg": "callout--yellow",
    "orange_bg": "callout--orange",
}


def _render_callout(icon, color, inner_lines):
    cls = _CALLOUT_CLASS.get(color, "callout--gray")
    parts, bullets = [], []

    def flush_bullets():
        if bullets:
            parts.append("<ul>" + "".join("<li>%s</li>" % render_inline(b) for b in bullets) + "</ul>")
            bullets.clear()

    for ln in inner_lines:
        s = ln.strip()
        if not s:
            continue
        if s.startswith("- "):
            bullets.append(s[2:])
        else:
            flush_bullets()
            parts.append("<p>%s</p>" % render_inline(s))
    flush_bullets()
    icon_html = ('<span class="callout__icon" aria-hidden="true">%s</span>' % html.escape(icon)) if icon else ""
    return '<div class="callout %s">%s<div class="callout__body">%s</div></div>' % (cls, icon_html, "".join(parts))


def _render_table(rows, header_row):
    out = ["<div class=\"table-wrap\"><table>"]
    for i, cells in enumerate(rows):
        tag = "th" if (header_row and i == 0) else "td"
        scope = ' scope="col"' if tag == "th" else ""
        out.append("<tr>" + "".join("<%s%s>%s</%s>" % (tag, scope, render_inline(c), tag) for c in cells) + "</tr>")
    out.append("</table></div>")
    return "".join(out)


# ---------- 본문 ----------
_TABLE_OPEN = re.compile(r"<table\b([^>]*)>")
_TR_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
_TD_RE = re.compile(r"<td>(.*?)</td>", re.S)
_CALLOUT_OPEN = re.compile(r'<callout\b[^>]*icon="([^"]*)"[^>]*color="([^"]*)"[^>]*>')


def render_body(body):
    lines = body.split("\n")
    html_parts = []
    i = 0
    n = len(lines)
    ul, ol, checks = [], [], []

    def flush_lists():
        if ul:
            html_parts.append("<ul>" + "".join("<li>%s</li>" % render_inline(x) for x in ul) + "</ul>")
            ul.clear()
        if ol:
            html_parts.append("<ol>" + "".join("<li>%s</li>" % render_inline(x) for x in ol) + "</ol>")
            ol.clear()
        if checks:
            items = "".join(
                '<li class="check %s"><span class="check__box" aria-hidden="true"></span>%s</li>'
                % ("is-done" if done else "", render_inline(txt)) for done, txt in checks
            )
            html_parts.append('<ul class="checklist-md">' + items + "</ul>")
            checks.clear()

    while i < n:
        line = lines[i]
        s = line.strip()

        if not s or s == "<empty-block/>":
            flush_lists(); i += 1; continue

        # 표
        mt = _TABLE_OPEN.match(s)
        if mt:
            attrs = mt.group(1)
            header_row = "header-row=\"true\"" in attrs
            buf = [line]
            while "</table>" not in lines[i] and i < n - 1:
                i += 1; buf.append(lines[i])
            block = "\n".join(buf)
            rows = []
            for tr in _TR_RE.findall(block):
                rows.append([c.strip() for c in _TD_RE.findall(tr)])
            flush_lists(); html_parts.append(_render_table(rows, header_row)); i += 1; continue

        # 콜아웃
        mc = _CALLOUT_OPEN.match(s)
        if mc:
            icon, color = mc.group(1), mc.group(2)
            inner = []
            # 같은 줄에 닫힘?
            if "</callout>" in s:
                inner_text = s[mc.end():s.find("</callout>")]
                inner = [inner_text]
            else:
                i += 1
                while i < n and "</callout>" not in lines[i]:
                    inner.append(lines[i]); i += 1
            flush_lists(); html_parts.append(_render_callout(icon, color, inner)); i += 1; continue

        # 구분선
        if s == "---":
            flush_lists(); html_parts.append("<hr />"); i += 1; continue

        # 제목 (페이지 제목이 h1 이므로 본문은 h2부터)
        if s.startswith("### "):
            flush_lists(); html_parts.append("<h4>%s</h4>" % render_inline(s[4:])); i += 1; continue
        if s.startswith("## "):
            flush_lists(); html_parts.append("<h3>%s</h3>" % render_inline(s[3:])); i += 1; continue
        if s.startswith("# "):
            flush_lists(); html_parts.append("<h2>%s</h2>" % render_inline(s[2:])); i += 1; continue

        # 체크리스트
        mck = re.match(r"- \[([ xX])\]\s+(.*)", s)
        if mck:
            if ul or ol:
                flush_lists()
            checks.append((mck.group(1).lower() == "x", mck.group(2))); i += 1; continue

        # 번호목록
        mo = re.match(r"\d+\.\s+(.*)", s)
        if mo:
            if ul or checks:
                flush_lists()
            ol.append(mo.group(1)); i += 1; continue

        # 불릿
        if s.startswith("- "):
            if ol or checks:
                flush_lists()
            ul.append(s[2:]); i += 1; continue

        # 문단
        flush_lists()
        html_parts.append("<p>%s</p>" % render_inline(s))
        i += 1

    flush_lists()
    return "\n".join(html_parts)


def convert(raw):
    """마크다운 원문 → (meta dict, content_html)."""
    meta, body = parse_front_matter(raw)
    return meta, render_body(body)


def make_excerpt(content_html, limit=140):
    text = re.sub(r"<[^>]+>", "", content_html)
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    return text[:limit] + ("…" if len(text) > limit else "")


if __name__ == "__main__":
    import sys
    meta, htmlout = convert(open(sys.argv[1], encoding="utf-8").read())
    print("META:", meta)
    print(htmlout[:1200])
