"""雙人模式（4F），兩種玩法：

【躲貓貓】偷卷室友 vs 抓人的
· 室友（真人）今天的穿著隨機，這層還有 7 個同學穿得一模一樣。室友要混在他們裡面：E 坐到椅子上假裝讀書、
  起來走走，撐到閉館就贏。
· 抓人的前 10 秒閉眼，之後要從一模一樣的人裡找出「動作怪怪的」真人，靠近按 E 抓住他。抓錯 3 次就輸。
· 道具（兩格，1、2 鍵使用）：飲水機裝水倒在地上讓對方滑倒、桌上的腎上腺素加速、書櫃拿書丟人（對方滿畫面都是書）。
  抓人的另外有一次「問館員」：小地圖標出室友大概在哪一帶。NPC 不會跑、不會丟書，用道具就等於露餡。

【巡館】抓人的 vs 館員
· 室友是 AI，坐在 4F 讀書；旁邊坐著穿得很像的同學。抓人的照線索認出他、抓到就贏，但要裝成普通同學。
· 館員（真人）要從人群裡找出抓人的，E 盤查。盤查錯 3 次就輸；閉館前沒被找到，抓人的也沒抓到室友，館員贏。
· 館員可以到監控室看監視器（A/D 切換，E 離開），看的時候本人站在監控室不能動。
· 抓人的可以去廁所換衣服（每局 2 次，要 4 秒）；館員如果正在看監視器，會看到有人進廁所。

連線分工：開房間的那台（host）負責算路人怎麼走和倒數計時，每秒傳 10 次給對方；兩邊各自傳自己的位置
（每秒 20 次），對方的身體在畫面上平滑地跟過去。地圖和路人的長相用同一個亂數種子，兩台蓋出來一模一樣。
"""
import math
import random

from ursina import Entity, Text, Vec3, camera, color, held_keys, scene, time

import fastops
from crowd import BAGS, HATS, JACKETS, NPC, dress_outfit, random_outfit
from net import Net, local_ip
from npc import to_cell
from world import CELL, cell_pos

MODES = {"hide": ("roommate", "catcher"), "patrol": ("catcher", "librarian")}
MODE_NAME = {"hide": "躲貓貓：偷卷室友 vs 抓人的", "patrol": "巡館：抓人的 vs 館員"}
ROUND = {"hide": 240, "patrol": 300}
HEADSTART = 10         # 躲貓貓：抓人的先閉眼幾秒
WARN_LIMIT = 3
LOOK_READERS, LOOK_WALKERS = 5, 2     # 躲貓貓：跟室友穿一樣的同學（坐著的、走動的）
ROLE_NAME = {"catcher": "抓人的", "roommate": "偷卷室友", "librarian": "館員"}
ITEM_NAME = {"water": "一瓶水", "boost": "腎上腺素", "book": "一本書", "ask": "問館員"}
TOILET_USES = 2

HELP = {
    "hide": ("兩台電腦連同一個 Wi-Fi 或手機熱點。一台選模式按「開房間」，\n"
             "另一台按「自動找房間」或輸入對方的 IP。\n\n"
             "偷卷室友：7 個同學跟你穿得一模一樣。E 坐到椅子上假裝讀書、\n"
             "　起來走走，撐到 22:00（4 分鐘）就贏。\n"
             "抓人的：前 10 秒閉眼，之後找出動作怪怪的人按 E 抓。抓錯 3 次輸。\n"
             "道具（1、2 鍵）：水倒地上讓人滑倒、腎上腺素加速、丟書擋視線。"),
    "patrol": ("兩台電腦連同一個 Wi-Fi 或手機熱點。一台選模式按「開房間」，\n"
               "另一台按「自動找房間」或輸入對方的 IP。\n\n"
               "抓人的：照穿著認出 AI 室友抓住他，但要裝成普通同學。\n"
               "　可以去廁所換衣服（2 次）。抓錯人館員會收到通報。\n"
               "館員：找出混在人群裡的抓人的，E 盤查，錯 3 次輸。\n"
               "　監控室可以看監視器；撐到閉館（5 分鐘）也算贏。"),
}


def angle_lerp(a, b, t):
    d = (b - a + 180) % 360 - 180
    return a + d * t


def wear(outfit):
    jacket, hat, bag = outfit
    return f"{jacket}外套、{hat}、{bag}書包"


class _Far:          # 小地圖要一個「館員」：放到很遠的地方就不會畫出來
    class root:
        position = Vec3(99999, 0, 99999)


def spread(cells, n, rng):
    """從 cells 挑 n 個彼此離很遠的格子。"""
    cells = sorted(cells)
    if not cells:
        return []
    out = [rng.choice(cells)]
    while len(out) < n:
        best = max(cells, key=lambda c: min(abs(c[0] - o[0]) + abs(c[1] - o[1]) for o in out))
        out.append(best)
    return out


