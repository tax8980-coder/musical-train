#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
기본 공유 미리보기 이미지(og.png) 생성기 — Python 표준 라이브러리만 사용.

세무법인 지율 브랜드 컬러의 1200x630 네이비 그라데이션 카드를 생성합니다.
(폰트 렌더링 라이브러리가 없어 텍스트 없이 브랜드 배경만 만듭니다.
 로고/문구가 들어간 완성본은 디자인 후 같은 경로에 덮어써 교체하세요.)

    python make_og.py
    -> assets/images/og.png
"""
import os
import struct
import zlib

W, H = 1200, 630

NAVY = (30, 58, 95)      # #1E3A5F
DEEP = (21, 44, 72)      # #152C48
BLUE = (59, 130, 246)    # #3B82F6
LINE = (255, 255, 255)


def lerp(a, b, t):
    return int(round(a + (b - a) * t))


def build_rows():
    rows = bytearray()
    # 대각선(135도 느낌) 그라데이션 + 하단 포인트 라인
    bar_y0, bar_y1 = 470, 474           # 얇은 블루 라인 위치
    frame = 26                          # 바깥 여백 프레임
    for y in range(H):
        rows.append(0)  # PNG filter type 0 (None)
        for x in range(W):
            t = (x / W + y / H) / 2      # 0(좌상) ~ 1(우하)
            r = lerp(NAVY[0], DEEP[0], t)
            g = lerp(NAVY[1], DEEP[1], t)
            b = lerp(NAVY[2], DEEP[2], t)

            # 하단 포인트 블루 라인
            if bar_y0 <= y <= bar_y1 and frame + 40 <= x <= W - frame - 40:
                r, g, b = BLUE

            # 얇은 프레임 라인
            on_frame = (
                (frame <= x <= W - frame) and (frame <= y <= W)  # dummy
            )
            if (
                (x == frame or x == W - frame - 1) and frame <= y <= H - frame - 1
            ) or (
                (y == frame or y == H - frame - 1) and frame <= x <= W - frame - 1
            ):
                r = lerp(r, LINE[0], 0.22)
                g = lerp(g, LINE[1], 0.22)
                b = lerp(b, LINE[2], 0.22)

            rows += bytes((r, g, b))
    return bytes(rows)


def chunk(tag, data):
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def main():
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "images")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "og.png")

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)  # 8-bit, truecolor RGB
    raw = build_rows()
    idat = zlib.compress(raw, 9)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    with open(out_path, "wb") as fp:
        fp.write(png)
    print("wrote", out_path, "(%d bytes)" % len(png))


if __name__ == "__main__":
    main()
