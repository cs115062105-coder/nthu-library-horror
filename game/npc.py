"""館內的兩個人：巡館的館員，還有躲在 4F 偷卷的室友。

館員：在走道上巡邏，聽到聲音會走過去看。看到你在館內奔跑（或吵到聲音條滿）就會警告你，
      警告三次你就被請出圖書館，隔天重來。
室友：坐在 4F 的桌子讀書，每隔幾秒抬頭張望。被他看到（或聽到你跑步），他就抱著書逃到別張桌子。
      趁他低頭讀書時躡手躡腳靠近按 E，或在他逃跑時追上去碰到他，就抓到了。
"""
import math
import random
from collections import deque

from ursina import Entity, Texture, Vec3, color, raycast, time

import textures as tx
from world import CELL, cell_pos


def to_cell(pos):
    return (round(pos.x / CELL), round(-pos.z / CELL))


def next_step(walkable, start, goal):
    """在走道格子上做 BFS，回傳往目標方向的下一格中心點。"""
    s, g = to_cell(start), to_cell(goal)
    if s == g or g not in walkable:
        return Vec3(goal.x, 0, goal.z) if s == g else Vec3(start)
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
        return Vec3(start)
    cell = g
    while prev[cell] != s and prev[cell] is not None:
        cell = prev[cell]
    return cell_pos(*cell)


def step_toward(entity, target, speed):
    """往 target 走一步，到了回傳 True。"""
    move = target - entity.position
    move.y = 0
    step = speed * time.dt
    if move.length() <= step:
        entity.position = Vec3(target.x, 0, target.z)
        return True
    entity.position += move.normalized() * step
    entity.look_at_2d(entity.position + move, "y")
    return False


def can_see(eye, forward, target, max_dist, half_angle, solids, ignore):
    """target 在 eye 的視野錐裡、距離內，而且中間沒有牆或書架擋住。"""
    to = target - eye
    dist = to.length()
    if dist < 0.01:
        return True
    if dist > max_dist:
        return False
    flat = Vec3(to.x, 0, to.z)
    if flat.length() > 0.01 and flat.normalized().dot(Vec3(forward.x, 0, forward.z).normalized()) < math.cos(math.radians(half_angle)):
        return False
    hit = raycast(eye, to.normalized(), distance=dist, ignore=ignore)
    return not (hit.hit and hit.entity in solids)


def bubble(text, font_path, fg, bg=(255, 255, 255)):
    return Texture(tx.sign([text], font_path, w=128, h=64, bg=bg, fg=fg, sizes=[40]), filtering="bilinear")


class Person:
    """方塊小人：hip 底下掛身體、頭、手腳，坐下時只要調 hip 高度和腳的角度。"""

    def __init__(self, shirt, pants, hair, skin=color.rgb32(235, 200, 170)):
        self.root = Entity()
        self.hip = Entity(parent=self.root, y=0.85)
        self.torso = Entity(parent=self.hip)
        Entity(parent=self.torso, model="cube", y=0.35, scale=(0.45, 0.7, 0.25), color=shirt)
        self.head = Entity(parent=self.torso, y=0.86)
        Entity(parent=self.head, model="sphere", scale=0.3, color=skin)
        Entity(parent=self.head, model="cube", position=(0, 0.1, -0.02), scale=(0.31, 0.13, 0.3), color=hair)
        for x in (-0.06, 0.06):   # 眼鏡
            Entity(parent=self.head, model="cube", position=(x, 0.01, 0.15), scale=(0.08, 0.06, 0.01),
                   color=color.rgb32(30, 30, 30))
        self.arms, self.legs = [], []
        for x in (-0.29, 0.29):
            arm = Entity(parent=self.torso, position=(x, 0.65, 0))
            Entity(parent=arm, model="cube", y=-0.3, scale=(0.12, 0.6, 0.12), color=shirt)
            self.arms.append(arm)
        for x in (-0.11, 0.11):
            leg = Entity(parent=self.hip, position=(x, 0, 0))
            Entity(parent=leg, model="cube", y=-0.42, scale=(0.16, 0.85, 0.16), color=pants)
            self.legs.append(leg)
        self.walk_t = 0.0

    def walk_anim(self, rate):
        self.walk_t += time.dt * rate
        swing = math.sin(self.walk_t) * 35
        for i, leg in enumerate(self.legs):
            leg.rotation_x = swing if i else -swing
        for i, arm in enumerate(self.arms):
            arm.rotation_x = -swing * 0.7 if i else swing * 0.7

    def stand(self):
        self.hip.y = 0.85
        self.torso.rotation_x = 0
        self.head.rotation = (0, 0, 0)
        for part in self.legs + self.arms:
            part.rotation_x = 0

    def sit(self):
        self.hip.y = 0.5
        for leg in self.legs:
            leg.rotation_x = -80      # 腳往前伸到桌子底下
        for arm in self.arms:
            arm.rotation_x = -60      # 手放在桌上


