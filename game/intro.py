"""開場動畫：按「開始遊戲」後先播一小段，交代劇情和怎麼玩。

· 第一幕：宿舍裡，你和室友約好「擺爛聯盟」
· 第二幕：隔天傍晚室友不見了，IG 限動的背景是總圖的落地窗
· 第三幕：衝進總圖，館員在巡館，旁白教你怎麼玩
空白鍵／Enter／滑鼠左鍵：下一句（字還在跑的話先整句跑完）
Esc：整段跳過
"""
import math

from PIL import Image, ImageDraw
from ursina import Cylinder, Entity, Text, Texture, Vec3, camera, color, destroy, time, window

from npc import Person

BASE = Vec3(600, 0, 600)        # 宿舍蓋在離圖書館很遠的地方，鏡頭只拍得到這間
NAMES = {   # 說話的人 → 名牌顏色
    "你": (230, 120, 30), "室友": (70, 120, 200), "館員": (40, 130, 90), "": (120, 120, 128),
}

# (說話的人, 台詞, 鏡頭, 動作)
SCRIPT = [
    ("", "期中考前一週，清大宿舍。", "dorm_wide", None),
    ("你", "我宣布，擺爛聯盟正式成立！這次期中考，誰都不准讀書。", "dorm_you", "you_raise"),
    ("室友", "沒問題！我明天要在宿舍睡一整天。讀書？那是什麼？", "dorm_mate", "mate_raise"),
    ("你", "一言為定！", "dorm_wide", "high_five"),
    ("", "隔天你睡到下午五點。室友早就出門了，你連他今天穿什麼都不知道。", "dorm_empty", "mate_gone"),
    ("你", "糟了，教授的報告明天要交，還要去總圖還書、找文獻……咦，他發了 IG 限動？", "phone", "phone"),
    ("你", "這背景……是總圖的落地窗！說好一起擺爛，結果你偷卷？", "phone", "phone_angry"),
    ("", "你抱著逾期的書衝進清大總圖。可是館員正在巡館——", "lib_wide", "lib"),
    ("館員", "同學，館內請勿奔跑、保持安靜。警告三次，就請你出去喔。", "lib_guard", "lib"),
    ("", "【任務】先到櫃臺還書，再一層層往上找線索。路人頭上有「？」就去問，答對題目他們會告訴你室友今天的外套、帽子和書包。", "lib_wide", "lib"),
    ("", "【操作】WASD 走路、滑鼠看、E 互動。Shift 跑步很吵；按住 Ctrl 躡手躡腳；C 躲到桌子底下。", "lib_wide", "lib"),
    ("", "【抓人】4F 坐滿了讀書的學生。照線索認出室友，趁他低頭時靠近按 E！認錯人會被館員罵。", "lib_guard", "lib"),
    ("", "卡住的時候，跟著黃色驚嘆號走。22:00 閉館前，一定要抓到他！", "lib_wide", "lib"),
]


def _sky_texture():
    """宿舍窗外的傍晚天空：上面藍紫、下面橘，遠處一排深色的宿舍樓和樹。"""
    w, h = 256, 192
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line((0, y, w, y), fill=(int(90 + 160 * t), int(90 + 70 * t), int(150 - 60 * t)))
    d.ellipse((170, 110, 210, 150), fill=(255, 220, 150))
    for i, x in enumerate(range(0, w, 40)):
        top = 120 + (i * 37) % 30
        d.rectangle((x, top, x + 34, h), fill=(60, 50, 70))
        for wy in range(top + 8, h, 14):
            for wx in range(x + 5, x + 30, 9):
                if (wx + wy + i) % 3:
                    d.rectangle((wx, wy, wx + 4, wy + 6), fill=(250, 210, 120))
    for x in range(-10, w, 22):
        d.ellipse((x, 160, x + 34, 200), fill=(40, 70, 50))
    return Texture(img)


