"""用 PIL 程式產生所有材質，不需要任何圖檔。

低解析度＋最近點取樣，做出 PS1 風格。之後組員拍了總圖的實景照片，
只要把對應的函式換成讀照片（Image.open）就好，其他程式不用改。
"""
import math
import random

from PIL import Image, ImageDraw, ImageFont


def _noise(img, amount, rng):
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, *a = px[x, y]
            n = rng.randint(-amount, amount)
            px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)), *a)
    return img


def carpet():
    """總圖閱覽區的深藍灰地毯，帶一點菱形織紋。"""
    rng = random.Random(1)
    img = Image.new("RGB", (64, 64), (52, 58, 72))
    d = ImageDraw.Draw(img)
    for i in range(0, 64, 8):
        d.line([(i, 0), (i + 64, 64)], fill=(47, 52, 66))
        d.line([(i, 64), (i + 64, 0)], fill=(47, 52, 66))
    for _ in range(25):   # 咖啡漬、磨損
        x, y = rng.randrange(64), rng.randrange(64)
        d.ellipse([x, y, x + rng.randint(2, 5), y + rng.randint(2, 4)], fill=(44, 46, 55))
    return _noise(img, 6, rng)


def stone():
    """大廳磨石子地板。"""
    rng = random.Random(2)
    img = Image.new("RGB", (64, 64), (150, 146, 138))
    d = ImageDraw.Draw(img)
    for _ in range(140):
        x, y = rng.randrange(64), rng.randrange(64)
        c = rng.choice([(110, 106, 100), (180, 176, 168), (125, 118, 105), (90, 88, 86)])
        d.rectangle([x, y, x + rng.randint(0, 1), y + rng.randint(0, 1)], fill=c)
    d.line([(0, 63), (63, 63)], fill=(120, 116, 110))
    d.line([(63, 0), (63, 63)], fill=(120, 116, 110))
    return _noise(img, 4, rng)


def ceiling():
    """60 公分見方的礦纖天花板。"""
    rng = random.Random(3)
    img = Image.new("RGB", (64, 64), (168, 168, 160))
    d = ImageDraw.Draw(img)
    for _ in range(90):
        x, y = rng.randrange(64), rng.randrange(64)
        d.point((x, y), fill=(140, 140, 134))
    d.rectangle([0, 0, 63, 63], outline=(110, 110, 105))
    if rng.random() < 1:   # 一塊漏水的黃漬
        d.ellipse([30, 34, 50, 50], fill=(160, 150, 120))
    return _noise(img, 5, rng)


def wall():
    """米白色牆面，下面有踢腳板和髒污。"""
    rng = random.Random(4)
    w, h = 64, 96
    img = Image.new("RGB", (w, h), (196, 190, 176))
    px = img.load()
    for y in range(h):
        grime = max(0, (y - 60) / 36) * 30
        for x in range(w):
            r, g, b = px[x, y]
            px[x, y] = (int(r - grime), int(g - grime), int(b - grime * 1.1))
    d = ImageDraw.Draw(img)
    d.rectangle([0, h - 6, w, h], fill=(70, 66, 62))   # 踢腳板
    return _noise(img, 5, rng)


def wood():
    rng = random.Random(5)
    img = Image.new("RGB", (64, 64), (138, 98, 62))
    d = ImageDraw.Draw(img)
    for y in range(0, 64, 2):
        off = int(3 * math.sin(y * 0.4))
        d.line([(0, y + off % 2), (63, y)], fill=(rng.randint(115, 130), rng.randint(80, 90), 52))
    return _noise(img, 6, rng)


def metal():
    rng = random.Random(6)
    img = Image.new("RGB", (32, 32), (128, 132, 134))
    d = ImageDraw.Draw(img)
    for x in range(0, 32, 3):
        d.line([(x, 0), (x, 31)], fill=(120, 124, 127))
    return _noise(img, 4, rng)


