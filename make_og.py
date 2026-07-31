#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""공유 미리보기(OG) 이미지 생성 → assets/images/og.png (1200x630).

    python make_og.py                 # assets/images/og.png 로 저장
    python make_og.py 다른경로.png     # 지정 경로로 저장(미리보기용)

구성: 네이비 그라데이션 배경 + 흰 카드 안의 브랜드 로고(知律) + '세무법인 지율' + 태그라인.
문구/색을 바꾸려면 아래 상수만 수정하세요. 필요 라이브러리: Pillow (pip install Pillow).
Windows 기본 한글 폰트(맑은 고딕)를 사용합니다.
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
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "assets", "images", "og.png")

W, H = 1200, 630
NAVY_TOP = (37, 72, 114)
NAVY_BOT = (18, 38, 64)
WHITE = (255, 255, 255)
TAGLINE_COL = (162, 196, 236)
SUB_COL = (198, 214, 236)
ACCENT = (59, 130, 246)

FONT_DIR = "C:/Windows/Fonts"
FONT_BOLD = os.path.join(FONT_DIR, "malgunbd.ttf")
FONT_REG = os.path.join(FONT_DIR, "malgun.ttf")

BRAND = "세무법인 지율"
TAGLINE = "근거로 풀어 쓴 세무 이야기"
SUB = "법인세 · 상속·증여 · 세액공제 세무 자문"


def vgradient(w, h, top, bot):
    base = Image.new("RGB", (w, h), top)
    draw = ImageDraw.Draw(base)
    for y in range(h):
        t = y / (h - 1)
        r = int(top[0] + (bot[0] - top[0]) * t)
        g = int(top[1] + (bot[1] - top[1]) * t)
        b = int(top[2] + (bot[2] - top[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return base


def main():
    img = vgradient(W, H, NAVY_TOP, NAVY_BOT).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # 흰 카드 (로고 칩)
    card_w, card_h = 300, 262
    card_x = (W - card_w) // 2
    card_y = 60

    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [card_x + 6, card_y + 12, card_x + card_w + 6, card_y + card_h + 12],
        radius=34, fill=(0, 0, 0, 80),
    )
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(14)))

    draw.rounded_rectangle(
        [card_x, card_y, card_x + card_w, card_y + card_h], radius=34, fill=WHITE,
    )

    # 로고 (원본 그대로, 카드 안 여백)
    logo = Image.open(LOGO).convert("RGBA")
    bbox = logo.getbbox()
    if bbox:
        logo = logo.crop(bbox)
    pad = 32
    scale = min((card_w - pad * 2) / logo.width, (card_h - pad * 2) / logo.height)
    lw, lh = int(logo.width * scale), int(logo.height * scale)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    img.alpha_composite(logo, (card_x + (card_w - lw) // 2, card_y + (card_h - lh) // 2))

    # 텍스트
    f_brand = ImageFont.truetype(FONT_BOLD, 62)
    f_tag = ImageFont.truetype(FONT_BOLD, 44)
    f_sub = ImageFont.truetype(FONT_REG, 28)

    cx = W // 2
    draw.text((cx, 392), BRAND, font=f_brand, fill=WHITE, anchor="mm")
    draw.line([(cx - 66, 448), (cx + 66, 448)], fill=ACCENT, width=4)
    draw.text((cx, 500), TAGLINE, font=f_tag, fill=TAGLINE_COL, anchor="mm")
    draw.text((cx, 556), SUB, font=f_sub, fill=SUB_COL, anchor="mm")

    img.convert("RGB").save(OUT, "PNG")
    print("wrote", OUT, img.size)


if __name__ == "__main__":
    main()
