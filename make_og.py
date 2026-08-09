#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""공유 미리보기(OG) 이미지 생성 → assets/images/og.png (1200x630).

    python make_og.py                 # assets/images/og.png 로 저장
    python make_og.py 다른경로.png     # 지정 경로로 저장(미리보기용)

구성(사이트 헤더 로고와 동일한 락업):
    네이비 그라데이션 배경 + 상단 은은한 글로우/하단 비네트(깊이감)
    + 붓글씨 '세무법인' + 흰 카드 안의 브랜드 로고(知律)
    + 홈페이지 H1과 동일한 태그라인 + 업무 요약

선명도: 2배(2400x1260)로 렌더링 후 LANCZOS 축소 → 글자·로고가 또렷.
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

# 최종 크기(1200x630). 실제 렌더링은 S배로 하고 마지막에 축소해 선명하게.
W, H = 1200, 630
S = 2

# 브랜드 색
NAVY_TOP = (32, 62, 100)     # 상단(브랜드 네이비 계열)
NAVY_BOT = (12, 26, 46)      # 하단(더 깊게)
WHITE = (255, 255, 255)
TAG_MAIN = (255, 255, 255)   # 메인 태그라인: 순백(최대 대비/선명)
SUB_COL = (176, 202, 236)    # 업무 요약: 라이트 블루
ACCENT = (77, 148, 255)      # 포인트(파랑)

FDIR = "C:/Windows/Fonts"
FONT_BOLD = os.path.join(FDIR, "malgunbd.ttf")
FONT_REG = os.path.join(FDIR, "malgun.ttf")

BRAND = "세무법인"                       # 붓글씨(오른쪽 흰 박스의 知律 로고와 한 세트)
# 홈페이지 H1: "세법을 가르치는 손창용 세무사가 직접 쓴 세무 이야기" → 2줄로 배치
TAGLINE_1 = "세법을 가르치는 손창용 세무사가"
TAGLINE_2 = "직접 쓴 세무 이야기"
SUB = "법인세 · 세액공제감면 · 상속·증여 · 조세불복"


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


def soft_ellipse(w, h, cx, cy, rx, ry, color, alpha, blur):
    """부드러운 빛번짐(글로우/비네트)용 타원 레이어."""
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(
        [cx - rx, cy - ry, cx + rx, cy + ry], fill=color + (alpha,)
    )
    return layer.filter(ImageFilter.GaussianBlur(blur))


def main():
    w, h = W * S, H * S
    img = vgradient(w, h, NAVY_TOP, NAVY_BOT).convert("RGBA")

    # 상단 중앙 은은한 글로우 → 로고에 시선 집중, 입체감
    img.alpha_composite(soft_ellipse(w, h, w // 2, int(0.30 * h),
                                     int(0.42 * w), int(0.30 * h),
                                     (120, 170, 240), 46, 90 * S))
    # 하단 비네트 → 전문적인 차분함
    img.alpha_composite(soft_ellipse(w, h, w // 2, int(1.06 * h),
                                     int(0.75 * w), int(0.42 * h),
                                     (0, 0, 0), 90, 110 * S))

    d = ImageDraw.Draw(img)

    # ── 로고 락업: 붓글씨 '세무법인' + 흰 박스(知律) ──────────
    f_brush = ImageFont.truetype(BRUSH_FONT, 130 * S)
    bb = d.textbbox((0, 0), BRAND, font=f_brush)
    btw, bth = bb[2] - bb[0], bb[3] - bb[1]

    box = 178 * S
    gap = 30 * S
    group_w = btw + gap + box
    gx = (w - group_w) // 2
    cy = 214 * S

    d.text((gx - bb[0], cy - bth // 2 - bb[1]), BRAND, font=f_brush, fill=WHITE)

    box_x = gx + btw + gap
    box_y = cy - box // 2
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        [box_x + 5 * S, box_y + 10 * S, box_x + box + 5 * S, box_y + box + 10 * S],
        radius=30 * S, fill=(0, 0, 0, 95),
    )
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14 * S)))
    d.rounded_rectangle([box_x, box_y, box_x + box, box_y + box], radius=30 * S, fill=WHITE)

    logo = Image.open(LOGO).convert("RGBA")
    lb = logo.getbbox()
    if lb:
        logo = logo.crop(lb)
    pad = 26 * S
    sc = min((box - pad * 2) / logo.width, (box - pad * 2) / logo.height)
    lw, lh = int(logo.width * sc), int(logo.height * sc)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    img.alpha_composite(logo, (box_x + (box - lw) // 2, box_y + (box - lh) // 2))

    # ── 구분선 ──────────────────────────────────────────────
    cx = w // 2
    div_y = 372 * S
    d.line([(cx - 66 * S, div_y), (cx + 66 * S, div_y)], fill=ACCENT, width=4 * S)

    # ── 태그라인(홈페이지 H1) 2줄 + 업무 요약 ────────────────
    f_tag = ImageFont.truetype(FONT_BOLD, 50 * S)
    f_sub = ImageFont.truetype(FONT_REG, 29 * S)
    d.text((cx, 422 * S), TAGLINE_1, font=f_tag, fill=TAG_MAIN, anchor="mm")
    d.text((cx, 482 * S), TAGLINE_2, font=f_tag, fill=TAG_MAIN, anchor="mm")
    d.text((cx, 548 * S), SUB, font=f_sub, fill=SUB_COL, anchor="mm")

    # ── 축소로 선명하게 ─────────────────────────────────────
    out = img.convert("RGB").resize((W, H), Image.LANCZOS)
    out.save(OUT, "PNG")
    print("wrote", OUT, out.size)


if __name__ == "__main__":
    main()