class Versus:
    def __init__(self, game, net, role, seed, mode="hide"):
        self.g, self.net, self.role, self.seed, self.mode = game, net, role, seed, mode
        self.host = net.is_host
        self.outfit = random_outfit(random.Random(seed))
        self.avatar = None
        self.spots = []
        self.seat = None            # 我（室友）坐在哪個位子（spots 的索引）
        self.remote = None          # 對方最新的狀態
        self.remote_seat = None
        self.ready_me = self.ready_them = False
        self.started = False
        self.over = False
        self.round = ROUND[mode]
        self.time_left = self.round
        self.warnings = 0           # 我抓錯／盤查錯幾次
        self.their = 0              # 對方抓錯／盤查錯幾次
        self.grab_cd = 0.0
        self.send_t = self.npc_t = 0.0
        self.rng = random.Random()
        # 道具
        self.inv = [None, None]
        self.pickups = []
        self.puddles = {}           # id → Entity
        self.books = []             # 飛行中的書
        self.boost = 0.0            # >0 加速中；<0 喘氣變慢
        self.slip = 0.0
        self.blind = 0.0
        self.ping_t = 0.0
        self.fx_id = 0
        # 巡館
        self.target_npc = None      # AI 室友是第幾個路人
        self.cctv = None            # 正在看第幾支監視器
        self.cams = []
        self.desk = self.toilet = None
        self.changing = 0.0
        self.toilet_left = TOILET_USES
        self.props = []
        self.cover = Entity(parent=camera.ui, model="quad", scale=(4, 2), z=-1.5,
                            color=color.rgba32(8, 8, 12, 255), enabled=False)
        self.cover_text = Text(parent=camera.ui, z=-1.6, origin=(0, 0), scale=1.6, color=color.rgb32(235, 228, 210),
                               enabled=False)
        self.book_screen = Entity(parent=camera.ui, model="quad", scale=(2.2, 1.2), z=-1.2, enabled=False)
        self.cctv_tint = Entity(parent=camera.ui, model="quad", scale=(4, 2), z=-1.1,
                                color=color.rgba32(20, 60, 30, 90), enabled=False)
        self.cctv_text = Text(parent=camera.ui, z=-1.15, position=(-0.6, 0.44), scale=1.4,
                              color=color.rgb32(190, 255, 190), enabled=False)
        self.slots = []
        for i in range(2):
            bg = Entity(parent=camera.ui, model="quad", position=(-0.12 + i * 0.24, -0.43), scale=(0.22, 0.06),
                        color=color.rgba32(0, 0, 0, 150), z=0.5, enabled=False)
            t = Text(parent=camera.ui, position=(-0.12 + i * 0.24, -0.43), origin=(0, 0), scale=0.95,
                     color=color.white, enabled=False)
            self.slots.append((bg, t))

    # ---------- 開局 ----------
    def build(self):
        """4F 蓋好之後：放路人（兩台一模一樣）、道具、對方的身體、自己的位置。"""
        g = self.g
        world = g.world
        g.crowd.rng = random.Random(self.seed + 1)
        g.crowd.spawn(world, (), walkers=8, readers=14)
        readers = [n for n in g.crowd.npcs if n.mode == "read"]
        walkers = [n for n in g.crowd.npcs if n.mode == "walk"]
        layout = random.Random(self.seed + 3)
        if self.mode == "hide":
            for n in readers[:LOOK_READERS] + walkers[:LOOK_WALKERS]:
                dress_outfit(n, self.outfit)
        else:   # 巡館：第一個坐著的就是 AI 室友，旁邊幾個穿得很像（至少一樣相同）
            mate = readers[0]
            dress_outfit(mate, self.outfit)
            mate.timer = None
            self.target_npc = g.crowd.npcs.index(mate)
            for n in readers[1:7]:
                o = random_outfit(layout, avoid=self.outfit)
                k = layout.randrange(3)
                o = tuple(self.outfit[i] if i == k else o[i] for i in range(3))
                if o == self.outfit:
                    o = random_outfit(layout, avoid=self.outfit)
                dress_outfit(n, o)
                n.timer = None
        self.spots = g.roommate.find_spots(world)
        self.place_props(layout)
        av_rng = random.Random(self.seed + 7)
        remote = self.other_role()
        if remote == "librarian":       # 對方是館員：用館員的模型
            self.avatar = g.librarian
            self.avatar.shh.enabled = False
        elif remote == "roommate":      # 對方是室友：長得跟那些同學一樣
            self.avatar = NPC("學生", av_rng, g.font_path, outfit=self.outfit)
        else:
            self.avatar = NPC("學生", av_rng, g.font_path)
        self.avatar.root.enabled = False
        self.avatar.net_pose = None
        g.place_player()
        if self.role == "roommate":     # 室友一開始就坐在離樓梯口很遠的空位
            start = g.player.position
            free = [i for i in self.free_seats() if (self.spots[i][0] - start).length() > 14] or self.free_seats()
            if free:
                self.sit(random.choice(free))
        elif self.role == "librarian" and self.desk:
            g.player.position = cell_pos(*self.desk["cell"]) + Vec3(0, 0.1, 0)
        if self.mode == "hide" and self.role == "catcher":
            self.inv[0] = "ask"
        self.ready_me = True
        self.net.send({"t": "ready"})
        self.cover.enabled = self.cover_text.enabled = True
        self.cover_text.text = "等對方準備好……"
        self.check_go()

    def other_role(self):
        a, b = MODES[self.mode]
        return b if self.role == a else a

    def wall_cells(self):
        """靠牆的走道格子，和「往牆的方向」。"""
        w = self.g.world
        out = []
        for c, r in sorted(w.walkable):
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if w.char(c + dc, r + dr) in "#W":
                    out.append(((c, r), Vec3(dc, 0, -dr)))
                    break
        return out

    def place_props(self, rng):
        g, w = self.g, self.g.world
        walls = self.wall_cells()
        wall_of = dict(walls)
        if self.mode == "hide":
            for cell in spread([c for c, _ in walls], 3, rng):        # 飲水機：三台，彼此離很遠
                d = wall_of[cell]
                base = cell_pos(*cell) + d * (CELL / 2 - 0.3)
                body = Entity(model="cube", position=base + Vec3(0, 0.65, 0), scale=(0.45, 1.3, 0.45),
                              color=color.rgb32(28, 28, 30))
                Entity(parent=body, model="cube", position=(0, 0.25, 0), scale=(1.02, 0.08, 1.02),
                       color=color.rgb(0.3, 1.2, 1.5))
                self.props.append(body)
                self.pickups.append(dict(kind="water", pos=cell_pos(*cell), look=base + Vec3(0, 0.9, 0), ent=None, cd=0))
            tables = sorted(w.hides, key=lambda p: (p.x, p.z))
            for p in rng.sample(tables, min(4, len(tables))):          # 腎上腺素：放在四張桌子上
                can = Entity(model="cube", position=p + Vec3(rng.uniform(-0.3, 0.3), 0.86, rng.uniform(-0.15, 0.15)),
                             scale=(0.09, 0.2, 0.09), color=color.rgb32(220, 40, 50))
                Entity(parent=can, model="cube", y=0.55, scale=(1.05, 0.1, 1.05), color=color.rgb32(240, 240, 240))
                self.props.append(can)
                self.pickups.append(dict(kind="boost", pos=p, look=can.position, ent=can, cd=0))
            for run in w.shelf_runs.values():                         # 每排書櫃都可以拿書
                for c, r in run[::2]:
                    p = cell_pos(c, r)
                    self.pickups.append(dict(kind="book", pos=p, look=p + Vec3(0, 1.2, 0), ent=None, cd=0, shelf=True))
            self.book_screen.texture = w.book_tex[0]
        else:
            down = w.stairs.get("down")
            start = to_cell(down["pos"]) if down else sorted(w.walkable)[0]
            near = sorted([c for c, _ in walls], key=lambda c: abs(c[0] - start[0]) + abs(c[1] - start[1]))
            desk_cell = next((c for c in near if abs(c[0] - start[0]) + abs(c[1] - start[1]) >= 3), near[0])
            far = max([c for c, _ in walls], key=lambda c: abs(c[0] - start[0]) + abs(c[1] - start[1]))
            for cell, kind in ((desk_cell, "desk"), (far, "toilet")):
                d = wall_of[cell]
                base = cell_pos(*cell) + d * (CELL / 2 - 0.35)
                yaw = math.degrees(math.atan2(-d.x, -d.z))
                if kind == "desk":     # 監控室：桌子加四個小螢幕
                    root = Entity(position=base, rotation_y=yaw)
                    Entity(parent=root, model="cube", y=0.38, scale=(1.4, 0.76, 0.6), color=color.rgb32(80, 70, 60))
                    for i in range(4):
                        Entity(parent=root, model="cube", position=(-0.48 + i * 0.32, 1.0, 0.1), scale=(0.3, 0.22, 0.04),
                               color=color.rgb(0.25, 0.9, 0.45))
                    self.desk = dict(cell=cell, look=base + Vec3(0, 1.0, 0))
                else:                  # 廁所門：灰色的門加 WC 標誌
                    root = Entity(position=base + d * 0.3, rotation_y=yaw)
                    Entity(parent=root, model="cube", y=1.05, scale=(1.0, 2.1, 0.06), color=color.rgb32(150, 155, 160))
                    Entity(parent=root, model="cube", position=(0, 1.75, -0.05), scale=(0.5, 0.25, 0.02),
                           color=color.rgb32(40, 90, 170))
                    Text(parent=root, text="WC 廁所", position=(0, 1.75, -0.07), origin=(0, 0), scale=6,
                         color=color.white, billboard=False)
                    self.toilet = dict(cell=cell, look=base + Vec3(0, 1.2, 0))
                self.props.append(root)
            # 監視器裝在靠牆的天花板角落，朝整層的中心往下看
            mid = sum((cell_pos(*c) for c in w.walkable), Vec3(0, 0, 0)) / max(1, len(w.walkable))
            for c in spread([c for c, _ in walls], 4, random.Random(self.seed + 5)):
                pos = cell_pos(*c) + wall_of[c] * 0.6 + Vec3(0, 3.2, 0)
                d = Vec3(mid.x - pos.x, 0, mid.z - pos.z)
                yaw = math.degrees(math.atan2(d.x, d.z))
                pitch = max(12.0, min(30.0, math.degrees(math.atan2(3.2, max(1.0, d.length() * 0.5)))))
                self.cams.append((pos, (pitch, yaw)))

    def check_go(self):
        if self.host and self.ready_me and self.ready_them and not self.started:
            self.net.send({"t": "go"})
            self.go()

    def go(self):
        self.started = True
        msg = {"roommate": "先找張椅子坐下，裝成在讀書的樣子。",
               "catcher": "閉眼 10 秒，室友正在躲……" if self.mode == "hide" else "裝成普通同學，去認出室友！",
               "librarian": "開館了。注意哪個同學怪怪的；監控室在你旁邊。"}[self.role]
        self.g.show_hint("開始！" + msg, 4)

    # ---------- 座位 ----------
    def free_seats(self):
        npcs = [n.root.position for n in self.g.crowd.npcs]
        out = []
        for i, s in enumerate(self.spots):
            if i == self.remote_seat:
                continue
            if all((s[0] - p).length() > 0.6 for p in npcs):
                out.append(i)
        return out

    def take_seat(self, i, taken):
        """開房間那台的路人要知道哪個位子被真人坐走了，才不會坐到他身上。"""
        if not self.host or i is None:
            return
        crowd, spot = self.g.crowd, self.spots[i]
        if taken:
            crowd.free = [s for s in crowd.free if (s[0] - spot[0]).length() > 0.5]
        elif all((s[0] - spot[0]).length() > 0.5 for s in crowd.free):
            crowd.free.append(spot)

    def sit(self, i):
        p = self.g.player
        spot = self.spots[i]
        self.seat = i
        p.rotation_y = spot[2]
        p.position = Vec3(spot[0].x, 0.1, spot[0].z) - p.forward * 0.15
        p.camera_pivot.rotation_x = 20
        self.take_seat(i, True)

    def stand_up(self):
        if self.seat is None:
            return
        spot = self.spots[self.seat]
        self.take_seat(self.seat, False)
        self.seat = None
        self.g.player.position = cell_pos(*spot[1]) + Vec3(0, 0.1, 0)

    # ---------- 按 E ----------
    def targets(self):
        out = []
        g = self.g
        if self.over or not self.started or self.changing > 0 or self.slip > 0:
            return out
        if self.cctv is not None:
            return out
        if self.role == "catcher" and self.mode == "hide" and self.time_left > self.round - HEADSTART:
            return out
        a = self.avatar.root.position if self.avatar and self.avatar.root.enabled else None
        if self.role == "catcher":
            for i, n in enumerate(g.crowd.npcs):
                out.append((n.position + Vec3(0, 1.0, 0), n.position, "抓住他！", lambda i=i: self.grab(i)))
            if a is not None and self.mode == "hide":
                out.append((a + Vec3(0, 1.0, 0), a, "抓住他！", lambda: self.grab(None)))
            if self.toilet and self.toilet_left > 0:
                out.append((self.toilet["look"], cell_pos(*self.toilet["cell"]),
                            f"進廁所換衣服（剩 {self.toilet_left} 次）", self.enter_toilet))
        elif self.role == "librarian":
            for i, n in enumerate(g.crowd.npcs):
                out.append((n.position + Vec3(0, 1.2, 0), n.position, "盤查這位同學", lambda i=i: self.check(i)))
            if a is not None:
                out.append((a + Vec3(0, 1.2, 0), a, "盤查這位同學", lambda: self.check(None)))
            if self.desk:
                out.append((self.desk["look"], cell_pos(*self.desk["cell"]), "看監視器", self.open_cctv))
        elif self.seat is not None:
            p = g.player.position
            out.append((p + g.player.forward, p, "站起來", self.stand_up))
        else:
            for i in self.free_seats():
                s = self.spots[i]
                out.append((s[0] + Vec3(0, 0.8, 0), cell_pos(*s[1]), "坐下來假裝讀書", lambda i=i: self.sit(i)))
        if None in self.inv and self.seat is None:
            for k, pk in enumerate(self.pickups):
                if pk["cd"] > 0:
                    continue
                label = {"water": "在飲水機裝一瓶水", "boost": "拿起腎上腺素", "book": "從書櫃拿一本書"}[pk["kind"]]
                out.append((pk["look"], pk["pos"], label, lambda k=k: self.pick(k)))
        return out

    def grab(self, i):
        """抓人的按 E：i 是路人編號，None 是對方玩家（躲貓貓的室友）。"""
        g = self.g
        if self.grab_cd > 0 or self.over:
            return
        self.grab_cd = 1.2
        if i is None or (self.mode == "patrol" and i == self.target_npc):
            g.play("punch")
            self.finish("catcher", "抓到了！就是他，在偷卷！")
            return
        self.warnings += 1
        g.play("shh")
        pos = g.crowd.npcs[i].root.position
        self.net.send({"t": "warn", "n": self.warnings, "x": round(pos.x, 1), "z": round(pos.z, 1)})
        if self.warnings >= WARN_LIMIT:
            self.finish(self.other_role(), "抓錯 3 次，被請出圖書館了。")
            return
        g.show_hint(f"抓錯人了！同學一臉莫名其妙。（抓錯 {self.warnings}/{WARN_LIMIT}）", 3)

    def check(self, i):
        """館員按 E 盤查：i 是路人編號，None 是對方玩家。"""
        g = self.g
        if self.grab_cd > 0 or self.over:
            return
        self.grab_cd = 1.2
        if i is None:
            g.play("shh")
            self.finish("librarian", "「同學，你一直盯著別人看，請出示學生證。」——抓到你了！")
            return
        self.warnings += 1
        g.play("shh")
        self.net.send({"t": "warn", "n": self.warnings})
        if self.warnings >= WARN_LIMIT:
            self.finish("catcher", "館員盤查錯 3 次，被投訴了。抓人的贏！")
            return
        g.show_hint(f"這位只是普通同學……（盤查錯 {self.warnings}/{WARN_LIMIT}）", 3)

    # ---------- 道具 ----------
    def pick(self, k):
        pk = self.pickups[k]
        if pk["cd"] > 0 or None not in self.inv:
            return
        self.inv[self.inv.index(None)] = pk["kind"]
        self.g.play("page")
        if pk["kind"] == "boost":
            self.take_pickup(k)
            self.net.send({"t": "pick", "i": k})
        elif pk["kind"] == "water":
            pk["cd"] = 3
        else:
            pk["cd"] = 1
        self.g.show_hint(f"拿到{ITEM_NAME[pk['kind']]}（按 {self.inv.index(pk['kind']) + 1} 使用）", 2)

    def take_pickup(self, k):
        pk = self.pickups[k]
        pk["cd"] = 40
        if pk["ent"]:
            pk["ent"].enabled = False

    def use(self, slot):
        kind = self.inv[slot]
        if not kind or self.seat is not None or self.over or not self.started or self.cctv is not None:
            return
        g, p = self.g, self.g.player
        if self.role == "catcher" and self.mode == "hide" and self.time_left > self.round - HEADSTART:
            return
        self.inv[slot] = None
        if kind == "water":
            pos = p.position + p.forward * 0.8
            self.fx_id += 1
            pid = f"{'h' if self.host else 'c'}{self.fx_id}"
            self.add_puddle(pid, pos.x, pos.z, mine=True)
            self.net.send({"t": "fx", "k": "puddle", "id": pid, "x": round(pos.x, 2), "z": round(pos.z, 2)})
            g.show_hint("你把水倒在地上。（自己踩到不會滑）", 2)
        elif kind == "boost":
            self.boost = 5.0
            g.play("sting", volume=0.3)
            g.show_hint("腎上腺素！5 秒內跑超快。", 2)
        elif kind == "book":
            eye = camera.world_position
            d = camera.forward
            self.throw(eye, d, mine=True)
            self.net.send({"t": "fx", "k": "book", "x": round(eye.x, 2), "y": round(eye.y, 2), "z": round(eye.z, 2),
                           "dx": round(d.x, 3), "dy": round(d.y, 3), "dz": round(d.z, 3)})
        elif kind == "ask":
            self.net.send({"t": "ask"})
            g.show_hint("你去問櫃臺的館員……", 2)

    def add_puddle(self, pid, x, z, mine):
        e = Entity(model="circle", position=(x, 0.03, z), rotation_x=90, scale=1.6,
                   color=color.rgba32(150, 200, 255, 120))
        e.mine, e.life = mine, 25.0
        self.puddles[pid] = e

    def throw(self, eye, d, mine):
        b = Entity(model="cube", position=eye + d * 0.5, scale=(0.18, 0.04, 0.25), color=color.rgb32(170, 60, 50))
        b.vel, b.life, b.mine = Vec3(d) * 15, 1.4, mine
        self.books.append(b)

    def update_items(self, dt):
        g, p = self.g, self.g.player
        for pk in self.pickups:
            if pk["cd"] > 0:
                pk["cd"] -= dt
                if pk["cd"] <= 0 and pk["ent"]:
                    pk["ent"].enabled = True
        for pid, e in list(self.puddles.items()):
            e.life -= dt
            gone = e.life <= 0
            if not gone and not e.mine and self.slip <= 0 and self.seat is None:
                d = Vec3(e.x - p.x, 0, e.z - p.z)
                if d.length() < 0.85 and g.moving:
                    self.slip = 1.6
                    g.play("thud")
                    g.show_hint("腳一滑，摔了一跤！", 2)
                    gone = True
                    self.net.send({"t": "fx", "k": "dry", "id": pid})
            if gone:
                fastops.bulk_destroy([e])
                del self.puddles[pid]
        a = self.avatar.root.position if self.avatar and self.avatar.root.enabled else None
        for b in list(self.books):
            b.life -= dt
            b.vel.y -= 4 * dt
            b.position += b.vel * dt
            b.rotation_y += 720 * dt
            hit = b.mine and a is not None and (b.position - (a + Vec3(0, 1.3, 0))).length() < 0.75
            if hit:
                self.net.send({"t": "hit"})
                g.show_hint("丟中了！", 1.5)
            if hit or b.life <= 0 or b.y < 0.05:
                fastops.bulk_destroy([b])
                self.books.remove(b)
        if self.boost > 0:
            self.boost -= dt
            if self.boost <= 0:
                self.boost = -2.0
                g.show_hint("呼……呼……喘不過氣，腳變慢了。", 2)
        elif self.boost < 0:
            self.boost = min(0.0, self.boost + dt)
        if self.blind > 0:
            self.blind -= dt
        self.book_screen.enabled = self.blind > 0
        if self.ping_t > 0:
            self.ping_t -= dt
            if self.ping_t <= 0:
                g.minimap.mark(None)
        for i, (bg, t) in enumerate(self.slots):
            on = self.mode == "hide"
            bg.enabled = t.enabled = on
            t.text = f"[{i + 1}] {ITEM_NAME[self.inv[i]]}" if self.inv[i] else f"[{i + 1}] （空）"

    def ping(self, pos, seconds=6):
        self.g.minimap.mark(Vec3(pos))
        self.ping_t = seconds

    # ---------- 巡館：監視器、廁所 ----------
    def open_cctv(self):
        if not self.cams:
            return
        self.cctv = 0
        self.show_cam()
        self.g.show_hint("A／D 切換監視器，E 離開", 3)

    def show_cam(self):
        pos, (pitch, yaw) = self.cams[self.cctv]
        camera.parent = scene
        camera.position = pos
        camera.rotation = (pitch, yaw, 0)
        self.cctv_tint.enabled = self.cctv_text.enabled = True
        g = self.g
        for e in (g.hud_bg, g.clock_text, g.goal_text, g.look_text):
            e.enabled = False

    def close_cctv(self):
        self.cctv = None
        camera.parent = self.g.player.camera_pivot
        camera.position = (0, 0, 0)
        camera.rotation = (0, 0, 0)
        self.cctv_tint.enabled = self.cctv_text.enabled = False
        g = self.g
        for e in (g.hud_bg, g.clock_text, g.goal_text, g.look_text):
            e.enabled = True

    def enter_toilet(self):
        if self.toilet_left <= 0:
            return
        self.toilet_left -= 1
        self.changing = 4.0
        self.net.send({"t": "toilet"})

    def finish_change(self):
        rng = random.Random()
        o = random_outfit(rng, avoid=None)
        self.net.send({"t": "outfit", "o": list(o)})
        self.g.show_hint(f"換好了：現在穿{wear(o)}。", 3)

    def input(self, key):
        """雙人模式自己處理的按鍵；回傳 True 表示吃掉了。"""
        if self.cctv is not None:
            if key in ("a", "left arrow"):
                self.cctv = (self.cctv - 1) % len(self.cams)
                self.show_cam()
            elif key in ("d", "right arrow"):
                self.cctv = (self.cctv + 1) % len(self.cams)
                self.show_cam()
            elif key in ("e", "escape"):
                self.close_cctv()
            return key in ("a", "d", "left arrow", "right arrow", "e", "escape")
        if key in ("1", "2"):
            self.use(int(key) - 1)
            return True
        return False

    # ---------- 每一幀 ----------
    def update(self):
        g = self.g
        for m in self.net.poll():
            self.handle(m)
        if not self.spots:         # 還在蓋 4F
            return
        self.update_avatar()
        if self.over:
            return
        dt = time.dt
        self.grab_cd -= dt
        if not self.started:
            g.player.speed = 0
            return
        if self.host:
            self.time_left -= dt
        self.update_items(dt)
        blind = self.role == "catcher" and self.mode == "hide" and self.time_left > self.round - HEADSTART
        if self.changing > 0:
            self.changing -= dt
            if self.changing <= 0:
                self.finish_change()
        covered = blind or self.changing > 0
        self.cover.enabled = self.cover_text.enabled = covered
        if blind:
            self.cover_text.text = f"閉上眼睛數到 10……　{int(self.time_left - (self.round - HEADSTART)) + 1}\n室友正在找地方躲"
        elif self.changing > 0:
            self.cover_text.text = f"在廁所換衣服……　{int(self.changing) + 1}"
        if self.cctv is not None:
            self.cctv_text.text = f"● REC　CAM {self.cctv + 1}/{len(self.cams)}　（A／D 切換，E 離開）"
        sitting = self.seat is not None
        frozen = covered or self.cctv is not None or self.slip > 0
        if self.slip > 0:
            self.slip -= dt
            g.player.camera_pivot.rotation_z = math.sin(self.slip * 6) * 12 if self.slip > 0 else 0
        g.sneaking = bool(held_keys["control"] or held_keys["left control"])
        g.moving = any(held_keys[k] for k in "wasd") and not sitting and not frozen
        g.running = g.moving and bool(held_keys["shift"]) and not g.sneaking
        speed = 3.2 if g.running else 0.9 if g.sneaking else 1.25     # 走路速度跟路人差不多（1.0–1.45），Shift 是快走
        speed *= 1.7 if self.boost > 0 else 0.6 if self.boost < 0 else 1.0
        g.player.speed = 0 if (sitting or frozen) else speed
        g.update_body()
        if sitting:
            g.player.camera_pivot.y = 1.15
        g.update_prompt(off=covered or self.cctv is not None)
        g.minimap.update(g.player, _Far)
        if self.host:
            g.crowd.update()
        else:
            self.apply_npcs()
        self.send_state()
        self.update_hud()
        if self.host and self.time_left <= 0:
            if self.mode == "hide":
                self.finish("roommate", "（叮咚）22:00 閉館了，室友成功混到最後！")
            else:
                self.finish("librarian", "（叮咚）22:00 閉館了，抓人的沒抓到室友，也被館員盯到最後。")

    def send_state(self):
        g, p = self.g, self.g.player
        self.send_t -= time.dt
        if self.send_t <= 0:
            self.send_t = 0.05
            mode = 4 if self.seat is not None else (2 if g.running else 3 if g.sneaking else 1) if g.moving else 0
            hidden = self.changing > 0
            self.net.send({"t": "s", "x": round(p.x, 2), "z": round(p.z, 2), "y": round(p.rotation_y, 1),
                           "p": round(p.camera_pivot.rotation_x, 1), "m": mode, "h": hidden,
                           "seat": -1 if self.seat is None else self.seat})
        if self.host:
            self.npc_t -= time.dt
            if self.npc_t <= 0:
                self.npc_t = 0.1
                rows = []
                for n in g.crowd.npcs:
                    pose = 2 if n.mode == "read" else 0 if n.pause > 0 or n.mode == "talk" else 1
                    rows.append([round(n.root.x, 2), round(n.root.z, 2), round(n.root.rotation_y), pose])
                self.net.send({"t": "n", "a": rows, "time": round(self.time_left, 1)})

    def apply_npcs(self):
        """加入的那台：路人照開房間那台傳來的位置走（中間平滑補上）。"""
        rows = getattr(self, "npc_rows", None)
        if not rows:
            return
        k = min(1.0, time.dt * 10)
        for n, (x, z, yaw, pose) in zip(self.g.crowd.npcs, rows):
            target = Vec3(x, 0, z)
            d = target - n.root.position
            n.root.position = target if d.length() > 3 else n.root.position + d * k
            n.root.rotation_y = angle_lerp(n.root.rotation_y, yaw, min(1.0, time.dt * 6))
            last = getattr(n, "net_pose", None)
            if pose == 2:
                if last != 2:
                    n.sit()
                n.t += time.dt
                n.update_glance()           # 抬頭張望兩台各自算（身體方向照房主的）
                lift = min(1.0, abs(n.look_yaw) / 30)
                n.torso.rotation_x = 15 - 9 * lift
                n.head.rotation = (22 - 24 * lift + math.sin(n.t * 1.3) * 1.5, n.look_yaw * 0.65, 0)
            elif pose == 1:
                n.walk_anim(6 * n.speed / 1.3)
            elif last != 0:
                n.stand()
            n.net_pose = pose

    def update_avatar(self):
        s, a = self.remote, self.avatar
        if not s or not a:
            return
        a.root.enabled = not s.get("h")         # 在廁所換衣服時看不到人
        k = min(1.0, time.dt * 12)
        if s["m"] == 4 and 0 <= s["seat"] < len(self.spots):
            spot = self.spots[s["seat"]]
            if a.net_pose != 4:
                a.sit()
            a.root.position = spot[0]
            a.root.rotation_y = spot[2]
            look = (s["y"] - spot[2] + 180) % 360 - 180      # 坐著時頭跟著真人的視線轉：這就是破綻
            a.head.rotation = (max(-20, min(35, s["p"] + 10)), max(-70, min(70, look)), 0)
            a.torso.rotation_x = 15 if s["p"] > 5 else 3
        else:
            target = Vec3(s["x"], 0, s["z"])
            d = target - a.root.position
            a.root.position = target if d.length() > 4 else a.root.position + d * k
            a.root.rotation_y = angle_lerp(a.root.rotation_y, s["y"], k)
            if s["m"] in (1, 2, 3):
                a.walk_anim({1: 6, 2: 11, 3: 4}[s["m"]])
            elif a.net_pose != 0:
                a.stand()
            a.head.rotation = (max(-25, min(25, s["p"])), 0, 0)
        a.net_pose = s["m"] if s["m"] in (0, 4) else 1

    def update_hud(self):
        g = self.g
        used = self.round - max(0.0, self.time_left)
        minutes = 18 * 60 + int(used / self.round * 240)
        left = max(0, int(self.time_left))
        if self.role == "roommate":
            miss = f"抓人的抓錯 {self.their}/{WARN_LIMIT}"
        else:
            miss = f"{'抓錯' if self.role == 'catcher' else '盤查錯'} {self.warnings}/{WARN_LIMIT}"
        g.clock_text.text = (f"{minutes // 60:02d}:{minutes % 60:02d}　雙人 4F　你是{ROLE_NAME[self.role]}　"
                             f"剩 {left // 60}:{left % 60:02d}　{miss}")
        if self.mode == "hide":
            if self.role == "roommate":
                g.goal_text.text = "目標：混進穿一樣的同學裡，別被抓到（E 坐下／站起來）"
                g.look_text.text = f"你今天穿：{wear(self.outfit)}（還有 7 個人跟你一樣）"
            else:
                g.goal_text.text = "目標：找出動作怪怪的那個人，靠近按 E 抓住他"
                g.look_text.text = f"室友穿：{wear(self.outfit)}（有 8 個人穿這樣）"
        elif self.role == "catcher":
            g.goal_text.text = "目標：認出室友抓住他，但別讓館員發現你在找人"
            g.look_text.text = f"室友穿：{wear(self.outfit)}（旁邊有人穿得很像）　廁所可以換衣服"
        else:
            g.goal_text.text = "目標：找出混在人群裡的抓人的，靠近按 E 盤查"
            g.look_text.text = "監控室在樓梯口旁邊；有人抓錯人會在小地圖上標出來"

    # ---------- 收訊息 ----------
    def handle(self, m):
        t = m.get("t")
        g = self.g
        if t == "s":
            seat = m.get("seat", -1)
            if self.host and seat != (self.remote_seat if self.remote_seat is not None else -1):
                self.take_seat(self.remote_seat, False)
                self.take_seat(seat if seat >= 0 else None, True)
            self.remote_seat = seat if seat >= 0 else None
            self.remote = m
        elif t == "n":
            self.npc_rows = m["a"]
            self.time_left = m["time"]
        elif t == "ready":
            self.ready_them = True
            self.check_go()
        elif t == "go":
            self.go()
        elif t == "warn":
            self.their = m["n"]
            if self.role == "roommate":
                g.show_hint(f"抓人的抓錯人了！（{self.their}/{WARN_LIMIT}）", 2.5)
            elif self.role == "librarian":
                g.show_hint(f"有同學被騷擾！小地圖上標出位置了。（抓人的抓錯 {self.their}/{WARN_LIMIT}）", 3)
                self.ping(Vec3(m.get("x", 0), 0, m.get("z", 0)))
            else:
                g.show_hint(f"館員盤查錯人了。（{self.their}/{WARN_LIMIT}）", 2.5)
        elif t == "fx":
            if m["k"] == "puddle":
                self.add_puddle(m["id"], m["x"], m["z"], mine=False)
                self.puddles[m["id"]].mine = False
            elif m["k"] == "dry" and m["id"] in self.puddles:
                fastops.bulk_destroy([self.puddles.pop(m["id"])])
            elif m["k"] == "book":
                self.throw(Vec3(m["x"], m["y"], m["z"]), Vec3(m["dx"], m["dy"], m["dz"]), mine=False)
        elif t == "hit":
            self.blind = 1.3
            g.play("thud")
            g.show_hint("一本書砸在你臉上！", 1.5)
        elif t == "pick":
            if 0 <= m["i"] < len(self.pickups):
                self.take_pickup(m["i"])
        elif t == "ask":             # 對方（抓人的）問館員：室友這台把自己大概的位置傳回去
            p = g.player.position
            r = random.Random()
            self.net.send({"t": "near", "x": round(p.x + r.uniform(-5, 5), 1), "z": round(p.z + r.uniform(-5, 5), 1)})
        elif t == "near":
            g.show_hint("館員：「穿這樣的同學？好像在那一帶。」（小地圖上的驚嘆號）", 4)
            self.ping(Vec3(m["x"], 0, m["z"]), 8)
        elif t == "toilet":
            if self.cctv is not None:
                g.show_hint("（監視器）有人走進廁所了……", 3)
                if self.toilet:
                    self.ping(cell_pos(*self.toilet["cell"]), 6)
        elif t == "outfit":
            if self.avatar is not None and self.avatar is not g.librarian:
                dress_outfit(self.avatar, tuple(m["o"]))
        elif t == "end":
            self.finish(m["w"], m["why"], send=False)
        elif t in ("lost", "bye"):
            if not self.over:
                self.finish(None, "對方離開了，連線中斷。", send=False)

    def finish(self, winner, why, send=True):
        if self.over:
            return
        self.over = True
        g = self.g
        if self.cctv is not None:
            self.close_cctv()
        if send:
            self.net.send({"t": "end", "w": winner, "why": why})
        self.cover.enabled = self.cover_text.enabled = False
        self.book_screen.enabled = False
        g.cleared = True
        g.player.speed = 0
        g.player.camera_pivot.rotation_z = 0
        g.update_prompt(off=True)
        if winner is None:
            head = "—— 連線中斷 ——"
        elif winner == self.role:
            head = "—— 你贏了！ ——"
        else:
            head = "—— 你輸了…… ——"
        g.play("chime")
        g.note_text.text = f"{head}\n\n{why}\n\n按 Enter 回到大廳"
        g.note_bg.enabled = True

    def stop(self):
        self.net.close()
        if self.cctv is not None:
            self.close_cctv()
        g = self.g
        if self.avatar and self.avatar is not g.librarian:
            fastops.bulk_destroy(fastops._descendants(self.avatar.root) + [self.avatar.root])
        self.avatar = None
        doomed = []
        for e in self.props + list(self.puddles.values()) + self.books:
            doomed += fastops._descendants(e) + [e]
        fastops.bulk_destroy(doomed)
        self.props, self.puddles, self.books = [], {}, []
        for e in (self.cover, self.cover_text, self.book_screen, self.cctv_tint, self.cctv_text):
            e.enabled = False
        for bg, t in self.slots:
            bg.enabled = t.enabled = False
        g.player.camera_pivot.rotation_z = 0
        g.minimap.mark(None)
        g.librarian.root.enabled = True
        g.hide_note()


