"""總圖不打烊 原型：第一人稱 3D 恐怖解謎。

操作：
  WASD 移動、滑鼠看、Shift 跑、E 互動（讀筆記、開門）、F 開關手電筒、ESC 離開

玩法：
  半夜的總圖，室友失蹤了。在書架間找出筆記，拼出出口密碼。
  書架間有「東西」——你看著它，它就不動；你一轉頭，它就靠近。
  凌晨 3:00 一到（或被它抓到），一切重來，但你會記得已經讀過的筆記。
"""
import math
from collections import deque
import os
import sys
from pathlib import Path

from ursina import (Ursina, Entity, Text, camera, color, held_keys, invoke, mouse,
                    raycast, scene, time, application, window, Vec3, Texture)
from ursina.prefabs.first_person_controller import FirstPersonController
from PIL import Image

CELL = 2.0
WALL_H = 3.2
LOOP_SECONDS = 180          # 現實 3 分鐘 = 遊戲時間 02:40 → 03:00
MONSTER_SPEED = 2.6
CATCH_DIST = 1.1

# # 牆  B 書架  . 地板  P 起點  M 怪物  1/2/3 筆記  D 出口
LEVEL = [
    "####################",
    "#P.....#...........#",
    "#.BBBB.#.BBBB.BBBB.#",
    "#......#..........3#",
    "#.BBBB.###.##.BBBB.#",
    "#..................#",
    "#.BBBB.BBBB.BBBB...#",
    "#1.................#",
    "#.BBBB.BBBB.BBBB.###",
    "#.........M........#",
    "###.#####.####.BBB.#",
    "#..2#.........#....D",
    "#...#....B....#....#",
    "####################",
]

NOTES = {
    "1": "（字跡潦草）考古題之書在地下書庫……門的密碼第一碼是 0。",
    "2": "它只在你不看的時候動。別背對它。第二碼是 3。",
    "3": "又是三點……我已經第幾次回到這裡了？最後一碼是 7。",
}
EXIT_CODE = "037"

