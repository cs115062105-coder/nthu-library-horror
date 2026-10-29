"""偷卷仔，給我站住！—— 第一人稱 3D 搞笑潛行解謎。

操作：
  WASD 移動、滑鼠看、Shift 跑、Ctrl 躡手躡腳、E 互動／抓人／痛扁、C 躲到桌子底下、ESC 回大廳

玩法：
  說好期中考一起擺爛的室友，被你發現偷偷跑來總圖讀書。
  從 1F 開始照著他留下的線索一層一層往上找，躲開會「噓」你的館員，
  在 4F 找到正在偷卷的他，抓住他、痛扁他。
  22:00 閉館（或被館員警告三次請出去）就是隔天重來，但你會記得找到過的線索。
"""
import math
import os
import random
from pathlib import Path

from ursina import (Ursina, Audio, Entity, Text, Vec2, Vec3, application, camera, color, destroy,
                    held_keys, invoke, raycast, scene, time, window)

import sfx
from events import Scares
from menu import DIFFICULTIES, Lobby
from minigames import GateRun, PrimeWall
from npc import Librarian, Roommate, to_cell
from player import Player
from world import World, cell_pos

MENU_SPOT = (5, 15)     # 大廳背景：1F 入口旁，望向圓形展區
MENU_LIBRARIAN = (17, 15)
SKY = color.rgb32(226, 226, 218)   # 白天的霧：遠處淡淡的米白色

NOTES = {
    "1": "（夜讀區，室友常坐的位子）桌上刻著：「擺爛聯盟　永不讀書」。\n旁邊卻壓著一張今天的「預約取書」收據……\n去聯合櫃臺的電腦查查看他預約了什麼。",
    "2": "（2F 桌上的便條，室友的字）「電腦教室最裡面那台，密碼是學校在新竹建校那年。」\n下面又補一行：「……我為什麼要寫下來？」",
    "3": "一張計算紙，寫滿了微積分。最下面寫著：「不能讓他知道。」",
    "5": "（語言學習區，耳機還是熱的）隨手寫的紙條：\n「線代錄音 → 視聽區最裡面那台（螢幕亮著）」",
    "6": "（被撕下來的筆記本內頁）「清華書房展示櫃：三碼。\n第一碼＝錄音帶的嗶聲數，第二碼夾在『300 科學類』的書裡，\n第三碼在討論室白板上。裡面放的是……要給他的東西。」",
    "4": "（B1 入口桌上）你到底怎麼進來的？館員看到會哭。",
}
# 樓梯間的門鎖：(樓層, 方向) → (需要的東西, 沒有時的提示)。白天的樓梯大家都能走，只有這兩扇不行
LOCKS = {
    ("1F", "down"): ("b1", "B1 密集書庫：館員專用。（室友不可能在這裡）"),
    ("4F", "up"): ("5f", "往 5F 的樓梯被施工圍籬擋住了。（5F 之後的樓層還在蓋）"),
}
READABLE = {
    "newspaper": "《清華新聞》頭條：「期中考週，總圖座位一位難求」\n副標：「有學生自稱『完全沒讀』，卻被拍到在 4F 讀到閉館」",
    "exhibit": "主題展「總圖的一天」\n18:00 晚餐人潮離開，是館內最安靜的四小時。\n館員提醒：館內請勿奔跑。",
}
CLUES = {
    "book": (1, "《物種原始》裡夾著一張便條：\n「第二碼：{d}」\n下面還寫著：「他一定想不到我在這裡。」"),
    "whiteboard": (2, "白板寫滿了微積分算式，角落圈著一個數字：{d}\n旁邊寫著：「讀書會成員：只有我。」"),
}
FIGHT_LINES = ["我只是剛好路過！", "我真的沒讀啦！", "這本是幫你借的！", "不要打臉！明天要考試！",
               "我錯了我錯了！", "是書自己跳到我手上的！", "你小聲點！館員會來！"]

FONT_CANDIDATES = [
    "C:/Windows/Fonts/msjh.ttc", "C:/Windows/Fonts/msjhbd.ttc", "C:/Windows/Fonts/mingliu.ttc",
    "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def wrap(s, width=20):
    """中文沒有空白可以斷行，固定每幾個字換一行（原本的換行保留）。"""
    return "\n".join(line[i:i + width] for line in s.split("\n") for i in range(0, max(len(line), 1), width))


def find_font():
    return next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)


def setup_font(path):
    if path:
        # Ursina 只會在字型資料夾裡用檔名找字型，所以把系統字型資料夾設成字型資料夾
        application.fonts_folder = Path(path).parent
        Text.default_font = Path(path).name