class Librarian(Person):
    def __init__(self, game):
        super().__init__(shirt=color.rgb32(235, 235, 230), pants=color.rgb32(50, 52, 60), hair=color.rgb32(60, 60, 60))
        self.game = game
        Entity(parent=self.torso, model="cube", position=(0, 0.33, 0), scale=(0.47, 0.6, 0.27),
               color=color.rgb32(40, 110, 80))     # 圖書館的綠色背心
        Entity(parent=self.torso, model="cube", position=(0.1, 0.5, 0.14), scale=(0.1, 0.05, 0.01),
               color=color.rgb32(250, 250, 250))   # 名牌
        self.shh = Entity(parent=self.root, model="quad", y=2.35, scale=(0.8, 0.4), billboard=True,
                          texture=bubble("噓！", game.font_path, (30, 30, 30)), enabled=False)
        self.target = None
        self.lookout = None      # 聽到聲音要過去看的位置
        self.pause = 0.0
        self.cooldown = 0.0
        self.shh_time = 0.0

    @property
    def position(self):
        return self.root.position

    def reset(self, pos):
        self.root.position = pos
        self.root.rotation_y = random.uniform(0, 360)
        self.target = self.lookout = None
        self.pause, self.cooldown = 1.0, 2.0
        self.shh.enabled = False
        self.stand()

    def investigate(self, pos):
        if to_cell(pos) in self.game.librarian_walkable:
            self.lookout = Vec3(pos.x, 0, pos.z)
            self.pause = 0.0

    def sees_player(self):
        g = self.game
        eye = self.root.position + Vec3(0, 1.6, 0)
        target = g.player.position + Vec3(0, 0.6 if g.hidden else 1.4, 0)
        return can_see(eye, self.root.forward, target, g.cfg["sight"], 55, g.solids, (self.root, g.player))

    def update(self):
        g = self.game
        self.cooldown -= time.dt
        if self.shh_time > 0:
            self.shh_time -= time.dt
            self.shh.enabled = self.shh_time > 0
        if self.pause > 0:          # 站著東張西望
            self.pause -= time.dt
            self.root.rotation_y += math.sin(self.pause * 2) * 40 * time.dt
            self.stand()
        else:
            goal = self.lookout or self.target
            if goal is None:
                cells = [c for c in g.librarian_walkable if (cell_pos(*c) - self.root.position).length() > 8]
                goal = self.target = cell_pos(*random.choice(cells or sorted(g.librarian_walkable)))
            nxt = next_step(g.librarian_walkable, self.root.position, goal)
            speed = g.cfg["speed"] * (1.5 if self.lookout else 1.0)
            if nxt == self.root.position or (step_toward(self.root, nxt, speed) and to_cell(nxt) == to_cell(goal)):
                if self.lookout:
                    g.show_hint("館員：「嗯？剛剛是誰？」", 2)
                self.target = self.lookout = None
                self.pause = random.uniform(1.0, 2.5)
            self.walk_anim(7)
        if g.hidden or self.cooldown > 0:
            return
        bumped = (g.player.position - self.root.position).length() < 1.0 and g.moving
        if (g.running or g.noise >= 1 or bumped) and (bumped or self.sees_player()):
            self.root.look_at_2d(g.player.position, "y")
            self.cooldown, self.pause, self.lookout = 3.0, 1.5, None
            self.shh_time = 1.6
            g.warn()