def _phone_texture(window_tex_img=None):
    """IG 限動：總圖的落地窗（綠樹＋窗框），上面一條進度條、頭像。"""
    w, h = 180, 320
    img = Image.new("RGB", (w, h), (235, 235, 230))
    d = ImageDraw.Draw(img)
    for y in range(h):     # 窗外的天空和樹
        t = y / h
        d.line((0, y, w, y), fill=(int(200 - 40 * t), int(220 - 30 * t), int(235 - 60 * t)))
    for x in range(-20, w, 30):
        d.ellipse((x, 150 + (x * 7) % 20, x + 60, 240), fill=(80, 140, 70))
    for x in range(0, w, 45):   # 落地窗的直框
        d.rectangle((x, 0, x + 4, h), fill=(90, 92, 96))
    d.rectangle((0, 95, w, 99), fill=(90, 92, 96))
    d.rectangle((0, 250, w, h), fill=(225, 205, 170))     # 窗邊的木頭桌
    d.rectangle((40, 262, 120, 300), fill=(40, 90, 160))  # 攤開的微積分課本
    d.rectangle((80, 262, 82, 300), fill=(20, 50, 100))
    d.rectangle((8, 8, w - 8, 11), fill=(255, 255, 255))   # 限動的進度條
    d.ellipse((10, 18, 32, 40), fill=(120, 125, 135))     # 頭像
    return Texture(img)


