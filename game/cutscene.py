"""遊戲中的短動畫（使用者要求）：

· stairs：走樓梯間，鏡頭沿著一段水泥樓梯往上／往下走，轉角牆上寫著要去的樓層
· warn：被館員警告，鏡頭轉向館員，館員搖手指「噓——」
· expel：被警告三次，換到 1F 真的出入口，館員在出口閘門旁指著外面，你垂頭喪氣走出去
· caught：第二階段被繃帶室友抓到，室友衝過來指著你、把書搶走

除了 warn、caught 是在原地演（用場上真的館員／室友），stairs 蓋在離圖書館很遠的地方，expel 在 1F 真的出入口演，
只有鏡頭看得到。播放時玩家停用（Ursina 會把鏡頭交還給場景），播完再啟用就會回到玩家眼睛。
Esc／空白鍵可以跳過。
"""
import math

from ursina import Entity, Text, Texture, Vec3, camera, color, destroy, time

import textures as tx
from npc import Person

STAIR_BASE = Vec3(-600, 0, 600)


def _stone_tile():
    """深灰石材磁磚（60 公分一塊）：帶一點斑駁，邊上一條淺色磁磚縫。"""
    import random
    from PIL import Image, ImageDraw, ImageFilter
    rnd = random.Random(7)
    im = Image.new("RGB", (128, 128), (82, 84, 86))
    d = ImageDraw.Draw(im)
    for _ in range(900):
        x, y = rnd.randrange(128), rnd.randrange(128)
        v = rnd.randint(-16, 16)
        d.point((x, y), fill=(82 + v, 84 + v, 86 + v))
    im = im.filter(ImageFilter.GaussianBlur(0.8))
    d = ImageDraw.Draw(im)
    d.line([(0, 0), (127, 0)], fill=(168, 168, 164), width=2)
    d.line([(0, 0), (0, 127)], fill=(168, 168, 164), width=2)
    return im


def _library_view():
    """樓梯口外面的圖書館：深色木條天花板配黃色燈條、白柱子、灰色條紋地毯。"""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (256, 224), (236, 236, 232))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 256, 70], fill=(60, 44, 36))
    for k in range(6):
        y = 10 + k * 10
        d.line([(10 + k * 6, y), (246 - k * 6, y)], fill=(250, 220, 120), width=2)
    d.rectangle([0, 150, 256, 224], fill=(120, 120, 122))
    for k in range(5):
        d.rectangle([0, 160 + k * 14, 256, 166 + k * 14], fill=(150, 150, 152))
    for x in (40, 180):
        d.rectangle([x, 70, x + 26, 150], fill=(246, 246, 244))
    for x in range(70, 170, 22):
        d.rectangle([x, 100, x + 16, 150], fill=(230, 232, 236))
        d.rectangle([x + 2, 104, x + 14, 146], fill=(140, 120, 110))
    return im


def look(pos, target):
    d = target - pos
    camera.position = pos
    camera.rotation = (-math.degrees(math.atan2(d.y, math.hypot(d.x, d.z))), math.degrees(math.atan2(d.x, d.z)), 0)


