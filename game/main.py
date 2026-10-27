"""總圖不打烊 原型：第一人稱 3D 恐怖解謎。

操作：
  WASD 移動、滑鼠看、Shift 跑、E 互動（讀筆記、開門）、F 開關手電筒、ESC 回大廳

玩法：
  期中考週的凌晨，你在總圖 24 小時夜讀區醒來，室友不見了。
  通往館藏區的門沒鎖。在書架間找出筆記，拼出地下書庫的密碼。
  書架間有「東西」——你看著它，它就不動；你一轉頭，它就靠近。
  凌晨 3:00 一到（或被它抓到），一切重來，但你會記得已經讀過的筆記。
"""
import math
import os
import random
from collections import deque
from pathlib import Path

from ursina import (Ursina, Audio, Entity, Text, Texture, Vec3, application, camera, color,
                    held_keys, invoke, raycast, scene, time, window)
from ursina.prefabs.first_person_controller import FirstPersonController
from PIL import Image

import sfx
from menu import DIFFICULTIES, Lobby
from world import CELL, World, cell_pos

CATCH_DIST = 1.1
MENU_SPOT = (1, 9)      # 大廳背景：書庫走道的一端
MENU_MONSTER = (7, 9)   # 走道另一頭站著它

NOTES = {
    "1": "（字跡潦草）考古題之書在 B1 地下書庫，門鎖是三碼。第一碼我夾在「300 自然科學」那排，一本凸出來的書裡。",
    "2": "服務台的電腦我還沒登出。查我的借閱紀錄，第二碼在上面。它只在你不看的時候動，別背對它。",
    "3": "又是三點……我已經第幾次回到這裡了？第三碼我寫在討論室 2 的白板上。",
    "4": "（室友的手機，螢幕還亮著）備忘錄：考古題之書 索書號 529.98。在 B 區密集書庫，夾在「520–529」那一櫃和下一櫃之間。轉書架前面的手輪，你站的那道走道就會打開。",
}
# 線索 → (密碼第幾碼, 找到時顯示的文字)
CLUES = {
    "book": (0, "《物種原始》裡夾著一張便條：\n「第一碼：{d}」\n字跡跟室友的一模一樣。"),
    "computer": (1, "借閱紀錄　陳○○\n《考古題之書》　已歸還（B1 地下書庫）\n歸還時間：03:00　備註：第二碼 {d}"),
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
        self.dead = False
        self.cleared = False
        self.bob = 0.0
        self.step_timer = 0.0
        self.beat_timer = 0.0
        self.time_left = 0

    # ---------- 樓層 ----------
    def load_floor(self, name):
        """拆掉目前的樓層，蓋出新的一層。每層是 world.FLOORS 裡的一張格子圖。"""
        if self.world:
            self.world.unload()
        self.world = World(self.font_path, name)
        self.world.set_code(self.code)
        self.notes = self.world.notes
        self.door = self.world.door
        self.solids = self.world.solids
        self.refresh_paths()
        if hasattr(self, "vignette"):
            self.apply_flashlight()   # 霧的參數要重新套到新蓋的東西上

    def refresh_paths(self):
        self.monster_walkable = self.world.walkable - self.world.spec["safe"]   # 夜讀區：它進不來

    def go_down(self):
        """1F 的門打開後：畫面全黑、換到 B1。"""
        self.dead = True   # 換樓層時暫停怪物和時鐘
        self.flash.color = color.rgba32(0, 0, 0, 255)
        self.goal_text.text = ""

        def arrive():
            self.load_floor("B1")
            self.reset_loop(first=True)
            self.later(self.flash_fade, 0.3)
        self.later(arrive, 1.6)

    # ---------- 大廳與開局 ----------
    def start(self, cfg, name):
        self.session += 1
        self.cfg, self.difficulty = cfg, name
        self.read_notes.clear()
        self.found.clear()
        self.code = "".join(random.choice("0123456789") for _ in range(3))   # 每局密碼都不同
        self.loop = 1
        self.cleared = False
        self.load_floor("1F")   # 重蓋一次，門、書架都回到原狀
        self.hide_note()
        self.flash_fade()
        self.state = "play"
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
        if self.world.floor != "1F":
            self.load_floor("1F")
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
        k = 1.15 if self.flashlight_on else 0.85
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
        self.player.position = self.world.start + Vec3(0, 0.1, 0)
        self.player.rotation_y = 90
        self.monster.position = self.world.monster_start
        self.time_left = self.cfg["seconds"]
        self.dead = False
        self.note_text.text = ""
        if self.world.floor == "B1":
            msg = ("身後的門自己鎖上了。這裡比樓上更冷。" if first
                   else f"……又是 02:40，你還在 B1。第 {self.loop} 次了。")
        else:
            msg = ("室友不見了。找到他留下的 3 張筆記，拼出 B1 地下書庫的密碼。" if first
                   else f"……又是 02:40。第 {self.loop} 次了。你記得讀過的筆記。")
        self.show_hint(wrap(msg, 24), 6)

    def show_hint(self, msg, seconds=3):
        self.hint.text = msg
        invoke(setattr, self.hint, "text", "", delay=seconds)

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
        to = self.player.position - self.monster.position
        to.y = 0
        if to.length() < CATCH_DIST:
            self.caught()
            return False
        target = self.next_step_toward(self.monster.position, self.player.position)
        move = target - self.monster.position
        move.y = 0
        step = self.cfg["speed"] * time.dt
        if move.length() <= step:
            self.monster.position = Vec3(target.x, 0, target.z)
        else:
            self.monster.position += move.normalized() * step
        self.monster.look_at_2d(self.player.position, "y")
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
        moving = any(held_keys[k] for k in "wasd")
        if moving:
            speed = 1.6 if held_keys["shift"] else 1.0
            self.bob += time.dt * 9 * speed
            self.step_timer -= time.dt * speed
            if self.step_timer <= 0:
                self.step_timer = 0.48
                self.play("step")
        self.player.camera_pivot.y = 1.7 + math.sin(self.bob) * 0.04

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
                if len(self.found) == 3:
                    self.world.keypad_light.color = color.lime
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
        if self.door and self.near(self.door.position, 2.2):
            if len(self.found) == 3:
                self.door.animate_position(self.door.position + Vec3(0, -2.3, 0), duration=1.5)
                self.show_note(f"你輸入了 {self.code}。門開了。\n往下的樓梯傳來翻書的聲音。")
                self.go_down()
            else:
                self.show_hint(f"密碼鎖：三碼。你知道的：{self.code_hint()}", 3)

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
        self.player.speed = 6.5 if held_keys["shift"] else 3.5
        self.time_left -= time.dt
        total = self.cfg["seconds"]
        game_min = 40 + (total - self.time_left) / total * 20
        self.clock_text.text = (f"02:{int(game_min):02d}　第 {self.loop} 輪　"
                                f"{self.difficulty}")
        if self.world.floor == "B1":
            self.goal_text.text = ("目標：在 B 區密集書庫找到《考古題之書》　在書架前按 E 轉手輪打開走道"
                                   if "4" in self.read_notes else "目標：入口桌上有東西在發光……")
        elif len(self.found) < 3:
            self.goal_text.text = (f"目標：找室友的筆記，照上面的提示找出密碼　密碼：{self.code_hint()}　"
                                   f"筆記 {len(self.read_notes & set('123'))}/3")
        else:
            self.goal_text.text = f"目標：到密集書庫最裡面的「B1 地下書庫」門，按 E 輸入 {self.code}"
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
        self.update_lights(self.update_monster())
        self.update_body()


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
    if key == "escape" or (game.cleared and key == "enter"):
        game.to_lobby()
    elif key == "e" and not game.cleared:
        game.interact()
    elif key == "f":
        game.flashlight_on = not game.flashlight_on
        game.apply_flashlight()


# 用一個空 Entity 掛每幀更新與按鍵處理，不依賴 __main__ 裡的全域函式
driver = Entity(update=game.update, input=handle_input)


if __name__ == "__main__":
    app.run()
