#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""연말정산 자가진단 페이지(yearend-check.html) 항목 채우기.

항목 원본: data/yearend-check/<slug>.html  (항목 하나 = 자기 <style>·<script> 를 가진 <section>)
항목 목록: data/yearend-check/items.json   (순서·slug·버튼 이름·제목·설명)
  - slug 는 공유 주소(/yearend-check/<slug>)가 되므로 한번 정하면 바꾸지 않는다.
  - title·lead 는 메신저 미리보기 제목·설명으로도 쓰인다(server.py _render_yearend_html).

yearend-check.html 의 <!-- YC:NAV --> … <!-- /YC:NAV --> 와
<!-- YC:PANES --> … <!-- /YC:PANES --> 사이만 다시 쓴다(나머지는 그대로).

사용법:  python build_yearend_check.py
"""
import html
import io
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data", "yearend-check")
PAGE = os.path.join(BASE, "yearend-check.html")

LINK_ICON = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/>'
             '<path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg>')


def load_items():
    return json.load(io.open(os.path.join(DATA, "items.json"), encoding="utf-8"))


def build():
    items = load_items()
    nav = ['      <nav class="yc-nav" aria-label="자가진단 항목">']
    for it in items:
        nav.append('        <a href="/yearend-check/%s" data-slug="%s">%s</a>'
                   % (it["slug"], it["slug"], html.escape(it["nav"])))
    nav.append("      </nav>")

    panes = ['      <div class="yc-panes">']
    for i, it in enumerate(items):
        frag = io.open(os.path.join(DATA, it["slug"] + ".html"), encoding="utf-8").read().strip()
        panes.append('      <div class="yc-pane" data-slug="%s"%s>' % (it["slug"], "" if i == 0 else " hidden"))
        panes.append('        <div class="yc-bar"><span class="yc-bar__label">자가진단 <b>%d</b> / %d</span>'
                     '<button class="yc-copy" type="button" data-slug="%s">%s 이 항목 링크 복사</button></div>'
                     % (i + 1, len(items), it["slug"], LINK_ICON))
        panes.append(frag)
        panes.append("      </div>")
    panes.append("      </div>")

    page = io.open(PAGE, encoding="utf-8").read()
    page, n1 = re.subn(r"<!-- YC:NAV -->.*?<!-- /YC:NAV -->",
                       lambda m: "<!-- YC:NAV -->\n" + "\n".join(nav) + "\n      <!-- /YC:NAV -->", page, flags=re.S)
    page, n2 = re.subn(r"<!-- YC:PANES -->.*?<!-- /YC:PANES -->",
                       lambda m: "<!-- YC:PANES -->\n" + "\n".join(panes) + "\n      <!-- /YC:PANES -->", page, flags=re.S)
    if n1 != 1 or n2 != 1:
        raise SystemExit("yearend-check.html 에서 YC:NAV / YC:PANES 표시를 찾지 못했습니다")
    io.open(PAGE, "w", encoding="utf-8", newline="\n").write(page)
    print("항목 %d개 → yearend-check.html (%.0fKB)" % (len(items), len(page.encode("utf-8")) / 1024))


if __name__ == "__main__":
    build()
