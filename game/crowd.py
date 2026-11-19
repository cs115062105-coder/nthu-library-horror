"""每層樓的路人：學生、教授、校外市民。

· 走動的：在走道上慢慢晃，走到你旁邊偶爾會碎念一句
· 看書的：坐在桌子旁低頭讀書
· 找你講話的：頭上有「？」，按 E 對話，常常要先答對一題才肯給你線索（內容由 main 決定）
· 4F 的「同學們」：坐了一排學生，穿著跟室友很像，要靠線索認出真正的室友
"""
import math
import random
from collections import deque

from ursina import Entity, Vec3, color, destroy, time

import body
from npc import Person, bubble, next_step, step_toward, to_cell
from world import cell_pos

JACKETS = {"紅色": (200, 50, 45), "藍色": (50, 90, 170), "綠色": (60, 130, 70), "黃色": (225, 190, 50), "白色": (236, 236, 232)}
HATS = {"黑色棒球帽": ("cap", (30, 30, 34)), "紅色毛帽": ("beanie", (200, 60, 60)), "沒戴帽子": None}
BAGS = {"黑色": (35, 35, 40), "紅色": (170, 50, 45), "藍色": (40, 80, 150)}

LOOKS = {   # 路人的樣子：(外套顏色候選, 褲子, 頭髮, 帽子機率, 書包機率)
    "學生": ([(90, 140, 200), (230, 230, 225), (60, 60, 66), (200, 120, 60), (120, 170, 110), (160, 90, 140)],
             (50, 60, 90), (30, 26, 24), 0.25, 0.8),
    "教授": ([(70, 70, 78), (110, 90, 70), (60, 70, 90)], (50, 50, 56), (150, 150, 150), 0.0, 0.0),
    "市民": ([(170, 120, 90), (120, 140, 160), (200, 180, 140)], (90, 80, 70), (80, 70, 60), 0.2, 0.3),
}

BARKS = {
    "學生": ["期中考到底考哪幾章……", "我昨天也說要擺爛，結果讀到三點。", "這層的冷氣好強。", "有人看到我的悠遊卡嗎？",
             "線代好難，我好想回家。", "噓——圖書館不要講話啦。"],
    "教授": ["同學，報告的參考文獻要寫格式喔。", "現在的學生都好認真。", "我的書怎麼又被借走了。"],
    "市民": ["清大圖書館好漂亮。", "這裡可以借書嗎？我是附近的居民。", "年輕人讀書真辛苦。"],
}


def path_to(walkable, start, goal):
    """走道格子上的 BFS，回傳整條路（格子中心點）。路人每換一次目的地才算一次，不用每一幀都算。"""
    s, g = to_cell(start), to_cell(goal)
    if g not in walkable:
        return []
    prev = {s: None}
    queue = deque([s])
    while queue:
        cur = queue.popleft()
        if cur == g:
            break
        c, r = cur
        for nxt in ((c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1)):
            if nxt in walkable and nxt not in prev:
                prev[nxt] = cur
                queue.append(nxt)
    if g not in prev:
        return []
    out, cell = [], g
    while cell is not None and cell != s:
        out.append(cell_pos(*cell))
        cell = prev[cell]
    return out[::-1]


def random_outfit(rng, avoid=None):
    """隨機一套「外套／帽子／書包」，不會跟 avoid（室友今天的穿著）一模一樣。"""
    while True:
        o = (rng.choice(list(JACKETS)), rng.choice(list(HATS)), rng.choice(list(BAGS)))
        if o != avoid:
            return o


def dress_outfit(person, outfit):
    jacket, hat, bag = outfit
    person.dress(jacket=JACKETS[jacket], hat=HATS[hat], bag=BAGS[bag])


