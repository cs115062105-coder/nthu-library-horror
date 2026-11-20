"""館內的兩個人：巡館的館員，還有躲在 4F 偷卷的室友。

館員：在走道上巡邏，聽到聲音會走過去看。看到你在館內奔跑（或吵到聲音條滿）就會警告你，
      警告三次你就被請出圖書館，隔天重來。
室友：坐在 4F 的桌子讀書，每隔幾秒抬頭張望。被他看到（或聽到你跑步），他就抱著書逃到別張桌子。
      趁他低頭讀書時躡手躡腳靠近按 E，或在他逃跑時追上去碰到他，就抓到了。
"""
import math
import random
from collections import deque

from ursina import Entity, Texture, Vec3, color, raycast, scene, time

import body
from shading import person_shader

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
    """小人：hip 底下掛身體、頭、手腳（模型在 body.py 捏），坐下時只要調 hip 高度和腳、膝蓋的角度。"""

    def __init__(self, shirt, pants, hair, skin=color.rgb32(235, 200, 170), style="short", glasses=True,
                 shoes=(60, 50, 45)):
        rgb = lambda c: c if isinstance(c, tuple) else (int(round(c[0] * 255)), int(round(c[1] * 255)), int(round(c[2] * 255)))
        skin, pants, hair = rgb(skin), rgb(pants), rgb(hair)
        self.skin = skin
        self.root = Entity()
        self.hip = Entity(parent=self.root, y=0.85)
        self.torso = Entity(parent=self.hip)
        self.parts = []
        self.shirt_parts = [self._part(self.torso, body.shirt_shape(), shirt)]
        self._part(self.torso, body.body_shape(skin, pants))
        self.head = Entity(parent=self.torso, y=0.79, scale=0.8)     # 頭約身高的 1/7
        self._part(self.head, body.head_shape(skin, hair, style))
        self.glasses = self._part(self.head, body.glasses_shape())
        self.glasses.enabled = glasses
        self.arms, self.elbows, self.hands, self.legs, self.knees = [], [], [], [], []
        for side in (-1, 1):
            arm = Entity(parent=self.torso, position=(side * 0.2, 0.56, 0))
            self.shirt_parts.append(self._part(arm, body.upper_sleeve_shape(), shirt))
            elbow = Entity(parent=arm, y=-0.33)
            self.shirt_parts.append(self._part(elbow, body.fore_sleeve_shape(), shirt))
            self._part(elbow, body.hand_shape(skin, side))      # 掌心朝身體
            self.arms.append(arm)
            self.elbows.append(elbow)
            self.hands.append(Entity(parent=elbow, y=-0.34))           # 手上拿東西就掛在這裡
        for x in (-0.088, 0.088):
            leg = Entity(parent=self.hip, position=(x, 0, 0))
            self._part(leg, body.thigh_shape(pants))
            knee = Entity(parent=leg, y=-0.42)
            self._part(knee, body.shin_shape(pants, shoes))
            self.legs.append(leg)
            self.knees.append(knee)
        self.rest()
        self.walk_t = 0.0
        self.hat = self.bag = None

    def _part(self, parent, mesh, tint=None, **kw):
        """掛一塊人物 mesh 上去，換成人物用的 shader。"""
        e = Entity(parent=parent, model=mesh, color=tint if tint is not None else color.white,
                   add_to_scene_entities=False, **kw)      # 身體零件不用每幀被引擎掃（跟著關節動就好）
        e.shader = person_shader          # 霧和相機位置從場景根節點繼承（shading.set_fog）
        self.parts.append(e)
        return e

    def set_glasses(self, on):
        self.glasses.enabled = on

    def hoodie(self):
        self.shirt_parts.append(self._part(self.torso, body.hood_shape(), self.shirt_parts[0].color))

    def dress(self, jacket=None, hat=None, bag=None):
        """換穿著：外套顏色、帽子（"cap" 棒球帽／"beanie" 毛帽／None）、書包顏色（None 就不背）。"""
        if jacket is not None:
            for part in self.shirt_parts:
                part.color = color.rgb32(*jacket)
        for e in (self.hat, self.bag):
            if e:
                e.enabled = False
        self.hat = self.bag = None
        if hat:
            shape = body.cap_shape(hat[1]) if hat[0] == "cap" else body.beanie_shape(hat[1])
            self.hat = self._part(self.head, shape)
        if bag:
            self.bag = self._part(self.torso, body.backpack_shape(bag), z=-0.17, y=0.1)

    def rest(self):
        """手自然垂下：稍微離開身體、手肘微彎。"""
        for i, arm in enumerate(self.arms):
            arm.rotation_z = 7 if i == 0 else -7
            self.elbows[i].rotation_x = -12

    def walk_anim(self, rate):
        self.walk_t += time.dt * rate
        swing = math.sin(self.walk_t) * 30
        for i, leg in enumerate(self.legs):
            leg.rotation_x = swing if i else -swing
            self.knees[i].rotation_x = max(0.0, leg.rotation_x) * 1.3 + 5     # 往後擺的那隻腳膝蓋彎
        for i, arm in enumerate(self.arms):
            arm.rotation_x = -swing * 0.65 if i else swing * 0.65
            self.elbows[i].rotation_x = -12 - max(0.0, -arm.rotation_x) * 0.8     # 手往前擺時手肘彎多一點
        self.hip.y = 0.85 - abs(math.cos(self.walk_t)) * 0.025 + 0.012       # 走路時身體上下輕輕晃
        self.hip.rotation_y = swing * 0.18                                   # 臀部跟著腳轉
        self.torso.rotation_y = -swing * 0.42                                # 肩膀反方向轉
        self.torso.rotation_z = math.sin(self.walk_t) * 1.5

    def stand(self):
        self.hip.y = 0.85
        self.hip.rotation_y = 0
        self.torso.rotation = (0, 0, 0)
        self.head.rotation = (0, 0, 0)
        for part in self.legs + self.arms + self.knees:
            part.rotation_x = 0
        self.rest()

    def sit(self):
        self.hip.y = 0.5
        self.hip.rotation_y = 0
        self.torso.rotation_y = self.torso.rotation_z = 0
        for leg in self.legs:
            leg.rotation_x = -85      # 大腿往前平放
        for knee in self.knees:
            knee.rotation_x = 85      # 小腿垂下來
        for i, arm in enumerate(self.arms):
            arm.rotation_x = -25      # 上臂往前、前臂放在桌上
            arm.rotation_z = 0
            self.elbows[i].rotation_x = -60


