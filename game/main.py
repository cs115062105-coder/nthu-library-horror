"""痛扁偷卷室友—— 第一人稱 3D 搞笑潛行解謎。

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
                    held_keys, invoke, mouse, raycast, scene, time, window)

import sfx
from events import Scares
from menu import DIFFICULTIES, Lobby
from crowd import BAGS, HATS, JACKETS, Crowd, dress_outfit, random_outfit
from dialog import Dialog
from intro import Intro
from cutscene import Cutscene
from quiz import LOCKER_RIDDLES, pick as pick_quiz
from minimap import Minimap, bang_texture, triangle
from npc import Hunter, Librarian, Roommate, to_cell
from player import Player
from versus import DuoPanel
import fastops
from shading import light_scene, set_fog, update_camera
from ursina.shaders import unlit_shader
from world import ORDER, World, cell_pos

SETTINGS = Path.home() / ".tou_juan_settings.json"


def load_setting(key, default):
    try:
        import json
        return json.loads(SETTINGS.read_text()).get(key, default)
    except Exception:
        return default


def save_setting(key, value):
    try:
        import json
        data = json.loads(SETTINGS.read_text()) if SETTINGS.exists() else {}
        data[key] = value
        SETTINGS.write_text(json.dumps(data))
    except Exception:
        pass

MENU_SPOT = (7, 13)     # 大廳背景：1F 入口旁，望向圓形的知識集展區
MENU_LIBRARIAN = (9, 13)
SKY = color.rgb32(226, 226, 218)   # 白天的霧：遠處淡淡的米白色

NOTES = {
    "1": "（輕學區，室友常坐的位子）桌上刻著：「擺爛聯盟　永不讀書」。\n旁邊卻壓著一張今天的「預約取書」收據……\n去聯合櫃臺的電腦查查看他預約了什麼。",
    "2": "（2F 桌上的便條，室友的字）「電腦教室最裡面那台，密碼是學校在新竹建校那年。」\n下面又補一行：「……我為什麼要寫下來？」",
    "3": "一張計算紙，寫滿了微積分。最下面寫著：「不能讓他知道。」",
    "5": "（語言學習區，耳機還是熱的）隨手寫的紙條：\n「線代錄音 → 視聽區最裡面那台（螢幕亮著）」",
    "6": "（被撕下來的筆記本內頁）「清華書房展示櫃：三碼。\n第一碼＝錄音帶的嗶聲數，第二碼夾在『300 科學類』的書裡，\n第三碼在討論室白板上。裡面放的是……要給他的東西。」",
    "4": "（B1 入口桌上）你到底怎麼進來的？館員看到會哭。",
}
# 樓梯間的門鎖：(樓層, 方向) → (需要的東西, 沒有時的提示)。白天的樓梯大家都能走，只有這兩扇不行
LOCKS = {
    ("1F", "down"): ("b1", "B1 密集書庫：館員專用。（室友不可能在這裡）"),
    ("4F", "up"): ("phase2", "先在 4F 抓到室友再說！"),
    ("6F", "up"): ("7f", "7F 是行政中心，不對外開放。"),
}
READABLE = {
    "newspaper": "《清華新聞》頭條：「期中考週，總圖座位一位難求」\n副標：「有學生自稱『完全沒讀』，卻被拍到在 4F 讀到閉館」",
    "exhibit": "主題展「總圖的一天」\n18:00 晚餐人潮離開，是館內最安靜的四小時。\n館員提醒：館內請勿奔跑。",
}
CLUES = {
    "book": (1, "《物種原始》裡夾著一張便條：\n「第二碼：{d}」\n下面還寫著：「他一定想不到我在這裡。」"),
    "whiteboard": (2, "白板寫滿了微積分算式，角落圈著一個數字：{d}\n旁邊寫著：「讀書會成員：只有我。」"),
}
# 第二階段：5F、6F 的考試用書（書名, 題庫分類）
EXAM_BOOKS = {"calc": ("微積分 精選 500 題", "5F"), "linalg": ("線性代數 一次搞懂", "5F"), "prog": ("程式設計 考前衝刺", "6F")}
# 被繃帶室友抓到的懲罰：原本的書被沒收，要多找一本（依序加進來）。最後一個值是讀的時候考哪一類題目
EXTRA_BOOKS = {"phys": ("普通物理 歷屆考古", "6F", "calc"), "stat": ("機率與統計 重點整理", "5F", "calc"),
               "ds": ("資料結構 一本通", "6F", "prog")}
BOOKS = dict(EXAM_BOOKS, **{k: v[:2] for k, v in EXTRA_BOOKS.items()})
QUIZ_KIND = dict({"calc": "calc", "linalg": "linalg", "prog": "prog"}, **{k: v[2] for k, v in EXTRA_BOOKS.items()})
CAUGHT_LIMIT = 3     # 被繃帶室友抓到幾次就 GAME OVER
TRANSCRIPT = [
    ("旁白", "室友縮在地上求饒，書包裡滑出一張紙。"),
    ("你", "……這是什麼？期中考模擬考成績單？"),
    ("旁白", "微積分 98。線性代數 100。程式設計 A+。"),
    ("你", "（腦袋一片空白）……所以全宿舍只有我一個人在擺爛？"),
    ("室友", "你、你不要跟過來喔！我要上樓繼續讀……啊不是，我要回宿舍！"),
    ("你", "完了完了完了。我也要讀。可是絕對不能讓他知道。"),
    ("旁白", "第二階段：換你偷卷！上 5F、6F 找到 3 本考試用書，坐下來偷偷讀完。\n頭包繃帶的室友會在樓上巡，被他看到你在讀書就前功盡棄。"),
]
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
        set_fog(color.clear, 10, 100)      # 霧和相機位置放在場景根節點，先給預設值
        update_camera()
        self.read_notes = set()      # 跨天保留：讀過的筆記
        self.found = set()           # 跨天保留：已經找到的密碼位數
        self.items = set()           # 跨天保留：查到的線索
        self.locker_no = 1
        self.entry = None            # 輸入密碼的畫面
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
        self.floor_cache = {}      # 這一局蓋過的樓層（藏起來，不拆）
        self.prebuild, self.prebuild_wait = [], 0
        self.loading = Entity(parent=camera.ui, z=-0.9, enabled=False)
        Entity(parent=self.loading, model="quad", scale=(4, 2), color=color.rgb32(20, 18, 28))
        self.loading_text = Text(parent=self.loading, position=(0, 0.06, -0.03), origin=(0, 0), scale=1.6,
                                 color=color.rgb32(235, 228, 210))
        Entity(parent=self.loading, model="quad", position=(0, -0.05, -0.01), scale=(0.62, 0.035), color=color.rgb32(60, 56, 70))
        self.loading_bar = Entity(parent=self.loading, model="quad", origin=(-0.5, 0), position=(-0.3, -0.05, -0.02),
                                  scale=(0.0, 0.025), color=color.rgb32(226, 112, 42))
        self.in_safe_zone = False
        self.hidden = False
        self.minimap = Minimap()     # 右上角的小地圖，每換一層重畫
        self.load_floor("1F")
        self.player = Player(position=self.world.start, speed=4)
        self.player.cursor.visible = False
        self.player.unstick = self.nearest_open
        self.librarian = Librarian(self)
        self.roommate = Roommate(self)
        self.setup_audio()
        self.ui_left = Entity(parent=camera.ui)   # 貼著畫面左緣的介面，螢幕比例不同也不會被切掉
        self.hud_bg = Entity(parent=self.ui_left, model="quad", origin=(-0.5, 0.5), position=(0.02, 0.49),
                             scale=(1.25, 0.125), color=color.rgba32(255, 255, 255, 150), z=0.6)
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
        # 卡關提示：同一個步驟待太久、或錯太多次，就在小地圖和場景裡標出下一步要去哪
        self.stage = None
        self.stage_time = 0.0
        self.mistakes = 0
        self.helping = False
        self.bang = Entity(model="quad", texture=bang_texture(), scale=0.7, billboard=True, always_on_top=True,
                           shader=unlit_shader, enabled=False)
        self.edge_bang = Entity(parent=camera.ui, model="quad", texture=bang_texture(), scale=0.07, enabled=False)
        self.edge_arrow = Entity(parent=self.edge_bang, model=triangle(), color=color.rgb32(255, 205, 30), scale=0.6,
                                 double_sided=True)
        self.goal_bang = Entity(parent=self.ui_left, model="quad", texture=bang_texture(), position=(0.022, 0.413),
                                scale=0.03, enabled=False)
        self.dialog = Dialog()        # 跟路人、櫃臺對話和答題
        self.crowd = Crowd(self)      # 每層樓的路人
        self.hunter = Hunter(self)    # 第二階段在 5F、6F 巡邏的室友
        self.outfit = ("紅色", "黑色棒球帽", "紅色")   # 室友今天的穿著，每局重抽
        self.studied = set()          # 第二階段讀完的書
        self.required = list(EXAM_BOOKS)   # 這局要讀完的書（被抓會多一本）
        self.caught = 0               # 被繃帶室友抓到幾次
        self.reading = 0.0            # 正在偷讀書的倒數
        self.reading_book = None
        self.look_text = Text(parent=self.ui_left, position=(0.04, 0.385), scale=0.85, color=color.rgb32(40, 90, 150))
        self.intro = Intro(self)
        self.cut = Cutscene(self)    # 走樓梯、館員警告／請出去、被繃帶室友抓到的短動畫     # 開場動畫：每次打開遊戲第一次按「開始遊戲」時播
        self.intro_seen = False
        self.bob = 0.0
        self.step_timer = 0.0
        self.time_left = 0
        self.versus = None            # 雙人模式（versus.py）；單人時是 None
        self.apply_view()

    # ---------- 樓層 ----------
    def load_floor(self, name, came="up", fresh=False):
        """換到另一層。每層是 world.FLOORS 裡的一張格子圖。
        came 是玩家怎麼來的：往上走來的就出現在新樓層的「往下」樓梯口，反之亦然。
        使用者：每上一層樓黑畫面有點久 → 蓋過的樓層不拆，只是藏起來，下次回來直接打開（同一局內）。
        fresh=True（開新的一局）才把全部拆掉重蓋，東西回到原狀。"""
        cache = self.floor_cache
        if fresh:
            for w in cache.values():
                w.unload()
            cache.clear()
            self.world = None
        if self.world:
            self.world.hide()
        built = name not in cache
        if built:
            cache[name] = World(self.font_path, name)
        else:
            cache[name].show()
        self.world = cache[name]
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
        self.minimap.load(self.world)
        self.apply_view(built)   # 新蓋的才要套光影 shader

    def refresh_paths(self):
        """館員只走得到跟他出發點連在一起的走道（知識集圓形展區裡面那幾格走不進去），也不巡夜讀區。"""
        open_cells = self.world.walkable - self.world.spec["safe"]
        start = to_cell(self.world.monster_start)
        reach, todo = {start}, [start]
        while todo:
            c, r = todo.pop()
            for nxt in ((c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1)):
                if nxt in open_cells and nxt not in reach:
                    reach.add(nxt)
                    todo.append(nxt)
        self.librarian_walkable = reach

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
        self.hide_help()
        self.update_prompt(off=True)
        self.goal_text.text = ""
        self.play("step")
        session = self.session

        def arrive():           # 樓梯動畫播完（畫面已經黑了）才換樓層
            if session != self.session:
                return
            self.flash.color = color.rgba32(0, 0, 0, 255)
            self.load_floor(stair["target"], came=direction)
            self.enter_floor(quiet=True)
            self.flash_fade()
            # 使用者：走到那層時要看到真的樓層畫面 → 從這層真的樓梯門走出來
            self.cut.play("arrive", on_done=self.floor_hint, came=direction)
        self.cut.play("stairs", on_done=arrive, direction=direction, target=stair["target"])

    # ---------- 卡關提示 ----------
    def stage_id(self):
        """現在卡在哪一步（跟在哪一層無關，換樓層不會重算時間）。"""
        if "phase2" in self.items:
            picked = sum(f"book_{b}" in self.items for b in self.required)
            return f"phase2-{picked}-{len(self.studied)}"
        for key in ("trail4", "trail3", "trail2", "locker_known"):
            if key in self.items:
                return key
        return "start"

    def mistake(self):
        """做錯一次（開錯櫃子、密碼錯、太早來、被室友掙脫……）。"""
        self.mistakes += 1

    def help_target(self):
        """下一步要去的位置；目標在別層就回傳往那層的樓梯。"""
        items, w = self.items, self.world
        if "phase2" in items:
            want, target = self.phase2_target()
        elif "trail4" in items:
            want = "4F"
            target = self.roommate.position if self.roommate.active else None
        elif "trail3" in items:
            want, target = "3F", next((t["pos"] for t in w.interactables if t["kind"] == "tape"), None)
        elif "trail2" in items:
            want, target = "2F", next((t["pos"] for t in w.interactables if t["kind"] == "lab_pc"), None)
        elif "locker_known" in items:
            want = "1F"
            target = next((t.get("look", t["pos"]) for t in w.interactables
                           if t["kind"] == "locker" and t.get("data") == self.locker_no), None)
        else:
            want, target = "1F", next((t["pos"] for t in w.interactables if t["kind"] == "counter_pc"), None)
        if w.floor != want:
            way = "up" if ORDER.index(want) > ORDER.index(w.floor) else "down"
            stair = w.stairs.get(way)
            return stair["pos"] if stair else None
        return target

    def phase2_target(self):
        """第二階段：還沒拿的書在哪層哪裡；拿了沒讀就去最近的桌子。"""
        w = self.world
        for name in self.required:
            floor = BOOKS[name][1]
            if f"book_{name}" not in self.items:
                if w.floor == floor:
                    return floor, next((t.get("look", t["pos"]) for t in w.interactables
                                        if t["kind"] == "exam_book" and t["data"] == name), None)
                return floor, None
        if w.floor in ("5F", "6F") and w.hides:
            return w.floor, min(w.hides, key=lambda p: (p - self.player.position).length())
        return "5F", None

    def update_help(self):
        stage = self.stage_id()
        if stage != self.stage:            # 進到下一步：重新計時、錯誤歸零、提示收起來
            self.stage, self.stage_time, self.mistakes = stage, 0.0, 0
            self.helping = False
        self.stage_time += time.dt
        if not self.helping and (self.stage_time > self.cfg.get("help_after", 90) or self.mistakes >= 2):
            self.helping = True
            self.play("chime", volume=0.4)
            self.show_hint("卡住了嗎？跟著黃色驚嘆號走（小地圖上也有）。", 4)
        target = self.help_target() if self.helping else None
        self.minimap.mark(target)
        self.goal_bang.enabled = self.helping
        self.bang.enabled = target is not None
        self.edge_bang.enabled = False
        if target is not None:
            self.bang.position = target + Vec3(0, 2.3 + 0.12 * math.sin(time.time() * 3), 0)
            to = target - self.player.position
            to.y = 0
            self.bang.scale = max(0.7, to.length() * 0.05)      # 遠的時候放大一點，才看得到
            fwd = camera.forward
            fwd = Vec3(fwd.x, 0, fwd.z).normalized()
            if to.length() > 0.5:
                to = to.normalized()
                ang = math.degrees(math.atan2(fwd.x * to.z - fwd.z * to.x, fwd.dot(to)))   # 正的在左邊
                if abs(ang) > 38:     # 不在畫面裡：在畫面左右邊緣放一個驚嘆號和箭頭
                    side = -1 if ang > 0 else 1
                    self.edge_bang.enabled = True
                    self.edge_bang.position = (side * (window.aspect_ratio / 2 - 0.09), 0.02 * math.sin(time.time() * 5))
                    self.edge_arrow.position = (side * 0.85, 0)
                    self.edge_arrow.rotation_z = 90 * side

    def hide_help(self):
        self.bang.enabled = self.goal_bang.enabled = self.edge_bang.enabled = False
        self.minimap.mark(None)

    # ---------- 劇情：路人、線索、第二階段 ----------
    def clue_text(self):
        """左上角：目前查到的室友穿著。"""
        jacket, hat, bag = self.outfit
        got = lambda key, v: v if key in self.items else "？"
        return (f"室友今天：外套 {got('clue_jacket', jacket)}　帽子 {got('clue_hat', hat)}　"
                f"書包 {got('clue_bag', bag)}")

    def anchor(self, kind, data=None):
        it = next((t for t in self.world.interactables if t["kind"] == kind and (data is None or t.get("data") == data)), None)
        return it["pos"] if it else self.world.start

    def talkers(self):
        """這層樓會主動找你講話的人：說什麼、出什麼題、答對給什麼。"""
        floor, phase2 = self.world.floor, "phase2" in self.items
        out = []

        def quiz_talk(n, key, intro, kind, reward_lines, done_line):
            if key in self.items:
                self.dialog.talk([(n.who, done_line)])
                return

            def right():
                self.items.add(key)
                n.set_mark("")
                self.play("page")
                self.dialog.talk([(n.who, line) for line in reward_lines()])

            def wrong():
                self.mistake()
                self.dialog.talk([(n.who, "哈哈，答錯了。再想想，想好再來找我。")])
            self.dialog.talk([(n.who, line) for line in intro], quiz=pick_quiz(kind), on_right=right, on_wrong=wrong)

        if floor == "1F" and not phase2:
            out.append(dict(who="學生", anchor=self.anchor("locker", self.locker_no), label="跟同學說話",
                            action=lambda n: quiz_talk(
                                n, "clue_bag",
                                ["你在找人？剛剛有個人鬼鬼祟祟地在自助取書櫃拿書，還一直回頭看。",
                                 "他背的書包我記得很清楚……想知道？先猜猜我的謎語。"], "riddle",
                                lambda: [f"他背一個{self.outfit[2]}的書包！拿了三本微積分就往樓上衝。"],
                                f"就是那個背{self.outfit[2]}書包的人。加油啊！")))
        elif floor == "2F" and not phase2:
            out.append(dict(who="教授", anchor=self.anchor("lab_pc"), label="跟教授說話",
                            action=lambda n: quiz_talk(
                                n, "prof_hint",
                                ["同學，你也是來找報告文獻的？現在的學生，報告都拖到最後一天。",
                                 "考你一題清華的常識，答對我就告訴你一件事。"], "nthu",
                                lambda: ["不錯！剛剛有個學生在電腦教室最裡面那台電腦，一直在輸入密碼。",
                                         "我瞄到他在試「建校那一年」……現在的學生，密碼都設這種。"],
                                "電腦教室最裡面那台，密碼跟建校那年有關。快去吧。")))
        elif floor == "3F" and not phase2:
            out.append(dict(who="市民", anchor=self.anchor("tape"), label="跟阿伯說話",
                            action=lambda n: quiz_talk(
                                n, "clue_jacket",
                                ["少年仔，你在找人喔？剛剛有個同學在那邊聽錄音帶，聽得好認真。",
                                 "阿伯考你一個謎語，猜對我就跟你說他穿什麼。"], "riddle",
                                lambda: [f"他穿一件{self.outfit[0]}的外套，聽完錄音帶就往 4F 跑了。"],
                                f"穿{self.outfit[0]}外套的那個啦，往 4F 去了。")))
        elif floor == "4F" and not phase2:
            out.append(dict(who="學生", anchor=self.world.stairs["down"]["pos"], label="跟同學說話", mark="…",
                            action=lambda n: self.dialog.talk([
                                (n.who, "今天 4F 好多人在讀書，全部都穿得差不多……你在找誰？"),
                                ("你", self.clue_text().replace("室友今天：", "我在找一個人：")),
                                (n.who, "那你要看清楚喔，認錯人館員會過來罵人的。")])))
        elif floor in ("5F", "6F") and phase2:
            out.append(dict(who="學生", anchor=self.world.stairs["down"]["pos"], label="跟同學說話",
                            action=lambda n: quiz_talk(
                                n, f"tip_{floor}",
                                ["……你也是來偷偷讀書的吧？我懂。頭包繃帶那個人一直在找你喔。",
                                 "考你一題，答對我就告訴你考試用書放在哪。"], "prog",
                                lambda: self.book_tip(),
                                "書架那邊有發光的書，就是你要的。小心繃帶男。")))
        return out

    def book_tip(self):
        self.helping = True      # 直接開黃色驚嘆號，標出書的位置
        left = [BOOKS[b][0] for b in self.required if f"book_{b}" not in self.items]
        if not left:
            return ["你書都拿齊了？那就找張桌子坐下來讀吧，記得躲著繃帶男。"]
        return [f"你要的是《{left[0]}》吧？我幫你在地圖上標起來了，跟著黃色驚嘆號走。"]

    def place_books(self):
        """第二階段：在 5F、6F 的書架上放發光的考試用書。"""
        if "phase2" not in self.items:
            return
        w = self.world
        placed = {t["data"] for t in w.interactables if t["kind"] == "exam_book"}
        names = [b for b in self.required if BOOKS[b][1] == w.floor and f"book_{b}" not in self.items and b not in placed]
        if not names:
            return
        rng = random.Random(hash((self.code, w.floor)))
        faces = []
        for (c, r) in sorted(w.walkable):
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if w.char(c + dc, r + dr) == "B":
                    faces.append(((c, r), (dc, dr)))
        rng.shuffle(faces)
        chosen = []
        for cell, d in faces:
            if all((cell_pos(*cell) - cell_pos(*o)).length() > 16 for o, _ in chosen):
                chosen.append((cell, d))
            if len(chosen) == len(names):
                break
        for name, (cell, (dc, dr)) in zip(names, chosen):
            p = cell_pos(*cell)
            look = p + Vec3(dc, 0, -dr) * 0.75 + Vec3(0, 1.25, 0)
            book = Entity(model="cube", position=look, scale=(0.08, 0.3, 0.22) if dc else (0.22, 0.3, 0.08),
                          color=color.rgb(0.6, 1.0, 1.6))
            glow = Entity(model="quad", position=look + Vec3(0, 0.45, 0), billboard=True, scale=0.35,
                          texture=bang_texture(), color=color.rgb(1.2, 1.2, 1.2))
            w.owned += [book, glow]
            w.interactables.append(dict(kind="exam_book", pos=p, look=look, data=name, ents=(book, glow)))

    def take_book(self, thing):
        name = thing["data"]
        if f"book_{name}" in self.items:
            return
        self.items.add(f"book_{name}")
        for e in thing["ents"]:
            e.enabled = False
        self.world.interactables.remove(thing)
        self.play("page")
        self.show_hint(f"拿到《{BOOKS[name][0]}》！找張桌子坐下來偷偷讀（按 E）。", 3)

    def unread(self):
        return [b for b in self.required if f"book_{b}" in self.items and b not in self.studied]

    def study(self):
        books = self.unread()
        if not books or self.reading > 0:
            return
        self.reading_book = books[0]
        self.reading = 3.0
        self.player.speed = 0
        self.show_hint(f"你翻開《{BOOKS[books[0]][0]}》，偷偷讀了起來……（別被室友看到）", 3)

    def finish_reading(self):
        name = self.reading_book
        kind = QUIZ_KIND[name]

        def right():
            self.studied.add(name)
            self.play("page")
            if all(b in self.studied for b in self.required):
                self.dialog.talk([("你", f"……讀完了。{len(self.required)} 本都讀完了。"), ("旁白", "期中考當天。")],
                                 on_done=self.ending)
            else:
                self.show_hint(f"讀懂了！（{len(self.studied)}/{len(self.required)}）", 3)

        def wrong():
            self.mistake()
            self.noise = 1.0
            self.show_hint("算錯了！你翻書翻得太用力，整層都聽到了。（再讀一次）", 3)
        self.dialog.talk([("旁白", f"《{BOOKS[name][0]}》的習題：")], quiz=pick_quiz(kind),
                         on_right=right, on_wrong=wrong)

    def grab_wrong(self, npc):
        self.mistake()
        self.show_hint("認錯人了！那位同學嚇了一跳：「你誰啊？」", 3)
        npc.mode = "read"
        self.later(lambda: setattr(npc, "mode", "decoy"), 6)
        self.warn()

    def hunter_spotted(self):
        """被繃帶室友抓到：播一小段動畫（他衝過來、把書搶走、把你痛扁一頓），懲罰是多找一本書；抓到 CAUGHT_LIMIT 次就 GAME OVER。"""
        if self.dead:
            return
        self.dead = True
        self.spotted += 1
        self.caught += 1
        self.reading = 0.0
        self.play("sting", volume=0.35)

        def after():
            self.flash.color = color.rgba32(30, 20, 20, 255)
            if self.caught >= CAUGHT_LIMIT:     # 動畫：你被打趴在地上，室友舉著書，GAME OVER
                self.flash_fade()
                self.cut.play("gameover", on_done=self.game_over)
                return
            extra = next((b for b in EXTRA_BOOKS if b not in self.required), None)
            if extra:
                self.required.append(extra)
                why = (f"被室友抓到了！（{self.caught}/{CAUGHT_LIMIT}）書被沒收，"
                       f"現在還要多讀一本《{BOOKS[extra][0]}》（在 {BOOKS[extra][1]}）。")
            else:
                why = f"被室友抓到了！（{self.caught}/{CAUGHT_LIMIT}）"
            self.dead = False
            self.new_day(why=why)
            self.later(self.flash_fade, 0.4)
        self.cut.play("caught", on_done=after)

    def game_over(self):
        self.update_prompt(off=True)
        self.hide_help()
        self.cleared = True
        self.dead = False
        self.goal_text.text = ""
        self.hunter.hide()
        self.player.enabled = False
        self.flash.color = color.rgba32(20, 10, 10, 120)
        self.note_bg.enabled = True
        self.note_text.text = (f"—— GAME OVER ——\n\n你被室友抓到 {self.caught} 次。\n"
                               "他把你的考試用書全部沒收，還在宿舍門口貼了一張「偷卷者」。\n\n"
                               f"{self.difficulty}·第 {self.day} 天·館員警告 {self.total_warnings} 次\n按 Enter 回到大廳")

    def demo_jump(self, key):
        """Demo 快速跳關（使用者 pitch 用）：F1 線索都拿到、直接到 4F 認室友；F2 直接進第二階段的 5F。"""
        if self.dialog.active or self.entry:
            return
        self.items.update({"locker_known", "trail2", "trail3", "trail4", "clue_hat", "clue_bag", "clue_jacket"})
        if key == "f2":
            self.items.add("phase2")
            self.roommate.hide()
            self.player.mouse_sensitivity = Vec2(40, 40)
        target = "4F" if key == "f1" else "5F"
        self.flash.color = color.rgba32(0, 0, 0, 255)

        def go():
            self.load_floor(target, came="up")
            self.enter_floor(quiet=True)
            self.flash_fade()
            self.show_hint("（Demo 跳關）" + ("線索都到手了：在 4F 的人群裡認出室友！" if key == "f1"
                                             else "第二階段：在 5F、6F 找發光的考試用書，小心繃帶室友！"), 4)
        self.later(go, 0.05)

    def start_phase2(self):
        def go():
            self.items.add("phase2")
            self.roommate.hide()
            self.cleared = False
            self.player.mouse_sensitivity = Vec2(40, 40)
            self.spawn_roommate()
            self.show_hint("第二階段：上 5F、6F 找 3 本考試用書，坐下偷偷讀。小心頭包繃帶的室友！", 5)
        self.dialog.talk(TRANSCRIPT, on_done=go, lock=1.5)   # 剛痛扁完還在狂按 E，等一下才吃按鍵

    # ---------- 大廳與開局 ----------
    def start(self, cfg, name, after_intro=False):
        # 使用者：不管選哪個難度，每次開始都要播開場動畫（Esc 可以跳過）。測試腳本把 intro_seen 設成 True 就不播
        if not after_intro and not self.intro_seen:
            self.state = "intro"
            self.intro.play(on_done=lambda: self.start(cfg, name, after_intro=True))
            return
        self.session += 1
        self.cfg, self.difficulty = cfg, name
        self.read_notes.clear()
        self.found.clear()
        self.items.clear()
        self.code = "".join(random.choice("123456789") for _ in range(3))   # 每局密碼都不同
        self.locker_no = random.randint(1, 6)
        self.outfit = random_outfit(random)
        dress_outfit(self.roommate, self.outfit)
        specs = random.random() < 0.45          # 室友今天有沒有戴眼鏡也是隨機的（路人也有一半戴）
        self.roommate.set_glasses(specs)
        self.hunter.set_glasses(specs)
        self.studied.clear()
        self.required = list(EXAM_BOOKS)
        self.caught = 0
        self.reading = 0.0
        self.stage = None
        self.day = 1
        self.total_warnings = self.spotted = 0
        self.cleared = False
        self.tape_playing = False
        self.load_floor("1F", came="start", fresh=True)   # 重蓋一次，東西都回到原狀
        # 使用者：第一次上樓也不要等 → 開局先把 2F–6F 都蓋好藏起來，畫面上顯示進度
        self.prebuild = ["2F", "3F", "4F", "5F", "6F"]
        self.prebuild_wait = 1
        self.state = "loading"
        self.player.enabled = False
        self.loading.enabled = True
        self.loading_text.text = "準備圖書館中……"

    def start_versus(self, net, role, seed, mode="hide"):
        """雙人模式：整棟 1F–6F 都蓋好（跟單人一樣先蓋完藏起來），路人和對方的身體由 versus.py 處理。"""
        from versus import Versus
        self.session += 1
        self.items.clear()
        self.cleared = self.dead = False
        self.fight = None
        self.versus = Versus(self, net, role, seed, mode)
        self.roommate.hide()
        self.hunter.hide()
        self.crowd.clear()
        self.librarian.root.enabled = False
        self.load_floor("1F", came="start", fresh=True)
        self.prebuild = ["2F", "3F", "4F", "5F", "6F"]
        self.prebuild_wait = 1
        self.state = "loading"
        self.player.enabled = False
        self.loading.enabled = True
        self.loading_text.text = "雙人模式：準備整棟圖書館中……"

    def begin_versus(self):
        self.hide_note()
        self.flash_fade()
        self.state = "play"
        self.noise_bg.enabled = False
        self.hud_bg.enabled = True
        self.minimap.show(True)
        self.player.enabled = True
        self.player.mouse_sensitivity = Vec2(40, 40)
        self.versus.build()

    def step_prebuild(self):
        """每一幀蓋一層（中間空一幀讓進度字先畫出來），全部蓋完才開始這一局。"""
        if self.prebuild_wait > 0:
            self.prebuild_wait -= 1
            return
        if self.prebuild:
            name = self.prebuild.pop(0)
            if name not in self.floor_cache:
                w = World(self.font_path, name)
                w.set_code(self.code)
                light_scene(w.owned)
                fastops.unlist_static(w.owned)
                w.hide()
                self.floor_cache[name] = w
            done = 6 - len(self.prebuild)
            nxt = self.prebuild[0] if self.prebuild else ""
            self.loading_text.text = (f"準備圖書館中……　{done}/6" + (f"\n正在蓋 {nxt}" if nxt else ""))
            self.loading_bar.scale_x = 0.6 * done / 6
            self.prebuild_wait = 1
            return
        self.loading.enabled = False
        set_fog(SKY, 28.0, 110.0)
        if self.versus:
            self.begin_versus()
        else:
            self.begin_game()

    def begin_game(self):
        self.hide_note()
        self.flash_fade()
        self.state = "play"
        self.noise_bg.enabled = self.hud_bg.enabled = True
        self.minimap.show(True)
        self.player.enabled = True
        self.new_day(first=True)

    def to_lobby(self):
        if self.versus:
            self.versus.stop()
            self.versus = None
        if self.cut.active:          # 動畫播到一半回大廳：直接收掉，不跑播完要做的事
            self.cut.on_done = None
            self.cut.finish()
        self.session += 1
        self.state = "menu"
        self.prebuild = []
        self.loading.enabled = False
        self.dead = False
        for t in (self.clock_text, self.goal_text, self.hint, self.note_text):
            t.text = ""
        self.hint_bg.enabled = False
        self.note_bg.enabled = False
        self.hide_help()
        self.dialog.root.enabled = False
        self.crowd.clear()
        self.hunter.hide()
        self.look_text.text = ""
        self.update_prompt(off=True)
        self.flash_fade()
        self.close_entry()
        self.end_fight_ui()
        self.scares.reset()
        self.noise, self.hidden = 0.0, False
        self.noise_bar.scale_x, self.noise_label.text = 0, ""
        self.noise_bg.enabled = self.hud_bg.enabled = False
        self.minimap.show(False)
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
    def apply_view(self, built=True):
        """白天：燈全亮，只留一層很淡的霧讓遠處柔和一點。"""
        if built:
            light_scene(self.world.owned if getattr(self, "_lit_once", False) else None)   # 新蓋的這層換成有光影的 shader
            self._lit_once = True
            fastops.unlist_static(self.world.owned)   # 靜態的東西不用每一幀被引擎掃
        set_fog(SKY, 28.0, 110.0)         # 霧設在場景根節點，大家一起繼承（不用逐個物件設）

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
        # 背景音樂（使用者給的 the_mountain-retro-game）：一直循環；有重要音效時（走路聲除外）自動調小
        self.bgm_volume = load_setting("bgm_volume", 0.5)
        self.bgm_duck_until = 0.0
        self.bgm_level = 1.0
        self.bgm = None
        self.bgm_next = 0.0          # 下一次開始放音樂的時間（使用者：偶爾也要有沒音樂的時候）
        try:
            self.bgm = Audio(Path(__file__).parent / "music" / "bgm.ogg", loop=False, autoplay=False,
                             volume=self.bgm_volume)
        except Exception as e:
            print("背景音樂載入失敗：", e)
        Entity(update=self.update_bgm, ignore_paused=True)

    def play(self, name, volume=None):
        s = self.sounds.get(name)
        if s:
            if volume is not None:
                s.volume = volume
            s.play()
            if name not in ("step", "hum"):          # 重要音效：背景音樂先讓開
                try:
                    length = float(s.length) or 1.0
                except Exception:
                    length = 1.0
                import time as _t
                self.bgm_duck_until = max(self.bgm_duck_until, _t.time() + min(length, 4.0) + 0.5)

    def update_bgm(self):
        """背景音樂音量：重要音效播放時降到 25%，播完再慢慢回來。"""
        if not self.bgm:
            return
        import time as _t
        now = _t.time()
        if now >= self.bgm_next:     # 放完一整首（約 1 分 48 秒）之後安靜 25–60 秒，只剩冷氣聲，再重新放
            self.bgm.play()
            try:
                length = float(self.bgm.length) or 109.0
            except Exception:
                length = 109.0
            self.bgm_next = now + length + random.uniform(25, 60)
        target = 0.25 if _t.time() < self.bgm_duck_until else 1.0
        rate = 6.0 if target < self.bgm_level else 1.2          # 壓下去快、回來慢
        self.bgm_level += (target - self.bgm_level) * min(1.0, time.dt * rate)
        self.bgm.volume = self.bgm_volume * self.bgm_level

    def set_bgm_volume(self, v, show=False):
        self.bgm_volume = max(0.0, min(1.0, round(v, 2)))
        save_setting("bgm_volume", self.bgm_volume)
        if show:
            self.show_hint(f"音樂音量 {int(self.bgm_volume * 100)}%（- / = 調整）", 1.5)

    # ---------- 一天 ----------
    def enter_floor(self, quiet=False):
        """走進一層樓：時間繼續走，只是重設這層的館員和室友。"""
        self.place_player()
        self.librarian.reset(self.world.monster_start)
        self.spawn_roommate()
        self.scares.reset()
        self.dead = False
        if not quiet:
            self.floor_hint()

    def floor_hint(self):
        msg = {"1F": "1F。入館閘門旁人來人往，櫃臺的館員抬頭看了你一眼。",
               "2F": "2F。期刊區很安靜，大家都在假裝自己很認真。",
               "3F": "3F。視聽區傳來線性代數的錄音……這聲音好熟。",
               "4F": "4F。一整層的中文書。空氣裡有一股「偷卷」的味道。",
               "5F": "5F。中文圖書 500–999，研究小間裡每個人都在埋頭苦讀。",
               "6F": "6F。西文圖書區，安靜到聽得見翻頁聲。",
               "B1": "B1。你怎麼進來的？"}.get(self.world.floor, f"{self.world.floor}。")
        if self.world.floor == "4F" and self.roommate.active:
            msg += "\n這層坐滿了讀書的同學。照線索認出室友，趁他低頭時靠近！"
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
            msg = ("18:00。你抱著逾期的書走進總圖。先去左邊的櫃臺還書，\n"
                   "順便查查室友在搞什麼。頭上有「？」的路人可以問線索。")
        else:
            msg = f"{why}\n第 {self.day} 天 18:00，你又來到總圖 {self.world.floor}。查到的線索都還記得。"
        self.show_hint(wrap(msg, 26), 6)

    def place_player(self):
        self.player.position = self.arrival + Vec3(0, 0.1, 0)
        self.player.rotation_y = self.arrival_rot
        self.player.camera_pivot.rotation_x = 0

    def spawn_roommate(self):
        """室友和這層的路人。第一階段室友坐在 4F（旁邊坐滿長得很像的同學）；第二階段他在 5F、6F 巡邏。"""
        floor, phase2 = self.world.floor, "phase2" in self.items
        taken = []
        self.hunter.hide()
        if floor == "4F" and "trail4" in self.items and not phase2:
            self.roommate.spawn(self.world, self.player.position)
            taken = [self.roommate.spot[0]]
        else:
            self.roommate.hide()
        if phase2 and floor in ("5F", "6F"):
            far = [c for c in self.librarian_walkable if (cell_pos(*c) - self.player.position).length() > 14]
            if far:
                self.hunter.spawn(cell_pos(*random.choice(sorted(far))))
        crowd = {"1F": (9, 9), "2F": (7, 8), "3F": (6, 7), "4F": (6, 4), "5F": (6, 8), "6F": (6, 8)}.get(floor, (0, 0))
        self.crowd.spawn(self.world, self.talkers(), walkers=crowd[0], readers=crowd[1], taken=taken)
        if self.roommate.active:
            self.crowd.seat_decoys(self.world, self.roommate, self.outfit)
        self.place_books()

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
        if self.dead or self.state != "play":
            return
        self.warnings += 1
        self.total_warnings += 1
        self.play("shh")
        if self.warnings >= 3:      # 動畫：館員在大門口指著外面，你垂頭喪氣走出去
            self.dead = True

            def out():
                self.dead = False
                self.new_day(why="你被館員請出了圖書館……")
                self.later(self.flash_fade, 0.4)

            def go():               # 先黑畫面換到 1F（隔天也從大門口重新進來），在真的出入口演
                if self.world.floor != "1F":
                    self.load_floor("1F", came="start")
                self.arrival, self.arrival_rot = self.world.start, 90
                self.librarian.reset(self.world.monster_start)
                self.spawn_roommate()
                self.flash_fade()
                self.cut.play("expel", on_done=out)
            self.update_prompt(off=True)
            self.hide_help()
            self.flash.color = color.rgba32(0, 0, 0, 255)
            self.later(go, 0.05)
            return
        line = "館內請勿奔跑！" if self.running else "請保持安靜！"
        text = f"館員：「噓——同學，{line}」（警告 {self.warnings}/3）"
        if (self.librarian.root.position - self.player.position).length() < 15:
            self.cut.play("warn", on_done=lambda: self.show_hint(text, 2), line=text)   # 動畫：館員轉過來搖手指
        else:
            self.show_hint(text, 3)

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
        self.fight_line.text = "室友：「等、等一下！我可以解釋！」"
        self.hp_bg.enabled = self.hp_bar.enabled = True
        self.hp_bar.scale_x = 0.6
        self.play("sting", volume=0.4)

    def hit(self):
        f = self.fight
        f["hp"] -= 1
        f["hits"] += 1
        f["shake"] = 0.15
        self.play("punch")
        self.hp_bar.scale_x = 0.6 * max(0, f["hp"]) / self.cfg["hits"]
        if f["hits"] % 4 == 1:
            self.fight_line.text = "室友：「" + random.choice(FIGHT_LINES) + "」"
        if f["hp"] <= 0:
            self.end_fight_ui()
            self.start_phase2()

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
            self.mistake()
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
        if self.versus:
            return self.versus.targets()
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
        out += self.crowd.targets()
        if "phase2" in self.items and self.unread() and self.world.floor in ("5F", "6F"):
            for p in self.world.hides:
                out.append((p + Vec3(0, 0.8, 0), p, "坐下來偷偷讀書", self.study))
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
        return {"read": "閱讀", "counter_pc": "到櫃臺還書", "lab_pc": "使用電腦", "tape": "聽錄音帶",
                "case": "打開展示櫃", "exam_book": "拿這本書"}.get(kind, "查看")

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
            if "locker_known" in self.items:
                self.show_note(self.reservation())
                return

            def right():
                self.items.add("locker_known")
                self.show_note(self.reservation())

            def wrong():
                self.mistake()
                self.dialog.talk([("櫃臺館員", "……同學，你真的有來過圖書館嗎？再想想看。")])
            self.dialog.talk([("你", "還書。這三本……逾期了一點點。（為了報告借的參考文獻）"),
                              ("櫃臺館員", "逾期三天喔。好，已經還了。還有什麼事嗎？"),
                              ("你", "那個……可以幫我查我室友今天預約了什麼書嗎？我要找他。"),
                              ("櫃臺館員", "查別人的預約？不行喔……除非你先答對這題館規，證明你是好讀者。")],
                             quiz=pick_quiz("rule"), on_right=right, on_wrong=wrong)
        elif kind == "exam_book":
            self.take_book(thing)
        elif kind == "locker":
            if data != self.locker_no:
                self.show_hint(f"A{data:02d}：別人的書，不要亂開。", 2)
                self.mistake()
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
                self.mistake()
            else:
                self.open_entry("電腦教室　登入", "密碼提示：本校在新竹建校的那一年", 4, self.lab_login)
        elif kind == "tape":
            if "trail3" not in self.items:
                self.show_hint("一台還在播的錄音機。這是誰的？", 2)
                self.mistake()
            else:
                self.play_tape()
        elif kind == "case":
            if "notes" in self.items:
                self.show_note("展示櫃已經空了。筆記在你書包裡。")
            else:
                self.open_entry("清華書房　展示櫃", f"三碼密碼鎖　你記得的：{self.code_hint()}", 3, self.case_open)

    def reservation(self):
        return (f"預約取書紀錄\n讀者：陳○○（你的室友）\n書名：《微積分　精選 500 題》等 3 本\n"
                f"取書櫃：A0?　櫃號提示：{LOCKER_RIDDLES[self.locker_no]}\n……說好的擺爛呢？")

    def lab_login(self, code):
        if code != "1956":
            self.show_hint("密碼錯誤。", 2)
            self.mistake()
            return
        self.items.add("trail3")
        self.items.add("clue_hat")
        self.show_note("登入成功。室友的搜尋紀錄：\n「怎麼偷讀書不被室友發現」「3F 視聽區 線代錄音」\n"
                       f"雲端相簿最新一張：今天的自拍，戴著{self.outfit[1]}（臉用貼圖遮住了）")

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
        self.later(done, 2.5 + n * 0.6)

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
        if "phase2" in items:
            missing = [b for b in self.required if f"book_{b}" not in items]
            n = len(self.required)
            if self.unread():
                return f"找張桌子坐下，偷偷讀《{BOOKS[self.unread()[0]][0]}》（{len(self.studied)}/{n}）"
            if missing:
                return f"到 {BOOKS[missing[0]][1]} 找《{BOOKS[missing[0]][0]}》（書架上發光的那本，{len(self.studied)}/{n}）"
            return "讀完了！"
        if "trail4" in items:
            if floor != "4F":
                return "室友在 4F 中文書區！從樓梯間上去"
            extra = "" if "notes" in items else "（清華書房的展示櫃好像藏著什麼）"
            return f"從一堆讀書的同學裡認出室友，趁他低頭時靠近按 E 抓住他{extra}"
        if "trail3" in items:
            return "到 3F 視聽區最裡面那台（螢幕亮著）聽錄音帶" if floor == "3F" else "上 3F，找視聽區還在播的那台錄音機"
        if "trail2" in items:
            return ("登入電腦教室最裡面那台電腦（密碼提示在校史展示區）" if floor == "2F"
                    else "上 2F，去室友預約的電腦教室")
        if floor != "1F":
            return "線索在 1F：回去查室友今天預約了什麼"
        if "locker_known" in items:
            return f"到北邊的自助取書區，打開謎語說的那一櫃：「{LOCKER_RIDDLES[self.locker_no]}」"
        return "先到左邊的聯合櫃臺還書，順便查室友的預約"

    def ending(self):
        self.update_prompt(off=True)
        self.hide_help()
        self.cleared = True
        self.goal_text.text = ""
        self.roommate.hide()
        self.player.enabled = False
        self.play("page")
        self.note_bg.enabled = True
        if "notes" in self.items:
            story = ("成績公布：你 92，他 100。他翻出那本展示櫃裡的筆記：\n「這本來就是要給你的。我怕你被當，才偷偷讀。」\n"
                     "你們決定期末不擺爛了，一起去總圖。\n\n—— 真結局：偷卷聯盟 ——")
        else:
            story = ("成績公布：你 85，他 100。\n兩個人在宿舍對看三秒，同時大喊：「你偷卷！」\n"
                     "擺爛聯盟，正式解散。\n\n—— 結局：大家都在偷卷 ——")
        self.note_text.text = (f"{story}\n{self.difficulty}·第 {self.day} 天·被室友發現 {self.spotted} 次·"
                               f"館員警告 {self.total_warnings} 次\n按 Enter 回到大廳")

    def hide_note(self):
        self.note_text.text = ""
        self.note_bg.enabled = False

    def update(self):
        update_camera()
        self.ui_left.x = -window.aspect_ratio / 2
        if self.state == "loading":
            self.step_prebuild()
            return
        if self.versus:
            if self.state in ("play", "loading_vs"):
                self.versus.update()
            return
        if self.state != "play" or self.cleared or self.dead:
            return
        self.minimap.update(self.player, self.librarian)
        if self.fight:
            self.update_prompt(off=True)
            self.update_fight()
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
                                f"館員警告 {self.warnings}/3"
                                + (f"　被室友抓 {self.caught}/{CAUGHT_LIMIT}" if "phase2" in self.items else ""))
        self.goal_text.text = "目標：" + self.goal()
        self.look_text.text = "" if "phase2" in self.items else self.clue_text()
        self.update_help()
        self.crowd.update()
        if self.dialog.active:
            if self.note_bg.enabled:
                self.hide_note()
            self.update_prompt(off=True)
            self.player.speed = 0
            return
        if self.reading > 0:
            self.reading -= time.dt
            self.player.speed = 0
            self.player.camera_pivot.y += (1.1 - self.player.camera_pivot.y) * min(1, time.dt * 8)
            if self.hunter.active:
                self.hunter.update()
            self.librarian.update()
            if self.reading <= 0 and not self.dead:
                self.finish_reading()
            return
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
        if self.hunter.active and not self.dead:
            self.hunter.update()
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


app = Ursina(title="痛扁偷卷室友", borderless=False, development_mode=False)
font_path = find_font()
setup_font(font_path)
window.color = SKY
game = Game(font_path)
lobby = Lobby(on_start=game.start, on_quit=application.quit, aim_camera=game.aim_menu_camera,
              music=game.bgm_volume, on_music=game.set_bgm_volume)
game.to_lobby()
lobby.duo = DuoPanel(lobby, game)


class PauseMenu:
    """使用者：Esc 不要直接回大廳 → 暫停選單（繼續／音樂音量／回大廳）。暫停時整個遊戲（館員、時鐘、計時）都停住。"""

    def __init__(self):
        from menu import _button
        from ursina import Slider
        self.root = Entity(parent=camera.ui, z=-0.8, enabled=False, ignore_paused=True)
        Entity(parent=self.root, model="quad", scale=(4, 2), color=color.rgba32(0, 0, 0, 150), ignore_paused=True)
        Entity(parent=self.root, model="quad", scale=(0.62, 0.56), color=color.rgba32(18, 18, 22, 235), ignore_paused=True)
        Text(parent=self.root, text="暫停", position=(0, 0.2), origin=(0, 0), scale=2.2, color=color.rgb32(225, 218, 200))
        self.buttons = [_button(self.root, "繼續遊戲", 0.07, self.resume, x=0, width=0.4),
                        _button(self.root, "回到大廳（這局會結束）", -0.17, self.quit, x=0, width=0.4)]
        Text(parent=self.root, text="音樂", position=(-0.19, -0.035), scale=0.9, color=color.light_gray)
        self.music = Slider(min=0, max=100, default=int(game.bgm_volume * 100), step=5, dynamic=True,
                            parent=self.root, position=(-0.1, -0.045), scale=0.5, ignore_paused=True)
        self.music.on_value_changed = lambda: game.set_bgm_volume(self.music.value / 100)
        for e in [self.music, *self.buttons] + list(self.music.children) + [c for b in self.buttons for c in b.children]:
            e.ignore_paused = True

    @property
    def active(self):
        return self.root.enabled

    def open(self):
        game.state = "pause"
        game.update_prompt(off=True)
        self.music.value = int(round(game.bgm_volume * 100))
        self.root.enabled = True
        application.paused = True
        game.player.relative = False
        mouse.enabled = True       # 玩家平常把 Ursina 的 mouse 關掉自己算視角，暫停時要打開，不然按鈕點不到
        mouse.locked = False
        mouse.visible = True

    def resume(self):
        self.root.enabled = False
        application.paused = False
        game.state = "play"
        lobby.music.value = int(round(game.bgm_volume * 100))
        mouse.locked = True
        if game.player.enabled:
            mouse.enabled = False
            game.player.grab_mouse()

    def quit(self):
        self.resume()
        game.to_lobby()


pause_menu = PauseMenu()
mouse.ignore_paused = True


def handle_input(key):
    if game.state == "intro":
        game.intro.input(key)
        return
    if game.state == "cutscene":
        game.cut.input(key)
        return
    if game.state == "menu":
        if key == "escape":
            lobby.hide_panel()
        return
    if game.dialog.active:
        game.dialog.input(key)
        return
    if game.entry:
        game.entry_key(key)
        return
    if game.state == "pause":
        if key == "escape":
            pause_menu.resume()
        return
    if game.versus and game.state == "play" and not game.cleared and game.versus.input(key):
        return
    if key in ("f1", "f2") and not game.cleared and not game.fight and not game.versus:   # Demo 用：直接跳到 4F 認人／第二階段
        game.demo_jump(key)
        return
    if game.fight and key in ("e", "left mouse down"):
        game.hit()
        return
    if key == "escape" and not game.cleared:
        pause_menu.open()
    elif key == "escape" or (game.cleared and key == "enter"):
        game.to_lobby()
    elif key == "e" and not game.cleared and not game.fight:
        game.interact()
    elif key == "c" and not game.cleared and not game.fight and not game.versus:
        game.toggle_hide()
    elif key == "m":
        game.minimap.toggle()
    elif key in ("-", "="):          # 遊戲中調背景音樂音量
        game.set_bgm_volume(game.bgm_volume + (0.1 if key == "=" else -0.1), show=True)
        lobby.music.value = int(game.bgm_volume * 100)


# 用一個空 Entity 掛每幀更新與按鍵處理，不依賴 __main__ 裡的全域函式
driver = Entity(update=game.update, input=handle_input, ignore_paused=True)   # 暫停時還要收得到 Esc


if __name__ == "__main__":
    app.run()