class DuoPanel:
    """大廳右邊的「雙人連線」面板：選模式、開房間／找房間／輸入 IP，連上之後兩台一起開始。"""

    def __init__(self, lobby, game):
        from menu import ACCENT, IDLE, _button
        from ursina.prefabs.input_field import InputField
        self.lobby, self.game = lobby, game
        self.accent, self.idle = ACCENT, IDLE
        self.net = None
        self.mode = "hide"
        self.my_role = "catcher"
        self.root = Entity(parent=lobby.panel, enabled=False)
        self.mode_buttons = {
            "hide": _button(self.root, "躲貓貓：室友 vs 抓人的", 0.0, lambda: self.pick("hide"), x=-0.22, width=0.42),
            "patrol": _button(self.root, "巡館：抓人的 vs 館員", 0.0, lambda: self.pick("patrol"), x=0.22, width=0.42)}
        self.host_buttons = [_button(self.root, "開房間", -0.08, lambda: self.host(0), x=-0.22, width=0.42),
                             _button(self.root, "開房間", -0.08, lambda: self.host(1), x=0.22, width=0.42)]
        _button(self.root, "自動找房間加入", -0.16, self.search, x=-0.22, width=0.42)
        self.field = InputField(parent=self.root, default_value="192.168.", character_limit=15,
                                position=(0.12, -0.16), scale=(0.24, 0.065))
        self.field.limit_content_to = "0123456789."
        _button(self.root, "用 IP 加入", -0.16, self.join, x=0.35, width=0.18)
        self.status = Text(parent=self.root, position=(-0.42, -0.21), scale=0.75, color=ACCENT, line_height=1.2)
        self.driver = Entity(update=self.update)
        self.pick("hide")

    def pick(self, mode):
        if self.net and mode != self.mode:      # 換模式：已經開好的房間關掉，重新開
            self.net.close()
            self.net = None
            self.status.text = "換了模式，請重新開房間。"
        self.mode = mode
        for m, b in self.mode_buttons.items():
            b.color = self.accent if m == mode else self.idle
        for b, role in zip(self.host_buttons, MODES[mode]):
            b.text = f"開房間（我當{ROLE_NAME[role]}）"
        if self.root.enabled:
            self.lobby.panel_text.text = HELP[mode]

    def open(self):
        self.lobby.show_panel("雙人連線", HELP[self.mode])
        self.root.enabled = True
        self.status.text = ""

    def cancel(self):
        if self.net:
            self.net.close()
            self.net = None
        self.root.enabled = False

    def fresh(self):
        if self.net:
            self.net.close()
        self.net = Net()
        return self.net

    def host(self, k):
        role = MODES[self.mode][k]
        self.my_role = role
        try:
            self.fresh().host()
        except OSError as e:
            self.net = None
            self.status.text = f"開不了房間：{e.strerror or e}"
            return
        self.status.text = (f"房間開好了（{MODE_NAME[self.mode]}），你當{ROLE_NAME[role]}。等對方加入……\n"
                            f"對方按「自動找房間」，或輸入這台的 IP：{local_ip()}\n"
                            "（Mac 跳出「允許傳入連線」、Windows 跳出防火牆，請按允許）")

    def search(self):
        self.fresh().search()
        self.status.text = "找房間中……（最多 6 秒）"

    def join(self):
        ip = self.field.text_field.text.strip()
        if ip.count(".") != 3:
            self.status.text = "IP 格式不對，例如 192.168.0.12"
            return
        self.fresh().join(ip)
        self.status.text = f"連線到 {ip} 中……"

    def update(self):
        while self.net:
            try:
                m = self.net.inbox.get_nowait()
            except Exception:
                return
            t = m.get("t")
            if t == "joined":           # 我是房主：對方進來了，決定種子和角色，一起開始
                seed = random.randrange(1, 10 ** 9)
                a, b = MODES[self.mode]
                other = b if self.my_role == a else a
                self.net.send({"t": "start", "seed": seed, "role": other, "mode": self.mode})
                self.begin(self.my_role, seed, self.mode)
            elif t == "found":
                self.status.text = f"找到房間 {m['ip']}，連線中……"
            elif t == "connected":
                self.status.text = "連上了！等房主開始……"
            elif t == "start":
                self.begin(m["role"], m["seed"], m.get("mode", "hide"))
            elif t == "fail":
                self.status.text = m["why"]
                self.net.close()
                self.net = None
            elif t in ("lost", "bye"):
                self.status.text = "對方斷線了。"
                self.net.close()
                self.net = None

    def begin(self, role, seed, mode):
        net, self.net = self.net, None       # 連線交給遊戲，大廳不再收訊息
        self.root.enabled = False
        self.lobby.hide()
        self.game.start_versus(net, role, seed, mode)
