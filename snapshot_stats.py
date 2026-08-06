#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""방문 통계(/api/stats)를 data/stats.json 에 병합 저장(재배포에도 보존).

토큰(JIYUL_ADMIN_TOKEN) 필요 — 미설정이면 조용히 건너뛴다.
값은 (day,category,name)별 MAX로 병합하여 절대 감소하지 않는다. 표준 라이브러리만 사용.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

TOKEN = os.environ.get("JIYUL_ADMIN_TOKEN", "").strip()
BASE = os.environ.get("STATS_BASE", "https://taxin4u.com").rstrip("/")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "stats.json")


def main():
    if not TOKEN:
        print("JIYUL_ADMIN_TOKEN 미설정 — 통계 백업 건너뜀")
        return 0
    url = BASE + "/api/stats?token=" + urllib.parse.quote(TOKEN)
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            raw = json.loads(r.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"통계 조회 실패({exc}) — 이번 실행 건너뜀")
        return 0

    new_rows = (raw.get("stats") or {}).get("rows") if isinstance(raw, dict) else None
    if not isinstance(new_rows, list):
        print("응답 형식 이상 — 건너뜀")
        return 0

    old = {}
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as fp:
                for r in (json.load(fp).get("rows") or []):
                    old[(r["day"], r["category"], r["name"])] = int(r["hits"])
        except Exception:  # noqa: BLE001
            old = {}

    merged = dict(old)
    for r in new_rows:
        try:
            key = (r["day"], r["category"], r["name"])
            val = int(r["hits"])
        except Exception:  # noqa: BLE001
            continue
        merged[key] = max(int(old.get(key, 0)), val)

    rows = [
        {"day": d, "category": c, "name": n, "hits": h}
        for (d, c, n), h in sorted(merged.items())
    ]
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump({"rows": rows}, fp, ensure_ascii=False, indent=2)
        fp.write("\n")
    print(f"저장: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
