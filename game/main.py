"""總圖不打烊 原型：第一人稱 3D 恐怖解謎。

操作：
  WASD 移動、滑鼠看、Shift 跑、E 互動（讀筆記、開門）、F 開關手電筒、ESC 回大廳

玩法：
  期中考週的凌晨，你在總圖 24 小時夜讀區醒來，室友不見了。
  照真實的總圖一層一層往上找室友留下的線索，最後下到 B1 地下書庫。
  書架間有「東西」——你看著它，它就不動；你一轉頭，它就靠近。
  凌晨 3:00 一到（或被它抓到），一切重來，但你會記得已經讀過的筆記。
"""
import math
import os
import random
from collections import deque
from pathlib import Path

from ursina import (Ursina, Audio, Entity, Text, Texture, Vec2, Vec3, application, camera, color, destroy,
                    held_keys, invoke, raycast, scene, time, window)
from ursina.prefabs.first_person_controller import FirstPersonController
from PIL import Image

import sfx
from events import Scares
from menu import DIFFICULTIES, Lobby
from world import CELL, World, cell_pos

CATCH_DIST = 1.1
MENU_SPOT = (5, 15)     # 大廳背景：1F 入口旁，望向圓形展區
MENU_MONSTER = (17, 15) # 展區正中間站著它

NOTES = {
    "1": "（室友的座位，筆電還開著）便利貼：「我先去找考古題之書了。我用櫃台電腦預約了一個東西，放在自助取書區。」",
    "2": "（字跡潦草）電腦教室最裡面那台我還沒登出……不對，它要密碼。提示寫在螢幕旁：本校在新竹建校的那一年。登入之後樓梯間的門禁就會開。它只在你不看的時候動。",
    "3": "又是三點……我已經第幾次回到這裡了？第三碼我寫在討論室 2 的白板上。",
    "5": "（語言學習區的桌上）「視聽區最裡面那台還在播錄音帶。數清楚嗶了幾聲，那是第一碼。別在它附近戴耳機。」",
    "6": "（被撕下來的筆記本內頁）「清華書房的展示櫃有三碼密碼鎖。第一碼在 3F 的錄音帶裡，第二碼夾在『300 科學類』的書裡，第三碼寫在討論室的白板上。」",
    "4": "（室友的手機，螢幕還亮著）備忘錄：考古題之書 索書號 529.98。在 B 區密集書庫，夾在「520–529」那一櫃和下一櫃之間。轉書架前面的手輪，你站的那道走道就會打開。",
}
# 線索 → (密碼第幾碼, 找到時顯示的文字)
# 樓梯間的門鎖：(樓層, 方向) → (需要的東西, 沒有時的提示)
LOCKS = {
    ("1F", "up"): ("keycard", "樓梯間的門要刷館員門卡。"),
    ("1F", "down"): ("b1", "B1 密集書庫：館員專用，門禁沒有開通。"),
    ("2F", "up"): ("3f", "往 3F 的門禁沒有開。要先登入電腦教室的系統。"),
    ("4F", "up"): ("5f", "往 5F 的樓梯被施工圍籬擋住了。（5F 之後的樓層還在蓋）"),
}
READABLE = {
    "newspaper": "《清華新聞》　日期：明天\n頭條：「資工系學生凌晨於總圖失蹤」\n副標：「同寢室友仍在館內尋找中」",
    "exhibit": "主題展「總圖的夜」\n閉館後，館員每小時巡館一次。\n02:40 那一班，從來沒有人回來簽到。",
}
CLUES = {
    "book": (1, "《物種原始》裡夾著一張便條：\n「第二碼：{d}」\n字跡跟室友的一模一樣。"),
    "whiteboard": (2, "白板角落圈著一個數字：{d}\n旁邊用紅筆寫著：「別回頭。」"),
}

FONT_CANDIDATES = [
    "C:/Windows/Fonts/msjh.ttc", "C:/Windows/Fonts/msjhbd.ttc", "C:/Windows/Fonts/mingliu.ttc",
    "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def wrap(s, width=20):
    """中文沒有空白可以斷行，固定每幾個字換一行。"""
    return "\n".join(s[i:i + width] for i in range(0, len(s), width))


def find_font():
    return next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)


def setup_font(path):
    if path:
        # Ursina 只會在字型資料夾裡用檔名找字型，所以把系統字型資料夾設成字型資料夾
        application.fonts_folder = Path(path).parent
        Text.default_font = Path(path).name


