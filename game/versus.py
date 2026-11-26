"""雙人模式：偷卷室友 vs 抓人的（4F）。

· 室友（真人）今天的穿著隨機，這層還有 7 個同學穿得一模一樣。室友要混在他們裡面：E 坐下假裝讀書、
  起來走走，撐到閉館就贏。
· 抓人的前 10 秒閉眼（讓室友先躲），之後要從一模一樣的人裡找出「動作怪怪的」真人，靠近按 E 抓住他。
  抓錯 3 次就被館員請出去，室友贏。

連線分工：開房間的那台（host）負責算路人怎麼走和倒數計時，每秒傳 10 次給對方；兩邊各自傳自己的位置
（每秒 20 次），對方的身體在畫面上平滑地跟過去。地圖和路人的長相用同一個亂數種子，兩台蓋出來一模一樣。
"""
import math
import random

from ursina import Entity, Text, Vec3, camera, color, held_keys, time

import fastops
from crowd import NPC, dress_outfit, random_outfit
from net import Net, local_ip
from world import cell_pos

ROUND = 240            # 一局 4 分鐘（遊戲裡的 18:00–22:00）
HEADSTART = 10         # 抓人的先閉眼幾秒
WARN_LIMIT = 3
LOOK_READERS, LOOK_WALKERS = 5, 2     # 跟室友穿一樣的同學（坐著的、走動的）
ROLE_NAME = {"catcher": "抓人的", "roommate": "偷卷室友"}

HELP = ("兩台電腦連同一個 Wi-Fi 或手機熱點。\n"
        "一台按「開房間」選自己的角色，另一台按「自動找房間」或輸入對方的 IP。\n\n"
        "偷卷室友：這層有 7 個同學跟你穿得一模一樣。混進去，\n"
        "　E 坐下假裝讀書、起來走走，撐到 22:00（4 分鐘）就贏。\n"
        "抓人的：前 10 秒先閉眼。之後找出動作怪怪的那個人，\n"
        "　靠近按 E 抓住他。抓錯 3 次就輸。")


def other(role):
    return "roommate" if role == "catcher" else "catcher"


def angle_lerp(a, b, t):
    d = (b - a + 180) % 360 - 180
    return a + d * t


class _Far:          # 小地圖要一個「館員」：雙人模式沒有館員，放到很遠的地方就不會畫出來
    class root:
        position = Vec3(99999, 0, 99999)


