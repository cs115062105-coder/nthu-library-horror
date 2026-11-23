"""遊戲中的短動畫（使用者要求）：

· stairs：走樓梯間，鏡頭沿著一段水泥樓梯往上／往下走，轉角牆上寫著要去的樓層
· warn：被館員警告，鏡頭轉向館員，館員搖手指「噓——」
· expel：被警告三次，館員在大門口指著外面，你垂頭喪氣走出圖書館
· caught：第二階段被繃帶室友抓到，室友衝過來指著你、把書搶走

除了 warn、caught 是在原地演（用場上真的館員／室友），stairs、expel 蓋在離圖書館很遠的地方，
只有鏡頭看得到。播放時玩家停用（Ursina 會把鏡頭交還給場景），播完再啟用就會回到玩家眼睛。
Esc／空白鍵可以跳過。
"""
import math

from ursina import Entity, Text, Texture, Vec3, camera, color, destroy, time

import textures as tx
from npc import Person

STAIR_BASE = Vec3(-600, 0, 600)
DOOR_BASE = Vec3(-600, 0, -600)


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
        self.t += time.dt
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
        """一段 10 階的水泥樓梯：上樓就從底下往上爬，下樓就從上面往下走；平台牆上掛綠色樓層牌。"""
        self.length = 1.5
        up = self.kw["direction"] == "up"
        root = self.own(Entity(position=STAIR_BASE))
        concrete, wall, rail = color.rgb32(150, 148, 142), color.rgb32(196, 194, 186), color.rgb32(60, 62, 66)
        n, rise, run, width = 10, 0.17, 0.3, 1.5
        for i in range(n):
            self.box(root, (0, rise * (i + 0.5), run * (i + 0.5)), (width, rise * (i + 1), run), concrete)
            self.box(root, (0, rise * (i + 1) + 0.003, run * i + 0.03), (width, 0.006, 0.05), color.rgb32(60, 62, 60))  # 防滑條
        top_y, top_z = rise * n, run * n
        self.box(root, (0, top_y / 2, top_z + 0.9), (width + 1.6, top_y, 1.8), concrete)                    # 平台
        self.box(root, (0, -0.05, -1.2), (width + 1.6, 0.1, 2.6), concrete)                                 # 一樓地面
        for x in (-width / 2 - 0.1, width / 2 + 0.1):
            self.box(root, (x, 2.2, top_z / 2), (0.2, 5.4, top_z + 5.0), wall)                              # 兩側牆
        self.box(root, (0, 2.2, top_z + 1.9), (width + 1.6, 5.4, 0.2), wall)                                # 平台盡頭的牆
        self.box(root, (0, 5.0, top_z / 2), (width + 1.6, 0.2, top_z + 5.0), wall)                           # 天花板
        self.box(root, (0, 2.2, -2.5), (width + 1.6, 5.4, 0.2), wall)
        ang = -math.degrees(math.atan2(rise, run))
        self.box(root, (-width / 2 + 0.05, 0.9 + top_y / 2, top_z / 2), (0.05, 0.05, math.hypot(top_y, top_z) + 0.3),
                 rail, rot=(ang, 0, 0))                                                                       # 扶手
        target = self.kw["target"]
        Entity(parent=root, model="quad", position=(0, top_y + 2.0, top_z + 1.79), scale=(1.1, 0.42),
               texture=self.sign([f"{'↑' if up else '↓'} {target}", "樓梯間 Stairs"]))
        Entity(parent=root, model="quad", position=(0, 4.88, top_z * 0.6), scale=(0.9, 0.25), rotation=(-90, 0, 0),
               color=color.rgb(1.5, 1.5, 1.4))                                                                # 日光燈
        import shading
        shading.light_scene(root.get_descendants())
        self.stair_path = ((0, 1.55, -0.9), (0, top_y + 1.55, top_z - 0.3))
        self.sign_at = STAIR_BASE + Vec3(0, top_y + 2.0, top_z + 1.79)
        if not up:
            self.stair_path = self.stair_path[::-1]
        self.caption.text = f"{'上' if up else '下'}樓到 {target}……"

    def tick_stairs(self, t):
        k = ease(t / self.length)
        a, b = (Vec3(*p) for p in self.stair_path)
        pos = STAIR_BASE + a + (b - a) * k
        pos.y += abs(math.sin(t * 9)) * 0.05                       # 一步一步的晃動
        if self.kw["direction"] == "up":     # 往上走：一直看著平台牆上的樓層牌
            look(pos, self.sign_at + Vec3(0, -0.3, 0))
        else:                                # 往下走：看著腳下的樓梯
            ahead = STAIR_BASE + b + (b - a).normalized() * 2
            ahead.y = pos.y - 1.4
            look(pos, ahead)
        self.black(1 - t / 0.2 if t < 0.2 else (t - (self.length - 0.25)) / 0.25)

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
        """總圖大門：館員站在門邊指著外面，你低著頭走出玻璃門，門外是晚上的清大。"""
        self.length = 4.2
        g = self.game
        root = self.own(Entity(position=DOOR_BASE))
        floor, wall = color.rgb32(120, 122, 126), color.rgb32(232, 230, 224)
        self.box(root, (0, -0.05, 0), (14, 0.1, 14), floor)
        self.box(root, (0, -0.06, 7), (20, 0.1, 6), color.rgb32(70, 72, 78))                    # 門外的地
        Entity(parent=root, model="quad", position=(0, 4, 14), scale=(40, 14),
               color=color.rgb32(26, 34, 64))                                                     # 夜空
        self.box(root, (0, 3.6, 4), (14, 0.8, 0.3), wall)                                          # 門楣
        Entity(parent=root, model="quad", position=(0, 3.6, 3.84), scale=(5.2, 0.62), rotation=(0, 0, 0),
               texture=self.sign(["國立清華大學圖書館", "NTHU Library"], w=512, h=72, bg=(72, 58, 128), sizes=[36, 18]))
        for x in (-5.5, 5.5):
            self.box(root, (x, 1.6, 4), (3, 3.2, 0.3), wall)
        for x in (-3.0, -1.0, 1.0, 3.0):                                                           # 玻璃門片
            if abs(x) < 2:
                continue
            Entity(parent=root, model="cube", position=(x, 1.6, 4), scale=(1.95, 3.2, 0.05),
                   color=color.rgba32(170, 200, 215, 90))
        self.box(root, (-2, 1.6, 4), (0.08, 3.2, 0.12), color.rgb32(60, 62, 66))
        self.box(root, (2, 1.6, 4), (0.08, 3.2, 0.12), color.rgb32(60, 62, 66))
        for x in (-6, 6):                                                                          # 路燈
            self.box(root, (x, 1.8, 9), (0.12, 3.6, 0.12), color.rgb32(50, 50, 54))
            Entity(parent=root, model="sphere", position=(x, 3.7, 9), scale=0.35, color=color.rgb(1.6, 1.5, 1.2))
        self.you = Person(shirt=color.rgb32(230, 120, 30), pants=color.rgb32(50, 50, 60), hair=color.rgb32(40, 30, 25),
                          glasses=False)
        self.own(self.you.root)
        self.you.root.position = DOOR_BASE + Vec3(-0.6, 0, -2.5)
        self.lib = g.librarian
        self.lib_saved = (Vec3(self.lib.root.position), self.lib.root.rotation_y)
        self.lib.root.position = DOOR_BASE + Vec3(1.6, 0, 2.6)
        self.lib.root.rotation_y = -150
        self.lib.stand()
        self.caption.text = "館員：「同學，你已經被警告三次了。請你出去。」"

    def tick_expel(self, t):
        you, lib = self.you, self.lib
        lib.arms[1].rotation_x = -85 * ease(t / 0.5)                     # 手臂伸直指向門外
        lib.arms[1].rotation_z = 25 * ease(t / 0.5)
        lib.elbows[1].rotation_x = -5
        walk = ease((t - 0.6) / 2.8)
        you.root.position = DOOR_BASE + Vec3(-0.6, 0, -2.5 + 9.0 * walk)
        you.root.rotation_y = 0
        if 0.6 < t < 3.4:
            you.walk_anim(5)
        else:
            you.stand()
        you.head.rotation_x = 22                                          # 垂頭喪氣
        if t > 2.2:
            self.caption.text = "你被館員請出了圖書館……明天再來吧。"
        side = DOOR_BASE + Vec3(-5.5 + t * 0.4, 1.7, -0.5)
        look(side, you.root.position + Vec3(0, 1.1, 0.8))
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