class Intro:
    def __init__(self, game):
        self.game = game
        self.font_path = game.font_path
        self.ui = Entity(parent=camera.ui, z=-0.7, enabled=False)
        self.box = Entity(parent=self.ui, model="quad", color=color.rgba32(15, 15, 20, 225), position=(0, -0.36),
                          scale=(1.5, 0.22))
        self.name_bg = Entity(parent=self.ui, model="quad", position=(-0.6, -0.235), scale=(0.2, 0.055), z=-0.01)
        self.name = Text(parent=self.ui, position=(-0.6, -0.235), origin=(0, 0), scale=1.2, color=color.white, z=-0.02)
        self.text = Text(parent=self.ui, position=(-0.7, -0.285), scale=1.5, color=color.rgb32(240, 236, 226),
                         line_height=1.25, z=-0.02)
        self.tip = Text(parent=self.ui, position=(0.72, -0.455), origin=(0.5, 0), scale=0.75,
                        color=color.rgb32(170, 170, 170), text="空白鍵／點一下：下一句　　Esc：跳過動畫", z=-0.02)
        self.bars = [Entity(parent=self.ui, model="quad", color=color.black, position=(0, y), scale=(4, 0.08), z=0.1)
                     for y in (0.47, -0.47)]
        self.phone = Entity(parent=self.ui, model="quad", position=(0.0, 0.1), scale=(0.24, 0.43), z=-0.03,
                            color=color.rgb32(25, 25, 28), enabled=False)
        self.phone_screen = Entity(parent=self.phone, model="quad", scale=(0.9, 0.9), z=-0.01, texture=_phone_texture())
        self.set = None
        self.i = -1
        self.t = 0.0
        self.shown = 0.0
        self.on_done = None
        self.driver = Entity(update=self.update, enabled=False)

    # ---------- 宿舍佈景 ----------
    def build_dorm(self):
        """照使用者拍的宿舍照片：長條形四人房，中間一條白磁磚走道，兩邊各兩組淺木色「上面床、下面衣櫃書桌」，
        床的樓梯是斜的置物階梯，盡頭一扇窗、窗上一台冷氣。門口那端往窗戶看。"""
        root = Entity(position=BASE)
        self.set = root
        wood, wood_dk = color.rgb32(206, 188, 162), color.rgb32(178, 160, 136)
        white, wall_col = color.rgb32(236, 233, 224), color.rgb32(236, 230, 212)
        L0, L1, W = -3.3, 3.0, 1.55          # 房間 z 從門到窗、x 半寬

        def box(pos, scale, col, rot=(0, 0, 0)):
            return Entity(parent=root, model="cube", position=pos, scale=scale, color=col, rotation=rot)
        tile = Image.new("RGB", (128, 128), (226, 223, 214))
        ImageDraw.Draw(tile).rectangle((0, 0, 127, 127), outline=(170, 166, 158), width=3)
        Entity(parent=root, model="quad", rotation_x=90, position=(0, 0.001, (L0 + L1) / 2), scale=(2 * W, L1 - L0),
               texture=Texture(tile), texture_scale=(2 * W / 0.4, (L1 - L0) / 0.4))     # 40 公分白磁磚
        box((0, -0.05, (L0 + L1) / 2), (2 * W, 0.1, L1 - L0), color.rgb32(200, 196, 188))
        box((0, 1.45, L1), (2 * W, 2.9, 0.1), wall_col)                       # 窗戶那面
        box((0, 1.45, L0), (2 * W, 2.9, 0.1), wall_col)                       # 門那面（在鏡頭後面）
        for side in (-1, 1):
            box((side * W, 1.45, (L0 + L1) / 2), (0.1, 2.9, L1 - L0), wall_col)
        box((0, 2.9, (L0 + L1) / 2), (2 * W, 0.1, L1 - L0), color.rgb32(242, 240, 234))
        box((0, 0.05, L1 - 0.06), (2 * W, 0.1, 0.02), color.rgb32(90, 60, 45))   # 深色踢腳板
        box((0.1, 2.87, (L0 + L1) / 2), (0.1, 0.04, 2.4), color.rgb32(250, 250, 250))   # 日光燈
        # 窗戶：窄長的白框窗，上面一台分離式冷氣
        Entity(parent=root, model="quad", position=(0.1, 1.3, L1 - 0.06), scale=(0.75, 1.5), texture=_sky_texture(),
               color=color.rgb(1.15, 1.15, 1.15))
        for y in (0.55, 1.3, 2.05):
            box((0.1, y, L1 - 0.08), (0.85, 0.06, 0.05), white)
        for x in (-0.3, 0.1, 0.5):
            box((x, 1.3, L1 - 0.08), (0.06, 1.55, 0.05), white)
        box((0.1, 2.45, L1 - 0.17), (0.95, 0.3, 0.22), color.rgb32(248, 248, 246))
        box((0.1, 2.33, L1 - 0.28), (0.85, 0.03, 0.02), color.rgb32(210, 210, 210))

        def wardrobe(x, z0, z1, h=2.0):       # 兩扇門的衣櫃，門朝走道
            zc = (z0 + z1) / 2
            box((x, h / 2, zc), (0.62, h, z1 - z0), wood)
            f = x - math.copysign(0.315, x)
            box((f, h / 2, zc), (0.01, h - 0.06, 0.012), wood_dk)                # 中間門縫
            for dz in (-0.07, 0.07):
                box((f - math.copysign(0.02, x), 1.0, zc + dz), (0.02, 0.16, 0.015), color.rgb32(190, 190, 192))

        def desk(x, z0, z1):                  # 書桌＋活動抽屜櫃
            box((x, 0.74, (z0 + z1) / 2), (0.62, 0.04, z1 - z0), wood)
            box((x + math.copysign(0.29, x), 0.37, (z0 + z1) / 2), (0.04, 0.74, z1 - z0), wood)
            px = x - math.copysign(0.05, x)
            box((px, 0.32, z0 + 0.25), (0.5, 0.6, 0.42), color.rgb32(225, 223, 216))
            for k in range(3):
                box((px - math.copysign(0.255, x), 0.15 + k * 0.19, z0 + 0.25), (0.01, 0.025, 0.22), color.rgb32(150, 150, 150))

        def loft(x, z0, z1):                  # 上舖：木床板、白色鐵柱、走道那側有欄杆
            box((x, 1.9, (z0 + z1) / 2), (0.95, 0.06, z1 - z0), wood)
            box((x, 1.84, (z0 + z1) / 2), (0.95, 0.06, z1 - z0), wood_dk)
            ax = x - math.copysign(0.46, x)
            for z in (z0 + 0.03, z1 - 0.03):
                box((ax, 1.3, z), (0.05, 2.6, 0.05), white)
            box((ax, 2.25, (z0 + z1) / 2 + 0.3), (0.035, 0.035, z1 - z0 - 0.6), white)
            for k in range(4):
                box((ax, 2.1, z0 + 0.6 + k * (z1 - z0 - 1.2) / 3), (0.03, 0.3, 0.03), white)

        def stair(x, z0):                     # 斜的置物階梯（照片裡上舖的樓梯）
            sx = x - math.copysign(0.05, x)
            box((sx, 0.95, z0 + 0.3), (0.5, 1.9, 0.04), wood)                    # 背板
            box((sx, 0.95, z0 + 0.3), (0.04, 2.1, 0.06), wood, rot=(-28, 0, 0))   # 斜梁
            for k in range(4):
                box((sx, 0.3 + k * 0.42, z0 + 0.1 + k * 0.12), (0.46, 0.04, 0.25), wood)

        for side in (-1, 1):
            x = side * (W - 0.32)
            # 門口這組：書桌（上面一層開放層板）、衣櫃，床在上面
            desk(x, L0, L0 + 1.0)
            box((x, 1.3, L0 + 0.5), (0.62, 0.03, 1.0), wood)
            wardrobe(x, L0 + 1.0, L0 + 1.8)
            loft(side * (W - 0.48), L0 + 0.1, L0 + 2.6)
            # 窗戶這組：樓梯、衣櫃、書桌，床在上面
            stair(x, L0 + 2.75)
            wardrobe(x, L0 + 3.4, L0 + 4.2)
            desk(x, L0 + 4.2, L1)
            loft(side * (W - 0.48), L0 + 2.7, L1 - 0.05)
            # 床上的被子和枕頭
            for z0, z1, col in ((L0 + 0.2, L0 + 2.5, (120, 150, 200) if side < 0 else (220, 150, 120)),
                                (L0 + 2.8, L1 - 0.15, (200, 200, 190))):
                box((side * (W - 0.48), 2.0, (z0 + z1) / 2), (0.85, 0.14, z1 - z0), color.rgb32(*col))
                box((side * (W - 0.48), 2.11, z1 - 0.25), (0.4, 0.1, 0.25), color.rgb32(245, 245, 245))
            # 桌上：筆電、零食
            box((x + 0.05 * side, 0.89, L0 + 0.55), (0.3, 0.22, 0.02), color.rgb32(40, 40, 46))
            box((x, 0.88, L0 + 0.2), (0.25, 0.25, 0.15), color.rgb32(240, 200, 80))
        Entity(parent=root, model=Cylinder(12), position=(-(W - 0.32), 0.76, L0 + 0.85), scale=(0.12, 0.18, 0.12),
               color=color.rgb32(200, 40, 40))      # 泡麵
        # ---- 生活感小東西（使用者：宿舍放什麼自由發揮）----
        def cyl(pos, r, h, col):
            return Entity(parent=root, model=Cylinder(10), position=pos, scale=(r, h, r), color=color.rgb32(*col))
        yx, mx = -(W - 0.32), W - 0.32                 # 你的桌子在左、室友在右
        top = 0.76
        # 你的桌子：擺爛現場，泡麵碗、能量飲料、搖桿
        for k, dz in enumerate((0.3, 0.45, 0.62)):
            cyl((yx + 0.12, top, L0 + dz), 0.11, 0.1, (230, 230, 225) if k else (200, 40, 40))
        for dz in (0.1, 0.16, 0.22):
            cyl((yx - 0.1, top, L0 + 0.75 + dz), 0.035, 0.13, (40, 180, 90))
        box((yx + 0.05, top + 0.03, L0 + 0.9), (0.16, 0.05, 0.1), color.rgb32(30, 30, 34))
        # 室友的桌子：螢幕、檯燈，還有一疊藏不住的課本（偷卷的伏筆）
        box((mx + 0.1, top + 0.25, L0 + 0.5), (0.04, 0.32, 0.55), color.rgb32(25, 25, 28))
        box((mx + 0.1, top + 0.25, L0 + 0.5), (0.05, 0.28, 0.5), color.rgb32(60, 90, 140))
        box((mx + 0.12, top + 0.05, L0 + 0.5), (0.12, 0.1, 0.12), color.rgb32(25, 25, 28))
        for k, col in enumerate(((180, 40, 40), (40, 80, 160), (230, 200, 60), (60, 140, 80), (240, 240, 235))):
            box((mx - 0.08, top + 0.03 + k * 0.055, L0 + 0.85), (0.24, 0.05, 0.32 - k * 0.02), color.rgb32(*col))
        cyl((mx + 0.15, top, L0 + 0.12), 0.08, 0.02, (40, 40, 44))      # 檯燈
        box((mx + 0.15, top + 0.22, L0 + 0.12), (0.02, 0.44, 0.02), color.rgb32(40, 40, 44))
        box((mx + 0.08, top + 0.44, L0 + 0.12), (0.18, 0.04, 0.1), color.rgb32(40, 40, 44))
        # 兩張桌上的水壺
        cyl((yx + 0.2, top, L0 + 0.1), 0.05, 0.22, (90, 160, 210))
        cyl((mx + 0.2, top, L0 + 0.9), 0.05, 0.22, (230, 120, 140))
        # 床邊欄杆晾著毛巾、衣服
        for side, z, col in ((-1, L0 + 1.4, (250, 200, 80)), (1, L0 + 0.9, (120, 200, 200)), (-1, L0 + 3.9, (220, 220, 230)),
                             (1, L0 + 4.6, (240, 160, 160))):
            ax = side * (W - 0.48) - side * 0.47
            box((ax, 1.95, z), (0.02, 0.5, 0.35), color.rgb32(*col))
        # 衣櫃門上貼的小海報、門口的拖鞋、窗邊的洗衣籃、垃圾桶
        for side, z, col in ((-1, L0 + 1.4, (60, 60, 120)), (1, L0 + 1.25, (230, 90, 60)), (1, L0 + 3.8, (90, 160, 120))):
            box((side * 0.905, 1.45, z), (0.01, 0.38, 0.27), color.rgb32(*col))
            box((side * 0.9, 1.45, z), (0.01, 0.24, 0.17), color.rgb32(245, 240, 225))
        for side, z, col in ((-1, L0 + 1.1, (40, 60, 130)), (1, L0 + 1.0, (60, 60, 60)), (-1, L0 + 3.6, (200, 60, 60)), (1, L0 + 3.5, (240, 240, 240))):
            for dz in (-0.07, 0.07):
                box((side * 0.75, 0.02, z + dz), (0.26, 0.03, 0.1), color.rgb32(*col))
        cyl((0.6, 0, L1 - 0.5), 0.24, 0.4, (150, 190, 230))                  # 洗衣籃
        box((0.6, 0.42, L1 - 0.5), (0.3, 0.1, 0.3), color.rgb32(230, 230, 235))
        cyl((-0.75, 0, L0 + 2.6), 0.14, 0.32, (90, 90, 96))                  # 垃圾桶
        cyl((-0.75, 0.3, L0 + 2.6), 0.1, 0.06, (230, 230, 225))              # 塞到滿出來的泡麵碗
        # 牆上的期中考倒數月曆
        box((-0.6, 2.25, L1 - 0.06), (0.35, 0.45, 0.02), color.rgb32(250, 250, 248))
        box((-0.6, 2.4, L1 - 0.075), (0.35, 0.12, 0.01), color.rgb32(200, 50, 50))
        import shading
        shading.light_scene(root.get_descendants())     # 跟圖書館一樣有光影，木櫃的面才分得出來

        self.you = Person(shirt=color.rgb32(230, 120, 30), pants=color.rgb32(50, 50, 60), hair=color.rgb32(40, 30, 25))
        self.mate = Person(shirt=color.rgb32(120, 125, 135), pants=color.rgb32(40, 60, 100), hair=color.rgb32(25, 22, 20))
        self.mate.dress(bag=(170, 50, 45))     # 室友的紅書包
        self.you.root.position = BASE + Vec3(-0.42, 0, -1.2)
        self.you.root.rotation_y = 90
        self.mate.root.position = BASE + Vec3(0.42, 0, -1.2)
        self.mate.root.rotation_y = -90
        self.phone_prop = Entity(parent=self.you.hands[1], model="cube", position=(0, -0.02, 0.1),
                                 scale=(0.08, 0.14, 0.02), color=color.rgb32(20, 20, 24), enabled=False)

    def clear_dorm(self):
        for e in (self.set, getattr(self, "you", None) and self.you.root, getattr(self, "mate", None) and self.mate.root):
            if e:
                destroy(e)
        self.set = None

    # ---------- 播放 ----------
    def play(self, on_done):
        self.on_done = on_done
        self.build_dorm()
        self.ui.enabled = True
        self.driver.enabled = True
        self.i = -1
        self.next()

    def finish(self):
        if not self.driver.enabled:
            return
        self.ui.enabled = False
        self.driver.enabled = False
        self.phone.enabled = False
        self.clear_dorm()
        done, self.on_done = self.on_done, None
        if done:
            done()

    def next(self):
        line = SCRIPT[self.i] if 0 <= self.i < len(SCRIPT) else None
        if line and self.shown < len(line[1]):     # 字還在跑：先整句顯示
            self.shown = len(line[1])
            return
        self.i += 1
        if self.i >= len(SCRIPT):
            self.finish()
            return
        who, words, shot, act = SCRIPT[self.i]
        self.shown, self.t = 0.0, 0.0
        self.name.text = who or "旁白"
        self.name_bg.color = color.rgb32(*NAMES[who])
        self.name_bg.scale_x = 0.05 + 0.045 * len(self.name.text)
        self.shot, self.act = shot, act
        self.phone.enabled = shot == "phone"
        if act == "mate_gone":
            self.mate.root.enabled = False
            self.you.root.position = BASE + Vec3(-0.1, 0, -0.8)
            self.you.root.rotation_y = 30
        if act == "lib":
            self.game.librarian.root.enabled = True

    def input(self, key):
        if key == "escape":
            self.finish()
        elif key in ("space", "enter", "left mouse down", "e"):
            self.next()

    def update(self):
        self.t += time.dt
        who, words, shot, act = SCRIPT[self.i]
        self.shown = min(len(words), self.shown + time.dt * 28)
        self.text.text = self.wrap(words[:int(self.shown)])
        self.animate(act)
        self.aim(shot)

    @staticmethod
    def wrap(s, width=30):
        return "\n".join(s[i:i + width] for i in range(0, len(s), width))

    def animate(self, act):
        t = self.t
        you, mate = self.you, self.mate
        for p in (you, mate):
            p.head.rotation_y = math.sin(t * 1.3 + (p is mate)) * 6     # 說話時頭輕輕晃
        you.arms[0].rotation_x = mate.arms[0].rotation_x = 0
        if act == "you_raise":
            you.arms[0].rotation_x = -150 + math.sin(t * 8) * 10
        elif act == "mate_raise":
            mate.arms[0].rotation_x = -150 + math.sin(t * 8) * 10
            mate.torso.rotation_z = math.sin(t * 3) * 4
        elif act == "high_five":
            k = min(1.0, t * 2)
            you.arms[0].rotation_x = mate.arms[0].rotation_x = -165 * k
            you.root.x = BASE.x - 0.42 + 0.17 * k
            mate.root.x = BASE.x + 0.42 - 0.17 * k
        if act in ("phone", "phone_angry"):
            self.phone_prop.enabled = True
            you.arms[1].rotation_x = -80
            if act == "phone_angry":
                shake = math.sin(t * 40) * 0.01 * max(0, 1 - t)
                self.phone.x = shake
                you.torso.rotation_z = math.sin(t * 30) * 3 * max(0, 1 - t * 0.7)
        if act == "lib":
            g = self.game.librarian
            g.root.position = Vec3((9 + math.sin(t * 0.25) * 2.5) * 2, 0, -26)     # 館員在大廳來回走
            g.root.rotation_y = 90 if math.cos(t * 0.25) > 0 else -90
            g.walk_anim(6)

    @staticmethod
    def look(pos, target):
        """鏡頭放在 pos、看向 target，不會歪頭（look_at 偶爾會讓畫面傾斜）。"""
        d = target - pos
        camera.position = pos
        camera.rotation = (-math.degrees(math.atan2(d.y, math.hypot(d.x, d.z))), math.degrees(math.atan2(d.x, d.z)), 0)

    def aim(self, shot):
        b = BASE
        sway = math.sin(self.t * 0.4) * 0.08
        shots = {
            "dorm_wide": (b + Vec3(sway, 1.6, -3.15), b + Vec3(0, 1.15, 0.6)),
            "dorm_you": (b + Vec3(0.35, 1.55, -3.1 + sway), b + Vec3(-0.42, 1.45, -1.2)),
            "dorm_mate": (b + Vec3(-0.35, 1.55, -3.1 + sway), b + Vec3(0.42, 1.45, -1.2)),
            "dorm_empty": (b + Vec3(-0.3, 1.75, -3.15), b + Vec3(0.6, 1.5, 1.5)),
            "phone": (b + Vec3(0.3, 1.55, -2.9), b + Vec3(-0.1, 1.35, -0.8)),
            "lib_wide": (Vec3(14 + sway * 4, 2.4, -33), Vec3(19, 1.3, -25)),
        }
        if shot == "lib_guard":
            g = self.game.librarian.root.position
            self.look(Vec3(g.x - 2.5, 1.8, g.z - 3.0), g + Vec3(0, 1.4, 0))
        else:
            self.look(*shots[shot])