class Roommate(Person):
    def __init__(self, game):
        super().__init__(shirt=color.rgb32(120, 125, 135), pants=color.rgb32(40, 60, 100), hair=color.rgb32(25, 22, 20))
        self.game = game
        Entity(parent=self.torso, model="cube", position=(0, 0.4, -0.2), scale=(0.38, 0.5, 0.16),
               color=color.rgb32(170, 50, 45))    # 書包
        self.book = Entity(parent=self.arms[1], model="cube", position=(-0.15, -0.6, 0.15), scale=(0.25, 0.04, 0.32),
                           color=color.rgb32(40, 90, 160))
        self.alarm = Entity(parent=self.root, model="quad", y=2.0, scale=(0.5, 0.5), billboard=True,
                            texture=bubble("！", game.font_path, (220, 30, 30), bg=(255, 245, 160)), enabled=False)
        self.root.enabled = False
        self.state = "gone"
        self.spots = []
        self.spot = None
        self.timer = 0.0
        self.face = 0.0
        self.flee_to = None

    @property
    def active(self):
        return self.root.enabled

    @property
    def position(self):
        return self.root.position

    def find_spots(self, world):
        """每張桌子旁邊可以坐的位置：(座位, 走過去要站的那格, 面向)。"""
        spots = []
        for p in world.hides:
            c, r = to_cell(p)
            for dr in (-1, 1):
                if (c, r + dr) in world.walkable:
                    seat = p + Vec3(0.45, 0, -dr * 0.75)
                    spots.append((seat, (c, r + dr), 180 if dr < 0 else 0))
        return spots

    def spawn(self, world, avoid):
        self.spots = self.find_spots(world)
        far = [s for s in self.spots if (s[0] - avoid).length() > 12] or self.spots
        self.root.enabled = True
        self.sit_at(random.choice(far))

    def hide(self):
        self.root.enabled = False
        self.state = "gone"

    def sit_at(self, spot):
        self.spot = spot
        self.root.position = spot[0]
        self.face = spot[2]
        self.root.rotation_y = self.face
        self.state = "study"
        self.timer = random.uniform(1.5, 3.0)   # 剛坐下會比較快抬頭
        self.alarm.enabled = False
        self.sit()

    def flee(self):
        g = self.game
        here = self.spot
        options = [s for s in self.spots if s is not here]
        if not options:
            return
        self.spot = max(options, key=lambda s: (s[0] - g.player.position).length() - 0.3 * (s[0] - self.root.position).length())
        self.flee_to = cell_pos(*self.spot[1])
        self.state = "flee"
        self.alarm.enabled = True
        self.stand()

    def noticed(self):
        """被他看到或聽到了嗎？"""
        g = self.game
        if g.hidden:
            return False
        dist = (g.player.position - self.root.position).length()
        if g.running and dist < 9:
            return True
        if g.moving and not g.sneaking and dist < 2.6:
            return True
        if self.state == "look":
            eye = self.root.position + Vec3(0, 1.3, 0)
            target = g.player.position + Vec3(0, 1.0 if g.sneaking else 1.4, 0)
            return can_see(eye, self.root.forward, target, 12, 60, g.solids, (self.root, g.player))
        return False

    def update(self):
        g = self.game
        if self.state in ("study", "look"):
            self.timer -= time.dt
            if self.timer <= 0:
                if self.state == "study":
                    self.state, self.timer = "look", random.uniform(1.3, 2.0)
                else:
                    self.state, self.timer = "study", random.uniform(3.5, 6.5)
            if self.state == "study":   # 低頭狂讀
                self.root.rotation_y = self.face
                self.torso.rotation_x = 18
                self.head.rotation = (25 + math.sin(time.time() * 6) * 3, 0, 0)
            else:                       # 抬頭左右張望
                self.torso.rotation_x = 0
                self.head.rotation = (0, 0, 0)
                self.root.rotation_y = self.face + math.sin(self.timer * 3.2) * 70
            if self.noticed():
                g.roommate_spotted()
        elif self.state == "flee":
            if (g.player.position - self.root.position).length() < 1.0:
                g.catch_roommate()
                return
            nxt = next_step(g.world.walkable, self.root.position, self.flee_to)
            arrived = step_toward(self.root, nxt, g.cfg["flee"]) and to_cell(nxt) == to_cell(self.flee_to)
            self.walk_anim(14)
            if arrived or nxt == self.root.position:
                self.sit_at(self.spot)