class NPC(Person):
    def __init__(self, who, rng, font_path, outfit=None):
        shirts, pants, hair, hat_p, bag_p = LOOKS[who]
        style = rng.choice(["short", "short", "side", "bangs", "long", "bun"] if who != "教授" else ["short", "side"])
        skin = rng.choice([(235, 200, 170), (225, 188, 155), (240, 210, 185), (205, 165, 130)])
        super().__init__(shirt=color.rgb32(*rng.choice(shirts)), pants=pants, hair=hair, skin=skin, style=style,
                         shoes=rng.choice([(60, 50, 45), (235, 235, 235), (40, 40, 45), (120, 80, 50)]))
        self.who = who
        if outfit:
            dress_outfit(self, outfit)
        else:
            hat = HATS["黑色棒球帽"] if rng.random() < hat_p else None
            bag = rng.choice(list(BAGS.values())) if rng.random() < bag_p else None
            self.dress(hat=hat, bag=bag)
        if who == "教授":     # 教授：領帶和一本厚厚的書
            self._part(self.torso, body.tie_shape((150, 40, 40)))
        self.rng = rng
        self.mode = "walk"
        self.goal = None
        self.pause = rng.uniform(0, 3)
        self.bark_cd = rng.uniform(5, 15)
        self.face = 0.0
        self.t = rng.uniform(0, 10)
        self.mark = None
        self.font_path = font_path
        self.seat = None
        self.path = []
        self.timer = None        # 坐著的人：還要讀多久才起來走走（None = 一直坐著）
        self.trips = rng.randint(1, 3)

    @property
    def position(self):
        return self.root.position

    def set_mark(self, text, fg=(40, 40, 40), bg=(255, 230, 120)):
        if self.mark:
            destroy(self.mark)
            self.mark = None
        if text:
            self.mark = Entity(parent=self.root, model="quad", y=2.3, scale=(0.32, 0.32), billboard=True,
                               texture=bubble(text, self.font_path, fg, bg=bg))

    def sit_at(self, spot):
        self.mode = "read"
        self.seat = spot
        self.root.position = spot[0]
        self.face = spot[2]
        self.root.rotation_y = self.face
        self.sit()

    def stand_at(self, pos, face=0):
        self.mode = "talk"
        self.root.position = pos
        self.root.rotation_y = face
        self.stand()

    def update(self, game, walkable, crowd):
        self.t += time.dt
        if self.mode in ("walk", "to_seat"):
            if self.pause > 0:
                self.pause -= time.dt
                self.stand()
            else:
                if self.goal is None or not self.path:
                    if self.mode == "to_seat" and self.goal is not None:     # 走到位子旁邊：坐下來讀一陣子
                        self.sit_at(self.seat)
                        self.timer = self.rng.uniform(25, 70)
                        return
                    self.trips -= 1
                    if self.trips <= 0 and self.rng.random() < 0.6:
                        self.seat = crowd.claim(self.root.position)
                        if self.seat:
                            self.mode, self.goal = "to_seat", cell_pos(*self.seat[1])
                            self.path = path_to(walkable, self.root.position, self.goal)
                            if not self.path:      # 走不到那個位子：直接放回去
                                crowd.release(self.seat)
                                self.seat, self.mode, self.goal = None, "walk", None
                            return
                    near = [c for c in crowd.cells if 4 < abs(c[0] - to_cell(self.root.position)[0]) + abs(c[1] - to_cell(self.root.position)[1]) < 18]
                    self.goal = cell_pos(*self.rng.choice(near or crowd.cells))
                    self.path = path_to(walkable, self.root.position, self.goal)
                    self.pause = self.rng.uniform(1.0, 4.0)
                    return
                if step_toward(self.root, self.path[0], 1.3):
                    self.path.pop(0)
                self.walk_anim(6)
        elif self.mode == "read" and self.timer is not None:
            self.timer -= time.dt
            if self.timer <= 0:      # 讀累了：起來走一走、去找書、去廁所……
                crowd.release(self.seat)
                self.seat = None
                self.root.position = cell_pos(*to_cell(self.root.position)) if to_cell(self.root.position) in walkable \
                    else crowd.near_walk(self.root.position)
                self.mode, self.goal, self.trips, self.path = "walk", None, self.rng.randint(1, 3), []
                self.stand()
                return
        if self.mode in ("read", "decoy"):
            self.root.rotation_y = self.face + (math.sin(self.t * 0.7) * 50 if math.sin(self.t * 0.31) > 0.85 else 0)
            self.torso.rotation_x = 15
            self.head.rotation = (22 + math.sin(self.t * 5) * 2, 0, 0)
        elif self.mode == "talk":
            d = game.player.position - self.root.position
            d.y = 0
            if d.length() < 4:
                self.root.look_at_2d(game.player.position, "y")
            if self.mark:      # 走到旁邊就收起頭上的「？」，不然會擋住整個畫面
                self.mark.enabled = d.length() > 2.6
            self.head.rotation_y = math.sin(self.t) * 8