class Versus:
    def __init__(self, game, net, role, seed):
        self.g, self.net, self.role, self.seed = game, net, role, seed
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
        self.time_left = ROUND
        self.warnings = 0
        self.grab_cd = 0.0
        self.send_t = self.npc_t = 0.0
        self.cover = Entity(parent=camera.ui, model="quad", scale=(4, 2), z=-1.5,
                            color=color.rgba32(8, 8, 12, 255), enabled=False)
        self.cover_text = Text(parent=camera.ui, z=-1.6, origin=(0, 0), scale=1.6, color=color.rgb32(235, 228, 210),
                               enabled=False)

    # ---------- 開局 ----------
    def build(self):
        """4F 蓋好之後：放路人（兩台一模一樣）、對方的身體、自己的位置。"""
        g = self.g
        g.crowd.rng = random.Random(self.seed + 1)
        g.crowd.spawn(g.world, (), walkers=8, readers=14)
        readers = [n for n in g.crowd.npcs if n.mode == "read"]
        walkers = [n for n in g.crowd.npcs if n.mode == "walk"]
        for n in readers[:LOOK_READERS] + walkers[:LOOK_WALKERS]:
            dress_outfit(n, self.outfit)
        self.spots = g.roommate.find_spots(g.world)
        av_rng = random.Random(self.seed + 7)
        if self.role == "catcher":      # 對方是室友：長得跟那些同學一樣
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
        self.ready_me = True
        self.net.send({"t": "ready"})
        self.cover.enabled = self.cover_text.enabled = True
        self.cover_text.text = "等對方準備好……"
        self.check_go()

    def check_go(self):
        if self.host and self.ready_me and self.ready_them and not self.started:
            self.net.send({"t": "go"})
            self.go()

    def go(self):
        self.started = True
        self.g.show_hint("開始！" + ("先找個位子坐下，裝成在讀書的樣子。" if self.role == "roommate"
                                   else "閉眼 10 秒，室友正在躲……"), 4)

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
        p.position = Vec3(spot[0].x, 0.1, spot[0].z) - p.forward * 0.3     # 往後一點，鏡頭不要插進桌上的檯燈
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
        if self.over or not self.started:
            return out
        if self.role == "catcher":
            if self.time_left > ROUND - HEADSTART:
                return out
            for n in self.g.crowd.npcs:
                out.append((n.position + Vec3(0, 1.0, 0), n.position, "抓住他！", lambda n=n: self.grab(n)))
            if self.avatar and self.avatar.root.enabled:
                a = self.avatar.root.position
                out.append((a + Vec3(0, 1.0, 0), a, "抓住他！", lambda: self.grab(None)))
        elif self.seat is not None:
            p = self.g.player.position
            out.append((p + self.g.player.forward, p, "站起來", self.stand_up))
        else:
            for i in self.free_seats():
                s = self.spots[i]
                out.append((s[0] + Vec3(0, 0.8, 0), cell_pos(*s[1]), "坐下來假裝讀書", lambda i=i: self.sit(i)))
        return out

    def grab(self, npc):
        g = self.g
        if self.grab_cd > 0 or self.over:
            return
        self.grab_cd = 1.2
        if npc is None:
            g.play("punch")
            self.finish("catcher", "抓到了！就是他，在偷卷！")
            return
        self.warnings += 1
        g.play("shh")
        self.net.send({"t": "warn", "n": self.warnings})
        if self.warnings >= WARN_LIMIT:
            self.finish("roommate", "抓錯 3 次，被館員請出圖書館了。")
            return
        g.show_hint(f"抓錯人了！同學一臉莫名其妙。館員：「不要騷擾別人。」（抓錯 {self.warnings}/{WARN_LIMIT}）", 3)

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
        self.grab_cd -= time.dt
        if not self.started:
            g.player.speed = 0
            return
        if self.host:
            self.time_left -= time.dt
        blind = self.role == "catcher" and self.time_left > ROUND - HEADSTART
        self.cover.enabled = self.cover_text.enabled = blind
        if blind:
            self.cover_text.text = f"閉上眼睛數到 10……　{int(self.time_left - (ROUND - HEADSTART)) + 1}\n室友正在找地方躲"
        sitting = self.seat is not None
        g.sneaking = bool(held_keys["control"] or held_keys["left control"])
        g.moving = any(held_keys[k] for k in "wasd") and not sitting and not blind
        g.running = g.moving and bool(held_keys["shift"]) and not g.sneaking
        g.player.speed = 0 if (sitting or blind) else 6.5 if g.running else 1.8 if g.sneaking else 3.5
        g.update_body()
        if sitting:
            g.player.camera_pivot.y = 1.15
        g.update_prompt(off=blind)
        g.minimap.update(g.player, _Far)
        if self.host:
            g.crowd.update()
        else:
            self.apply_npcs()
        self.send_state()
        self.update_hud()
        if self.host and self.time_left <= 0:
            self.finish("roommate", "（叮咚）22:00 閉館了，室友成功混到最後！")

    def send_state(self):
        g, p = self.g, self.g.player
        self.send_t -= time.dt
        if self.send_t <= 0:
            self.send_t = 0.05
            mode = 4 if self.seat is not None else (2 if g.running else 3 if g.sneaking else 1) if g.moving else 0
            self.net.send({"t": "s", "x": round(p.x, 2), "z": round(p.z, 2), "y": round(p.rotation_y, 1),
                           "p": round(p.camera_pivot.rotation_x, 1), "m": mode,
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
            n.root.rotation_y = angle_lerp(n.root.rotation_y, yaw, k)
            last = getattr(n, "net_pose", None)
            if pose == 2:
                if last != 2:
                    n.sit()
                n.t += time.dt
                n.torso.rotation_x = 15
                n.head.rotation = (22 + math.sin(n.t * 5) * 2, 0, 0)
            elif pose == 1:
                n.walk_anim(6)
            elif last != 0:
                n.stand()
            n.net_pose = pose

    def update_avatar(self):
        s, a = self.remote, self.avatar
        if not s or not a:
            return
        a.root.enabled = True
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
        used = ROUND - max(0.0, self.time_left)
        minutes = 18 * 60 + int(used / ROUND * 240)
        left = max(0, int(self.time_left))
        g.clock_text.text = (f"{minutes // 60:02d}:{minutes % 60:02d}　雙人模式 4F　你是{ROLE_NAME[self.role]}　"
                             f"剩 {left // 60}:{left % 60:02d}　抓錯 {self.warnings}/{WARN_LIMIT}")
        jacket, hat, bag = self.outfit
        wear = f"{jacket}外套、{hat}、{bag}書包"
        if self.role == "roommate":
            g.goal_text.text = "目標：混進穿一樣的同學裡，別被抓到（E 坐下／站起來）"
            g.look_text.text = f"你今天穿：{wear}（還有 7 個人跟你一樣）"
        else:
            g.goal_text.text = "目標：找出動作怪怪的那個人，靠近按 E 抓住他"
            g.look_text.text = f"室友穿：{wear}（有 8 個人穿這樣）"

    # ---------- 收訊息 ----------
    def handle(self, m):
        t = m.get("t")
        if t == "s":
            if self.host and m["seat"] != (self.remote_seat if self.remote_seat is not None else -1):
                self.take_seat(self.remote_seat, False)
                self.take_seat(m["seat"] if m["seat"] >= 0 else None, True)
            self.remote_seat = m["seat"] if m["seat"] >= 0 else None
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
            self.warnings = m["n"]
            if self.role == "roommate":
                self.g.show_hint(f"抓人的抓錯人了！（{self.warnings}/{WARN_LIMIT}）", 2.5)
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
        if send:
            self.net.send({"t": "end", "w": winner, "why": why})
        self.cover.enabled = self.cover_text.enabled = False
        g.cleared = True
        g.player.speed = 0
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
        if self.avatar:
            fastops.bulk_destroy(fastops._descendants(self.avatar.root) + [self.avatar.root])
            self.avatar = None
        for e in (self.cover, self.cover_text):
            e.enabled = False
        self.g.librarian.root.enabled = True
        self.g.hide_note()


class DuoPanel:
    """大廳右邊的「雙人連線」面板：開房間／找房間／輸入 IP，連上之後兩台一起開始。"""

    def __init__(self, lobby, game):
        from menu import ACCENT, _button
        from ursina.prefabs.input_field import InputField
        self.lobby, self.game = lobby, game
        self.net = None
        self.my_role = "catcher"
        self.root = Entity(parent=lobby.panel, enabled=False)
        _button(self.root, "開房間（我當抓人的）", -0.02, lambda: self.host("catcher"), x=-0.22, width=0.42)
        _button(self.root, "開房間（我當室友）", -0.02, lambda: self.host("roommate"), x=0.22, width=0.42)
        _button(self.root, "自動找房間加入", -0.1, self.search, x=-0.22, width=0.42)
        self.field = InputField(parent=self.root, default_value="192.168.", character_limit=15,
                                position=(0.12, -0.1), scale=(0.24, 0.065))
        self.field.limit_content_to = "0123456789."
        _button(self.root, "用 IP 加入", -0.1, self.join, x=0.35, width=0.18)
        self.status = Text(parent=self.root, position=(-0.42, -0.17), scale=0.8, color=ACCENT, line_height=1.25)
        self.driver = Entity(update=self.update)

    def open(self):
        self.lobby.show_panel("雙人連線", HELP)
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

    def host(self, role):
        self.my_role = role
        try:
            self.fresh().host()
        except OSError as e:
            self.net = None
            self.status.text = f"開不了房間：{e.strerror or e}"
            return
        self.status.text = (f"房間開好了，你當{ROLE_NAME[role]}。等對方加入……\n"
                            f"對方按「自動找房間」，或輸入這台的 IP：{local_ip()}\n"
                            "（Mac 跳出「允許傳入連線」請按允許）")

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
                self.net.send({"t": "start", "seed": seed, "role": other(self.my_role)})
                self.begin(self.my_role, seed)
            elif t == "found":
                self.status.text = f"找到房間 {m['ip']}，連線中……"
            elif t == "connected":
                self.status.text = "連上了！等房主開始……"
            elif t == "start":
                self.begin(m["role"], m["seed"])
            elif t == "fail":
                self.status.text = m["why"]
                self.net.close()
                self.net = None
            elif t in ("lost", "bye"):
                self.status.text = "對方斷線了。"
                self.net.close()
                self.net = None

    def begin(self, role, seed):
        net, self.net = self.net, None       # 連線交給遊戲，大廳不再收訊息
        self.root.enabled = False
        self.lobby.hide()
        self.game.start_versus(net, role, seed)