BOOK_COLORS = [(110, 32, 30), (34, 52, 92), (40, 76, 52), (150, 128, 70), (88, 60, 40),
               (60, 60, 64), (170, 160, 140), (120, 70, 90), (30, 30, 34), (96, 104, 60)]


def books(seed):
    """一整面書架正面：五層鐵架，每層塞滿高高低低的書，部分書背有索書號貼紙。"""
    rng = random.Random(100 + seed)
    w, h = 128, 128
    img = Image.new("RGB", (w, h), (26, 24, 22))
    d = ImageDraw.Draw(img)
    shelf_h = h // 5
    for s in range(5):
        top, bottom = s * shelf_h, (s + 1) * shelf_h - 3
        x = 1
        while x < w - 2:
            bw = rng.randint(3, 7)
            if rng.random() < 0.06:   # 空位
                x += bw + 2
                continue
            bh = rng.randint(int(shelf_h * 0.55), shelf_h - 5)
            c = rng.choice(BOOK_COLORS)
            c = tuple(max(0, min(255, v + rng.randint(-15, 15))) for v in c)
            d.rectangle([x, bottom - bh, x + bw - 1, bottom], fill=c)
            d.line([(x, bottom - bh), (x, bottom)], fill=tuple(int(v * 0.7) for v in c))
            if bh > 12 and rng.random() < 0.7:
                d.rectangle([x, bottom - 5, x + bw - 2, bottom - 3], fill=(225, 222, 210))
            if rng.random() < 0.3:
                d.line([(x + 1, bottom - bh + 3), (x + bw - 2, bottom - bh + 3)], fill=(200, 180, 90))
            x += bw
        d.rectangle([0, bottom + 1, w, bottom + 3], fill=(140, 144, 146))   # 鐵製層板
    d.rectangle([0, 0, 1, h], fill=(140, 144, 146))
    d.rectangle([w - 2, 0, w, h], fill=(140, 144, 146))
    return _noise(img, 5, rng)