class Crowd:
    def __init__(self, game):
        self.game = game
        self.npcs = []
        self.free = []
        self.cells = []
        self.rng = random.Random()
        self.global_cd = 0.0

    def clear(self):
        for n in self.npcs:
            destroy(n.root)
        self.npcs = []

    def spawn(self, world, talkers=(), walkers=3, readers=3, taken=()):
        """talkers：[dict(who, anchor(位置), label, action, mark)]，由 main 依劇情決定。"""
        self.clear()
        rng, fp = self.rng, self.game.font_path
        walk = sorted(world.walkable)
        self.cells = walk
        if not walk:
            return
        for _ in range(walkers):
            n = NPC(rng.choice(["學生", "學生", "市民", "教授"]), rng, fp)
            n.root.position = cell_pos(*rng.choice(walk))
            self.npcs.append(n)
        spots = [s for s in self.game.roommate.find_spots(world) if all((s[0] - t).length() > 0.5 for t in taken)]
        rng.shuffle(spots)
        for spot in spots[:readers]:
            n = NPC(rng.choice(["學生", "學生", "學生", "市民"]), rng, fp)
            n.sit_at(spot)
            n.timer = rng.uniform(8, 60)
            self.npcs.append(n)
        self.free = spots[readers:]
        for spec in talkers:
            n = NPC(spec["who"], rng, fp)
            pos = self.stand_spot(world, spec["anchor"])
            n.stand_at(pos)
            n.spec = spec
            n.set_mark(spec.get("mark", "？"))
            self.npcs.append(n)

    def claim(self, pos):
        """找一個空位子（離 pos 近一點的優先），拿走。"""
        if not self.free:
            return None
        self.free.sort(key=lambda s: (s[0] - pos).length() + self.rng.uniform(0, 10))
        return self.free.pop(0)

    def release(self, spot):
        if spot is not None:
            self.free.append(spot)

    def near_walk(self, pos):
        cells = sorted(self.game.world.walkable, key=lambda c: (cell_pos(*c) - pos).length())
        return cell_pos(*cells[0]) if cells else pos

    def stand_spot(self, world, anchor, near=3.5):
        """離 anchor 大約 near 公尺、站得到的走道格子。"""
        cells = sorted(world.walkable, key=lambda c: abs((cell_pos(*c) - anchor).length() - near))
        return cell_pos(*cells[0]) if cells else anchor

    def seat_decoys(self, world, roommate, outfit, n=7):
        """4F：在室友附近的桌子坐滿學生，穿著跟室友很像但不完全一樣。回傳被坐走的位置。"""
        busy = [n.seat[0] for n in self.npcs if n.seat is not None] + \
               [n.goal for n in self.npcs if n.mode == "to_seat" and n.goal is not None]
        spots = [s for s in roommate.spots if s is not roommate.spot and all((s[0] - b).length() > 1.2 for b in busy)]
        spots.sort(key=lambda s: (s[0] - roommate.position).length())
        used = []
        for spot in spots[:n]:
            if any((spot[0] - u[0]).length() < 1.2 for u in used):
                continue
            o = random_outfit(self.rng, avoid=outfit)
            # 至少跟室友有一樣相同，認人才需要湊齊線索
            k = self.rng.randrange(3)
            o = tuple(outfit[i] if i == k else o[i] for i in range(3))
            if o == outfit:
                o = random_outfit(self.rng, avoid=outfit)
            d = NPC("學生", self.rng, self.game.font_path, outfit=o)
            d.sit_at(spot)
            d.mode = "decoy"
            d.outfit = o
            self.npcs.append(d)
            used.append(spot)
        roommate.spots = [s for s in roommate.spots if s not in used]
        self.free = [s for s in self.free if all((s[0] - u[0]).length() > 1.2 for u in used + [roommate.spot])]
        return used

    def targets(self):
        out = []
        for n in self.npcs:
            if n.mode == "talk":
                out.append((n.position + Vec3(0, 1.4, 0), n.position, n.spec["label"], lambda n=n: n.spec["action"](n)))
            elif n.mode == "decoy":
                out.append((n.position + Vec3(0, 1.0, 0), n.position, "抓住他！", lambda n=n: self.game.grab_wrong(n)))
        return out

    def update(self):
        g = self.game
        walkable = g.world.walkable
        self.global_cd -= time.dt
        for n in self.npcs:
            n.update(g, walkable, self)
            if n.mode == "walk":
                n.bark_cd -= time.dt
                d = g.player.position - n.position
                d.y = 0
                if d.length() < 2.2 and n.bark_cd <= 0 and self.global_cd <= 0 and not g.hint.text:
                    g.show_hint(f"{n.who}：「{self.rng.choice(BARKS[n.who])}」", 2.5)
                    n.bark_cd, self.global_cd = 25, 8
