"""總圖不打烊 原型：第一人稱 3D 恐怖解謎。

操作：
  WASD 移動、滑鼠看、Shift 跑、E 互動（讀筆記、開門）、F 開關手電筒、ESC 離開

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
from world import CELL, World, cell_pos

LOOP_SECONDS = 180          # 現實 3 分鐘 = 遊戲時間 02:40 → 03:00
MONSTER_SPEED = 2.6
CATCH_DIST = 1.1
SAFE_ZONE = {(c, r) for c in range(1, 9) for r in range(15, 20)}   # 夜讀區：它進不來

NOTES = {
    "1": "（字跡潦草）考古題之書在地下書庫……門的密碼第一碼是 0。",
    "2": "它只在你不看的時候動。別背對它。第二碼是 3。",
    "3": "又是三點……我已經第幾次回到這裡了？最後一碼是 7。",
}
EXIT_CODE = "037"

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
        self.read_notes = set()      # 跨迴圈保留：玩家記得的線索
        self.loop = 1
        self.world = World(font_path)
        self.notes = self.world.notes
        self.door = self.world.door
        self.solids = self.world.solids
        self.monster_walkable = self.world.walkable - SAFE_ZONE
        self.player = FirstPersonController(position=self.world.start + Vec3(0, 0.1, 0), speed=4)
        self.player.cursor.visible = False
        self.player.gravity = 1
        self.monster = self.make_monster()
        self.setup_lights()
        self.dust = self.make_dust()
        self.setup_audio()
        self.clock_text = Text(position=(-0.85, 0.47), scale=1.2, color=color.light_gray)
        self.hint = Text(position=(-0.3, -0.38), scale=1.1, color=color.white)
        self.note_text = Text(position=(-0.6, 0.1), scale=1.3, color=color.rgb32(240, 230, 200))
        self.note_bg = Entity(parent=camera.ui, model="quad", color=color.rgba32(0, 0, 0, 200),
                              scale=(1.25, 0.32), position=(-0.02, 0.06), z=0.5, enabled=False)
        self.flash = Entity(parent=camera.ui, model="quad", scale=(2, 1), color=color.rgba32(0, 0, 0, 0), z=-1)
        self.dead = False
        self.cleared = False
        self.bob = 0.0
        self.step_timer = 0.0
        self.beat_timer = 0.0
        self.reset_loop(first=True)

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
        self.time_left = LOOP_SECONDS
        self.dead = False
        self.note_text.text = ""
        msg = ("夜讀區的燈還亮著。室友不見了，通往館藏區的門卻沒鎖。" if first
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
        if dist > (10 if self.flashlight_on else 3):   # 在黑暗裡看不到它，它就會動
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
        step = MONSTER_SPEED * time.dt
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
        invoke(self.flash_fade, delay=1.5)
        invoke(self.reset_loop, delay=1.5)

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
    def interact(self):
        for key, note in self.notes.items():
            if (note.position - self.player.position).length() < 1.8:
                self.read_notes.add(key)
                self.play("page")
                self.note_text.text = wrap(NOTES[key])
                self.note_bg.enabled = True
                invoke(self.hide_note, delay=6)
                if len(self.read_notes) == len(NOTES):
                    self.world.keypad_light.color = color.lime
                return
        if (self.door.position - self.player.position).length() < 2.2:
            if len(self.read_notes) == len(NOTES):
                self.cleared = True
                self.door.animate_position(self.door.position + Vec3(0, -2.3, 0), duration=1.5)
                self.note_text.text = f"你輸入了 {EXIT_CODE}。門開了。\n往下的樓梯傳來翻書的聲音。\n\n第一章　完\n（迴圈次數：{self.loop}）"
                self.player.enabled = False
            else:
                self.show_hint(f"密碼鎖：三位數。你只知道 {len(self.read_notes)} 碼。", 3)

    def hide_note(self):
        self.note_text.text = ""
        self.note_bg.enabled = False

    def update(self):
        self.update_dust()
        if self.cleared or self.dead:
            return
        self.player.speed = 6.5 if held_keys["shift"] else 3.5
        self.time_left -= time.dt
        game_min = 40 + (LOOP_SECONDS - self.time_left) / LOOP_SECONDS * 20
        self.clock_text.text = f"02:{int(game_min):02d}　第 {self.loop} 輪　筆記 {len(self.read_notes)}/3"
        if self.time_left <= 0:
            self.flash.color = color.rgba32(0, 0, 0, 255)
            self.dead = True
            self.show_hint("03:00", 2)
            invoke(self.flash_fade, delay=1.5)
            invoke(self.reset_loop, delay=1.5)
            return
        safe = self.to_cell(self.player.position) in SAFE_ZONE
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


def handle_input(key):
    if key == "escape":
        application.quit()
    elif key == "e":
        game.interact()
    elif key == "f":
        game.flashlight_on = not game.flashlight_on
        game.apply_flashlight()


# 用一個空 Entity 掛每幀更新與按鍵處理，不依賴 __main__ 裡的全域函式
driver = Entity(update=game.update, input=handle_input)


if __name__ == "__main__":
    app.run()
