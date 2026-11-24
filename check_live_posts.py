#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""저장소의 칼럼(data/posts.json)이 라이브 홈페이지에 모두 올라가 있는지 확인한다.

노션 동기화 워크플로(notion-sync.yml)가 쓴다. 표준 라이브러리만 사용.

  python check_live_posts.py          빠진 칼럼이 있으면 GITHUB_OUTPUT 에 need=true (재배포 필요)
  python check_live_posts.py --wait   재배포 뒤 반영될 때까지 최대 5분 기다리고, 끝내 없으면 실패(exit 1)

왜 필요한가: 예전에는 새 칼럼이 없어도 실행 때마다 재배포했다. 실행 횟수를 늘리면서
'빠진 칼럼이 있을 때만' 재배포하도록 바꿨다. 커밋은 됐는데 배포가 실패한 경우에도
다음 실행이 라이브를 보고 다시 배포하므로 스스로 복구된다.
"""
import json
import os
import sys
import time
import urllib.request

URL = os.environ.get("POSTS_URL", "https://taxin4u.com/api/posts")
BASE = os.path.dirname(os.path.abspath(__file__))


def repo_slugs():
    with open(os.path.join(BASE, "data", "posts.json"), encoding="utf-8") as fp:
        d = json.load(fp)
    posts = d.get("posts", []) if isinstance(d, dict) else d
    return {p["slug"] for p in posts}


def live_slugs():
    req = urllib.request.Request(URL, headers={"User-Agent": "jiyul-sync/1.0", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read().decode("utf-8"))
    return {p["slug"] for p in d["posts"]}


def missing():
    """라이브에 없는 칼럼 목록. 홈페이지를 읽지 못하면 None."""
    try:
        return sorted(repo_slugs() - live_slugs())
    except Exception as exc:  # noqa: BLE001
        print("라이브 조회 실패: %s" % exc)
        return None


def main():
    if "--wait" in sys.argv:
        miss = None
        for _ in range(20):
            miss = missing()
            if miss == []:
                print("확인 완료 — 저장소의 칼럼이 모두 홈페이지에 있습니다.")
                return 0
            time.sleep(15)
        print("::error::재배포했지만 홈페이지에 반영되지 않았습니다: %s" % (miss,))
        return 1

    miss = missing()
    for _ in range(2):              # 일시적인 조회 실패는 다시 시도
        if miss is not None:
            break
        time.sleep(10)
        miss = missing()
    need = miss is None or bool(miss)
    print("재배포 %s — 라이브에 없는 칼럼: %s" % ("필요" if need else "불필요", miss))
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fp:
            fp.write("need=%s\n" % ("true" if need else "false"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
