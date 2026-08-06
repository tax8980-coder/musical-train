#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""라이브 조회수(/api/views)를 data/views.json 에 병합 저장.

컨테이너 임시 DB는 재배포 때 초기화되지만, 서버는 부팅 시 이 파일로 조회수를 복원한다.
값은 slug별 MAX로 병합하므로 절대 감소하지 않고, 일시적 조회 실패에도 slug가 유실되지 않는다.
GitHub Actions(스케줄)에서 실행하며 표준 라이브러리만 사용한다.
"""
import json
import os
import sys
import urllib.request

URL = os.environ.get("VIEWS_URL", "https://taxin4u.com/api/views")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "views.json")


def main():
    try:
        with urllib.request.urlopen(URL, timeout=20) as r:
            raw = json.loads(r.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - 실패해도 스냅샷을 훼손하지 않고 종료
        print(f"조회수 조회 실패({exc}) — 이번 실행 건너뜀")
        return 0

    new = raw.get("views") if isinstance(raw, dict) else None
    if not isinstance(new, dict):
        print("응답 형식 이상 — 건너뜀")
        return 0

    old = {}
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as fp:
                old = json.load(fp) or {}
        except Exception:  # noqa: BLE001
            old = {}

    merged = dict(old)
    for k, v in new.items():
        try:
            v = int(v)
        except (TypeError, ValueError):
            continue
        merged[k] = max(int(old.get(k, 0) or 0), v)  # slug별 MAX → 감소 없음

    merged = {k: merged[k] for k in sorted(merged)}
    with open(OUT, "w", encoding="utf-8") as fp:
        json.dump(merged, fp, ensure_ascii=False, indent=2)
        fp.write("\n")
    print(f"저장: {len(merged)} slugs, 합계 {sum(merged.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
