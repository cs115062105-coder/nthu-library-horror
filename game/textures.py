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
    """白天的窗：藍天白雲、成功湖邊的樹、遠處的大樓。"""
    rng = random.Random(7)
    w, h = 64, 96
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = y / h
            px[x, y] = (int(120 + 90 * t), int(175 + 60 * t), int(235 + 15 * t))
    d = ImageDraw.Draw(img)
    for _ in range(4):   # 雲
        cx, cy = rng.randint(0, w), rng.randint(6, 36)
        for k in range(3):
            d.ellipse([cx - 9 + k * 6, cy - 4, cx + 3 + k * 6, cy + 5], fill=(250, 250, 252))
    d.rectangle([40, 50, 56, 74], fill=(196, 190, 178))   # 遠處的系館
    for yy in range(54, 72, 5):
        d.line([(42, yy), (54, yy)], fill=(150, 170, 190))
    for _ in range(7):   # 樹
        cx = rng.randint(0, w)
        d.ellipse([cx - 12, 60 + rng.randint(-6, 6), cx + 12, 100], fill=(70 + rng.randint(0, 30), 130 + rng.randint(0, 30), 70))
    d.rectangle([0, 0, w - 1, h - 1], outline=(120, 122, 126), width=2)
    d.line([(w // 2, 0), (w // 2, h)], fill=(120, 122, 126), width=2)
    d.line([(0, h // 2), (w, h // 2)], fill=(120, 122, 126), width=2)
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
    """尋人啟事（你自己貼的）：室友的照片，臉上被畫了鬼臉。"""
    rng = random.Random(9)
    w, h = 120, 170
    img = Image.new("RGB", (w, h), (246, 240, 214))
    d = ImageDraw.Draw(img)
    d.text((22, 6), "通 緝", font=_font(font_path, 30), fill=(190, 40, 30))
    d.rectangle([25, 44, 95, 114], fill=(170, 200, 220))
    d.ellipse([45, 52, 75, 82], fill=(235, 200, 170))
    d.rectangle([38, 82, 82, 114], fill=(60, 90, 140))
    for x in (53, 64):   # 被畫上去的眼鏡
        d.ellipse([x - 4, 62, x + 4, 70], outline=(20, 20, 20), width=2)
    d.arc([52, 70, 68, 78], 0, 180, fill=(20, 20, 20), width=2)
    f = _font(font_path, 11)
    for i, t in enumerate(["罪名：偷卷", "自稱「完全沒讀書」", "抓到請就地痛扁"]):
        d.text((8, 120 + i * 15), t, font=f, fill=(40, 40, 40))
    return _noise(img, 4, rng)


def poster_notice(font_path):
    rng = random.Random(10)
    w, h = 120, 160
    img = Image.new("RGB", (w, h), (222, 226, 236))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, 28], fill=(90, 40, 120))
    d.text((10, 4), "清華大學圖書館", font=_font(font_path, 16), fill=(255, 255, 255))
    f = _font(font_path, 12)
    for i, t in enumerate(["期中考週", "館藏區 22:00 閉館", "館內請勿奔跑", "請保持安靜", "", "※ 本館不提供", "  任何考古題"]):
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


# ---------- 1F 實景：照總圖 1F 的照片做的 ----------
def tile():
    """1F 大廳的深灰色長條地磚，交錯排列，偶爾一條不鏽鋼收邊條。"""
    rng = random.Random(13)
    w, h = 64, 64
    img = Image.new("RGB", (w, h), (64, 64, 66))
    d = ImageDraw.Draw(img)
    for row in range(4):
        y0 = row * 16
        off = 0 if row % 2 == 0 else 16
        for k in range(-1, 3):
            x0 = off + k * 32
            g = rng.randint(70, 86)
            d.rectangle([x0 + 1, y0 + 1, x0 + 31, y0 + 15], fill=(g, g, g + 2))
    d.line([(0, 63), (63, 63)], fill=(150, 152, 156))   # 收邊條
    return _noise(img, 3, rng)


def white_wall():
    """1F 的白牆：乾淨的白色，下面一條深灰踢腳板。"""
    rng = random.Random(14)
    img = Image.new("RGB", (64, 96), (236, 236, 234))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 92, 64, 96], fill=(80, 80, 82))
    return _noise(img, 2, rng)


def plaster():
    """1F 的白色平頂天花板，一格一盞圓形嵌燈。"""
    img = Image.new("RGB", (32, 32), (238, 238, 240))
    d = ImageDraw.Draw(img)
    d.ellipse([12, 12, 19, 19], fill=(200, 200, 205))
    d.ellipse([14, 14, 17, 17], fill=(255, 255, 250))
    return img


def planks():
    """聯合櫃臺上方的木條天花板。"""
    rng = random.Random(15)
    img = Image.new("RGB", (64, 64), (190, 170, 140))
    d = ImageDraw.Draw(img)
    for x in range(0, 64, 8):
        c = rng.randint(170, 205)
        d.rectangle([x, 0, x + 6, 63], fill=(c, c - 22, c - 55))
        d.line([(x + 7, 0), (x + 7, 63)], fill=(110, 95, 75))
    return _noise(img, 6, rng)


def cubbies(seed):
    """自助取書櫃：白色的格子櫃，每格放著幾本預約書，右下角一個紅色感應燈。"""
    rng = random.Random(200 + seed)
    w, h = 64, 96
    img = Image.new("RGB", (w, h), (240, 240, 240))
    d = ImageDraw.Draw(img)
    cw, ch = 16, 16
    for gy in range(0, h, ch):
        for gx in range(0, w, cw):
            d.rectangle([gx + 1, gy + 1, gx + cw - 2, gy + ch - 2], fill=(205, 205, 208))
            x = gx + 3
            for _ in range(rng.randint(0, 4)):
                bw = rng.randint(2, 3)
                bh = rng.randint(7, 12)
                d.rectangle([x, gy + ch - 3 - bh, x + bw - 1, gy + ch - 3], fill=rng.choice(BOOK_COLORS))
                x += bw
            d.point((gx + cw - 4, gy + ch - 4), fill=(210, 40, 40))
        d.line([(0, gy), (w, gy)], fill=(250, 250, 250))
    return _noise(img, 3, rng)


def covers(seed):
    """知識集的木色展示板：上面一條主題展標題，下面三排三列的書封面。"""
    rng = random.Random(300 + seed)
    w, h = 64, 128
    img = Image.new("RGB", (w, h), (214, 190, 150))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, 20], fill=(245, 245, 245))
    for i, c in enumerate([(230, 60, 60), (60, 120, 220), (90, 180, 80), (240, 180, 40)]):
        d.rectangle([3 + i * 5, 4, 6 + i * 5, 16], fill=c)
    d.rectangle([26, 7, 58, 12], fill=(70, 120, 190))
    for row in range(3):
        y = 30 + row * 30
        d.line([(2, y + 24), (w - 2, y + 24)], fill=(170, 170, 170))
        for col in range(3):
            x = 6 + col * 20
            c = tuple(rng.randint(40, 230) for _ in range(3))
            d.rectangle([x, y, x + 12, y + 17], fill=c)
            d.rectangle([x + 2, y + 3, x + 10, y + 6], fill=(250, 250, 250))
    return _noise(img, 3, rng)