class Game:
    def __init__(self, font_path):
        self.read_notes = set()      # 跨天保留：讀過的筆記
        self.found = set()           # 跨天保留：已經找到的密碼位數
        self.items = set()           # 跨天保留：查到的線索
        self.locker_no = 1
        self.entry = None            # 輸入密碼的畫面
        self.mini = None             # 正在玩的小遊戲
        self.crew = 0                # 揪來一起扁他的人數
        self.fight = None            # 痛扁小遊戲
        self.arrival = None
        self.code = "000"
        self.day = 1
        self.cfg = DIFFICULTIES["普通"]
        self.difficulty = "普通"
        self.state = "menu"
        self.session = 0             # 每開一局加一，舊的延遲事件就不會跑到新的一局
        self.font_path = font_path
        self.world = None
        self.in_safe_zone = False
        self.hidden = False
        self.load_floor("1F")
        self.player = Player(position=self.world.start, speed=4)
        self.player.cursor.visible = False
        self.player.unstick = self.nearest_open
        self.librarian = Librarian(self)
        self.roommate = Roommate(self)
        self.setup_audio()
        self.ui_left = Entity(parent=camera.ui)   # 貼著畫面左緣的介面，螢幕比例不同也不會被切掉
        self.hud_bg = Entity(parent=self.ui_left, model="quad", origin=(-0.5, 0.5), position=(0.02, 0.49),
                             scale=(1.25, 0.09), color=color.rgba32(255, 255, 255, 150), z=0.6)
        self.clock_text = Text(parent=self.ui_left, position=(0.04, 0.47), scale=1.2, color=color.rgb32(40, 40, 50))
        self.goal_text = Text(parent=self.ui_left, position=(0.04, 0.425), scale=1.0, color=color.rgb32(150, 70, 20))
        self.prompt = Text(position=(0, -0.06), origin=(0, 0), scale=1.1, color=color.white)
        self.prompt_bg = Entity(parent=camera.ui, model="quad", position=(0, -0.06), z=0.6,
                                color=color.rgba32(0, 0, 0, 150), enabled=False)
        self.dot = Entity(parent=camera.ui, model="circle", scale=0.006, color=color.rgba32(255, 255, 255, 200),
                          enabled=False)
        self.hint = Text(position=(-0.3, -0.33), scale=1.1, color=color.white)
        self.hint_bg = Entity(parent=camera.ui, model="quad", color=color.rgba32(0, 0, 0, 140), origin=(-0.5, 0.5),
                              position=(-0.31, -0.32), z=0.6, enabled=False)
        self.note_text = Text(position=(-0.6, 0.12), scale=1.3, color=color.rgb32(240, 230, 200))
        self.note_bg = Entity(parent=camera.ui, model="quad", color=color.rgba32(0, 0, 0, 210),
                              scale=(1.3, 0.45), position=(-0.02, 0.04), z=0.5, enabled=False)
        self.flash = Entity(parent=camera.ui, model="quad", scale=(2, 1), color=color.rgba32(0, 0, 0, 0), z=-1)
        self.entry_bg = Entity(parent=camera.ui, model="quad", color=color.rgba32(10, 20, 30, 235),
                               scale=(0.8, 0.45), z=0.4, enabled=False)
        self.entry_title = Text(position=(0, 0.16), origin=(0, 0), scale=1.2, color=color.rgb32(150, 200, 240))
        self.entry_text = Text(position=(0, -0.03), origin=(0, 0), scale=2.0, color=color.white)
        self.fight_title = Text(position=(0, 0.38), origin=(0, 0), scale=1.8, color=color.rgb32(220, 40, 30))
        self.fight_line = Text(position=(0, 0.25), origin=(0, 0), scale=1.4, color=color.white)
        self.hp_bg = Entity(parent=camera.ui, model="quad", position=(0, 0.31), scale=(0.6, 0.03),
                            color=color.rgba32(0, 0, 0, 160), enabled=False)
        self.hp_bar = Entity(parent=camera.ui, model="quad", origin=(-0.5, 0), position=(-0.3, 0.31), z=-0.01,
                             scale=(0.6, 0.026), color=color.rgb32(230, 60, 40), enabled=False)
        self.dead = False
        self.cleared = False
        self.tape_playing = False
        self.noise = 0.0             # 聲音條：跑步會累積，滿了館員會聽到
        self.warnings = 0            # 今天被館員警告幾次，三次就被請出去
        self.total_warnings = 0
        self.spotted = 0             # 被室友發現（逃跑）幾次
        self.moving = self.running = self.sneaking = False
        self.noise_bg = Entity(parent=self.ui_left, model="quad", origin=(-0.5, 0), position=(0.04, -0.44),
                               scale=(0.3, 0.018), color=color.rgba32(0, 0, 0, 60))
        self.noise_bar = Entity(parent=self.ui_left, model="quad", origin=(-0.5, 0), position=(0.04, -0.44),
                                scale=(0, 0.018), color=color.rgb32(90, 90, 100))
        self.noise_label = Text(parent=self.ui_left, position=(0.04, -0.405), scale=0.8, color=color.rgb32(30, 30, 40))
        self.scares = Scares(self)
        self.bob = 0.0
        self.step_timer = 0.0
        self.time_left = 0
        self.apply_view()

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
        self.apply_view()   # 霧的參數要重新套到新蓋的東西上

    def refresh_paths(self):
        self.librarian_walkable = self.world.walkable - self.world.spec["safe"]   # 館員不巡夜讀區

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
        self.dead = True   # 換樓層時暫停館員和時鐘
        self.update_prompt(off=True)
        self.flash.color = color.rgba32(0, 0, 0, 255)
        self.goal_text.text = ""
        self.play("step")

        def arrive():
            self.load_floor(stair["target"], came=direction)
            self.enter_floor()
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
        self.day = 1
        self.total_warnings = self.spotted = self.crew = 0
        self.cleared = False
        self.tape_playing = False
        self.load_floor("1F", came="start")   # 重蓋一次，東西都回到原狀
        self.hide_note()
        self.flash_fade()
        self.state = "play"
        self.noise_bg.enabled = self.hud_bg.enabled = True
        self.player.enabled = True
        self.new_day(first=True)

    def to_lobby(self):
        self.session += 1
        self.state = "menu"
        self.dead = False
        for t in (self.clock_text, self.goal_text, self.hint, self.note_text):
            t.text = ""
        self.hint_bg.enabled = False
        self.note_bg.enabled = False
        self.update_prompt(off=True)
        self.flash_fade()
        self.close_entry()
        self.end_fight_ui()
        if self.mini:
            self.mini.close()
            self.mini = None
        self.scares.reset()
        self.noise, self.hidden = 0.0, False
        self.noise_bar.scale_x, self.noise_label.text = 0, ""
        self.noise_bg.enabled = self.hud_bg.enabled = False
        if self.world.floor != "1F":
            self.load_floor("1F", came="start")
        self.in_safe_zone = False
        self.roommate.hide()
        self.player.position = cell_pos(*MENU_SPOT)
        self.player.enabled = False      # 停用時 Ursina 會把鏡頭交還給場景，滑鼠也會解鎖
        self.librarian.reset(cell_pos(*MENU_LIBRARIAN))
        self.librarian.root.look_at_2d(self.player.position, "y")
        lobby.show()

    def aim_menu_camera(self, forward, sway):
        camera.position = cell_pos(*MENU_SPOT) + Vec3(forward, 1.6, 0)
        camera.rotation = (4, 90 + sway, 0)

    def later(self, fn, delay):
        """延遲執行，但如果玩家已經回大廳或重開一局就取消。"""
        session = self.session
        invoke(lambda: fn() if session == self.session else None, delay=delay)

    # ---------- 場景 ----------
    def apply_view(self):
        """白天：燈全亮，只留一層很淡的霧讓遠處柔和一點。"""
        scene.fog_color = SKY
        scene.fog_density = (20.0, 75.0)

    def setup_audio(self):
        self.sounds = {}
        try:
            paths = sfx.generate()
            volumes = dict(step=0.35, sting=0.5, page=0.6, rumble=0.7, beep=0.6, chime=0.7, ring=0.5,
                           thud=0.8, shh=0.8, punch=0.9)
            self.sounds = {name: Audio(paths[name], autoplay=False, volume=v) for name, v in volumes.items()}
            self.sounds["hum"] = Audio(paths["hum"], loop=True, autoplay=True, volume=0.06)   # 冷氣和日光燈
        except Exception as e:   # 沒有音效卡也能玩
            print("音效載入失敗：", e)

    def play(self, name, volume=None):
        s = self.sounds.get(name)
        if s:
            if volume is not None:
                s.volume = volume
            s.play()

    # ---------- 一天 ----------
    def enter_floor(self):
        """走進一層樓：時間繼續走，只是重設這層的館員和室友。"""
        self.place_player()
        self.librarian.reset(self.world.monster_start)
        self.spawn_roommate()
        self.scares.reset()
        self.dead = False
        msg = {"1F": "1F。入館閘門旁人來人往，櫃臺的館員抬頭看了你一眼。",
               "2F": "2F。期刊區很安靜，大家都在假裝自己很認真。",
               "3F": "3F。視聽區傳來線性代數的錄音……這聲音好熟。",
               "4F": "4F。一整層的中文書。空氣裡有一股「偷卷」的味道。",
               "B1": "B1。你怎麼進來的？"}.get(self.world.floor, f"{self.world.floor}。")
        if self.world.floor == "4F" and self.roommate.active:
            msg += "\n他就在這層某張桌子。趁他低頭時靠近，他抬頭時躲好！"
        self.show_hint(wrap(msg, 26), 5)

    def new_day(self, first=False, why=""):
        if not first:
            self.day += 1
        self.place_player()
        self.librarian.reset(self.world.monster_start)
        self.time_left = self.cfg["seconds"]
        self.dead = False
        self.warnings = 0
        self.noise, self.hidden = 0.0, False
        self.spawn_roommate()
        self.scares.reset()
        self.note_text.text = ""
        if first:
            msg = ("18:00。室友說今天要在宿舍睡一整天，IG 限動卻拍到總圖的窗戶。\n"
                   "說好一起擺爛，結果你偷卷？今天一定要抓到你。")
        else:
            msg = f"{why}\n第 {self.day} 天 18:00，你又來到總圖 {self.world.floor}。查到的線索都還記得。"
        self.show_hint(wrap(msg, 26), 6)

    def place_player(self):
        self.player.position = self.arrival + Vec3(0, 0.1, 0)
        self.player.rotation_y = self.arrival_rot
        self.player.camera_pivot.rotation_x = 0

    def spawn_roommate(self):
        if self.world.floor == "4F" and "trail4" in self.items:
            self.roommate.spawn(self.world, self.player.position)
        else:
            self.roommate.hide()

    def end_day(self, why, tint):
        if self.dead:
            return
        self.update_prompt(off=True)
        self.dead = True
        self.hidden = False
        self.flash.color = tint
        self.later(self.flash_fade, 1.8)
        self.later(lambda: self.new_day(why=why), 1.8)

    def show_hint(self, msg, seconds=3):
        self.hint.text = msg
        self.hint_bg.enabled = bool(msg)
        lines = msg.count("\n") + 1
        self.hint_bg.scale = (min(1.2, max(len(l) for l in msg.split("\n")) * 0.026 + 0.04), lines * 0.042 + 0.02)

        def clear():
            if self.hint.text == msg:   # 只清掉自己這則，後來的提示不要被提早清掉
                self.hint.text = ""
                self.hint_bg.enabled = False
        invoke(clear, delay=seconds)

    def flash_fade(self):
        self.flash.color = color.rgba32(0, 0, 0, 0)

    def player_sees(self, target):
        """目標在玩家視野內、而且中間沒有牆或書架擋住。"""
        eye = camera.world_position
        to = target + Vec3(0, 1.6, 0) - eye
        dist = to.length()
        if dist < 0.01:
            return True
        fwd = camera.forward
        if (to.x * fwd.x + to.y * fwd.y + to.z * fwd.z) / dist < math.cos(math.radians(42)):
            return False
        hit = raycast(eye, to.normalized(), distance=dist, ignore=(self.player,), traverse_target=scene)
        return not (hit.hit and hit.entity in self.solids)

    # ---------- 館員 ----------
    def warn(self):
        self.warnings += 1
        self.total_warnings += 1
        self.play("shh")
        if self.warnings >= 3:
            self.show_hint("館員：「同學，你已經被警告三次了。請你出去。」", 3)
            self.end_day("你被館員請出了圖書館……", color.rgba32(0, 0, 0, 255))
            return
        line = "館內請勿奔跑！" if self.running else "請保持安靜！"
        self.show_hint(f"館員：「噓——同學，{line}」（警告 {self.warnings}/3）", 3)

    # ---------- 室友 ----------
    def roommate_spotted(self):
        self.spotted += 1
        self.play("sting", volume=0.35)
        self.show_hint(random.choice(["室友：「！？你怎麼在這？」（抱著書逃走了）",
                                      "室友：「我、我只是來還書的！」（拔腿就跑）",
                                      "室友：「被發現了！」（把書塞進書包逃走）"]), 3)
        self.roommate.flee()

    def catch_roommate(self):
        """抓到了！進入痛扁小遊戲。"""
        if self.fight or self.cleared:
            return
        r = self.roommate
        r.state = "caught"
        r.alarm.enabled = False
        r.stand()
        away = self.player.position - r.position
        away.y = 0
        if away.length() < 1.6:   # 退一點，整個人入鏡
            self.player.position = r.position + (away.normalized() if away.length() > 0.01 else Vec3(0, 0, 1)) * 1.6
        r.root.look_at_2d(self.player.position, "y")
        self.player.look_at_2d(r.position, "y")
        self.player.camera_pivot.rotation_x = 8
        self.player.speed = 0
        self.player.mouse_sensitivity = Vec2(0, 0)
        self.hidden = False
        self.fight = dict(hp=self.cfg["hits"], time=self.cfg["fight_time"], shake=0.0, hits=0)
        self.fight_title.text = "抓到了！狂按 E 或滑鼠左鍵痛扁他！"
        if self.crew:
            self.show_hint(f"你揪來的 {self.crew} 個人從書架後面衝出來！每一下 ×{self.power()}", 3)
        self.fight_line.text = "室友：「等、等一下！我可以解釋！」"
        self.hp_bg.enabled = self.hp_bar.enabled = True
        self.hp_bar.scale_x = 0.6
        self.play("sting", volume=0.4)

    def start_mini(self, mini):
        if self.state != "play" or self.cleared or self.fight or self.mini:
            mini.close()
            return
        self.close_entry()
        self.hide_note()
        self.update_prompt(off=True)
        self.mini = mini
        self.player.speed = 0
        self.player.mouse_sensitivity = Vec2(0, 0)
        self.hidden = False

    def end_mini(self, callback):
        """小遊戲結束：恢復操作，再把結果交給 callback。"""
        def done(result):
            self.mini = None
            self.player.mouse_sensitivity = Vec2(40, 40)
            callback(result)
        return done

    def hit(self):
        f = self.fight
        f["hp"] -= self.power()
        f["hits"] += 1
        f["shake"] = 0.15
        self.play("punch")
        self.hp_bar.scale_x = 0.6 * max(0, f["hp"]) / self.cfg["hits"]
        if f["hits"] % 4 == 1:
            self.fight_line.text = "室友：「" + random.choice(FIGHT_LINES) + "」"
        if f["hp"] <= 0:
            self.end_fight_ui()
            self.ending()

    def power(self):
        """揪來的人越多，每一下越痛：30 人 ×2、150 人 ×3、600 人 ×4。"""
        return 1 + sum(self.crew >= n for n in (30, 150, 600))

    def update_fight(self):
        f = self.fight
        f["time"] -= time.dt
        r = self.roommate
        if f["shake"] > 0:
            f["shake"] -= time.dt
            r.torso.rotation_x = -25 * f["shake"] / 0.15
            r.head.rotation_z = random.uniform(-25, 25)
        else:
            r.torso.rotation_x = 0
            r.head.rotation_z = 0
        self.fight_title.text = f"狂按 E 或滑鼠左鍵痛扁他！　{max(0, f['time']):.1f} 秒"
        if f["time"] <= 0:   # 打不夠，他掙脫逃走
            self.end_fight_ui()
            self.show_hint("室友掙脫了！「下次再說！」……他又跑了。", 3)
            self.spotted += 1
            self.roommate.flee()

    def end_fight_ui(self):
        self.fight = None
        self.fight_title.text = self.fight_line.text = ""
        self.hp_bg.enabled = self.hp_bar.enabled = False
        self.player.mouse_sensitivity = Vec2(40, 40)

    # ---------- 互動 ----------
    def show_note(self, text):
        self.play("page")
        self.note_text.text = text
        self.note_bg.enabled = True
        self.later(self.hide_note, 8)

    def near(self, pos, dist):
        d = pos - self.player.position
        d.y = 0
        return d.length() < dist

    def code_hint(self):
        return " ".join(self.code[i] if i in self.found else "_" for i in range(3))

    def targets(self):
        """附近所有可以按 E 的東西：(看的位置, 要站的位置, 提示文字, 動作)。"""
        out = []
        r = self.roommate
        if r.active and r.state in ("study", "look"):
            out.append((r.position + Vec3(0, 1.0, 0), r.position, "抓住他！", self.catch_roommate))
        for key, note in self.notes.items():
            out.append((note.position, note.position, "看紙條", lambda k=key: self.read_note(k)))
        for name, pos in self.world.clues.items():
            label = "看白板" if name == "whiteboard" else "抽出那本凸出來的書"
            look = self.world.whiteboard.position if name == "whiteboard" and self.world.whiteboard else pos
            out.append((look, pos, label, lambda n=name: self.read_clue(n)))
        for thing in self.world.interactables:
            out.append((thing.get("look", thing["pos"]), thing["pos"], self.label(thing), lambda t=thing: self.use(t)))
        for direction, stair in self.world.stairs.items():
            out.append((stair["door"].position, stair["pos"], "上樓" if direction == "up" else "下樓",
                        lambda d=direction: self.take_stairs(d)))
        return out

    def focus(self):
        """玩家「正在看」的那個東西：要站得夠近，然後挑最接近視線正中央的。"""
        fwd = camera.forward
        fwd = Vec3(fwd.x, 0, fwd.z).normalized()
        best, best_score = None, None
        for look, stand, label, action in self.targets():
            to = look - self.player.position
            to.y = 0
            dist = to.length()
            if not (self.near(stand, 1.8) or dist < 2.4):
                continue
            facing = to.normalized().dot(fwd) if dist > 0.3 else 1.0
            if facing < 0.35 and dist > 1.2:   # 背對著的東西不算
                continue
            score = (1 - facing) * 3 + dist * 0.4
            if best_score is None or score < best_score:
                best, best_score = (label, action), score
        return best

    def interact(self):
        target = self.focus()
        if target:
            target[1]()
            return
        bank, aisle = self.world.bank_at(self.player.position)
        if bank and bank["aisle"] != aisle:
            self.world.open_aisle(bank, aisle)
            self.refresh_paths()
            self.play("rumble")

    def read_note(self, key):
        self.read_notes.add(key)
        self.show_note(wrap(NOTES[key], 24))

    def read_clue(self, name):
        index, text = CLUES[name]
        self.found.add(index)
        self.show_note(text.format(d=self.code[index]))

    @staticmethod
    def label(thing):
        kind = thing["kind"]
        if kind == "locker":
            return f"打開 A{thing['data']:02d} 櫃"
        return {"read": "閱讀", "counter_pc": "查櫃臺電腦", "lab_pc": "使用電腦", "tape": "聽錄音帶",
                "case": "打開展示櫃"}.get(kind, "查看")

    def update_prompt(self, off=False):
        """準心下方顯示現在按 E 會做什麼。"""
        target = None if off or self.entry or self.hidden else self.focus()
        self.prompt.text = f"[E] {target[0]}" if target else ""
        self.prompt_bg.enabled = bool(target)
        if target:
            self.prompt_bg.scale = (len(self.prompt.text) * 0.022 + 0.04, 0.045)
        self.dot.enabled = not off

    def nearest_open(self, pos):
        """離 pos 最近的走道格子中心（卡住時用）。"""
        cells = sorted(self.world.walkable, key=lambda c: (cell_pos(*c) - pos).length())
        return cell_pos(*cells[0]) if cells else pos

    def use(self, thing):
        """各樓層設施的互動：讀東西、查電腦、開取書櫃、登入電腦教室、聽錄音帶、開展示櫃。"""
        kind, data = thing["kind"], thing.get("data")
        if kind == "read":
            text = data.split(":", 1)[1] if data.startswith("history:") else READABLE[data]
            self.show_note(text)
        elif kind == "counter_pc":
            self.items.add("locker_known")
            self.show_note(f"預約取書紀錄\n讀者：陳○○（你的室友）\n書名：《微積分　精選 500 題》等 3 本\n"
                           f"取書櫃：A{self.locker_no:02d}　狀態：待取件\n……說好的擺爛呢？")
        elif kind == "locker":
            if data != self.locker_no:
                self.show_hint(f"A{data:02d}：別人的書，不要亂開。", 2)
            elif "trail2" in self.items:
                self.show_hint("你已經翻過這個櫃子了。", 2)
            else:
                self.items.add("trail2")
                self.play("page")
                self.show_note("櫃子裡：《微積分 精選 500 題》《線性代數 一次搞懂》《期中考 必勝寶典》\n"
                               "還夾著一張「2F 電腦教室」的座位預約單，時間就是今天。")
        elif kind == "lab_pc":
            if "trail3" in self.items:
                self.show_note("瀏覽紀錄還開著：「3F 視聽區 線代錄音」")
            elif "trail2" not in self.items:
                self.show_hint("一台上鎖的電腦。（先去 1F 查查室友今天預約了什麼）", 3)
            else:
                if "lab_pw" in self.items:   # 密碼已經對過，直接重玩防偷看程式
                    self.start_mini(PrimeWall(self, self.end_mini(self.prime_done)))
                else:
                    self.open_entry("電腦教室　登入", "密碼提示：本校在新竹建校的那一年", 4, self.lab_login)
        elif kind == "tape":
            if "trail3" not in self.items:
                self.show_hint("一台還在播的錄音機。這是誰的？", 2)
            else:
                self.play_tape()
        elif kind == "case":
            if "notes" in self.items:
                self.show_note("展示櫃已經空了。筆記在你書包裡。")
            else:
                self.open_entry("清華書房　展示櫃", f"三碼密碼鎖　你記得的：{self.code_hint()}", 3, self.case_open)

    def lab_login(self, code):
        if code != "1956":
            self.show_hint("密碼錯誤。", 2)
            return
        self.show_hint("密碼正確……螢幕跳出「防偷看程式」！", 2)
        self.start_mini(PrimeWall(self, self.end_mini(self.prime_done)))

    def prime_done(self, ok):
        if not ok:
            self.show_hint("登入失敗。再按一次 E 重新挑戰防偷看程式。", 3)
            self.items.add("lab_pw")
            return
        self.items.add("trail3")
        self.show_note("登入成功。室友的搜尋紀錄：\n「怎麼偷讀書不被室友發現」\n「偷卷 被抓到 怎麼辦」\n「3F 視聽區 線代錄音」")

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
            self.items.add("trail4")
            self.show_note("錄音帶是室友自己錄的線代重點，最後他小聲說：\n「……錄到這裡，我上 4F 中文書區繼續讀，讀到閉館。\n絕對不能讓他知道。」\n（剛剛嗶了幾聲？記下來）")
            if "crew_asked" not in self.items:
                self.items.add("crew_asked")
                self.later(lambda: self.start_mini(GateRun(self, self.end_mini(self.crew_done))), 6)
        self.later(done, 2.5 + n * 0.6)

    def crew_done(self, count):
        self.crew = count
        self.show_hint(f"揪到 {count} 個人，大家說好在 4F 埋伏。痛扁時每一下 ×{self.power()}！", 4)

    def case_open(self, code):
        if code != self.code:
            self.show_hint("鎖沒有開。", 2)
            return
        self.items.add("notes")
        self.play("page")
        self.show_note("展示櫃裡是一本手寫筆記，封面寫著：\n「給那個說要擺爛的傢伙　期中考重點」\n……你默默把它收進書包。")

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
        """左上角的目標：依樓層和已經查到的線索決定下一步。"""
        floor, items = self.world.floor, self.items
        if "trail4" in items:
            if floor != "4F":
                return "室友在 4F 中文書區！從樓梯間上去"
            extra = "" if "notes" in items else "（清華書房的展示櫃好像藏著什麼）"
            return f"趁室友低頭讀書，按住 Ctrl 靠近，按 E 抓住他{extra}"
        if "trail3" in items:
            return "到 3F 視聽區最裡面那台（螢幕亮著）聽錄音帶" if floor == "3F" else "上 3F，找視聽區還在播的那台錄音機"
        if "trail2" in items:
            return ("登入電腦教室最裡面那台電腦（密碼提示在校史展示區）" if floor == "2F"
                    else "上 2F，去室友預約的電腦教室")
        if floor != "1F":
            return "線索在 1F：回去查室友今天預約了什麼"
        if "locker_known" in items:
            return f"到最裡面（北邊）的自助取書區，打開 A{self.locker_no:02d} 櫃"
        return "到左邊的聯合櫃臺，用電腦查室友的預約"

    def ending(self):
        self.update_prompt(off=True)
        self.cleared = True
        self.goal_text.text = ""
        self.roommate.hide()
        self.player.enabled = False
        self.play("page")
        self.note_bg.enabled = True
        if "notes" in self.items:
            story = ("你把他打到求饒。他從書包拿出另一本筆記：\n「這……本來要考前一天給你的。我怕你被當，才偷偷讀。」\n"
                     "你的拳頭停在半空中。\n\n—— 真結局：偷卷是為了你 ——")
        else:
            story = ("他鼻青臉腫地承認：「我只是想偷偷考 100 分……」\n隔週成績公布：他 100 分，你 38 分。\n"
                     "你默默決定明天也來總圖。\n\n—— 結局：擺爛聯盟解散 ——")
        self.note_text.text = (f"{story}\n{self.difficulty}·第 {self.day} 天·被室友發現 {self.spotted} 次·"
                               f"館員警告 {self.total_warnings} 次·揪了 {self.crew} 人\n按 Enter 回到大廳")

    def hide_note(self):
        self.note_text.text = ""
        self.note_bg.enabled = False

    def update(self):
        self.ui_left.x = -window.aspect_ratio / 2
        if self.state != "play" or self.cleared or self.dead:
            return
        if self.fight:
            self.update_prompt(off=True)
            self.update_fight()
            return
        if self.mini:             # 玩小遊戲時時間暫停
            self.mini.update()
            return
        self.sneaking = bool(held_keys["control"] or held_keys["left control"])
        self.moving = any(held_keys[k] for k in "wasd") and not self.hidden and not self.entry
        self.running = self.moving and bool(held_keys["shift"]) and not self.sneaking
        self.player.speed = (0 if self.entry or self.hidden else 6.5 if self.running
                             else 1.8 if self.sneaking else 3.5)
        self.time_left -= time.dt
        total = self.cfg["seconds"]
        minutes = 18 * 60 + int((total - max(0, self.time_left)) / total * 240)
        self.clock_text.text = (f"{minutes // 60:02d}:{minutes % 60:02d}　第 {self.day} 天　{self.world.floor}　"
                                f"館員警告 {self.warnings}/3")
        self.goal_text.text = "目標：" + self.goal()
        self.update_prompt()
        if self.time_left <= 0:
            self.play("chime")
            self.show_hint("（叮咚）22:00，總圖閉館了。請攜帶隨身物品離館。", 3)
            self.end_day("又沒抓到他……明天再來。", color.rgba32(20, 20, 40, 255))
            return
        self.in_safe_zone = to_cell(self.player.position) in self.world.spec["safe"]
        self.update_noise()
        self.librarian.update()
        if self.roommate.active and not self.dead:
            self.roommate.update()
        self.scares.update()
        self.update_body()

    # ---------- 聲音、躲藏 ----------
    def update_noise(self):
        rate = (0.0 if self.sneaking else 0.45 if self.running else 0.03) if self.moving else -0.35
        self.noise = min(1.0, max(0.0, self.noise + rate * time.dt))
        if self.noise >= 1 and not self.in_safe_zone and not self.librarian.lookout:
            self.librarian.investigate(self.player.position)
            self.show_hint("館員好像聽到這邊有聲音，往這裡走過來了。", 2)
        self.noise_bar.scale_x = 0.3 * self.noise
        self.noise_bar.color = color.rgb32(200, 60, 40) if self.noise > 0.8 else color.rgb32(90, 90, 100)
        self.noise_label.text = "躲在桌子底下" if self.hidden else "聲音（Shift 跑步會變大）"

    def update_body(self):
        if self.moving:
            speed = 1.6 if self.running else 1.0
            self.bob += time.dt * 9 * speed
            self.step_timer -= time.dt * speed
            if self.step_timer <= 0:
                self.step_timer = 0.48
                self.play("step", volume=0.08 if self.sneaking else 0.6 if self.running else 0.35)
        eye = 0.6 if self.hidden else 1.2 if self.sneaking else 1.7
        self.player.camera_pivot.y += (eye + math.sin(self.bob) * 0.04 - self.player.camera_pivot.y) * min(1, time.dt * 10)

    def toggle_hide(self):
        if self.hidden:
            self.hidden = False
            self.show_hint("你從桌子底下爬出來。", 2)
            return
        spot = min(self.world.hides, key=lambda p: (p - self.player.position).length(), default=None)
        if spot is None or not self.near(spot, 1.9):
            self.show_hint("附近沒有可以躲的桌子。", 2)
            return
        self.hidden = True
        self.show_hint("你縮到桌子底下。館員和室友都看不到你。（C 出來）", 3)


app = Ursina(title="偷卷仔，給我站住！", borderless=False, development_mode=False)
font_path = find_font()
setup_font(font_path)
window.color = SKY
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
    if game.mini:
        game.mini.key(key)
        return
    if game.fight and key in ("e", "left mouse down"):
        game.hit()
        return
    if key == "escape" or (game.cleared and key == "enter"):
        game.to_lobby()
    elif key == "e" and not game.cleared and not game.fight:
        game.interact()
    elif key == "c" and not game.cleared and not game.fight:
        game.toggle_hide()


# 用一個空 Entity 掛每幀更新與按鍵處理，不依賴 __main__ 裡的全域函式
driver = Entity(update=game.update, input=handle_input)


if __name__ == "__main__":
    app.run()
