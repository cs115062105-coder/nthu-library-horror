"""開場動畫：按「開始遊戲」後先播一小段，交代劇情和怎麼玩。

· 第一幕：宿舍裡，你和室友約好「擺爛聯盟」
· 第二幕：隔天傍晚室友不見了，IG 限動的背景是總圖的落地窗
· 第三幕：衝進總圖，館員在巡館，旁白教你怎麼玩
空白鍵／Enter／滑鼠左鍵：下一句（字還在跑的話先整句跑完）
Esc：整段跳過
"""
import math

from PIL import Image, ImageDraw
from ursina import Entity, Text, Texture, Vec3, camera, color, destroy, time, window

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
        root = Entity(position=BASE)
        self.set = root
        floor_col, wall_col = color.rgb32(196, 176, 150), color.rgb32(232, 226, 214)

        def box(pos, scale, col):
            return Entity(parent=root, model="cube", position=pos, scale=scale, color=col)
        box((0, -0.05, 0), (6, 0.1, 5), floor_col)
        box((0, 1.5, 2.5), (6, 3, 0.1), wall_col)          # 北牆（窗戶那面）
        box((-3, 1.5, 0), (0.1, 3, 5), wall_col)
        box((3, 1.5, 0), (0.1, 3, 5), wall_col)
        box((0, 3, 0), (6, 0.1, 5), color.rgb32(240, 238, 232))
        Entity(parent=root, model="quad", position=(0, 1.7, 2.44), scale=(1.8, 1.3), texture=_sky_texture(),
               color=color.rgb(1.1, 1.1, 1.1))   # 窗外
        box((0, 1.7, 2.42), (1.9, 0.06, 0.04), color.rgb32(200, 200, 200))
        box((0, 1.05, 2.42), (2.0, 0.06, 0.12), color.rgb32(200, 200, 200))
        box((0, 2.35, 2.42), (2.0, 0.06, 0.04), color.rgb32(200, 200, 200))
        for side in (-1, 1):        # 兩組床下書桌的上下舖：上面床，下面書桌
            x = side * 2.0
            wood = color.rgb32(170, 130, 90)
            for dz in (-1.0, 1.0):
                for dx in (-0.55, 0.55):
                    box((x + dx, 1.0, dz), (0.08, 2.0, 0.08), wood)
            box((x, 1.65, 0), (1.2, 0.12, 2.1), wood)                      # 床板
            box((x, 1.78, 0), (1.1, 0.15, 2.0), color.rgb32(120, 150, 200) if side < 0 else color.rgb32(220, 150, 120))
            box((x, 0.75, 0.4), (1.1, 0.05, 1.0), color.rgb32(200, 170, 130))   # 書桌
            box((x + 0.1 * side, 0.95, 0.5), (0.35, 0.25, 0.02), color.rgb32(40, 40, 46))  # 筆電
            box((x, 0.9, -0.3), (0.3, 0.3, 0.2), color.rgb32(240, 200, 80))        # 零食
        box((-2.0, 1.95, -0.8), (0.4, 0.12, 0.25), color.rgb32(245, 245, 245))     # 枕頭
        box((2.0, 1.95, -0.8), (0.4, 0.12, 0.25), color.rgb32(245, 245, 245))
        Entity(parent=root, model="quad", position=(-2.94, 1.6, 0.9), rotation_y=-90, scale=(0.6, 0.8),
               color=color.rgb32(200, 60, 50))        # 牆上的海報
        Entity(parent=root, model="quad", position=(-2.93, 1.6, 0.9), rotation_y=-90, scale=(0.4, 0.15),
               color=color.rgb32(250, 240, 200))
        box((0, 0.2, -1.2), (1.2, 0.4, 0.7), color.rgb32(110, 90, 70))   # 中間的小茶几
        Entity(parent=root, model="cylinder", position=(0.3, 0.4, -1.2), scale=(0.12, 0.2, 0.12),
               color=color.rgb32(200, 40, 40))      # 泡麵

        self.you = Person(shirt=color.rgb32(230, 120, 30), pants=color.rgb32(50, 50, 60), hair=color.rgb32(40, 30, 25))
        self.mate = Person(shirt=color.rgb32(120, 125, 135), pants=color.rgb32(40, 60, 100), hair=color.rgb32(25, 22, 20))
        Entity(parent=self.mate.torso, model="cube", position=(0, 0.4, -0.2), scale=(0.38, 0.5, 0.16),
               color=color.rgb32(170, 50, 45))     # 室友的紅書包
        self.you.root.position = BASE + Vec3(-0.7, 0, -0.6)
        self.you.root.rotation_y = 90
        self.mate.root.position = BASE + Vec3(0.7, 0, -0.6)
        self.mate.root.rotation_y = -90
        self.phone_prop = Entity(parent=self.you.arms[1], model="cube", position=(0, -0.62, 0.12),
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
            self.you.root.position = BASE + Vec3(-0.3, 0, -0.4)
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
            you.root.x = BASE.x - 0.7 + 0.25 * k
            mate.root.x = BASE.x + 0.7 - 0.25 * k
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
            "dorm_wide": (b + Vec3(sway, 1.75, -4.6), b + Vec3(0, 1.1, 0)),
            "dorm_you": (b + Vec3(0.9, 1.6, -2.7 + sway), b + Vec3(-0.6, 1.45, -0.6)),
            "dorm_mate": (b + Vec3(-0.9, 1.6, -2.7 + sway), b + Vec3(0.6, 1.45, -0.6)),
            "dorm_empty": (b + Vec3(-1.2, 1.8, -3.8), b + Vec3(2.0, 1.6, 0)),
            "phone": (b + Vec3(0.7, 1.6, -2.6), b + Vec3(-0.3, 1.35, -0.4)),
            "lib_wide": (Vec3(14 + sway * 4, 2.4, -33), Vec3(19, 1.3, -25)),
        }
        if shot == "lib_guard":
            g = self.game.librarian.root.position
            self.look(Vec3(g.x - 2.5, 1.8, g.z - 3.0), g + Vec3(0, 1.4, 0))
        else:
            self.look(*shots[shot])