def grid():
    """深色鋁格柵天花板：一格一格的方框，透出上面更暗的管線層。"""
    img = Image.new("RGB", (32, 32), (52, 52, 55))
    d = ImageDraw.Draw(img)
    for i in range(0, 32, 4):
        d.line([(i, 0), (i, 31)], fill=(118, 118, 122))
        d.line([(0, i), (31, i)], fill=(118, 118, 122))
    return img


def stripes(base=(128, 130, 134), band=(78, 80, 86), seed=16):
    """條紋地毯：底色上一條條細條紋，偶爾一條比較寬的帶。2F 是淺灰配深灰，3F 深咖啡配淺色，4F 灰褐配深咖啡。"""
    rng = random.Random(seed)
    img = Image.new("RGB", (64, 64), base)
    d = ImageDraw.Draw(img)
    for y in range(0, 64, 4):
        k = rng.randint(-24, -8)
        d.line([(0, y), (63, y)], fill=tuple(max(0, v + k) for v in base))
    d.rectangle([0, 40, 63, 45], fill=band)
    return _noise(img, 4, rng)


def slats():
    """4F 的深色木條天花板：一條條深咖啡木條，縫裡看得到上面黑黑的管線。"""
    rng = random.Random(17)
    img = Image.new("RGB", (64, 64), (28, 26, 26))
    d = ImageDraw.Draw(img)
    for x in range(0, 64, 8):
        c = rng.randint(92, 118)
        d.rectangle([x, 0, x + 5, 63], fill=(c, c * 6 // 10, c * 4 // 10))
        d.line([(x + 1, 0), (x + 1, 63)], fill=(c + 25, (c + 25) * 6 // 10, (c + 25) * 4 // 10))
    return _noise(img, 5, rng)


def nthu_letters(font_path):
    """4F 清華書房的玻璃牆：銀色格子書架做成的 N T H U 四個大字，背景透明。"""
    w, h = 512, 160
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for x in range(0, w, 64):     # 書架的直隔板
        d.rectangle([x, 0, x + 3, h], fill=(205, 208, 212, 255))
    for y in (6, 52, 98, 150):    # 層板
        d.rectangle([0, y, w, y + 3], fill=(205, 208, 212, 255))
    f = _font(font_path, 150)
    for i, ch in enumerate("NTHU"):
        tw = d.textlength(ch, font=f)
        d.text((i * 128 + (128 - tw) / 2, -18), ch, font=f, fill=(225, 232, 234, 235))
    return img


def magazines(seed):
    """期刊牆：淺木色的斜板，每格立著一本彩色雜誌，下面一條木頭隔板。"""
    rng = random.Random(400 + seed)
    w, h = 64, 96
    img = Image.new("RGB", (w, h), (200, 168, 120))
    d = ImageDraw.Draw(img)
    for row in range(4):
        y = 4 + row * 23
        d.rectangle([0, y + 19, w, y + 22], fill=(150, 118, 80))
        for col in range(3):
            x = 3 + col * 21
            if rng.random() < 0.85:
                c = tuple(rng.randint(40, 235) for _ in range(3))
                d.rectangle([x, y, x + 15, y + 18], fill=c)
                d.rectangle([x + 2, y + 2, x + 13, y + 5], fill=(250, 250, 250))
                d.rectangle([x + 3, y + 8, x + 12, y + 15], fill=tuple(max(0, v - 50) for v in c))
    return _noise(img, 4, rng)


def blind():
    """窗邊的捲簾：半透明的米白色，一條條細橫紋。"""
    img = Image.new("RGB", (32, 32), (226, 222, 210))
    d = ImageDraw.Draw(img)
    for y in range(0, 32, 3):
        d.line([(0, y), (31, y)], fill=(208, 204, 192))
    return img
