#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""카드뉴스 세트별 메신저 미리보기 이미지(og-card.jpg) 생성.

카카오톡·페이스북 등은 미리보기 이미지를 가로로 잘라 보여준다.
카드 원본(1080x1350, 4:5)을 그대로 쓰면 위쪽 로고만 보이고 제목이 잘리므로,
1200x630(1.91:1)에 제목이 통째로 들어가는 전용 이미지를 따로 만든다.

사용법:  python make_cardnews_og.py
         data/cardnews.json 의 모든 세트에 대해
         assets/cardnews/<slug>/og-card.jpg 를 새로 만든다.
"""
import io
import json
import os

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
W, H = 1200, 630
PAD = 72
NAVY = (30, 58, 95)
NAVY_2 = (42, 90, 154)
WHITE = (255, 255, 255)
SKY = (168, 196, 236)
SUB = (201, 217, 240)

FONT_BOLD = r"C:\Windows\Fonts\malgunbd.ttf"
FONT_REG = r"C:\Windows\Fonts\malgun.ttf"


def _font(path, size):
    return ImageFont.truetype(path, size)


NO_LINE_START = "·.,)]}>」』!?%’”…:;"
import re as _re

def _tokens(text):
    """한글은 한 글자씩, 영문·숫자는 덩어리째 끊는다(중간에서 잘리지 않도록)."""
    return _re.findall(r"[A-Za-z0-9][A-Za-z0-9.,%\-]*|\s+|.", text)


def _wrap(draw, text, font, max_w):
    """줄바꿈. 문장부호(·, 괄호 등)로 줄이 시작하지 않도록 앞 글자와 붙여 넘긴다."""
    lines, cur = [], ""
    for tok in _tokens(text):
        trial = cur + tok
        if draw.textlength(trial.strip(), font=font) <= max_w or not cur.strip():
            cur = trial
            continue
        # 띄어쓰기가 줄 뒤쪽(60% 이후)에 있으면 거기서 끊는다 — 어절이 자연스럽게 유지된다
        head = cur.rstrip()
        sp = head.rfind(" ")
        if sp > 0 and draw.textlength(head[:sp], font=font) >= max_w * 0.6:
            lines.append(head[:sp])
            # 다음 줄로 넘길 때는 rstrip 하지 않은 cur 에서 잘라야 어절 뒤 공백이 살아남는다
            # (head 로 자르면 '살면 ' + '증여세가' 가 '살면증여세가' 로 붙어 버린다)
            cur = cur[sp + 1:] + tok
            continue
        # 다음 줄이 문장부호로 시작하면 직전 글자를 함께 넘긴다
        if tok and tok[0] in NO_LINE_START and len(head) > 1:
            lines.append(head[:-1].rstrip())
            cur = head[-1] + tok
        else:
            lines.append(head)
            cur = tok.lstrip() if tok.strip() else ""
    if cur.strip():
        lines.append(cur.rstrip())
    return lines


def _fit_title(draw, text, max_w, max_lines, hi=62, lo=38):
    """제목이 max_lines 안에 다 들어가는 가장 큰 글자크기를 찾는다."""
    for size in range(hi, lo - 1, -2):
        f = _font(FONT_BOLD, size)
        lines = _wrap(draw, text, f, max_w)
        if len(lines) <= max_lines:
            return f, lines
    f = _font(FONT_BOLD, lo)
    lines = _wrap(draw, text, f, max_w)
    return f, lines[:max_lines]


def _background():
    """좌상→우하 네이비 그라데이션(작은 이미지를 확대해 띠 없이 부드럽게)."""
    small = Image.new("RGB", (64, 34))
    px = small.load()
    for y in range(small.height):
        for x in range(small.width):
            t = (x / (small.width - 1)) * 0.6 + (y / (small.height - 1)) * 0.4
            px[x, y] = tuple(int(NAVY[i] + (NAVY_2[i] - NAVY[i]) * t) for i in range(3))
    return small.resize((W, H), Image.BICUBIC)


def _rounded(img, radius):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1],
                                           radius=radius, fill=255)
    out = img.convert("RGB")
    out.putalpha(mask)
    return out


def make_og(item):
    slug = item["slug"]
    d = item["dir"].lstrip("/")
    cover_path = os.path.join(BASE, d, item["cards"][0]["file"])
    out_path = os.path.join(BASE, d, "og-card.jpg")

    img = _background()
    draw = ImageDraw.Draw(img)

    # 오른쪽: 카드 표지 미리보기(세로 카드)
    thumb_h = H - PAD * 2
    thumb_w = int(thumb_h * 1080 / 1350)
    cover = Image.open(cover_path).convert("RGB").resize((thumb_w, thumb_h), Image.LANCZOS)
    cover = _rounded(cover, 18)
    tx = W - PAD - thumb_w
    img.paste(cover, (tx, PAD), cover)

    text_w = tx - PAD - 44

    # 눈썹줄
    f_eyebrow = _font(FONT_BOLD, 24)
    draw.text((PAD, PAD + 4), "카드뉴스 · 세무법인 지율", font=f_eyebrow, fill=SKY)

    # 제목(최대 3줄, 전체가 들어가도록 글자크기 자동 조절)
    f_title, title_lines = _fit_title(draw, item.get("title", ""), text_w, 3)
    y = PAD + 62
    for ln in title_lines:
        draw.text((PAD, y), ln, font=f_title, fill=WHITE)
        y += int(f_title.size * 1.34)

    # 부제(최대 2줄)
    sub = item.get("subtitle") or ""
    if sub:
        f_sub = _font(FONT_REG, 26)
        y += 14
        for ln in _wrap(draw, sub, f_sub, text_w)[:2]:
            draw.text((PAD, y), ln, font=f_sub, fill=SUB)
            y += int(f_sub.size * 1.45)

    # 하단 정보
    f_foot = _font(FONT_BOLD, 24)
    foot = "카드 %d장 · taxin4u.com" % len(item.get("cards") or [])
    draw.text((PAD, H - PAD - 24), foot, font=f_foot, fill=SKY)

    img.save(out_path, "JPEG", quality=88, optimize=True, progressive=True)
    return out_path, os.path.getsize(out_path)


def main():
    sets = json.load(io.open(os.path.join(BASE, "data", "cardnews.json"), encoding="utf-8"))
    for item in sets:
        path, size = make_og(item)
        print("  %-58s %5.0fKB" % (os.path.relpath(path, BASE), size / 1024))


if __name__ == "__main__":
    main()
