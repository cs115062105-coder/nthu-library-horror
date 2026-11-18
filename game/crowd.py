"""每層樓的路人：學生、教授、校外市民。

· 走動的：在走道上慢慢晃，走到你旁邊偶爾會碎念一句
· 看書的：坐在桌子旁低頭讀書
· 找你講話的：頭上有「？」，按 E 對話，常常要先答對一題才肯給你線索（內容由 main 決定）
· 4F 的「同學們」：坐了一排學生，穿著跟室友很像，要靠線索認出真正的室友
"""
import math
import random

from ursina import Entity, Vec3, color, destroy, time

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
        super().__init__(shirt=color.rgb32(*rng.choice(shirts)), pants=color.rgb32(*pants), hair=color.rgb32(*hair))
        self.who = who
        if outfit:
            dress_outfit(self, outfit)
        else:
            hat = HATS["黑色棒球帽"] if rng.random() < hat_p else None
            bag = rng.choice(list(BAGS.values())) if rng.random() < bag_p else None
            self.dress(hat=hat, bag=bag)
        if who == "教授":     # 教授：領帶和一本厚厚的書
            Entity(parent=self.torso, model="cube", position=(0, 0.45, 0.13), scale=(0.07, 0.4, 0.01), color=color.rgb32(150, 40, 40))
        self.rng = rng
        self.mode = "walk"
        self.goal = None
        self.pause = rng.uniform(0, 3)
        self.bark_cd = rng.uniform(5, 15)
        self.face = 0.0
        self.t = rng.uniform(0, 10)
        self.mark = None
        self.font_path = font_path

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
        self.root.position = spot[0]
        self.face = spot[2]
        self.root.rotation_y = self.face
        self.sit()

    def stand_at(self, pos, face=0):
        self.mode = "talk"
        self.root.position = pos
        self.root.rotation_y = face
        self.stand()

    def update(self, game, walkable):
        self.t += time.dt
        if self.mode == "walk":
            if self.pause > 0:
                self.pause -= time.dt
                self.stand()
            else:
                if self.goal is None or to_cell(self.root.position) == to_cell(self.goal):
                    cells = sorted(walkable)
                    self.goal = cell_pos(*self.rng.choice(cells))
                    self.pause = self.rng.uniform(1.0, 4.0)
                    return
                nxt = next_step(walkable, self.root.position, self.goal)
                if nxt == self.root.position:
                    self.goal = None
                else:
                    step_toward(self.root, nxt, 1.3)
                    self.walk_anim(6)
        elif self.mode in ("read", "decoy"):
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
            self.npcs.append(n)
        for spec in talkers:
            n = NPC(spec["who"], rng, fp)
            pos = self.stand_spot(world, spec["anchor"])
            n.stand_at(pos)
            n.spec = spec
            n.set_mark(spec.get("mark", "？"))
            self.npcs.append(n)

    def stand_spot(self, world, anchor, near=3.5):
        """離 anchor 大約 near 公尺、站得到的走道格子。"""
        cells = sorted(world.walkable, key=lambda c: abs((cell_pos(*c) - anchor).length() - near))
        return cell_pos(*cells[0]) if cells else anchor

    def seat_decoys(self, world, roommate, outfit, n=7):
        """4F：在室友附近的桌子坐滿學生，穿著跟室友很像但不完全一樣。回傳被坐走的位置。"""
        spots = [s for s in roommate.spots if s is not roommate.spot]
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
            n.update(g, walkable)
            if n.mode == "walk":
                n.bark_cd -= time.dt
                d = g.player.position - n.position
                d.y = 0
                if d.length() < 2.2 and n.bark_cd <= 0 and self.global_cd <= 0 and not g.hint.text:
                    g.show_hint(f"{n.who}：「{self.rng.choice(BARKS[n.who])}」", 2.5)
                    n.bark_cd, self.global_cd = 25, 8
