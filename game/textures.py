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
    """白天的窗：從室內看出去，外面亮到有點過曝（跟影片裡一樣），只看得到模糊的樹和遠處的系館。
    先畫好再整張模糊，最後才畫清楚的窗框。"""
    from PIL import ImageFilter
    rng = random.Random(7)
    w, h = 256, 384
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=(int(214 + 30 * t), int(228 + 20 * t), int(242 + 10 * t)))
    for _ in range(3):   # 遠處的系館，淡淡的
        x0 = rng.randint(-20, w - 40)
        top = rng.randint(170, 220)
        d.rectangle([x0, top, x0 + rng.randint(50, 110), 300], fill=(212, 210, 204))
        for yy in range(top + 8, 296, 14):
            d.line([(x0 + 4, yy), (x0 + 100, yy)], fill=(186, 196, 206), width=3)
    for _ in range(16):  # 成功湖邊的樹：深淺不一的綠，一團一團
        cx, cy = rng.randint(-20, w + 20), rng.randint(250, 330)
        r = rng.randint(30, 60)
        g = rng.randint(0, 40)
        d.ellipse([cx - r, cy - r, cx + r, cy + r * 2], fill=(110 + g, 150 + g, 104 + g // 2))
    d.rectangle([0, 330, w, h], fill=(150, 158, 140))
    img = img.filter(ImageFilter.GaussianBlur(5))
    d = ImageDraw.Draw(img)
    frame = (168, 170, 174)
    d.rectangle([0, 0, w - 1, h - 1], outline=frame, width=6)
    d.rectangle([w // 2 - 3, 0, w // 2 + 3, h], fill=frame)
    d.rectangle([0, h // 2 - 3, w, h // 2 + 3], fill=frame)
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


def grid(back=(52, 52, 55), bars=(118, 118, 122)):
    """鋁格柵天花板：一格一格的方框，透出上面的管線層。1F 是深色的，3F 書架區是白色的。"""
    img = Image.new("RGB", (32, 32), back)
    d = ImageDraw.Draw(img)
    for i in range(0, 32, 4):
        d.line([(i, 0), (i, 31)], fill=bars)
        d.line([(0, i), (31, i)], fill=bars)
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


def bands(seed=31):
    """3F 的地毯：一公尺寬的深炭灰和淺灰帶子交錯，帶子裡有細細的毛紋。"""
    rng = random.Random(seed)
    img = Image.new("RGB", (64, 64))
    d = ImageDraw.Draw(img)
    for y in range(64):
        base = (70, 70, 72) if y < 32 else (182, 180, 176)
        k = rng.randint(-14, 10)
        d.line([(0, y), (63, y)], fill=tuple(max(0, min(255, v + k)) for v in base))
    for _ in range(90):      # 一小段一小段的毛紋
        x, y = rng.randrange(64), rng.randrange(64)
        c = (95, 95, 98) if y < 32 else (205, 203, 198)
        d.line([(x, y), (min(63, x + rng.randint(3, 10)), y)], fill=c)
    return _noise(img, 4, rng)


def dvds(seed):
    """3F 媒體區的白色架子：五層擺滿 DVD 盒，大多是酒紅、粉色、黑色、白色。"""
    rng = random.Random(500 + seed)
    w, h = 128, 128
    img = Image.new("RGB", (w, h), (232, 232, 230))
    d = ImageDraw.Draw(img)
    cols = [(120, 40, 50), (196, 140, 150), (226, 196, 200), (30, 30, 34), (236, 236, 232), (90, 60, 110), (60, 90, 140)]
    shelf_h = h // 5
    for s in range(5):
        top, bottom = s * shelf_h + 4, (s + 1) * shelf_h - 3
        x = 2
        while x < w - 3:
            if rng.random() < 0.05:
                x += 6
                continue
            c = rng.choice(cols)
            d.rectangle([x, top + 2, x + 1, bottom], fill=c)
            d.point((x, top + 4), fill=(250, 250, 250))
            x += 2
        d.rectangle([0, bottom + 1, w, bottom + 3], fill=(250, 250, 248))   # 白色層板
    d.rectangle([0, 0, 2, h], fill=(250, 250, 248))
    return _noise(img, 3, rng)


def wood_slats():
    """3F 走道旁的淺色木條牆：一條條直的木條，縫是深色的。"""
    rng = random.Random(41)
    img = Image.new("RGB", (64, 64), (90, 62, 38))
    d = ImageDraw.Draw(img)
    for x in range(0, 64, 6):
        c = rng.randint(190, 214)
        d.rectangle([x, 0, x + 4, 63], fill=(c, c * 72 // 100, c * 46 // 100))
        d.line([(x + 1, 0), (x + 1, 63)], fill=(c + 20, (c + 20) * 72 // 100, (c + 20) * 46 // 100))
    return _noise(img, 6, rng)


def timeline(seed):
    """1F 知識集的弧形展牆：米白底，一排排年份、一段段字、幾張照片和黃色標籤。"""
    rng = random.Random(700 + seed)
    w, h = 128, 96
    img = Image.new("RGB", (w, h), (246, 242, 228))
    d = ImageDraw.Draw(img)
    for col in range(3):
        x = 6 + col * 41
        y = 8
        while y < h - 10:
            kind = rng.random()
            if kind < 0.2:       # 照片
                d.rectangle([x, y, x + 20, y + 14], fill=rng.choice([(60, 40, 50), (90, 110, 130), (150, 120, 90)]))
                y += 18
            elif kind < 0.35:    # 黃色標籤
                d.rectangle([x, y, x + 30, y + 6], fill=(245, 225, 120))
                y += 10
            else:                # 年份＋幾行字
                d.rectangle([x, y, x + 12, y + 3], fill=(150, 150, 150))
                for k in range(rng.randint(2, 4)):
                    d.line([(x, y + 6 + k * 3), (x + rng.randint(18, 32), y + 6 + k * 3)], fill=(120, 120, 124))
                y += 8 + 3 * 4
    d.rectangle([0, h - 4, w, h], fill=(225, 220, 200))
    return _noise(img, 3, rng)


def leaf():
    """地上貼的淡藍綠色葉子貼紙（透明背景）。"""
    w, h = 128, 64
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([4, 8, w - 4, h - 8], fill=(170, 220, 215, 200))
    d.line([(8, h // 2), (w - 8, h // 2)], fill=(235, 250, 248, 220), width=2)
    for x in range(24, w - 20, 16):
        d.line([(x, h // 2), (x + 10, 14)], fill=(235, 250, 248, 200))
        d.line([(x, h // 2), (x + 10, h - 14)], fill=(235, 250, 248, 200))
    return img


def books_light(seed):
    """6F 西文書：白色書架，書背大多是白、米、淺藍、淺灰，高高低低，偶爾一本深色的。"""
    rng = random.Random(900 + seed)
    w, h = 128, 128
    img = Image.new("RGB", (w, h), (226, 228, 230))
    d = ImageDraw.Draw(img)
    cols = [(240, 238, 230), (228, 220, 200), (180, 200, 220), (200, 204, 210), (150, 170, 196),
            (236, 236, 240), (120, 140, 170), (60, 70, 96), (150, 60, 60), (210, 190, 150)]
    weights = [6, 5, 4, 4, 3, 5, 2, 1, 1, 2]
    shelf_h = h // 6
    for s in range(6):
        bottom = (s + 1) * shelf_h - 3
        x = 2
        while x < w - 3:
            bw = rng.randint(2, 5)
            if rng.random() < 0.08:
                x += bw + 3
                continue
            bh = rng.randint(int(shelf_h * 0.5), shelf_h - 5)
            c = rng.choices(cols, weights)[0]
            c = tuple(max(0, min(255, v + rng.randint(-12, 12))) for v in c)
            d.rectangle([x, bottom - bh, x + bw - 1, bottom], fill=c)
            d.line([(x, bottom - bh), (x, bottom)], fill=tuple(int(v * 0.8) for v in c))
            if bh > 10 and rng.random() < 0.6:
                d.rectangle([x, bottom - 5, x + bw - 2, bottom - 3], fill=(250, 250, 250))
            x += bw
        d.rectangle([0, bottom + 1, w, bottom + 3], fill=(248, 248, 248))   # 白色層板
    d.rectangle([0, 0, 2, h], fill=(248, 248, 248))
    return _noise(img, 3, rng)


def photo(seed):
    """6F 藝想空間 II 的攝影展：模糊背景前一朵花或一片葉子的特寫。"""
    rng = random.Random(seed * 17 + 3)
    w, h = 64, 48
    bg = rng.choice([(40, 70, 40), (110, 140, 60), (30, 30, 36), (170, 120, 150), (60, 90, 110)])
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    for _ in range(14):     # 模糊的背景光斑
        x, y, r = rng.randrange(w), rng.randrange(h), rng.randint(4, 12)
        c = tuple(max(0, min(255, v + rng.randint(-30, 40))) for v in bg)
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    fg = rng.choice([(220, 80, 140), (240, 200, 60), (120, 190, 70), (200, 60, 50), (180, 140, 220)])
    cx, cy = rng.randint(20, 44), rng.randint(14, 34)
    for k in range(6):      # 花瓣
        a = k * math.pi / 3 + rng.random() * 0.3
        px, py = cx + math.cos(a) * 7, cy + math.sin(a) * 7
        d.ellipse([px - 6, py - 4, px + 6, py + 4], fill=fg)
    d.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(250, 230, 120))
    return _noise(img, 6, rng)


def ink(word, font_path):
    """白底上幾道紫色水墨筆刷，中間直排一個大大的書法詞。"""
    rng = random.Random(len(word) * 7 + ord(word[0]))
    w, h = 160, 240
    img = Image.new("RGB", (w, h), (248, 248, 250))
    d = ImageDraw.Draw(img)
    for _ in range(26):       # 淡紫色的暈染
        x, y, r = rng.randrange(w), rng.randrange(h // 2, h), rng.randint(6, 26)
        c = rng.choice([(150, 120, 190), (190, 170, 220), (110, 80, 160), (220, 210, 236)])
        d.ellipse([x - r, y - r // 2, x + r, y + r // 2], fill=c)
    f = _font(font_path, 64)
    for i, ch in enumerate(word):
        d.text((w // 2 - 32, 18 + i * 74), ch, font=f, fill=(34, 30, 44))
    return img


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


def painting(seed):
    """藝想空間的畫：幾塊色塊和線條的抽象畫，每幅不一樣。"""
    rng = random.Random(seed * 31 + 7)
    palette = [(214, 92, 64), (236, 196, 90), (60, 96, 150), (90, 150, 130), (40, 40, 48), (232, 228, 216), (170, 120, 160)]
    img = Image.new("RGB", (64, 48), rng.choice([(238, 234, 222), (222, 214, 196), (34, 38, 52)]))
    d = ImageDraw.Draw(img)
    for _ in range(rng.randint(3, 6)):
        x, y = rng.randint(-10, 54), rng.randint(-10, 38)
        w, h = rng.randint(10, 34), rng.randint(8, 26)
        c = rng.choice(palette)
        (d.ellipse if rng.random() < 0.4 else d.rectangle)([x, y, x + w, y + h], fill=c)
    for _ in range(rng.randint(1, 3)):
        d.line([(rng.randint(0, 63), rng.randint(0, 47)), (rng.randint(0, 63), rng.randint(0, 47))],
               fill=rng.choice(palette), width=rng.randint(1, 3))
    return _noise(img, 3, rng)


def books_hd(seed, light=True, rows=6):
    """高解析度的書架正面（512×512）：每本書有圓弧的明暗、索書號貼紙、書名色帶，
    書後面和上一層層板下面有陰影，偶爾一個白色拱形書擋（照 6F 影片）。先畫兩倍大再縮小，邊緣才平滑。"""
    rng = random.Random(2000 + seed + (0 if light else 500))
    S = 1024
    if light:
        cols = [(238, 236, 228), (226, 218, 198), (176, 196, 218), (198, 202, 208), (146, 166, 194), (236, 236, 240),
                (116, 136, 168), (56, 66, 92), (150, 62, 60), (208, 188, 148), (90, 110, 80)]
        weights = [7, 5, 4, 4, 3, 5, 2, 2, 1, 2, 1]
        back = (214, 214, 212)
    else:
        cols = list(BOOK_COLORS)
        weights = [1] * len(cols)
        back = (40, 38, 36)
    img = Image.new("RGB", (S, S), back)
    d = ImageDraw.Draw(img)
    rh = S / rows
    for s in range(rows):
        top, bottom = int(s * rh), int((s + 1) * rh - 0.012 * S)
        for y in range(top, bottom):            # 書後面的背板：越上面越暗（上一層層板的影子）
            k = 0.62 + 0.38 * (y - top) / max(1, bottom - top)
            d.line([(0, y), (S, y)], fill=tuple(int(v * k) for v in back))
        x = 4 + rng.randint(0, 20)
        while x < S - 8:
            r = rng.random()
            if r < 0.015:                      # 空位
                x += rng.randint(16, 40)
                continue
            if r < 0.035 and light:             # 白色拱形書擋
                bw = 30
                d.rectangle([x, bottom - rh * 0.62, x + bw, bottom], fill=(242, 242, 240))
                d.rectangle([x + 2, bottom - rh * 0.62, x + 4, bottom], fill=(205, 205, 205))
                ax0, ax1 = x + 8, x + bw - 8
                d.rectangle([ax0, bottom - rh * 0.3, ax1, bottom - 2], fill=(150, 150, 152))
                d.ellipse([ax0, bottom - rh * 0.38, ax1, bottom - rh * 0.22], fill=(150, 150, 152))
                x += bw + 2
                continue
            bw = rng.randint(12, 30)
            bh = int(rh * rng.uniform(0.58, 0.9))
            c = rng.choices(cols, weights)[0]
            j = rng.randint(-16, 16)
            c = tuple(max(0, min(255, v + j)) for v in c)
            y0 = bottom - bh
            for i in range(bw):                 # 書背是圓的：兩邊暗、中間亮
                t = i / max(1, bw - 1)
                k = 0.72 + 0.36 * math.sin(math.pi * t) ** 0.6
                d.line([(x + i, y0), (x + i, bottom)], fill=tuple(min(255, int(v * k)) for v in c))
            d.line([(x, y0), (x + bw - 1, y0)], fill=tuple(int(v * 0.6) for v in c))
            if rng.random() < 0.55:             # 書名色帶 + 細細的字
                band = rng.choice([(30, 30, 34), (240, 236, 220), (170, 140, 60), (120, 30, 30)])
                by = y0 + int(bh * rng.uniform(0.08, 0.2))
                d.rectangle([x + 2, by, x + bw - 3, by + int(bh * 0.1)], fill=band)
            txt = (40, 40, 40) if sum(c) > 450 else (225, 225, 220)
            for k2 in range(rng.randint(2, 5)):
                ty = y0 + int(bh * (0.3 + 0.08 * k2))
                d.line([(x + bw // 2, ty), (x + bw // 2, ty + int(bh * 0.05))], fill=txt, width=2)
            if bh > rh * 0.5 and rng.random() < 0.85:   # 白色索書號貼紙
                ly = bottom - int(rh * 0.2)
                d.rectangle([x + 2, ly, x + bw - 3, ly + int(rh * 0.13)], fill=(246, 246, 240))
                for k2 in range(3):
                    d.line([(x + 4, ly + 6 + k2 * 7), (x + bw - 6, ly + 6 + k2 * 7)], fill=(70, 70, 70), width=2)
            x += bw + rng.choice([0, 0, 0, 1, 2])
        d.rectangle([0, bottom, S, int((s + 1) * rh)], fill=(150, 150, 150))   # 層板（3D 層板會蓋在上面）
    img = img.resize((512, 512), Image.LANCZOS)
    return _noise(img, 3, rng)


def photo_tile(path, size=512):
    """讀一張從影片截下來的材質。"""
    return Image.open(path).convert("RGB").resize((size, size), Image.LANCZOS)


def tile_hd():
    """1F 大廳的地磚（512×512 = 一格 2 m）：灰色石材，一塊 1 m × 0.5 m，對齊排列，
    細細的深色縫，每塊深淺不太一樣、有細小的石材斑點和一點反光（照 1F 影片）。"""
    import numpy as np
    from PIL import ImageFilter
    rng = random.Random(113)
    S = 1024
    nrng = np.random.default_rng(113)
    speck = nrng.normal(0, 7, (S, S))
    cloud = np.asarray(Image.fromarray(np.uint8(np.clip(nrng.normal(128, 40, (64, 64)), 0, 255)))
                       .resize((S, S), Image.BICUBIC).filter(ImageFilter.GaussianBlur(20))).astype(float) - 128
    base = np.zeros((S, S))
    tw, th = S // 2, S // 4
    for r in range(4):
        for c in range(2):
            g = rng.uniform(96, 116)
            base[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = g
            # 斜斜的一點反光
            yy, xx = np.mgrid[0:th, 0:tw]
            base[r * th:(r + 1) * th, c * tw:(c + 1) * tw] += 6 * np.sin((xx + yy * 0.6) / tw * math.pi * rng.uniform(0.5, 1.2))
    a = base + speck + cloud * 0.25
    for r in range(5):       # 磚縫
        a[max(0, r * th - 3):r * th + 3, :] = 52
    for c in range(3):
        a[:, max(0, c * tw - 3):c * tw + 3] = 52
    rgb = np.stack([a, a, a * 1.02 + 2], -1)
    img = Image.fromarray(np.uint8(np.clip(rgb, 0, 255)))
    return img.resize((512, 512), Image.LANCZOS)


def screen_hd(font_path, kind=0):
    """電腦螢幕畫面（512×320）：館藏查詢系統。藍色標題列、搜尋框、一筆一筆的查詢結果。
    kind 換不同的畫面，免得每台都一樣。"""
    rng = random.Random(300 + kind)
    w, h = 512, 320
    img = Image.new("RGB", (w, h), (246, 247, 249))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, 14], fill=(222, 224, 228))                    # 視窗標題列
    for i, c in enumerate([(236, 96, 90), (240, 190, 70), (98, 196, 90)]):
        d.ellipse([6 + i * 14, 3, 14 + i * 14, 11], fill=c)
    d.rectangle([0, 14, w, 58], fill=(36, 74, 140))                     # 網站標題
    f_big, f_mid, f_small = _font(font_path, 20), _font(font_path, 14), _font(font_path, 11)
    d.text((16, 24), "館藏查詢  Library Catalog", font=f_big, fill=(250, 250, 252))
    d.rectangle([16, 70, 400, 96], fill=(255, 255, 255), outline=(170, 176, 186))
    q = rng.choice(["微積分 考古題", "演算法", "線性代數", "期中考 解答", "資料結構"])
    d.text((24, 75), q, font=f_mid, fill=(40, 40, 46))
    d.rectangle([408, 70, 496, 96], fill=(226, 102, 31))
    d.text((430, 75), "搜尋", font=f_mid, fill=(255, 255, 255))
    titles = ["微積分（第十版）", "演算法導論", "線性代數及其應用", "資料結構：使用 C++", "機率與統計",
              "離散數學", "計算機組織", "作業系統概論", "普通物理學", "工程數學"]
    rng.shuffle(titles)
    for i in range(5):
        y = 110 + i * 41
        d.rectangle([16, y, 46, y + 34], fill=rng.choice([(70, 110, 170), (170, 60, 60), (60, 130, 90), (200, 160, 60)]))
        d.text((56, y), titles[i], font=f_mid, fill=(30, 60, 130))
        d.text((56, y + 18), f"QA{rng.randint(100, 999)}.{rng.randint(1, 99)}  ·  {rng.choice(['4F', '5F', '6F'])} 書庫  ·  "
               + rng.choice(["可借閱", "已借出", "可借閱"]), font=f_small, fill=(110, 112, 120))
        d.line([(16, y + 38), (w - 16, y + 38)], fill=(226, 228, 232))
    d.rectangle([0, h - 16, w, h], fill=(30, 32, 38))                   # 工作列
    for i in range(6):
        d.rectangle([180 + i * 26, h - 13, 198 + i * 26, h - 3], fill=rng.choice([(70, 130, 220), (230, 230, 235), (240, 170, 60)]))
    return img


def keyboard():
    """鍵盤上面：深灰底，一排排淺灰鍵帽（256×80）。"""
    w, h = 256, 80
    img = Image.new("RGB", (w, h), (34, 34, 38))
    d = ImageDraw.Draw(img)
    rows = [15, 14, 13, 12]
    for r, n in enumerate(rows):
        kw = (w - 12) / (n + 0.5 * r)
        x = 6 + r * kw * 0.25
        for k in range(n):
            d.rounded_rectangle([x + 1, 5 + r * 15, x + kw - 2, 17 + r * 15], radius=2, fill=(70, 70, 76))
            x += kw
    d.rounded_rectangle([60, 66, 196, 76], radius=2, fill=(70, 70, 76))   # 空白鍵
    return img
