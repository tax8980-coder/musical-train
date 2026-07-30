#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
content/*.md (세무칼럼 원고) → data/posts.json 빌드.

    python build_posts.py

각 .md 파일의 프런트매터(slug/title/summary/tags/date/source)를 읽고
본문을 HTML로 변환해 data/posts.json 으로 저장합니다.
홈페이지·블로그는 이 JSON을 읽어 목록/본문을 렌더링합니다.
"""
import json
import os
import glob

from notion_md import convert, make_excerpt

BASE = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(BASE, "content")
OUT = os.path.join(BASE, "data", "posts.json")


def build():
    posts = []
    for path in sorted(glob.glob(os.path.join(CONTENT_DIR, "*.md"))):
        raw = open(path, encoding="utf-8").read()
        meta, content_html = convert(raw)
        slug = meta.get("slug") or os.path.splitext(os.path.basename(path))[0]
        title = meta.get("title", slug)
        summary = meta.get("summary") or make_excerpt(content_html)
        posts.append({
            "slug": slug,
            "title": title,
            "summary": summary,
            "tags": meta.get("tags", []),
            "date": meta.get("date", ""),
            "source": meta.get("source", ""),
            "content_html": content_html,
        })

    # 최신순 정렬 (date 문자열 기준)
    posts.sort(key=lambda p: p.get("date", ""), reverse=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump({"posts": posts, "count": len(posts)}, fp, ensure_ascii=False, indent=2)
    print("wrote %s (%d posts)" % (OUT, len(posts)))
    for p in posts:
        print("  - [%s] %s" % (p["date"], p["title"][:50]))


if __name__ == "__main__":
    build()