def ease(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


class Cutscene:
    def __init__(self, game):
        self.game = game
        self.ui = Entity(parent=camera.ui, z=-0.6, enabled=False)
        self.bars = [Entity(parent=self.ui, model="quad", color=color.black, position=(0, y), scale=(4, 0.1))
                     for y in (0.46, -0.46)]
        self.caption = Text(parent=self.ui, position=(0, -0.37), origin=(0, 0), scale=1.4,
                            color=color.rgb32(245, 240, 230), z=-0.01)
        self.fade = Entity(parent=self.ui, model="quad", scale=(4, 2), color=color.rgba32(0, 0, 0, 0), z=-0.02)
        self.driver = Entity(update=self.update, enabled=False)
        self.kind, self.t, self.length = None, 0.0, 1.0
        self.on_done = None
        self.ents = []
        self.kw = {}

    @property
    def active(self):
        return self.driver.enabled

    # ---------- 播放控制 ----------
    def play(self, kind, on_done, **kw):
        g = self.game
        self.kind, self.kw, self.on_done, self.t = kind, kw, on_done, 0.0
        self.prev_state = g.state
        g.state = "cutscene"
        g.update_prompt(off=True)
        g.hide_help()
        self.saved_fov = camera.fov
        g.player.enabled = False
        self.hud = [e for e in (g.ui_left, g.hint, g.hint_bg, g.minimap.root, g.bang, g.edge_bang) if e.enabled]
        for e in self.hud:                    # 動畫時把介面藏起來，只留黑邊和字幕
            e.enabled = False
        g.hint.text = ""
        self.ui.enabled = True
        self.caption.text = ""
        self.fade.color = color.rgba32(0, 0, 0, 0)
        getattr(self, "start_" + kind)()
        self.driver.enabled = True

    def finish(self):
        if not self.driver.enabled:
            return
        self.driver.enabled = False
        getattr(self, "end_" + self.kind, lambda: None)()
        for e in self.ents:
            destroy(e)
        self.ents = []
        self.ui.enabled = False
        for e in self.hud:
            if e is not self.game.hint_bg:
                e.enabled = True
        camera.fov = self.saved_fov
        g = self.game
        g.state = "play"
        g.player.enabled = True
        done, self.on_done = self.on_done, None
        if done:
            done()

    def input(self, key):
        if key in ("escape", "space", "enter"):
            self.finish()

    def update(self):
        self.t += min(time.dt, 0.05)    # 剛換完樓層那一幀 dt 很大，不要讓動畫一下跳到後面
        getattr(self, "tick_" + self.kind)(self.t)
        if self.t >= self.length:
            self.finish()

    def black(self, a):
        self.fade.color = color.rgba(0, 0, 0, max(0.0, min(1.0, a)))

    def own(self, e):
        self.ents.append(e)
        return e

    def box(self, parent, pos, scale, col, rot=(0, 0, 0)):
        return Entity(parent=parent, model="cube", position=pos, scale=scale, color=col, rotation=rot)

    def sign(self, lines, w=256, h=96, bg=(20, 110, 60), fg=(255, 255, 255), sizes=None):
        im = tx.sign(lines, self.game.font_path, w=w, h=h, bg=bg, fg=fg, sizes=sizes or [44, 20][:len(lines)])
        return Texture(im, filtering="bilinear")

    # ---------- 樓梯間 ----------
    def start_stairs(self):
        """照使用者拍的樓梯間影片（IMG_0925–0927）：白牆、深灰石材磁磚踏階（有磁磚縫）、
        每段第一階和最後一階有黃色止滑條；兩段樓梯中間是白色矮牆，上面黑色鐵欄杆（幾條橫桿）；
        外牆有黑色圓扶手；中間一個平台折返；牆上日光燈和綠色逃生指示燈；
        樓梯口是灰色鐵門框的開口，看得到外面的圖書館。上樓從下面的門口走進來，爬兩段，到上面的門口；下樓反過來。"""
        self.length = 3.2
        up = self.kw["direction"] == "up"
        root = self.own(Entity(position=STAIR_BASE))
        tile = Texture(_stone_tile(), filtering="mipmap")
        white, riser_c, rail = color.rgb32(238, 238, 234), color.rgb32(62, 64, 66), color.rgb32(36, 36, 38)
        yellow = color.rgb32(235, 200, 40)
        n, rise, run, w = 12, 0.17, 0.3, 1.45
        H = n * rise                      # 一段樓梯的高度
        L = n * run                       # 一段樓梯的長度
        X1, X2 = -0.86, 0.86              # 第一段（往 +z 爬）、第二段（往 -z 爬）的中線
        TOP = 2 * H

        treads = []

        def tread(x, y, z, sx, sz):
            treads.append(Entity(parent=root, model="cube", position=(x, y - 0.015, z), scale=(sx, 0.03, sz), texture=tile,
                                 texture_scale=(sx / 0.6, sz / 0.6), color=color.rgb32(205, 205, 205)))
        for k in range(n):                # 第一段：z 從 0 往 L，y 從 0 往 H
            y, z = rise * (k + 1), run * (k + 0.5)
            tread(X1, y, z, w, run)
            self.box(root, (X1, y - rise / 2, z - run / 2), (w, rise, 0.02), riser_c)
            self.box(root, (X1, y / 2, z), (w, y, run), color.rgb32(90, 92, 94))   # 實心底
        for k in range(n):                # 第二段：z 從 L 往 0，y 從 H 往 2H
            y, z = H + rise * (k + 1), L - run * (k + 0.5)
            tread(X2, y, z, w, run)
            self.box(root, (X2, y - rise / 2, z + run / 2), (w, rise, 0.02), riser_c)
        self.box(root, (X2, H - 0.1, L / 2), (w, 0.2, L), white)          # 第二段的樓梯底板
        for x, z0, z1, y0 in ((X1, 0.03, L - 0.03, 0), (X2, L - 0.03, 0.03, H)):   # 黃色止滑條：每段第一階、最後一階
            self.box(root, (x, y0 + rise + 0.003, z0 + (0.02 if z1 > z0 else -0.02)), (w, 0.006, 0.05), yellow)
            self.box(root, (x, y0 + H + 0.003, z1), (w, 0.006, 0.05), yellow)
        tread(0, 0.0, -1.0, 3.2, 2.0)                                       # 一樓樓梯口地板
        tread(0, H, L + 0.8, 3.2, 1.6)                                      # 中間平台
        self.box(root, (0, H / 2 - 0.02, L + 0.8), (3.2, H - 0.04, 1.6), white)
        tread(0, TOP, -1.0, 3.2, 2.0)                                       # 上面樓梯口
        self.box(root, (0, TOP - 0.12, -1.0), (3.2, 0.2, 2.0), white)
        # 牆
        self.box(root, (-1.7, 3.0, 1.6), (0.2, 7.0, 7.0), white)
        self.box(root, (1.7, 3.0, 1.6), (0.2, 7.0, 7.0), white)
        self.box(root, (0, 3.0, L + 1.7), (3.6, 7.0, 0.2), white)
        self.box(root, (0, 6.2, 1.6), (3.6, 0.2, 7.0), white)                # 天花板
        # 兩段中間：白色矮牆＋黑色鐵欄杆
        ang = -math.degrees(math.atan2(H, L))
        slope = math.hypot(H, L)
        for y0, sgn in ((0, 1), (H, -1)):
            mid = Vec3(0, y0 + H / 2, L / 2)
            self.box(root, mid + Vec3(0, 0.05, 0), (0.22, 0.42, slope), white, rot=(ang * sgn, 0, 0))
            for k, hh in enumerate((0.45, 0.62, 0.79, 0.96)):
                self.box(root, mid + Vec3(0, hh, 0), (0.04, 0.03, slope), rail, rot=(ang * sgn, 0, 0))
            for f in (0.1, 0.4, 0.7, 0.95):           # 立柱
                zz = L * f if sgn > 0 else L * (1 - f)
                self.box(root, (0, y0 + H * f + 0.6, zz), (0.04, 0.85, 0.04), rail)
            for x in (-1.58, 1.58):                    # 外牆上的黑色圓扶手
                if (x < 0) == (sgn > 0):
                    self.box(root, mid + Vec3(x, 0.9 - H / 2 + H / 2, 0), (0.05, 0.05, slope), rail, rot=(ang * sgn, 0, 0))
        self.box(root, (0, H + 0.55, L + 0.02), (0.22, 1.1, 0.2), white)    # 平台轉角的矮牆
        # 燈和指示牌
        for y in (H + 2.6, TOP + 2.4):
            self.box(root, (0, y, L + 1.58), (1.0, 0.08, 0.1), color.rgb(1.6, 1.6, 1.55))
        self.box(root, (0, H + 2.1, L + 1.59), (0.34, 0.14, 0.03), color.rgb32(40, 160, 80))      # 逃生指示燈
        self.box(root, (-1.59, H + 2.3, L - 0.4), (0.03, 0.5, 0.9), color.rgb32(250, 222, 150))   # 牆上透光的小窗
        target = self.kw["target"]
        Entity(parent=root, model="quad", position=(0, H + 1.55, L + 1.58), scale=(0.9, 0.34),
               texture=self.sign([f"{'↑' if up else '↓'} {target}", "樓梯間 Stairs"]))
        # 上下兩個樓梯口：灰色鐵門框的開口，外面是亮亮的圖書館
        view = Texture(_library_view(), filtering="bilinear")
        for y0, x in ((0, X1), (TOP, X2)):
            zw = -2.0
            self.box(root, (x - 1.25, y0 + 1.6, zw), (1.0, 3.2, 0.2), white)
            self.box(root, (x + 1.25, y0 + 1.6, zw), (1.0, 3.2, 0.2), white)
            self.box(root, (x, y0 + 2.75, zw), (1.5, 0.9, 0.2), white)
            for dx in (-0.76, 0.76):
                self.box(root, (x + dx, y0 + 1.15, zw), (0.06, 2.3, 0.24), color.rgb32(120, 124, 130))
                self.box(root, (x + dx * 1.15, y0 + 1.15, zw + 0.4), (0.04, 2.25, 0.8), color.rgb32(132, 136, 142),
                         rot=(0, 0, 0))                                    # 往外開的鐵門片
            self.box(root, (x, y0 + 2.31, zw), (1.58, 0.06, 0.24), color.rgb32(120, 124, 130))
            Entity(parent=root, model="quad", position=(x, y0 + 1.4, zw - 1.2), scale=(3.2, 2.8), texture=view,
                   rotation=(0, 180, 0))
            self.box(root, (x, y0 - 0.02, zw - 0.6), (1.5, 0.04, 1.2), color.rgb32(110, 110, 112))
        import shading
        shading.light_scene(root.get_descendants())        # 有光影，白牆和階梯的面才分得出來
        for e in treads:                                    # 換 shader 會把 texture_scale 洗掉，補回去
            e.texture_scale = (e.scale_x / 0.6, e.scale_z / 0.6)
        e1 = 1.55
        path = [(X1, 0, -1.3), (X1, 0, 0), (X1, H, L), (X1, H, L + 0.75), (X2, H, L + 0.75), (X2, H, L),
                (X2, TOP, 0), (X2, TOP, -1.3)]
        self.path = [STAIR_BASE + Vec3(px, py + e1, pz) for px, py, pz in path]
        if not up:
            self.path = self.path[::-1]
        self.seg = [(a - b).length() for a, b in zip(self.path[1:], self.path[:-1])]
        self.caption.text = f"{'上' if up else '下'}樓到 {target}……"

    def path_at(self, s):
        for a, b, l in zip(self.path[:-1], self.path[1:], self.seg):
            if s <= l:
                return a + (b - a) * (s / l if l else 0)
            s -= l
        return self.path[-1]

    def tick_stairs(self, t):
        total = sum(self.seg)
        s = total * ease(t / self.length)
        pos = self.path_at(s)
        pos.y += abs(math.sin(t * 10)) * 0.04                         # 一步一步的晃動
        ahead = self.path_at(min(total + 1.0, s + 1.6))
        if s + 1.6 > total:                                           # 快到了：看向門外
            ahead = self.path[-1] + (self.path[-1] - self.path[-2]).normalized() * (s + 1.6 - total + 0.5)
        up = self.kw["direction"] == "up"
        ahead.y = pos.y + (ahead.y - pos.y) * 0.5 - (0.35 if up else 0.75)    # 走樓梯時眼睛看著前面幾階
        look(pos, ahead)
        self.black(1 - t / 0.2 if t < 0.2 else (t - (self.length - 0.3)) / 0.3)

    def end_stairs(self):
        self.black(1)
        self.game.flash.color = color.rgba32(0, 0, 0, 255)

    # ---------- 館員警告 ----------
    def start_warn(self):
        """鏡頭轉向館員，館員面向你、舉起手指搖一搖：「噓——」。"""
        self.length = 1.6
        g = self.game
        lib = g.librarian
        lib.root.look_at_2d(g.player.position, "y")
        lib.stand()
        lib.shh.enabled = True
        self.eye = g.player.position + Vec3(0, 1.6, 0)
        self.from_dir = camera.forward
        self.caption.text = self.kw["line"]

    def tick_warn(self, t):
        g = self.game
        lib = g.librarian
        head = lib.root.position + Vec3(0, 1.62, 0)
        d0 = Vec3(self.from_dir)
        d1 = (head - self.eye).normalized()
        k = ease(t / 0.35)
        d = (d0 * (1 - k) + d1 * k).normalized()
        look(self.eye, self.eye + d)
        camera.fov = self.saved_fov - 18 * ease((t - 0.3) / 0.4)           # 慢慢拉近
        arm = lib.arms[1]
        arm.rotation_x = -120 * ease(t / 0.3)
        lib.elbows[1].rotation_x = -70 * ease(t / 0.3)
        arm.rotation_z = -8 + math.sin(t * 14) * 12 * ease((t - 0.3) / 0.2)  # 搖手指
        lib.head.rotation_y = math.sin(t * 7) * 6

    def end_warn(self):
        lib = self.game.librarian
        lib.stand()

    # ---------- 被請出去 ----------
    def start_expel(self):
        """在遊戲裡真的 1F 出入口演（使用者：驅逐的畫面用我們的出入口）：館員站在出口閘門旁指著門外，
        你低著頭穿過出口閘門、走出斜面落地窗上的「出口」玻璃門。main 會先把樓層換成 1F 才播。"""
        self.length = 4.6
        g, w = self.game, self.game.world
        C = 2.0
        gb = w.spec["gate_bank"]
        dc, dr = gb["dir"]
        along = Vec3(dc, 0, -dr).normalized()
        inside = Vec3(-along.z, 0, along.x)
        c0 = Vec3(gb["center"][0] * C, 0, -gb["center"][1] * C)
        (ec, er), _, _ = w.spec["facade_doors"][0]          # 出口門
        door = Vec3(ec * C, 0, -er * C) + inside * 0.3
        lane = c0 + along * (-0.5 * gb["step"] * C)          # 出口那兩道裡靠中間的一道
        self.path = [lane + inside * 3.2, lane + inside * 0.9, lane - inside * 0.9,
                     door + inside * 0.9, door, door - inside * 2.5]
        self.along, self.inside, self.c0 = along, inside, c0
        self.you = Person(shirt=color.rgb32(230, 120, 30), pants=color.rgb32(50, 50, 60), hair=color.rgb32(40, 30, 25),
                          glasses=False)
        self.own(self.you.root)
        self.you.root.position = self.path[0]
        self.lib = g.librarian
        self.lib_saved = (Vec3(self.lib.root.position), self.lib.root.rotation_y)
        spot = c0 + along * (-2.4 * gb["step"] * C) + inside * 1.0   # 出口閘門靠門那一頭
        self.lib.root.position = spot
        d = door - spot
        self.lib.root.rotation_y = math.degrees(math.atan2(d.x, d.z))
        self.lib.stand()
        self.caption.text = "館員：「同學，你已經被警告三次了。請你出去。」"

    def _along_path(self, k):
        pts = self.path
        segs = [(pts[i + 1] - pts[i]).length() for i in range(len(pts) - 1)]
        s = k * sum(segs)
        for i, L in enumerate(segs):
            if s <= L or i == len(segs) - 1:
                q = pts[i] + (pts[i + 1] - pts[i]) * (min(s, L) / L)
                return q, pts[i + 1] - pts[i]
            s -= L

    def tick_expel(self, t):
        you, lib = self.you, self.lib
        lib.arms[1].rotation_x = -85 * ease(t / 0.5)                     # 手臂伸直指向門外
        lib.arms[1].rotation_z = 25 * ease(t / 0.5)
        lib.elbows[1].rotation_x = -5
        k = max(0.0, min(1.0, (t - 0.6) / 3.4))
        q, d = self._along_path(k)
        you.root.position = q
        you.root.rotation_y = math.degrees(math.atan2(d.x, d.z))
        if 0.6 < t < 4.0:
            you.walk_anim(5)
        else:
            you.stand()
        you.head.rotation_x = 22                                          # 垂頭喪氣
        if t > 2.4:
            self.caption.text = "你被館員請出了圖書館……明天再來吧。"
        cam = self.c0 + self.inside * 5.0 + self.along * (2.6 - t * 0.3) + Vec3(0, 2.1, 0)
        look(cam, q * 0.7 + self.path[4] * 0.3 + Vec3(0, 1.0, 0))
        self.black(1 - t / 0.3 if t < 0.3 else (t - (self.length - 0.6)) / 0.6)

    def end_expel(self):
        self.black(1)
        self.game.flash.color = color.rgba32(0, 0, 0, 255)
        self.lib.root.position, self.lib.root.rotation_y = self.lib_saved
        self.lib.stand()

    # ---------- 被室友抓到 ----------
    def start_caught(self):
        """繃帶室友衝過來，指著你大喊，然後把你手上的書搶走。"""
        self.length = 2.8
        g = self.game
        h = g.hunter
        self.eye = g.player.position + Vec3(0, 1.6, 0)
        self.from_dir = camera.forward
        self.h_from = Vec3(h.root.position)
        flat = Vec3(g.player.position.x - h.root.x, 0, g.player.position.z - h.root.z)
        dist = flat.length()
        self.h_to = self.h_from + flat.normalized() * max(0.0, dist - 1.3) if dist > 0.01 else self.h_from
        h.alarm.enabled = True
        self.book = self.own(Entity(model="cube", scale=(0.22, 0.3, 0.06), color=color.rgb32(200, 60, 50)))
        self.caption.text = "室友：「你在讀書？！你不是說要擺爛？」"

    def tick_caught(self, t):
        g, h = self.game, self.game.hunter
        h.alarm.enabled = t < 0.4           # 驚嘆號只亮一下，不然靠近時會擋住整個畫面
        k = ease(t / 0.8)
        h.root.position = self.h_from + (self.h_to - self.h_from) * k
        h.root.look_at_2d(g.player.position, "y")
        if t < 0.8:
            h.walk_anim(14)
        else:
            h.stand()
            h.arms[1].rotation_x = -90                                  # 指著你
            h.elbows[1].rotation_x = 0
        head = h.root.position + Vec3(0, 1.6, 0)
        d0, d1 = Vec3(self.from_dir), (head - self.eye).normalized()
        kk = ease(t / 0.3)
        look(self.eye, self.eye + (d0 * (1 - kk) + d1 * kk).normalized())
        camera.fov = self.saved_fov - 14 * ease((t - 0.8) / 0.4)
        # 書：一開始在你手上（畫面下方），1.4 秒後被搶到他手上
        mine = self.eye + camera.forward * 0.6 + camera.down * 0.35 + camera.right * 0.12
        kb = ease((t - 1.4) / 0.4)
        if t > 1.4:                                      # 搶到書高高舉起來
            h.arms[0].rotation_x = -150 * kb
            h.elbows[0].rotation_x = -10
        his = h.hands[0].world_position
        self.book.position = mine + (his - mine) * kb
        self.book.look_at(self.eye)
        if t > 1.5:
            self.caption.text = "室友：「這本我沒收了！」"

    def end_caught(self):
        h = self.game.hunter
        h.stand()
        h.alarm.enabled = False
