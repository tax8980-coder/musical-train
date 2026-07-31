#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""공유 미리보기(OG) 이미지 생성 → assets/images/og.png (1200x630).

    python make_og.py                 # assets/images/og.png 로 저장
    python make_og.py 다른경로.png     # 지정 경로로 저장(미리보기용)

구성(사이트 헤더 로고와 동일한 락업):
    네이비 그라데이션 배경
    + 붓글씨 '세무법인' + 흰 카드 안의 브랜드 로고(知律)
    + 태그라인 '근거로 풀어 쓴 세무 이야기' + 업무 요약

문구/색을 바꾸려면 아래 상수만 수정하세요. 필요 라이브러리: Pillow (pip install Pillow).
'세무법인' 붓글씨는 assets/fonts/NanumBrushScript-Regular.ttf, 나머지 텍스트는 맑은 고딕.
"""
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(BASE, "assets", "images", "logo-brand.png")
BRUSH_FONT = os.path.join(BASE, "assets", "fonts", "NanumBrushScript-Regular.ttf")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "assets", "images", "og.png")

W, H = 1200, 630
NAVY_TOP = (37, 72, 114)
NAVY_BOT = (18, 38, 64)
WHITE = (255, 255, 255)
TAG_COL = (176, 204, 240)
SUB_COL = (198, 214, 236)
ACCENT = (59, 130, 246)

FDIR = "C:/Windows/Fonts"
FONT_BOLD = os.path.join(FDIR, "malgunbd.ttf")
FONT_REG = os.path.join(FDIR, "malgun.ttf")

BRAND = "세무법인"          # 붓글씨로 렌더링 (오른쪽 흰 박스의 知律 로고와 한 세트)
TAGLINE = "근거로 풀어 쓴 세무 이야기"
SUB = "법인세 · 상속·증여 · 세액공제 세무 자문"


def vgradient(w, h, top, bot):
    im = Image.new("RGB", (w, h), top)
    dr = ImageDraw.Draw(im)
    for y in range(h):
        t = y / (h - 1)
        dr.line([(0, y), (w, y)], fill=(
            int(top[0] + (bot[0] - top[0]) * t),
            int(top[1] + (bot[1] - top[1]) * t),
            int(top[2] + (bot[2] - top[2]) * t),
        ))
    return im


def main():
    img = vgradient(W, H, NAVY_TOP, NAVY_BOT).convert("RGBA")
    d = ImageDraw.Draw(img)

    # ── 로고 락업: 붓글씨 '세무법인' + 흰 박스(知律) ──────────
    f_brush = ImageFont.truetype(BRUSH_FONT, 132)
    bb = d.textbbox((0, 0), BRAND, font=f_brush)
    btw, bth = bb[2] - bb[0], bb[3] - bb[1]

    box = 184
    gap = 30
    group_w = btw + gap + box
    gx = (W - group_w) // 2
    cy = 232

    d.text((gx - bb[0], cy - bth // 2 - bb[1]), BRAND, font=f_brush, fill=WHITE)

    box_x = gx + btw + gap
    box_y = cy - box // 2
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        [box_x + 5, box_y + 9, box_x + box + 5, box_y + box + 9], radius=30, fill=(0, 0, 0, 80),
    )
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)))
    d.rounded_rectangle([box_x, box_y, box_x + box, box_y + box], radius=30, fill=WHITE)

    logo = Image.open(LOGO).convert("RGBA")
    lb = logo.getbbox()
    if lb:
        logo = logo.crop(lb)
    pad = 26
    sc = min((box - pad * 2) / logo.width, (box - pad * 2) / logo.height)
    lw, lh = int(logo.width * sc), int(logo.height * sc)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    img.alpha_composite(logo, (box_x + (box - lw) // 2, box_y + (box - lh) // 2))

    # ── 태그라인 ────────────────────────────────────────────
    f_tag = ImageFont.truetype(FONT_BOLD, 46)
    f_sub = ImageFont.truetype(FONT_REG, 28)
    cx = W // 2
    d.line([(cx - 66, 398), (cx + 66, 398)], fill=ACCENT, width=4)
    d.text((cx, 452), TAGLINE, font=f_tag, fill=TAG_COL, anchor="mm")
    d.text((cx, 512), SUB, font=f_sub, fill=SUB_COL, anchor="mm")

    img.convert("RGB").save(OUT, "PNG")
    print("wrote", OUT, img.size)


if __name__ == "__main__":
    main()