FONT_CANDIDATES = [
    "C:/Windows/Fonts/msjh.ttc", "C:/Windows/Fonts/msjhbd.ttc", "C:/Windows/Fonts/mingliu.ttc",
    "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def wrap(s, width=20):
    """中文沒有空白可以斷行，固定每幾個字換一行。"""
    return "\n".join(s[i:i + width] for i in range(0, len(s), width))


def cell_pos(c, r):
    return Vec3(c * CELL, 0, -r * CELL)


class Game:
    def __init__(self):
        self.read_notes = set()      # 跨迴圈保留：玩家記得的線索
        self.loop = 1
        self.solids = []
        self.notes = {}
        self.build_level()
        self.player = FirstPersonController(position=self.start + Vec3(0, 0.1, 0), speed=4)
        self.player.cursor.visible = False
        self.player.gravity = 1
        self.monster = self.make_monster()
        self.setup_lights()
        self.clock_text = Text(position=(-0.85, 0.47), scale=1.2, color=color.light_gray)
        self.hint = Text(position=(-0.25, -0.38), scale=1.1, color=color.white)
        self.note_text = Text(position=(-0.6, 0.1), scale=1.3, color=color.rgb32(240, 230, 200))
        self.note_bg = Entity(parent=camera.ui, model="quad", color=color.rgba32(0, 0, 0, 200),
                              scale=(1.25, 0.32), position=(-0.02, 0.06), z=0.5, enabled=False)
        self.flash = Entity(parent=camera.ui, model="quad", scale=(2, 1), color=color.rgba32(0, 0, 0, 0), z=-1)
        self.dead = False
        self.cleared = False
        self.reset_loop(first=True)

    # ---------- 場景 ----------
    def build_level(self):
        rows, cols = len(LEVEL), len(LEVEL[0])
        self.walkable = {(c, r) for r, row in enumerate(LEVEL) for c, ch in enumerate(row) if ch not in "#BD"}
        cx, cz = (cols - 1) * CELL / 2, -(rows - 1) * CELL / 2
        Entity(model="plane", scale=(cols * CELL, 1, rows * CELL), position=(cx, 0, cz),
               color=color.rgb32(70, 62, 55), collider="box")
        Entity(model="plane", scale=(cols * CELL, 1, rows * CELL), position=(cx, WALL_H, cz),
               rotation_x=180, color=color.rgb32(40, 40, 45))
        for r, row in enumerate(LEVEL):
            for c, ch in enumerate(row):
                p = cell_pos(c, r)
                if ch == "#":
                    e = Entity(model="cube", position=p + Vec3(0, WALL_H / 2, 0),
                               scale=(CELL, WALL_H, CELL), color=color.rgb32(120, 115, 105),
                               collider="box")
                    self.solids.append(e)
                elif ch == "B":
                    e = Entity(model="cube", position=p + Vec3(0, 1.1, 0), scale=(CELL * 0.95, 2.2, CELL * 0.6),
                               color=color.rgb32(95, 60, 35), collider="box")
                    for i in range(4):   # 一排排書脊
                        Entity(parent=e, model="cube", position=(0, -0.38 + i * 0.25, 0.51),
                               scale=(0.95, 0.12, 0.02), color=color.rgb32(150 - i * 20, 40 + i * 25, 40))
                    self.solids.append(e)
                elif ch == "P":
                    self.start = p
                elif ch == "M":
                    self.monster_start = p
                elif ch in NOTES:
                    self.notes[ch] = Entity(model="cube", position=p + Vec3(0, 0.9, 0), scale=(0.35, 0.02, 0.45),
                                            color=color.rgb32(235, 225, 190))
                    Entity(model="cube", position=p + Vec3(0, 0.45, 0), scale=(0.8, 0.9, 0.6),
                           color=color.rgb32(80, 70, 60), collider="box")
                elif ch == "D":
                    self.door = Entity(model="cube", position=p + Vec3(0, 1.2, 0), scale=(0.3, 2.4, 1.4),
                                       color=color.rgb32(60, 90, 70), collider="box")
                    self.solids.append(self.door)

    def make_monster(self):
        m = Entity(position=self.monster_start)
        Entity(parent=m, model="cube", position=(0, 1.15, 0), scale=(0.55, 2.3, 0.35), color=color.rgb32(15, 15, 18))
        Entity(parent=m, model="sphere", position=(0, 2.45, 0), scale=0.45, color=color.rgb32(220, 215, 205))
        for x in (-0.09, 0.09):
            Entity(parent=m, model="sphere", position=(x, 2.48, 0.2), scale=0.08, color=color.black)
        return m

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
                a = min(1.0, max(0.0, (d - 0.28) / 0.42))
                px[x, y] = (0, 0, 0, int(255 * a ** 1.4))
        self.vignette = Entity(parent=camera.ui, model="quad", texture=Texture(img),
                               scale=(window.aspect_ratio * 1.15, 1.15), z=1)
        self.flashlight_on = True
        self.apply_flashlight()

    def apply_flashlight(self):
        scene.fog_density = (1.0, 10.0) if self.flashlight_on else (0.3, 3.0)
        self.vignette.scale = (window.aspect_ratio * (1.15 if self.flashlight_on else 0.8),
                               1.15 if self.flashlight_on else 0.8)

    # ---------- 迴圈 ----------
    def reset_loop(self, first=False):
        if not first:
            self.loop += 1
        self.player.position = self.start + Vec3(0, 0.1, 0)
        self.player.rotation_y = 90
        self.monster.position = self.monster_start
        self.time_left = LOOP_SECONDS
        self.dead = False
        self.note_text.text = ""
        msg = "室友不見了。找出筆記，拼出出口密碼。" if first else f"……又是 02:40。第 {self.loop} 次了。你記得讀過的筆記。"
        self.show_hint(msg, 5)

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
        if dist > (8.5 if self.flashlight_on else 2.5):   # 在黑暗裡看不到它，它就會動
            return False
        fwd = camera.forward
        cos_angle = (to.x * fwd.x + to.y * fwd.y + to.z * fwd.z) / dist
        if cos_angle < math.cos(math.radians(42)):
            return False
        hit = raycast(eye, to.normalized(), distance=dist, ignore=(self.player,), traverse_target=scene)
        return not (hit.hit and hit.entity in self.solids)

    def update_monster(self):
        if self.player_sees(self.monster.world_position):
            return
        to = self.player.position - self.monster.position
        to.y = 0
        dist = to.length()
        if dist < CATCH_DIST:
            self.caught()
            return
        target = self.next_step_toward(self.monster.position, self.player.position)
        move = target - self.monster.position
        move.y = 0
        step = MONSTER_SPEED * time.dt
        if move.length() <= step:
            self.monster.position = Vec3(target.x, 0, target.z)
        else:
            self.monster.position += move.normalized() * step
        self.monster.look_at_2d(self.player.position, "y")

    def to_cell(self, pos):
        return (round(pos.x / CELL), round(-pos.z / CELL))

    def next_step_toward(self, start, goal):
        """在走廊格子上做 BFS，回傳往玩家方向的下一格中心點。"""
        s, g = self.to_cell(start), self.to_cell(goal)
        if s == g or g not in self.walkable:
            return Vec3(goal.x, 0, goal.z)
        prev = {s: None}
        queue = deque([s])
        while queue:
            cur = queue.popleft()
            if cur == g:
                break
            c, r = cur
            for nxt in ((c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1)):
                if nxt in self.walkable and nxt not in prev:
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
        self.flash.color = color.rgba32(150, 0, 0, 220)
        self.show_hint("它抓到你了。", 2)
        invoke(self.flash_fade, delay=1.5)
        invoke(self.reset_loop, delay=1.5)

    def flash_fade(self):
        self.flash.color = color.rgba32(0, 0, 0, 0)

    # ---------- 互動 ----------
    def interact(self):
        for key, note in self.notes.items():
            if (note.position - self.player.position).length() < 1.8:
                self.read_notes.add(key)
                self.note_text.text = wrap(NOTES[key])
                self.note_bg.enabled = True
                invoke(self.hide_note, delay=6)
                return
        if (self.door.position - self.player.position).length() < 2.2:
            if len(self.read_notes) == len(NOTES):
                self.cleared = True
                self.note_text.text = f"你輸入了 {EXIT_CODE}。門開了。\n\n第一章　完\n（迴圈次數：{self.loop}）"
                self.player.enabled = False
            else:
                known = len(self.read_notes)
                self.show_hint(f"密碼鎖：三位數。你只知道 {known} 碼。", 3)

    def hide_note(self):
        self.note_text.text = ""
        self.note_bg.enabled = False

    def update(self):
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
        self.update_monster()


def setup_font():
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            # Ursina 只會在字型資料夾裡用檔名找字型，所以把系統字型資料夾設成字型資料夾
            application.fonts_folder = Path(path).parent
            Text.default_font = Path(path).name
            return


app = Ursina(title="總圖不打烊 原型", borderless=False, development_mode=False)
setup_font()
window.color = color.black
game = Game()


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