class Game:
    def __init__(self, font_path):
        self.read_notes = set()      # 跨迴圈保留：玩家記得的筆記
        self.found = set()           # 跨迴圈保留：已經找到的密碼位數
        self.items = set()           # 跨迴圈保留：門卡、門禁權限
        self.locker_no = 1
        self.entry = None            # 輸入密碼的畫面
        self.arrival = None
        self.code = "000"
        self.loop = 1
        self.cfg = DIFFICULTIES["普通"]  # 怪物速度、迴圈秒數、手電筒照多遠
        self.difficulty = "普通"
        self.state = "menu"
        self.session = 0             # 每開一局加一，舊的延遲事件（例如被抓後重來）就不會跑到新的一局
        self.font_path = font_path
        self.world = None
        self.load_floor("1F")
        self.player = FirstPersonController(position=self.world.start + Vec3(0, 0.1, 0), speed=4)
        self.player.cursor.visible = False
        self.player.gravity = 1
        self.monster = self.make_monster()
        self.setup_lights()
        self.dust = self.make_dust()
        self.setup_audio()
        self.clock_text = Text(position=(-0.85, 0.47), scale=1.2, color=color.light_gray)
        self.goal_text = Text(position=(-0.85, 0.425), scale=1.0, color=color.rgb32(230, 200, 120))
        self.hint = Text(position=(-0.3, -0.38), scale=1.1, color=color.white)
        self.note_text = Text(position=(-0.6, 0.1), scale=1.3, color=color.rgb32(240, 230, 200))
        self.note_bg = Entity(parent=camera.ui, model="quad", color=color.rgba32(0, 0, 0, 200),
                              scale=(1.3, 0.4), position=(-0.02, 0.04), z=0.5, enabled=False)
        self.flash = Entity(parent=camera.ui, model="quad", scale=(2, 1), color=color.rgba32(0, 0, 0, 0), z=-1)
        self.entry_bg = Entity(parent=camera.ui, model="quad", color=color.rgba32(10, 20, 30, 235),
                               scale=(0.8, 0.45), z=0.4, enabled=False)
        self.entry_title = Text(position=(0, 0.16), origin=(0, 0), scale=1.2, color=color.rgb32(150, 200, 240))
        self.entry_text = Text(position=(0, -0.03), origin=(0, 0), scale=2.0, color=color.white)
        self.dead = False
        self.cleared = False
        self.tape_playing = False
        self.noise = 0.0             # 聲音條：跑步會累積，滿了它就聽到你
        self.alert = 0.0             # 它聽到你之後加速的剩餘秒數
        self.hidden = False          # 躲在桌子底下
        self.wander = None           # 你躲起來時，它亂晃的目標
        self.battery = 100.0
        self.batteries = []          # 地上的電池
        self.noise_bg = Entity(parent=camera.ui, model="quad", origin=(-0.5, 0), position=(-0.85, -0.44),
                               scale=(0.3, 0.018), color=color.rgba32(255, 255, 255, 40))
        self.noise_bar = Entity(parent=camera.ui, model="quad", origin=(-0.5, 0), position=(-0.85, -0.44),
                                scale=(0, 0.018), color=color.rgb32(200, 190, 170))
        self.noise_label = Text(position=(-0.85, -0.41), scale=0.8, color=color.light_gray)
        self.scares = Scares(self)
        self.bob = 0.0
        self.step_timer = 0.0
        self.beat_timer = 0.0
        self.time_left = 0

    # ---------- 樓層 ----------
    def load_floor(self, name, came="up"):
        """拆掉目前的樓層，蓋出新的一層。每層是 world.FLOORS 裡的一張格子圖。
        came 是玩家怎麼來的：往上走來的就出現在新樓層的「往下」樓梯口，反之亦然。"""
        if self.world:
            self.world.unload()
        self.world = World(self.font_path, name)
        self.world.set_code(self.code)
        self.notes = self.world.notes
        self.solids = self.world.solids
        stair = self.world.stairs.get("down" if came == "up" else "up")
        if came == "start" or not stair:
            self.arrival, self.arrival_rot = self.world.start, 90
        else:   # 出現在樓梯口，面向室內
            d = stair["pos"] - stair["door"].position
            self.arrival, self.arrival_rot = stair["pos"], math.degrees(math.atan2(d.x, d.z))
        self.refresh_paths()
        if hasattr(self, "vignette"):
            self.apply_flashlight()   # 霧的參數要重新套到新蓋的東西上

    def refresh_paths(self):
        self.monster_walkable = self.world.walkable - self.world.spec["safe"]   # 夜讀區：它進不來

    def take_stairs(self, direction):
        """走進樓梯間：畫面全黑、換樓層。"""
        stair = self.world.stairs[direction]
        lock = LOCKS.get((self.world.floor, direction))
        if lock and lock[0] not in self.items:
            self.show_hint(lock[1], 3)
            return
        if not stair["target"]:
            self.show_hint("這裡沒有路了。", 2)
            return
        self.dead = True   # 換樓層時暫停怪物和時鐘
        self.flash.color = color.rgba32(0, 0, 0, 255)
        self.goal_text.text = ""
        self.play("step")

        def arrive():
            self.load_floor(stair["target"], came=direction)
            self.reset_loop(first=True)
            self.later(self.flash_fade, 0.3)
        self.later(arrive, 0.8)

    # ---------- 大廳與開局 ----------
    def start(self, cfg, name):
        self.session += 1
        self.cfg, self.difficulty = cfg, name
        self.read_notes.clear()
        self.found.clear()
        self.items.clear()
        self.code = "".join(random.choice("123456789") for _ in range(3))   # 每局密碼都不同
        self.locker_no = random.randint(1, 6)
        self.loop = 1
        self.cleared = False
        self.tape_playing = False
        self.load_floor("1F", came="start")   # 重蓋一次，書架都回到原狀
        self.hide_note()
        self.flash_fade()
        self.state = "play"
        self.noise_bg.enabled = True
        self.player.enabled = True
        self.reset_loop(first=True)

    def to_lobby(self):
        self.session += 1
        self.state = "menu"
        self.dead = False
        for t in (self.clock_text, self.goal_text, self.hint, self.note_text):
            t.text = ""
        self.note_bg.enabled = False
        self.flash_fade()
        self.close_entry()
        self.scares.reset()
        for b in self.batteries:
            destroy(b)
        self.batteries = []
        self.noise, self.hidden = 0.0, False
        self.noise_bar.scale_x, self.noise_label.text = 0, ""
        self.noise_bg.enabled = False
        if self.world.floor != "1F":
            self.load_floor("1F", came="start")
        self.flashlight_on = True
        self.in_safe_zone = False
        self.apply_flashlight()
        self.player.position = cell_pos(*MENU_SPOT)
        self.player.enabled = False      # 停用時 Ursina 會把鏡頭交還給場景，滑鼠也會解鎖
        self.monster.position = cell_pos(*MENU_MONSTER)
        self.monster.look_at_2d(self.player.position, "y")
        lobby.show()

    def aim_menu_camera(self, forward, sway):
        camera.position = cell_pos(*MENU_SPOT) + Vec3(forward, 1.6, 0)
        camera.rotation = (4, 90 + sway, 0)

    def later(self, fn, delay):
        """延遲執行，但如果玩家已經回大廳或重開一局就取消。"""
        session = self.session
        invoke(lambda: fn() if session == self.session else None, delay=delay)

    # ---------- 場景 ----------
    def make_monster(self):
        """又高又瘦、駝背、長髮蓋住臉的「東西」。"""
        m = Entity(position=self.world.monster_start)
        skin, cloth, hair = color.rgb32(200, 196, 186), color.rgb32(18, 18, 22), color.rgb32(8, 8, 10)
        body = Entity(parent=m, rotation_x=12)
        Entity(parent=body, model="cube", position=(0, 1.55, 0), scale=(0.42, 1.0, 0.24), color=cloth)
        for x in (-0.12, 0.12):
            Entity(parent=m, model="cube", position=(x, 0.55, 0), scale=(0.1, 1.1, 0.1), color=cloth)
        self.monster_arms = []
        for x in (-0.28, 0.28):
            arm = Entity(parent=body, position=(x, 2.0, 0))
            Entity(parent=arm, model="cube", position=(0, -0.65, 0), scale=(0.07, 1.3, 0.07), color=skin)
            for f in (-0.03, 0.0, 0.03):   # 細長的手指
                Entity(parent=arm, model="cube", position=(f, -1.42, 0.02), scale=(0.015, 0.22, 0.015), color=skin)
            self.monster_arms.append(arm)
        self.monster_head = Entity(parent=body, position=(0, 2.25, 0.05))
        Entity(parent=self.monster_head, model="sphere", scale=(0.3, 0.36, 0.3), color=skin)
        Entity(parent=self.monster_head, model="cube", position=(0, -0.15, -0.06), scale=(0.34, 0.75, 0.3), color=hair)
        Entity(parent=self.monster_head, model="cube", position=(0.05, -0.25, 0.15), scale=(0.24, 0.6, 0.03), color=hair)
        for x in (-0.06, 0.06):   # 頭髮縫隙裡的眼睛
            Entity(parent=self.monster_head, model="sphere", position=(x, 0.03, 0.16), scale=0.035,
                   color=color.rgb32(255, 250, 230))
        return m

    def make_dust(self):
        """手電筒光裡飄的灰塵。"""
        rng = random.Random(7)
        root = Entity()
        for _ in range(70):
            Entity(parent=root, model="quad", billboard=True, scale=rng.uniform(0.006, 0.014),
                   position=(rng.uniform(-4, 4), rng.uniform(0.3, 3), rng.uniform(-4, 4)),
                   color=color.rgba32(230, 225, 210, rng.randint(30, 80)))
        return root

    def setup_lights(self):
        """手電筒效果：黑色濃霧當作黑暗，再疊一張中間透明、四周全黑的暈影。
        不用即時光源，任何顯示卡都跑得動。"""
        scene.fog_color = color.black
        size = 512
        img = Image.new("RGBA", (size, size))
        px = img.load()
        for y in range(size):
            for x in range(size):
                d = math.hypot(x - size / 2, y - size / 2) / (size / 2)
                a = min(1.0, max(0.0, (d - 0.3) / 0.45))
                px[x, y] = (0, 0, 0, int(255 * a ** 1.4))
        self.vignette = Entity(parent=camera.ui, model="quad", texture=Texture(img),
                               scale=(window.aspect_ratio * 1.15, 1.15), z=1)
        self.flashlight_on = True
        self.in_safe_zone = True
        self.apply_flashlight()

    def apply_flashlight(self):
        scene.fog_color = color.black   # 新蓋的樓層也要拿到霧的顏色
        if self.in_safe_zone:          # 夜讀區燈火通明，看得比較遠
            scene.fog_density = (4.0, 22.0)
        else:
            scene.fog_density = (1.0, 13.0) if self.flashlight_on else (0.5, 4.0)
        k = 0.7 if getattr(self, "hidden", False) else 1.15 if self.flashlight_on else 0.85   # 躲在桌下視野變窄
        self.vignette.scale = (window.aspect_ratio * k, k)

    def setup_audio(self):
        self.sounds = {}
        try:
            paths = sfx.generate()
            self.sounds = {
                "hum": Audio(paths["hum"], loop=True, autoplay=True, volume=0.25),
                "heartbeat": Audio(paths["heartbeat"], autoplay=False),
                "step": Audio(paths["step"], autoplay=False, volume=0.35),
                "sting": Audio(paths["sting"], autoplay=False, volume=0.8),
                "page": Audio(paths["page"], autoplay=False, volume=0.6),
                "rumble": Audio(paths["rumble"], autoplay=False, volume=0.7),
                "beep": Audio(paths["beep"], autoplay=False, volume=0.6),
                "chime": Audio(paths["chime"], autoplay=False, volume=0.7),
                "ring": Audio(paths["ring"], autoplay=False, volume=0.5),
                "thud": Audio(paths["thud"], autoplay=False, volume=0.8),
            }
        except Exception as e:   # 沒有音效卡也能玩
            print("音效載入失敗：", e)

    def play(self, name, volume=None):
        s = self.sounds.get(name)
        if s:
            if volume is not None:
                s.volume = volume
            s.play()

    # ---------- 迴圈 ----------
    def reset_loop(self, first=False):
        if not first:
            self.loop += 1
        self.player.position = self.arrival + Vec3(0, 0.1, 0)
        self.player.rotation_y = self.arrival_rot
        self.monster.position = self.world.monster_start
        self.time_left = self.cfg["seconds"]
        self.dead = False
        self.battery, self.noise, self.alert, self.hidden, self.wander = 100.0, 0.0, 0.0, False, None
        self.spawn_batteries()
        self.scares.reset()
        self.note_text.text = ""
        floor = self.world.floor
        if not first:
            msg = f"……又是 02:40，你還在 {floor}。第 {self.loop} 次了。你記得找到過的東西。"
        else:
            msg = {"1F": "夜讀區的燈還亮著。室友的位子空了，筆電還開著。",
                   "2F": "2F。期刊架之間很安靜，安靜得不太對勁。",
                   "3F": "3F。小舞台上的鋼琴蓋是開的。剛剛好像有人在彈。",
                   "4F": "4F。一整層的中文書。故事牆上的老照片都在看你。",
                   "B1": "身後的門自己鎖上了。這裡比樓上更冷。"}.get(floor, f"{floor}。")
        self.show_hint(wrap(msg, 24), 6)

    def show_hint(self, msg, seconds=3):
        self.hint.text = msg

        def clear():
            if self.hint.text == msg:   # 只清掉自己這則，後來的提示不要被提早清掉
                self.hint.text = ""
        invoke(clear, delay=seconds)

    # ---------- 怪物 ----------
    def player_sees(self, target):
        """目標在視野內、而且中間沒有牆或書架擋住，就算『被看著』。"""
        eye = camera.world_position
        to = target + Vec3(0, 1.6, 0) - eye
        dist = to.length()
        if dist < 0.01:
            return True
        if dist > (self.cfg["sight"] if self.flashlight_on else 3):   # 在黑暗裡看不到它，它就會動
            return False
        fwd = camera.forward
        cos_angle = (to.x * fwd.x + to.y * fwd.y + to.z * fwd.z) / dist
        if cos_angle < math.cos(math.radians(42)):
            return False
        hit = raycast(eye, to.normalized(), distance=dist, ignore=(self.player,), traverse_target=scene)
        return not (hit.hit and hit.entity in self.solids)

    def update_monster(self):
        if self.player_sees(self.monster.world_position):
            return False
        goal = self.player.position
        if self.hidden:   # 找不到你，就在這層樓亂晃
            if self.wander is None or (self.wander - self.monster.position).length() < 0.5:
                self.wander = cell_pos(*random.choice(sorted(self.monster_walkable)))
            goal = self.wander
        else:
            to = self.player.position - self.monster.position
            to.y = 0
            if to.length() < CATCH_DIST:
                self.caught()
                return False
        target = self.next_step_toward(self.monster.position, goal)
        move = target - self.monster.position
        move.y = 0
        step = self.cfg["speed"] * (1.8 if self.alert > 0 else 1.0) * time.dt
        if move.length() <= step:
            self.monster.position = Vec3(target.x, 0, target.z)
        else:
            self.monster.position += move.normalized() * step
        self.monster.look_at_2d(goal, "y")
        # 沒被看著的時候會抽搐，被看到就定格在奇怪的姿勢
        self.monster_head.rotation_z = random.uniform(-25, 25)
        for arm in self.monster_arms:
            arm.rotation_x = random.uniform(-20, 20)
        return True

    def to_cell(self, pos):
        return (round(pos.x / CELL), round(-pos.z / CELL))

    def next_step_toward(self, start, goal):
        """在走道格子上做 BFS，回傳往玩家方向的下一格中心點。"""
        s, g = self.to_cell(start), self.to_cell(goal)
        if g not in self.monster_walkable:
            return Vec3(start)
        if s == g:
            return Vec3(goal.x, 0, goal.z)
        prev = {s: None}
        queue = deque([s])
        while queue:
            cur = queue.popleft()
            if cur == g:
                break
            c, r = cur
            for nxt in ((c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1)):
                if nxt in self.monster_walkable and nxt not in prev:
                    prev[nxt] = cur
                    queue.append(nxt)
        if g not in prev:
            return Vec3(start)
        cell = g
        while prev[cell] != s and prev[cell] is not None:
            cell = prev[cell]
        return cell_pos(*cell)

    def caught(self):
        if self.dead:
            return
        self.dead = True
        self.play("sting")
        self.flash.color = color.rgba32(150, 0, 0, 220)
        self.show_hint("它抓到你了。", 2)
        self.later(self.flash_fade, 1.5)
        self.later(self.reset_loop, 1.5)

    def flash_fade(self):
        self.flash.color = color.rgba32(0, 0, 0, 0)

    # ---------- 氣氛 ----------
    def update_lights(self, monster_moving):
        for light in self.world.lights:
            panel, pool, state = light
            if state == "dead":
                continue
            near = monster_moving and (panel.position - self.monster.position).length() < 7
            if state == "flicker" or near:
                World.set_light(light, random.random() > (0.5 if near else 0.25))
            elif not pool.enabled:
                World.set_light(light, True)

    def update_dust(self):
        p = self.player.position
        for d in self.dust.children:
            d.y += math.sin(time.time() * 0.7 + d.x) * 0.002 - 0.001
            d.x += 0.002
            for axis in ("x", "z"):   # 灰塵跟著玩家，超出範圍就從另一邊繞回來
                off = getattr(d, axis) - getattr(p, axis)
                if abs(off) > 4:
                    setattr(d, axis, getattr(p, axis) + (off + 4) % 8 - 4)
            if d.y < 0.2:
                d.y = 3

    def update_body(self):
        sneaking = held_keys["control"] or held_keys["left control"]
        moving = any(held_keys[k] for k in "wasd") and not self.hidden
        if moving:
            speed = 1.6 if held_keys["shift"] else 1.0
            self.bob += time.dt * 9 * speed
            self.step_timer -= time.dt * speed
            if self.step_timer <= 0:
                self.step_timer = 0.48
                self.play("step", volume=0.08 if sneaking else 0.6 if held_keys["shift"] else 0.35)
        eye = 0.6 if self.hidden else 1.2 if sneaking else 1.7
        self.player.camera_pivot.y += (eye + math.sin(self.bob) * 0.04 - self.player.camera_pivot.y) * min(1, time.dt * 10)

        dist = (self.monster.position - self.player.position).length()
        self.beat_timer -= time.dt
        if dist < 12 and self.beat_timer <= 0:
            self.beat_timer = 0.45 + dist / 12 * 0.8
            self.play("heartbeat", volume=max(0.15, 1 - dist / 12))

    # ---------- 互動 ----------
    def show_note(self, text):
        self.play("page")
        self.note_text.text = text
        self.note_bg.enabled = True
        self.later(self.hide_note, 7)

    def near(self, pos, dist):
        d = pos - self.player.position
        d.y = 0
        return d.length() < dist

    def code_hint(self):
        return " ".join(self.code[i] if i in self.found else "_" for i in range(3))

    def interact(self):
        for key, note in self.notes.items():
            if self.near(note.position, 1.8):
                self.read_notes.add(key)
                self.show_note(wrap(NOTES[key]))
                return
        for name, pos in self.world.clues.items():
            if self.near(pos, 1.6):
                index, text = CLUES[name]
                self.found.add(index)
                self.show_note(text.format(d=self.code[index]))
                return
        spots = [(i, (i["pos"] - self.player.position).length()) for i in self.world.interactables]
        spots = [x for x in spots if self.near(x[0]["pos"], 1.6)]
        if spots:
            self.use(min(spots, key=lambda x: x[1])[0])
            return
        book = self.world.exam_book
        if book and self.near(book.world_position, 2.2):
            self.ending()
            return
        bank, aisle = self.world.bank_at(self.player.position)
        if bank:
            if bank["aisle"] == aisle:
                self.show_hint("這道走道已經是開的。", 2)
            else:
                self.world.open_aisle(bank, aisle)
                self.refresh_paths()
                self.play("rumble")
                self.show_hint("手輪很重……書架轟隆隆地移開了。", 3)
            return
        for direction, stair in self.world.stairs.items():
            if self.near(stair["pos"], 1.6):
                self.take_stairs(direction)
                return

    def use(self, thing):
        """各樓層設施的互動：讀東西、查電腦、開取書櫃、登入電腦教室。"""
        kind, data = thing["kind"], thing.get("data")
        if kind == "read":
            text = data.split(":", 1)[1] if data.startswith("history:") else READABLE[data]
            self.show_note(text)
        elif kind == "counter_pc":
            self.items.add("locker_known")
            self.show_note(f"預約取書通知\n讀者：陳○○　書名：（空白）\n取書櫃：A{self.locker_no:02d}　狀態：待取件")
        elif kind == "locker":
            if data != self.locker_no:
                self.show_hint(f"A{data:02d}：空的。", 2)
            elif "keycard" in self.items:
                self.show_hint("櫃子已經空了。", 2)
            else:
                self.items.add("keycard")
                self.play("page")
                self.show_note("櫃子裡沒有書，只有一張館員門卡。\n卡套上貼著便利貼：「樓梯間 → 2F 電腦教室」")
        elif kind == "lab_pc":
            if "3f" in self.items:
                self.show_note("已登入。樓梯間門禁：已開通。")
            else:
                self.open_entry("電腦教室　登入", "密碼提示：本校在新竹建校的那一年", 4, self.lab_login)
        elif kind == "tape":
            self.play_tape()
        elif kind == "case":
            if "b1" in self.items:
                self.show_note("展示櫃已經開了。")
            else:
                self.open_entry("清華書房　展示櫃", f"三碼密碼鎖　你記得的：{self.code_hint()}", 3, self.case_open)

    def lab_login(self, code):
        if code != "1956":
            self.show_hint("密碼錯誤。", 2)
            return
        self.items.add("3f")
        self.show_note("登入成功。最後一筆查詢：\n《考古題之書》索書號 529.98　館藏地：B1 密集書庫\n系統訊息：樓梯間 3F 門禁已開通。")

    def play_tape(self):
        """3F 視聽座位的錄音帶：嗶幾聲就是第一碼。"""
        if self.tape_playing:
            return
        self.tape_playing = True
        n = int(self.code[0])
        self.show_hint("（喀。錄音帶開始轉）", 1.2)
        for i in range(n):
            self.later(lambda k=i + 1: (self.play("beep"), self.show_hint("嗶 " * k, 1.5)), 1.5 + i * 0.6)

        def done():
            self.tape_playing = False
            self.found.add(0)
            self.show_note("錄音帶最後是室友的聲音，很小聲：\n「……數到幾了？那就是第一碼。\n上 4F，清華書房。」")
        self.later(done, 2.5 + n * 0.6)

    def case_open(self, code):
        if code != self.code:
            self.show_hint("鎖沒有開。", 2)
            return
        self.items.add("b1")
        self.play("page")
        self.show_note("展示櫃裡的推薦書全被翻到同一頁：\n「B1 密集書庫　館員通行證」\n通行證就夾在書裡。B1 門禁開了。")

    # ---------- 輸入密碼的畫面 ----------
    def open_entry(self, title, hint, length, on_submit):
        self.entry = dict(buf="", length=length, on_submit=on_submit)
        self.hide_note()
        self.entry_bg.enabled = True
        self.entry_title.text = f"{title}\n{hint}"
        self.player.mouse_sensitivity = Vec2(0, 0)
        self.refresh_entry()

    def refresh_entry(self):
        e = self.entry
        shown = " ".join(e["buf"].ljust(e["length"], "_"))
        self.entry_text.text = f"{shown}\n\n數字鍵輸入　Enter 確定　Esc 取消"

    def entry_key(self, key):
        e = self.entry
        if key in "0123456789" and len(key) == 1 and len(e["buf"]) < e["length"]:
            e["buf"] += key
        elif key == "backspace":
            e["buf"] = e["buf"][:-1]
        elif key == "enter":
            buf, fn = e["buf"], e["on_submit"]
            self.close_entry()
            fn(buf)
            return
        elif key == "escape":
            self.close_entry()
            return
        self.refresh_entry()

    def close_entry(self):
        self.entry = None
        self.entry_bg.enabled = False
        self.entry_title.text = ""
        self.entry_text.text = ""
        self.player.mouse_sensitivity = Vec2(40, 40)

    def goal(self):
        """左上角的目標：依樓層和已經拿到的東西決定下一步。"""
        floor, items, notes = self.world.floor, self.items, self.read_notes
        if "b1" in items and floor != "B1":
            return "B1 門禁開了。從右下角的樓梯間一路往下到 B1"
        if floor == "1F":
            if "keycard" in items:
                return "用門卡打開右下角的樓梯間，上 2F"
            if "locker_known" in items:
                return f"到最裡面（北邊）的自助取書區，打開 A{self.locker_no:02d} 櫃"
            if "1" in notes:
                return "到左邊的聯合櫃臺，查電腦上的預約"
            return "看看室友在夜讀區的座位（書車上有東西）"
        if floor == "2F":
            if "3f" in items:
                return "門禁開了。從樓梯間上 3F"
            if "2" in notes:
                return "登入電腦教室最裡面那台電腦（密碼提示在校史展示區）"
            return "找找室友在 2F 留下的東西"
        if floor == "3F":
            if 0 in self.found:
                return "記住錄音帶的嗶聲數，上 4F 找清華書房"
            if "5" in notes:
                return "到視聽區找還在播的那台（螢幕亮著），按 E 聽錄音帶"
            return "找找室友在 3F 留下的東西（語言學習區）"
        if floor == "4F":
            if "6" not in notes:
                return "找找室友在 4F 留下的東西"
            return f"湊齊三碼，打開清華書房的展示櫃　密碼：{self.code_hint()}"
        if floor == "B1":
            return ("在 B 區密集書庫找到《考古題之書》，在書架前按 E 轉手輪"
                    if "4" in notes else "入口桌上有東西在發光……")
        if len(self.found) < 3:
            return f"找室友的筆記，照上面的提示找出密碼　密碼：{self.code_hint()}"
        return f"密碼是 {self.code}"

    def ending(self):
        self.cleared = True
        self.goal_text.text = ""
        self.player.enabled = False
        self.play("page")
        self.note_bg.enabled = True
        self.note_text.text = (f"《考古題之書》\n扉頁的借閱紀錄只有兩行：陳○○，還有……你的名字。\n"
                               f"借閱日期是明天。\n\n第一章　完（{self.difficulty}・迴圈 {self.loop} 次）\n按 Enter 回到大廳")

    def hide_note(self):
        self.note_text.text = ""
        self.note_bg.enabled = False

    def update(self):
        self.update_dust()
        if self.state != "play" or self.cleared or self.dead:
            return
        sneaking = held_keys["control"] or held_keys["left control"]
        self.player.speed = (0 if self.entry or self.hidden else 6.5 if held_keys["shift"]
                             else 1.8 if sneaking else 3.5)
        self.time_left -= time.dt
        total = self.cfg["seconds"]
        game_min = 40 + (total - self.time_left) / total * 20
        self.clock_text.text = (f"02:{int(game_min):02d}　第 {self.loop} 輪　"
                                f"{self.difficulty}　電池 {int(self.battery)}%")
        self.goal_text.text = "目標：" + self.goal()
        if self.time_left <= 0:
            self.flash.color = color.rgba32(0, 0, 0, 255)
            self.dead = True
            self.show_hint("03:00", 2)
            self.later(self.flash_fade, 1.5)
            self.later(self.reset_loop, 1.5)
            return
        safe = self.to_cell(self.player.position) in self.world.spec["safe"]
        if safe != self.in_safe_zone:
            self.in_safe_zone = safe
            self.apply_flashlight()
        self.update_noise(sneaking)
        self.update_battery()
        moving = self.update_monster()
        if self.scares.blackout <= 0:
            self.update_lights(moving)
        self.scares.update()
        self.update_body()

    # ---------- 聲音、躲藏、電池 ----------
    def update_noise(self, sneaking):
        walking = any(held_keys[k] for k in "wasd") and not self.hidden and not self.entry
        rate = (0.0 if sneaking else 0.55 if held_keys["shift"] else 0.05) if walking else -0.3
        self.noise = min(1.0, max(0.0, self.noise + rate * time.dt))
        self.alert = max(0.0, self.alert - time.dt)
        if self.noise >= 1 and self.alert <= 0 and not self.in_safe_zone:
            self.alert, self.noise = 6.0, 0.5
            self.play("sting", volume=0.25)
            self.show_hint("它聽到你了。", 2)
        self.noise_bar.scale_x = 0.3 * self.noise
        self.noise_bar.color = color.rgb32(200, 40, 40) if self.alert > 0 else color.rgb32(200, 190, 170)
        self.noise_label.text = "它聽到了！" if self.alert > 0 else "躲起來中" if self.hidden else "聲音"

    def update_battery(self):
        if self.flashlight_on and not self.in_safe_zone:
            self.battery = max(0.0, self.battery - self.cfg["drain"] * time.dt)
            if self.battery <= 0:
                self.flashlight_on = False
                self.apply_flashlight()
                self.show_hint("手電筒沒電了。找找地上有沒有電池。", 3)
        for b in list(self.batteries):
            if self.near(b.position, 1.2):
                self.batteries.remove(b)
                destroy(b)
                self.battery = min(100.0, self.battery + 45)
                self.play("page")
                self.show_hint(f"撿到電池。電量 {int(self.battery)}%", 2)

    def spawn_batteries(self):
        for b in self.batteries:
            destroy(b)
        self.batteries = []
        cells = sorted(self.world.walkable - self.world.spec["safe"])
        stairs = [s["pos"] for s in self.world.stairs.values()]
        cells = [c for c in cells if all((cell_pos(*c) - p).length() > 6 for p in stairs)]
        for c in random.sample(cells, min(3, len(cells))):
            b = Entity(position=cell_pos(*c) + Vec3(random.uniform(-0.5, 0.5), 0, random.uniform(-0.5, 0.5)))
            Entity(parent=b, model="cube", position=(0, 0.06, 0), scale=(0.12, 0.12, 0.3), color=color.rgb32(40, 40, 40))
            Entity(parent=b, model="cube", position=(0, 0.06, 0.12), scale=(0.125, 0.125, 0.08),
                   color=color.rgb32(220, 160, 40))
            Entity(parent=b, model="quad", rotation_x=90, position=(0, 0.01, 0), scale=0.8, texture=self.world.t["glow"],
                   color=color.rgba32(255, 200, 90, 70))
            self.batteries.append(b)

    def toggle_hide(self):
        if self.hidden:
            self.hidden = False
            self.apply_flashlight()
            self.show_hint("你從桌子底下爬出來。", 2)
            return
        spot = min(self.world.hides, key=lambda p: (p - self.player.position).length(), default=None)
        if spot is None or not self.near(spot, 1.9):
            self.show_hint("附近沒有可以躲的桌子。", 2)
            return
        self.hidden = True
        self.wander = None
        self.apply_flashlight()
        self.show_hint("你縮到桌子底下。它找不到你，但時間還在走。（C 出來）", 3)


app = Ursina(title="總圖不打烊 原型", borderless=False, development_mode=False)
font_path = find_font()
setup_font(font_path)
window.color = color.black
game = Game(font_path)
lobby = Lobby(on_start=game.start, on_quit=application.quit, aim_camera=game.aim_menu_camera)
game.to_lobby()


def handle_input(key):
    if game.state == "menu":
        if key == "escape":
            lobby.hide_panel()
        return
    if game.entry:
        game.entry_key(key)
        return
    if key == "escape" or (game.cleared and key == "enter"):
        game.to_lobby()
    elif key == "e" and not game.cleared:
        game.interact()
    elif key == "f":
        if game.battery <= 0 and not game.flashlight_on:
            game.show_hint("手電筒沒電了。", 2)
            return
        game.flashlight_on = not game.flashlight_on
        game.apply_flashlight()
    elif key == "c" and not game.cleared:
        game.toggle_hide()


# 用一個空 Entity 掛每幀更新與按鍵處理，不依賴 __main__ 裡的全域函式
driver = Entity(update=game.update, input=handle_input)


if __name__ == "__main__":
    app.run()