def window():
    """夜晚的窗：深藍天空、月光、成功湖邊的樹影、遠處路燈。"""
    rng = random.Random(7)
    w, h = 64, 96
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = y / h
            glow = max(0, 1 - math.hypot(x - 46, y - 18) / 30) * 50
            px[x, y] = (int(14 + 20 * t + glow * 0.8), int(20 + 26 * t + glow * 0.9), int(42 + 30 * t + glow))
    d = ImageDraw.Draw(img)
    d.ellipse([42, 14, 50, 22], fill=(210, 220, 230))
    for i in range(7):   # 樹影
        cx = rng.randint(0, w)
        d.ellipse([cx - 12, 58 + rng.randint(-6, 6), cx + 12, 100], fill=(6, 9, 14))
    d.rectangle([12, 70, 13, 80], fill=(240, 200, 120))
    d.rectangle([0, 0, w - 1, h - 1], outline=(40, 42, 46), width=2)
    d.line([(w // 2, 0), (w // 2, h)], fill=(40, 42, 46), width=2)
    d.line([(0, h // 2), (w, h // 2)], fill=(40, 42, 46), width=2)
    return img


def light_panel():
    img = Image.new("RGB", (32, 32), (250, 250, 240))
    d = ImageDraw.Draw(img)
    for i in range(0, 32, 4):
        d.line([(i, 0), (i, 31)], fill=(220, 222, 214))
        d.line([(0, i), (31, i)], fill=(220, 222, 214))
    d.rectangle([0, 0, 31, 31], outline=(150, 150, 145), width=2)
    return img


def glow():
    """地上的光暈：中間亮、往外透明。"""
    size = 64
    img = Image.new("RGBA", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            dd = math.hypot(x - size / 2, y - size / 2) / (size / 2)
            a = max(0.0, 1 - dd) ** 2
            px[x, y] = (255, 255, 255, int(255 * a))
    return img


def _font(path, size):
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def sign(lines, font_path, w=256, h=80, bg=(28, 58, 52), fg=(235, 235, 225), sizes=None):
    """指示牌：第一行中文大字，第二行英文小字。"""
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    sizes = sizes or [int(h * 0.42), int(h * 0.2)]
    y = h * 0.1
    for line, size in zip(lines, sizes):
        f = _font(font_path, size)
        tw = d.textlength(line, font=f)
        d.text(((w - tw) / 2, y), line, font=f, fill=fg)
        y += size * 1.25
    d.rectangle([0, 0, w - 1, h - 1], outline=(200, 200, 190), width=2)
    return img


def poster_missing(font_path):
    """尋人啟事：室友的照片被撕掉了一半。"""
    rng = random.Random(9)
    w, h = 120, 170
    img = Image.new("RGB", (w, h), (232, 228, 214))
    d = ImageDraw.Draw(img)
    d.text((26, 6), "尋 人", font=_font(font_path, 30), fill=(150, 20, 20))
    d.rectangle([25, 44, 95, 114], fill=(120, 120, 118))
    d.ellipse([45, 52, 75, 82], fill=(70, 70, 70))
    d.rectangle([38, 82, 82, 114], fill=(70, 70, 70))
    d.polygon([(60, 44), (95, 44), (95, 114), (72, 96)], fill=(200, 196, 182))   # 撕掉的角
    f = _font(font_path, 11)
    for i, t in enumerate(["資工系大二 陳○○", "最後出現：總圖 02:40", "見到請聯絡 0912-○○○-○○○"]):
        d.text((8, 120 + i * 15), t, font=f, fill=(40, 40, 40))
    return _noise(img, 6, rng)


def poster_notice(font_path):
    rng = random.Random(10)
    w, h = 120, 160
    img = Image.new("RGB", (w, h), (222, 226, 236))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, 28], fill=(90, 40, 120))
    d.text((10, 4), "清華大學圖書館", font=_font(font_path, 16), fill=(255, 255, 255))
    f = _font(font_path, 12)
    for i, t in enumerate(["期中考週", "夜讀區 24 小時開放", "館藏區 23:00 閉館", "閉館後請勿逗留", "", "※ 本館不提供", "  任何考古題"]):
        d.text((8, 36 + i * 17), t, font=f, fill=(30, 30, 40))
    return _noise(img, 4, rng)


def note_paper():
    rng = random.Random(11)
    img = Image.new("RGB", (32, 40), (236, 228, 200))
    d = ImageDraw.Draw(img)
    for y in range(6, 38, 4):
        d.line([(3, y), (rng.randint(14, 29), y)], fill=(60, 60, 90))
    return img


def screen():
    img = Image.new("RGB", (32, 24), (20, 40, 60))
    d = ImageDraw.Draw(img)
    d.rectangle([2, 2, 29, 5], fill=(60, 110, 160))
    for y in range(8, 22, 3):
        d.line([(3, y), (24, y)], fill=(90, 140, 180))
    return img


def whiteboard(digit, font_path):
    """討論室的白板：期中考範圍、亂畫的公式，角落圈著一個數字。"""
    rng = random.Random(12)
    w, h = 300, 190
    img = Image.new("RGB", (w, h), (232, 234, 230))
    d = ImageDraw.Draw(img)
    for _ in range(6):   # 沒擦乾淨的痕跡
        x, y = rng.randrange(w), rng.randrange(h)
        d.ellipse([x, y, x + rng.randint(30, 80), y + rng.randint(8, 20)], fill=(215, 218, 214))
    f = _font(font_path, 16)
    blue, red = (30, 50, 140), (170, 30, 30)
    for i, t in enumerate(["期中考範圍 Ch.1 – Ch.7", "∫ x² dx = x³/3 + C", "BFS → queue", "DP 記得 base case"]):
        d.text((14, 12 + i * 26), t, font=f, fill=blue)
    d.text((14, 130), "別回頭。", font=_font(font_path, 22), fill=red)
    d.ellipse([200, 95, 280, 175], outline=red, width=4)
    d.text((222, 100), str(digit), font=_font(font_path, 56), fill=red)
    d.rectangle([0, 0, w - 1, h - 1], outline=(150, 150, 150), width=4)
    return img