class Librarian(Person):
    def __init__(self, game):
        super().__init__(shirt=color.rgb32(240, 240, 236), pants=(50, 52, 60), hair=(70, 68, 66), style="side",
                         skin=(228, 192, 160), shoes=(30, 28, 28))
        self.game = game
        self._part(self.torso, body.tie_shape((30, 80, 60)))
        self._part(self.torso, body.vest_shape((40, 110, 80)))          # 圖書館的綠色背心、名牌
        self.books = self._part(self.hands[0], body.book_stack(), position=(0.05, 0.03, 0.04), rotation=(80, 0, 90))
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
        self.dress(bag=(170, 50, 45))    # 書包；每局開始時 game 會照「今天的穿著」重新換
        self.book = Entity(parent=self.hands[1], model="cube", position=(-0.15, 0.0, 0.12), scale=(0.25, 0.04, 0.32),
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


class Hunter(Person):
    """第二階段（5F、6F）：被打完、頭上包著繃帶的室友在樓層裡巡來巡去。
    被他看到你在偷讀書就完了（隔天重來）；聽到你跑步會走過去看。躲在桌子底下他看不到。"""

    def __init__(self, game):
        super().__init__(shirt=color.rgb32(120, 125, 135), pants=color.rgb32(40, 60, 100), hair=color.rgb32(25, 22, 20))
        self.game = game
        self._part(self.head, body.bandage_shape())      # 繃帶
        self.alarm = Entity(parent=self.root, model="quad", y=2.0, scale=(0.5, 0.5), billboard=True,
                            texture=bubble("！", game.font_path, (220, 30, 30), bg=(255, 245, 160)), enabled=False)
        self.root.enabled = False
        self.target = self.lookout = None
        self.pause = 0.0
        self.cooldown = 0.0

    @property
    def active(self):
        return self.root.enabled

    @property
    def position(self):
        return self.root.position

    def spawn(self, pos):
        self.root.enabled = True
        self.root.position = pos
        self.target = self.lookout = None
        self.pause, self.cooldown = 2.0, 3.0
        self.alarm.enabled = False
        self.stand()

    def hide(self):
        self.root.enabled = False

    def sees_player(self):
        g = self.game
        if g.hidden:
            return False
        dist = 5 if g.sneaking else 10
        eye = self.root.position + Vec3(0, 1.6, 0)
        target = g.player.position + Vec3(0, 1.0 if g.sneaking else 1.4, 0)
        return can_see(eye, self.root.forward, target, dist, 55, g.solids, (self.root, g.player))

    def update(self):
        g = self.game
        self.cooldown -= time.dt
        if self.pause > 0:
            self.pause -= time.dt
            self.root.rotation_y += math.sin(self.pause * 2) * 50 * time.dt
            self.stand()
        else:
            goal = self.lookout or self.target
            if goal is None:
                cells = [c for c in g.librarian_walkable if (cell_pos(*c) - self.root.position).length() > 8]
                goal = self.target = cell_pos(*random.choice(cells or sorted(g.librarian_walkable)))
            nxt = next_step(g.librarian_walkable, self.root.position, goal)
            speed = g.cfg["speed"] * (1.4 if self.lookout else 0.9)
            if nxt == self.root.position or (step_toward(self.root, nxt, speed) and to_cell(nxt) == to_cell(goal)):
                if self.lookout:
                    g.show_hint("室友：「……是我聽錯了嗎？」", 2)
                self.target = self.lookout = None
                self.pause = random.uniform(1.5, 3.0)
            self.walk_anim(7)
        if self.cooldown > 0:
            return
        if g.running and (g.player.position - self.root.position).length() < 9 and not self.lookout:
            self.lookout = Vec3(g.player.position.x, 0, g.player.position.z)
            self.pause = 0
        if self.sees_player():
            self.alarm.enabled = True
            self.root.look_at_2d(g.player.position, "y")
            self.cooldown = 5.0
            g.hunter_spotted()
