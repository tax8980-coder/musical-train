#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""카드뉴스 세트별 메신저 미리보기 이미지(og-cover.jpg) 생성.

카카오톡·페이스북 등은 미리보기 이미지를 가로로 잘라 보여준다.
카드 원본(1080x1350, 4:5)을 그대로 쓰면 위쪽 로고만 보이고 제목이 잘리므로,
1200x630(1.91:1) 전용 이미지를 따로 만든다.

'가운데 정사각형 안전' 배치(2026-11-09): 페이스북 모바일은 같은 이미지를
가운데 정사각형으로 잘라 보여준다. 예전 배치(왼쪽 제목 + 오른쪽 표지)는
제목 앞부분과 표지 오른쪽이 모두 잘렸다. 그래서 표지 카드(제목이 이미 들어 있음)를
가운데 630x630 안에 크게 두고, 짧은 브랜드 문구만 양끝(잘려도 되는 자리)에 둔다.
→ 1:1 로 잘려도, 1.91:1 로 다 보여도 모두 온전하다.

파일명을 og-card.jpg → og-cover.jpg 로 바꾼 것은 카카오톡·페이스북이 같은
주소의 이미지를 캐시해 새 이미지를 안 읽어 가기 때문이다. 다시 디자인을 바꾸면
파일명도 다시 바꾸고 server.py 의 OG_COVER_FILE 을 같이 고친다.

사용법:  python make_cardnews_og.py
         data/cardnews.json 의 모든 세트에 대해
         assets/cardnews/<slug>/og-cover.jpg 를 새로 만든다.
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


OG_FILE = "og-cover.jpg"
SAFE = H                      # 가운데 정사각형 한 변(630)
SAFE_X0 = (W - SAFE) // 2     # 285
SAFE_X1 = SAFE_X0 + SAFE      # 915
EDGE = 40                     # 양끝 문구 여백 — 문구는 SAFE_X0 - 24 안쪽까지만


def _shadow(size, radius, blur=18, alpha=110):
    from PIL import ImageFilter
    w, h = size
    pad = blur * 3
    sh = Image.new("L", (w + pad * 2, h + pad * 2), 0)
    ImageDraw.Draw(sh).rounded_rectangle([pad, pad, pad + w, pad + h], radius=radius, fill=alpha)
    return sh.filter(ImageFilter.GaussianBlur(blur)), pad


def _side_text(draw, lines, x, align):
    """양끝 문구. 정사각형으로 잘릴 때 반쯤 걸리지 않도록 안전영역 밖에만 둔다."""
    total = sum(int(f.size * 1.5) for _, f, _ in lines)
    y = (H - total) // 2
    for text, f, color in lines:
        w = draw.textlength(text, font=f)
        tx = x if align == "left" else x - w
        draw.text((tx, y), text, font=f, fill=color)
        y += int(f.size * 1.5)


def make_og(item):
    d = item["dir"].lstrip("/")
    cover_path = os.path.join(BASE, d, item["cards"][0]["file"])
    out_path = os.path.join(BASE, d, OG_FILE)

    img = _background()
    draw = ImageDraw.Draw(img)

    # 가운데: 표지 카드(4:5) — 정사각형 안전영역 안에 크게
    thumb_h = H - 56
    thumb_w = int(thumb_h * 1080 / 1350)
    tx, ty = (W - thumb_w) // 2, (H - thumb_h) // 2
    sh, pad = _shadow((thumb_w, thumb_h), 22)
    img.paste((8, 20, 38), (tx - pad, ty - pad + 8), sh)
    cover = Image.open(cover_path).convert("RGB").resize((thumb_w, thumb_h), Image.LANCZOS)
    cover = _rounded(cover, 22)
    img.paste(cover, (tx, ty), cover)

    # 양끝: 잘려도 되는 짧은 브랜드 문구
    f_big = _font(FONT_BOLD, 34)
    f_small = _font(FONT_BOLD, 22)
    n = len(item.get("cards") or [])
    _side_text(draw, [("카드뉴스", f_small, SKY), ("세무법인", f_big, WHITE), ("지율", f_big, WHITE)],
               EDGE + 8, "left")
    _side_text(draw, [("카드 %d장" % n, f_small, SKY), ("손창용세무사", f_big, WHITE),
                      ("taxin4u.com", f_small, SUB)], W - EDGE - 8, "right")

    img.save(out_path, "JPEG", quality=88, optimize=True, progressive=True)
    return out_path, os.path.getsize(out_path)


def main():
    sets = json.load(io.open(os.path.join(BASE, "data", "cardnews.json"), encoding="utf-8"))
    for item in sets:
        path, size = make_og(item)
        print("  %-58s %5.0fKB" % (os.path.relpath(path, BASE), size / 1024))


if __name__ == "__main__":
    main()
