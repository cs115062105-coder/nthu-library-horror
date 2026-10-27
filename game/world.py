"""把格子地圖蓋成 3D 的清大總圖。

樓層照總圖官網的樓層導覽（https://www.lib.nthu.edu.tw/library/libtour.html）：
1F 借還書、自助取書、閱報區、清沙龍；2F 期刊、學位論文、校史展示、電腦教室；
4F/5F 中文圖書；B1 密集書庫。每層是 FLOORS 裡的一張格子圖。
"""
import random

from ursina import Entity, Texture, Vec3, color, destroy, scene
from ursina.models.procedural.cylinder import Cylinder

import textures as tx

CELL = 2.0
WALL_H = 3.2
SHADE = 0.62    # 整體調暗：半夜的圖書館只剩部分燈亮著

# #  牆          W  窗（看得到外面的月光）  B  開架書架    K  密集書庫
# T  閱覽桌      C  自習座位               S  總服務台    O  柱子
# G  玻璃隔間    R  感應閘門（可通過）      ,  大廳磨石子  .  地毯
# P  起點        M  怪物                   1–4 筆記       U/D 樓梯間往上／往下的門
# k  可移動的密集書架（由 banks 決定哪一道走道是開的）
# N  報紙／期刊架  E  展覽看板  Y  沙發  L  自助取書櫃  H  校史展板  Q  電腦桌  q  還開著的那台電腦
ORDER = ["B1", "1F", "2F", "3F", "4F", "5F", "6F"]

# 1F：借還書櫃台、自助取書區、閱報區、輕學區、知識集展覽、清沙龍。夜讀區在前棟，從左下角接過來。
LEVEL_1F = [
    "####UD##WWWWWWWWWWWWWWWWWW######",
    "#......#.......................#",
    "#.......NN.NN.NN..T..T..T..T..T#",
    "#......#.......................#",
    "#......#NN.NN.NN..T..T..T..T..T#",
    "####.###.......................#",
    "#..............................#",
    "#..E..E..E..E.....YTY...YTY...L#",
    "#.............................L#",
    "#..E..E..E..E.....YTY...YTY...L#",
    "#.............................L#",
    "#....................M........L#",
    "#.............................L#",
    "#..............................#",
    "###########R,R,R#######..#######",
    "#........#,,,,,,#..............#",
    "#.T..T.1..,,,,,,...Y..Y..Y..Y..#",
    "#........#,S,,,,#..............#",
    "#P.T..T..#,S,,,,#..Y..Y..Y..Y..#",
    "#........#,,,,,,#..............#",
    "#WWWWWWWW#GGGGGG################",
]
# 2F：期刊、學位論文、校史展示區、電腦教室、閱覽區
LEVEL_2F = [
    "####UD##WWWWWWWWWWWWWWWWWW######",
    "#......#.T..T..T..T..T..T..T...#",
    "#..............................#",
    "#......#.T..T..T..T..T..T..T...#",
    "####.###.......................#",
    "#..............................#",
    "#.NN.NN.NN.NN...GGGGGG.GGGGGGGG#",
    "#...............G..............#",
    "#.NN.NN.NN.NN...G.Q.Q.Q.Q.Q.q..#",
    "#...............G..............#",
    "#.BBBBB.BBBBBB..G.Q.Q.Q.Q.Q.Q..#",
    "#...............GGGGGGGGGGGGGGG#",
    "#.BBBBB.BBBBBB.................#",
    "#...................M..........#",
    "#.H..H..H..H..H................#",
    "#2.............................#",
    "################################",
]
# 舊的開架書庫，之後改成 4F
LEVEL_STACKS = [
    "###D###WWWWWWWWWWWWWWWWWW#######",
    "#.....#..................G..T..#",
    "#K.K.K#.T..T..T..T..T..T....T..#",
    "#K.K.K#..................GGGGGG#",
    "#K.K.K#.......1..........G..T..#",
    "#...........................T..#",
    "#######..................GGGGGG#",
    "#..............................#",
    "#.BBBBBB.BBBBBB..O..BBBBBB.BBB.#",
    "#..............................#",
    "#.BBBBBB.BBBBBB..O..BBBBBB.BBB.#",
    "#..............M...............#",
    "#.BBBBBB.BBBBBB..O..BBBBBB.BBB.#",
    "#2.............................#",
    "###########R,R,R#######..#######",
    "#........#,,,,,,#C.C.C.C.C.C.C.#",
    "#.T..T....,,,,,,...............#",
    "#........#,S,,,,#C.C.C.C.C.C.3.#",
    "#P.T..T..#,S,,,,#..............#",
    "#........#,,,,,,#C.C.C.C.C.C.C.#",
    "#WWWWWWWW#GGGGGG################",
]
BLOCKED = set("#WBKTCSOGDUkNEYLHQq")

# B1 地下書庫：兩區可移動的密集書架。轉書架尾端的手輪，你站的那一道走道就會打開。
LEVEL_B1 = [
    "#U########################",
    "#P.......................#",
    "#..T4..O.......O.....T...#",
    "#........................#",
    "#........................#",
    "#..kkkkkkkk...kkkkkkkk...#",
    "#..kkkkkkkk...kkkkkkkk...#",
    "#..kkkkkkkk...kkkkkkkk...#",
    "#..kkkkkkkk...kkkkkkkk...#",
    "#..kkkkkkkk...kkkkkkkk...#",
    "#..kkkkkkkk...kkkkkkkk...#",
    "#........................#",
    "#.BBBBBB..BBBBBB..BBBBB..#",
    "#...........M............#",
    "##########################",
]
BANKS_B1 = [
    dict(name="A", col=3, row=5, length=6, aisle=0,
         labels=["000–099", "100–199", "200–299", "300–399", "400–449", "450–499", "500–509"]),
    dict(name="B", col=14, row=5, length=6, aisle=7,
         labels=["510–519", "520–529", "530–539", "540–549", "550–559", "560–569", "570–579"]),
]
EXAM_BOOK = ("B", 1)   # 考古題之書：B 區「520–529」那一櫃的右手邊

# 吊牌：格子 → (中文, 英文)
HANGING_1F = {
    (4, 16): ("夜讀區 24H", "Moonlight Study Area"),
    (13, 16): ("總服務台", "Circulation Desk"),
    (12, 13): ("館藏區", "Stacks  ↑"),
    (15, 1): ("閱覽區　請保持安靜", "Reading Area · Quiet Please"),
    (7, 5): ("密集書庫", "Compact Shelving"),
    (23, 2): ("討論室 1", "Discussion Room 1"),
    (23, 5): ("討論室 2", "Discussion Room 2"),
    (24, 15): ("自習座位", "Study Carrels"),
}
# 牆上的海報：(牆的格子, 朝哪一格的方向, 種類)
POSTERS_1F = [
    ((0, 17), (1, 0), "missing"),
    ((9, 15), (-1, 0), "notice"),
    ((16, 18), (-1, 0), "missing"),
    ((6, 4), (1, 0), "notice"),
]
# 書架端板上的分類號（中國圖書分類法）
CALL_NUMBERS = ["000 總類", "100 哲學", "200 宗教", "300 自然科學", "400 應用科學",
                "500 社會科學", "600 中國史地", "700 世界史地", "800 語言文學",
                "900 藝術", "529 考試用書", "R 參考書"]

# 一直閃的壞燈管（格子）
FLICKER_1F = {(9, 9), (21, 11), (5, 13), (28, 7), (13, 4), (25, 18)}
DEAD_1F = {(3, 7), (17, 9), (11, 13), (29, 13), (2, 9)}

HISTORY = [("1911", "清華學堂在北京成立"), ("1928", "改名國立清華大學"), ("1956", "在新竹建校"),
           ("1971", "成立大學部"), ("2013", "旺宏館（學習資源中心）啟用")]

FLOORS = {
    "1F": dict(level=LEVEL_1F, floor="carpet", banks=[], flicker=FLICKER_1F, dead=DEAD_1F,
               safe={(c, r) for c in range(1, 9) for r in range(15, 20)},
               hanging={(4, 16): ("夜讀區 24H", "Moonlight Study Area"), (13, 16): ("借還書 · 讀者諮詢", "Circulation · Information"),
                        (12, 13): ("館藏區", "Library  ↑"), (11, 1): ("閱報區", "Newspapers"),
                        (23, 1): ("輕學區", "Light Up Zone"), (7, 8): ("知識集 · 主題展", "The Circle · Exhibition"),
                        (22, 8): ("清沙龍", "Idea Hub"), (28, 6): ("自助取書區", "Self Pick-up"),
                        (23, 15): ("逗留點", "Meeting Point"), (4, 3): ("樓梯間", "Stairs")},
               posters=[((0, 17), (1, 0), "missing"), ((9, 15), (-1, 0), "notice"), ((16, 18), (-1, 0), "missing"),
                        ((7, 3), (1, 0), "notice")]),
    "2F": dict(level=LEVEL_2F, floor="carpet", banks=[], safe=set(), dead_ratio=0.25, flicker_ratio=0.15,
               shelf_labels=["學位論文 Theses"],
               hanging={(4, 3): ("樓梯間", "Stairs"), (6, 5): ("期刊", "Periodicals"),
                        (7, 13): ("本校學位論文", "NTHU Theses"), (8, 13): ("校史展示區", "University History"),
                        (22, 5): ("電腦教室", "Computer Lab"), (17, 2): ("閱覽區", "Reading Area")},
               posters=[((0, 9), (1, 0), "missing"), ((31, 13), (-1, 0), "notice")]),
    "4F": dict(level=LEVEL_STACKS, hanging=HANGING_1F, posters=POSTERS_1F, flicker=FLICKER_1F, dead=DEAD_1F,
               floor="carpet", banks=[], safe=set()),
    "B1": dict(level=LEVEL_B1, banks=BANKS_B1, floor="stone", safe=set(), dead_ratio=0.45, flicker_ratio=0.2,
               hanging={(8, 3): ("密集書庫 A 區", "Compact Shelving A"), (17, 3): ("密集書庫 B 區", "Compact Shelving B"),
                        (2, 3): ("B1 地下書庫", "Basement Stacks")},
               posters=[((0, 2), (1, 0), "missing")]),
}


def cell_pos(c, r):
    return Vec3(c * CELL, 0, -r * CELL)


def facing_y(d):
    """quad 的正面是 -z。回傳讓正面朝向世界方向 d 的 rotation_y。"""
    return {(0, -1): 0, (0, 1): 180, (1, 0): -90, (-1, 0): 90}[(round(d.x), round(d.z))]


class World:
    _textures = None   # 材質只產生一次，換樓層時沿用

    def __init__(self, font_path, floor="1F"):
        first_entity = len(scene.entities)
        self.font_path = font_path
        self.floor = floor
        self.spec = FLOORS[floor]
        self.level = self.spec["level"]
        self.rows, self.cols = len(self.level), len(self.level[0])
        for r, row in enumerate(self.level):
            assert len(row) == self.cols, f"{floor} 第 {r} 行長度 {len(row)}，應該是 {self.cols}"
        self.rng = random.Random(42)
        self.door = None
        self.whiteboard = None
        self.banks = []
        self.stairs = {}        # "up"/"down" → 玩家要站的位置
        self.interactables = [] # 可以按 E 的東西：dict(kind, pos, data)
        self.lockers = 0
        self.history_i = 0
        self.racks = 0
        self.solids = []        # 擋視線的東西（牆、書架）
        self.lights = []        # [panel, pool, 狀態]
        self.notes = {}
        self.clues = {}         # 線索名稱 → 玩家要站在附近的位置
        self.shelf_runs = {}    # 第幾排書架 → 格子
        self.walkable = set()
        self.groups = {}        # 不會動的裝飾依材質分組，最後每組合併成一個 mesh，顯示卡才跑得動
        self.load_textures()
        self.build()
        for tex, g in self.groups.values():
            g.combine()
            g.texture = tex
            g.color = color.rgb(SHADE, SHADE, SHADE)
        if floor == "4F":
            self.place_clues()
        self.build_banks()
        self.owned = [e for e in scene.entities[first_entity:]]   # 換樓層時要拆掉的東西

    def unload(self):
        for e in self.owned:
            try:
                destroy(e)
            except Exception:
                pass

    # ---------- 小工具 ----------
    def load_textures(self):
        if World._textures:
            self.t, self.book_tex = World._textures
            return

        def t(img, filtering=None):
            return Texture(img, filtering=filtering)
        self.t = {
            "carpet": t(tx.carpet()), "stone": t(tx.stone()), "ceiling": t(tx.ceiling()),
            "wall": t(tx.wall()), "wood": t(tx.wood()), "metal": t(tx.metal()),
            "window": t(tx.window()), "panel": t(tx.light_panel()), "glow": t(tx.glow(), "bilinear"),
            "note": t(tx.note_paper()), "screen": t(tx.screen()),
            "missing": t(tx.poster_missing(self.font_path), "bilinear"),
            "notice": t(tx.poster_notice(self.font_path), "bilinear"),
        }
        self.book_tex = [t(tx.books(i)) for i in range(6)]
        World._textures = (self.t, self.book_tex)

    def char(self, c, r):
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return self.level[r][c]
        return "#"

    def group(self, tex):
        key = id(tex)
        if key not in self.groups:
            self.groups[key] = (tex, Entity())
        return self.groups[key][1]

    def box(self, pos, scale, tex=None, col=color.white, tscale=(1, 1), parent=None):
        return Entity(parent=parent or self.group(tex), model="cube", position=pos, scale=scale,
                      texture=tex, color=col, texture_scale=tscale)

    def quad(self, pos, scale, tex=None, col=color.white, rot=(0, 0, 0), parent=None, double=False):
        return Entity(parent=parent or self.group(tex), model="quad", position=pos, scale=scale,
                      texture=tex, color=col, rotation=rot, double_sided=double)

    def collider(self, pos, scale, occludes=True):
        e = Entity(model="cube", position=pos, scale=scale, collider="box", visible=False)
        if occludes:
            self.solids.append(e)
        return e

    def text_tex(self, lines, **kw):
        return Texture(tx.sign(lines, self.font_path, **kw), filtering="bilinear")

    # ---------- 建造 ----------
    def build(self):
        w, d = self.cols * CELL, self.rows * CELL
        center = Vec3((self.cols - 1) * CELL / 2, 0, -(self.rows - 1) * CELL / 2)
        Entity(model="quad", position=center, scale=(w, d), rotation_x=90, texture=self.t[self.spec["floor"]],
               texture_scale=(self.cols, self.rows), color=color.rgb(SHADE, SHADE, SHADE))
        Entity(model="quad", position=center + Vec3(0, WALL_H, 0), scale=(w, d), rotation_x=-90,
               texture=self.t["ceiling"], texture_scale=(self.cols * 3, self.rows * 3), color=color.rgb(0.4, 0.4, 0.4))
        Entity(model="plane", scale=(w, 1, d), position=center, collider="box", visible=False)

        shelf_run = 0
        for r, row in enumerate(self.level):
            for c, ch in enumerate(row):
                p = cell_pos(c, r)
                if ch not in BLOCKED:
                    self.walkable.add((c, r))
                if ch == "#":
                    self.wall(c, r, p)
                elif ch == "W":
                    self.window(c, r, p)
                elif ch == "B":
                    if self.char(c - 1, r) != "B":
                        shelf_run += 1
                    self.shelf(c, r, p, shelf_run)
                elif ch == "K":
                    self.compact(c, r, p)
                elif ch == "T":
                    self.table(p)
                elif ch == "C":
                    self.carrel(p)
                elif ch == "S":
                    self.counter(c, r, p)
                elif ch == "O":
                    self.pillar(p)
                elif ch == "G":
                    self.glass(c, r, p)
                elif ch == "R":
                    self.gate(p)
                elif ch == ",":
                    self.quad(p + Vec3(0, 0.005, 0), (CELL, CELL), self.t["stone"], rot=(90, 0, 0))
                elif ch == "P":
                    self.start = p
                elif ch == "M":
                    self.monster_start = p
                elif ch in "1234":
                    self.note(ch, p)
                elif ch == "D":
                    self.stair(c, r, p, "down")
                elif ch == "U":
                    self.stair(c, r, p, "up")
                elif ch == "N":
                    self.rack(c, r, p)
                elif ch == "E":
                    self.exhibit(p)
                elif ch == "Y":
                    self.sofa(p)
                elif ch == "L":
                    self.locker(c, r, p)
                elif ch == "H":
                    self.history(p)
                elif ch in "Qq":
                    self.computer(p, live=ch == "q")
        for (c, r), lines in self.spec["hanging"].items():
            self.hanging_sign(cell_pos(c, r), lines)
        for (c, r), (dc, dr), kind in self.spec["posters"]:
            dvec = Vec3(dc, 0, -dr)
            self.quad(cell_pos(c, r) + dvec * (CELL / 2 + 0.01) + Vec3(self.rng.uniform(-0.4, 0.4), 1.55, 0),
                      (0.6, 0.85), self.t[kind], rot=(0, facing_y(dvec), self.rng.uniform(-4, 4)))
        self.ceiling_lights()

    def open_sides(self, c, r):
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if self.char(c + dc, r + dr) not in "#W":
                yield Vec3(dc, 0, -dr)

    def wall(self, c, r, p):
        if not any(True for _ in self.open_sides(c, r)):
            return   # 被牆包住的格子看不到，不用蓋
        self.box(p + Vec3(0, WALL_H / 2, 0), (CELL, WALL_H, CELL), self.t["wall"])
        self.collider(p + Vec3(0, WALL_H / 2, 0), (CELL, WALL_H, CELL))

    def window(self, c, r, p):
        self.box(p + Vec3(0, 0.45, 0), (CELL, 0.9, CELL), self.t["wall"], tscale=(1, 0.3))
        self.box(p + Vec3(0, WALL_H - 0.15, 0), (CELL, 0.3, CELL), self.t["wall"], tscale=(1, 0.1))
        self.box(p + Vec3(0, 1.85, 0), (CELL, 1.9, CELL * 0.6), self.t["window"])
        for side in self.open_sides(c, r):
            self.box(p + side * (CELL / 2) + Vec3(0, 0.92, 0), (CELL if side.z else 0.3, 0.05, 0.3 if side.z else CELL),
                     col=color.rgb32(170, 165, 150))
            pool = self.quad(p + side * (CELL * 0.9) + Vec3(0, 0.015, 0), (CELL * 1.4, CELL * 1.1),
                             self.t["glow"], col=color.rgba32(120, 150, 210, 70), rot=(90, 0, 0))
        self.collider(p + Vec3(0, WALL_H / 2, 0), (CELL, WALL_H, CELL))

    def shelf(self, c, r, p, run):
        self.shelf_runs.setdefault(run, []).append((c, r))
        tex = self.book_tex[(c * 7 + r * 3) % len(self.book_tex)]
        self.box(p + Vec3(0, 1.1, 0), (CELL, 2.2, 0.62), self.t["metal"])
        for side in (1, -1):
            self.quad(p + Vec3(0, 1.08, side * 0.315), (CELL * 0.98, 2.1), tex,
                      rot=(0, 0 if side < 0 else 180, 0))
        for dc in (-1, 1):
            if self.char(c + dc, r) != "B":
                end = Vec3(dc, 0, 0)
                self.box(p + end * (CELL / 2) + Vec3(0, 1.1, 0), (0.06, 2.24, 0.66), col=color.rgb32(90, 96, 100))
                labels = self.spec.get("shelf_labels", CALL_NUMBERS)
                label = labels[(run - 1) % len(labels)]
                code, name = label.split(" ")
                self.quad(p + end * (CELL / 2 + 0.035) + Vec3(0, 1.75, 0), (0.5, 0.26),
                          self.text_tex([code, name], w=160, h=80, bg=(30, 34, 40), sizes=[30, 20]),
                          rot=(0, facing_y(end), 0))
        self.collider(p + Vec3(0, 1.1, 0), (CELL, 2.2, 0.62))

    def compact(self, c, r, p):
        self.box(p + Vec3(0, 1.3, 0), (CELL * 0.9, 2.6, CELL * 0.98), self.t["metal"], col=color.rgb32(150, 160, 150))
        for side in (1, -1):
            self.quad(p + Vec3(side * (CELL * 0.45 + 0.005), 1.25, 0), (CELL * 0.95, 2.4),
                      self.book_tex[(r + side) % 6], rot=(0, -90 * side, 0))
        if self.char(c, r + 1) not in "K":   # 走道那一端有手搖輪
            front = p + Vec3(0, 0, -CELL / 2 - 0.02)
            self.quad(front + Vec3(0, 1.3, 0), (CELL * 0.9, 2.6), col=color.rgb32(120, 130, 120), rot=(0, 180, 0))
            Entity(parent=self.group(None), model=Cylinder(resolution=10, radius=0.22, height=0.05, direction=(0, 0, -1)),
                   position=front + Vec3(0, 1.1, -0.02), color=color.rgb32(60, 60, 62))
            self.quad(front + Vec3(0, 2.2, -0.01), (0.5, 0.2),
                      self.text_tex([f"K-{c:02d}"], w=128, h=48, bg=(240, 240, 230), fg=(30, 30, 30), sizes=[30]),
                      rot=(0, 180, 0))
        self.collider(p + Vec3(0, 1.3, 0), (CELL * 0.9, 2.6, CELL * 0.98))

    def chair(self, pos, rot):
        ch = Entity(parent=self.group(None), position=pos, rotation_y=rot)
        dark = color.rgb32(45, 45, 50)
        self.box((0, 0.45, 0), (0.45, 0.05, 0.45), col=color.rgb32(70, 80, 110), parent=ch)
        self.box((0, 0.75, 0.21), (0.45, 0.55, 0.04), col=color.rgb32(70, 80, 110), parent=ch)
        for x in (-0.2, 0.2):
            for z in (-0.2, 0.2):
                self.box((x, 0.22, z), (0.03, 0.45, 0.03), col=dark, parent=ch)

    def clutter(self, top, spread):
        """桌上的書、講義、喝一半的飲料。"""
        for _ in range(self.rng.randint(1, 3)):
            off = Vec3(self.rng.uniform(-spread, spread), 0, self.rng.uniform(-0.25, 0.25))
            h = self.rng.uniform(0.03, 0.12)
            self.box(top + off + Vec3(0, h / 2, 0), (0.22, h, 0.3), col=color.rgb32(*self.rng.choice(tx.BOOK_COLORS)))
        if self.rng.random() < 0.5:
            self.box(top + Vec3(self.rng.uniform(-spread, spread), 0.08, 0.1), (0.07, 0.16, 0.07),
                     col=color.rgb32(200, 190, 160))

    def lamp(self, top):
        self.box(top + Vec3(0, 0.2, 0), (0.03, 0.4, 0.03), col=color.rgb32(40, 40, 40))
        self.box(top + Vec3(0, 0.42, 0.06), (0.18, 0.06, 0.12), col=color.rgb32(230, 220, 170))

    def table(self, p):
        top = p + Vec3(0, 0.76, 0)
        self.box(top - Vec3(0, 0.02, 0), (1.7, 0.05, 1.0), self.t["wood"])
        for x in (-0.75, 0.75):
            for z in (-0.4, 0.4):
                self.box(p + Vec3(x, 0.37, z), (0.05, 0.74, 0.05), col=color.rgb32(50, 50, 54))
        for x in (-0.45, 0.45):
            for z, rot in ((-0.75, 0), (0.75, 180)):
                if self.rng.random() < 0.85:
                    jitter = self.rng.uniform(-15, 15)
                    self.chair(p + Vec3(x + self.rng.uniform(-0.1, 0.1), 0, z), rot + jitter)
        if self.rng.random() < 0.5:
            self.lamp(top + Vec3(0, 0, 0))
        self.clutter(top, 0.6)
        self.collider(p + Vec3(0, 0.4, 0), (1.7, 0.8, 1.0), occludes=False)

    def carrel(self, p):
        top = p + Vec3(0, 0.76, 0)
        self.box(top - Vec3(0, 0.02, 0), (1.2, 0.05, 0.7), self.t["wood"])
        for x in (-0.6, 0.6):
            self.box(p + Vec3(x, 0.65, 0), (0.04, 1.3, 0.75), col=color.rgb32(120, 110, 95))
        self.box(p + Vec3(0, 1.0, -0.36), (1.2, 0.5, 0.04), col=color.rgb32(120, 110, 95))
        self.chair(p + Vec3(0, 0, 0.6), 180 + self.rng.uniform(-20, 20))
        self.lamp(top + Vec3(0.35, 0, -0.2))
        self.clutter(top, 0.3)
        self.collider(p + Vec3(0, 0.65, 0), (1.25, 1.3, 0.75), occludes=False)

    def counter(self, c, r, p):
        if self.floor == "1F" and not any(i["kind"] == "counter_pc" for i in self.interactables):
            self.interactables.append(dict(kind="counter_pc", pos=p + Vec3(CELL * 0.6, 0, 0)))
        self.box(p + Vec3(0, 0.55, 0), (1.0, 1.1, CELL), self.t["wood"], tscale=(1, 2))
        self.box(p + Vec3(0, 1.12, 0), (1.15, 0.05, CELL * 1.02), col=color.rgb32(210, 205, 195))
        self.box(p + Vec3(0.1, 1.35, 0.3), (0.05, 0.38, 0.55), col=color.rgb32(30, 30, 32))
        self.quad(p + Vec3(0.13, 1.35, 0.3), (0.5, 0.32), self.t["screen"], rot=(0, -90, 0))
        self.collider(p + Vec3(0, 0.55, 0), (1.0, 1.1, CELL), occludes=False)

    def pillar(self, p):
        Entity(parent=self.group(self.t["wall"]), model=Cylinder(resolution=14, radius=0.5, height=WALL_H),
               position=p, texture=self.t["wall"], texture_scale=(3, 1))
        self.collider(p + Vec3(0, WALL_H / 2, 0), (0.9, WALL_H, 0.9))

    def glass(self, c, r, p):
        along_x = self.char(c - 1, r) == "G" or self.char(c + 1, r) == "G"
        size = (CELL, WALL_H - 0.1, 0.06) if along_x else (0.06, WALL_H - 0.1, CELL)
        frame = color.rgb32(70, 74, 78)
        self.box(p + Vec3(0, WALL_H / 2, 0), size, col=color.rgba32(150, 190, 200, 45))
        self.box(p + Vec3(0, 0.05, 0), (size[0] + 0.02, 0.1, size[2] + 0.04), col=frame)
        self.box(p + Vec3(0, WALL_H - 0.05, 0), (size[0] + 0.02, 0.1, size[2] + 0.04), col=frame)
        self.collider(p + Vec3(0, WALL_H / 2, 0), size, occludes=False)

    def gate(self, p):
        for x in (-0.9, 0.9):
            self.box(p + Vec3(x, 0.5, 0), (0.18, 1.0, 0.7), col=color.rgb32(170, 172, 175))
            self.box(p + Vec3(x, 1.0, 0), (0.2, 0.03, 0.72), col=color.rgb32(40, 160, 90))
            self.collider(p + Vec3(x, 0.5, 0), (0.18, 1.0, 0.7), occludes=False)

    def note(self, key, p):
        self.box(p + Vec3(0, 0.45, 0), (0.8, 0.05, 0.5), self.t["metal"])
        self.box(p + Vec3(0, 0.85, 0), (0.8, 0.05, 0.5), self.t["metal"])
        for x in (-0.38, 0.38):
            self.box(p + Vec3(x, 0.45, 0), (0.04, 0.9, 0.5), col=color.rgb32(110, 112, 115))
        for i in range(5):
            self.box(p + Vec3(-0.3 + i * 0.13, 0.6, 0), (0.08, 0.26, 0.3), col=color.rgb32(*tx.BOOK_COLORS[i * 2]))
        self.notes[key] = Entity(model="quad", position=p + Vec3(0, 0.885, 0), scale=(0.3, 0.38),
                                 rotation=(90, 20, 0), texture=self.t["note"], double_sided=True)

    # ---------- 解謎線索 ----------
    def place_clues(self):
        """三個線索各自藏在總圖的設施裡，筆記只告訴你去哪找。"""
        # 1. 「300 自然科學」那排書架上，一本凸出來的書
        run = next(i for i in self.shelf_runs if CALL_NUMBERS[(i - 1) % len(CALL_NUMBERS)].startswith("300"))
        cells = self.shelf_runs[run]
        c, r = cells[len(cells) // 2]
        p = cell_pos(c, r)
        Entity(model="cube", position=p + Vec3(0.3, 1.32, -0.36), scale=(0.07, 0.3, 0.22),
               color=color.rgb32(150, 40, 35))
        Entity(model="quad", position=p + Vec3(0.3, 1.52, -0.36), scale=(0.05, 0.06), rotation=(0, 0, 0),
               color=color.rgb32(240, 235, 210))   # 書頁間露出的紙條
        self.clues["book"] = cell_pos(c, r + 1)
        # 2. 總服務台還沒登出的電腦（螢幕比較亮）
        c, r = next((c, r) for r, row in enumerate(self.level) for c, ch in enumerate(row) if ch == "S")
        p = cell_pos(c, r)
        Entity(model="quad", position=p + Vec3(0.135, 1.35, 0.3), scale=(0.5, 0.32), rotation=(0, -90, 0),
               texture=self.t["screen"], color=color.rgb(1.4, 1.4, 1.4))
        self.clues["computer"] = p + Vec3(CELL * 0.6, 0, 0)
        # 3. 討論室 2 的白板（數字每局不同，開局時才畫上去）
        wall = (31, 4)
        p = cell_pos(*wall) + Vec3(-CELL / 2 - 0.02, 1.5, 0)
        self.whiteboard = Entity(model="quad", position=p, scale=(1.5, 0.95), rotation=(0, 90, 0))
        self.clues["whiteboard"] = cell_pos(wall[0] - 1, wall[1])

    def set_code(self, code):
        if self.whiteboard:
            self.whiteboard.texture = Texture(tx.whiteboard(code[2], self.font_path), filtering="bilinear")

    # ---------- 1F／2F 的設施 ----------
    def stair(self, c, r, p, direction):
        side = next(Vec3(dc, 0, -dr) for dc, dr in ((0, 1), (0, -1), (1, 0), (-1, 0))
                    if self.char(c + dc, r + dr) not in BLOCKED)   # 朝向可以走的那一格
        self.wall(c, r, p)
        door = Entity(model="cube", position=p + side * (CELL / 2 + 0.03) + Vec3(0, 1.1, 0),
                      scale=(1.2 if side.z else 0.06, 2.2, 0.06 if side.z else 1.2), color=color.rgb32(48, 70, 60))
        i = ORDER.index(self.floor) + (1 if direction == "up" else -1)
        target = ORDER[i] if 0 <= i < len(ORDER) else None
        label = f"{'↑' if direction == 'up' else '↓'} {target or '—'}"
        sub = "B1 密集書庫：館員專用" if target == "B1" else "樓梯間 Stairs"
        self.quad(p + side * (CELL / 2 + 0.07) + Vec3(0, 2.55, 0), (1.1, 0.34),
                  self.text_tex([label, sub], w=256, h=80, bg=(20, 110, 60)), rot=(0, facing_y(side), 0))
        self.stairs[direction] = dict(pos=p + side * CELL, door=door, target=target)

    def rack(self, c, r, p):
        """報紙／期刊架：斜的架子上插著一份份報紙。"""
        self.box(p + Vec3(0, 0.6, 0), (CELL * 0.9, 1.2, 0.5), self.t["wood"])
        for i in range(4):
            self.box(p + Vec3(-0.65 + i * 0.43, 1.0, 0.27), (0.36, 0.45, 0.02), col=color.rgb32(215, 210, 195))
            self.box(p + Vec3(-0.65 + i * 0.43, 1.1, 0.285), (0.3, 0.04, 0.005), col=color.rgb32(40, 40, 40))
        self.collider(p + Vec3(0, 0.6, 0), (CELL * 0.9, 1.2, 0.5), occludes=False)
        self.racks += 1
        if self.racks == 1:   # 第一份報紙：日期是明天
            self.interactables.append(dict(kind="read", pos=p + Vec3(0, 0, -CELL * 0.6), data="newspaper"))

    def exhibit(self, p):
        tex = self.text_tex(["知識集 · 主題展", "總圖的夜"], w=200, h=260, bg=(40, 40, 60), sizes=[26, 34])
        for rot in (0, 180):
            self.quad(p + Vec3(0, 1.3, 0.03 if rot else -0.03), (0.9, 1.2), tex, rot=(0, rot, 0))
        self.box(p + Vec3(0, 0.35, 0), (0.06, 0.7, 0.06), col=color.rgb32(60, 60, 60))
        self.collider(p + Vec3(0, 1.0, 0), (1.0, 2.0, 0.2), occludes=False)
        self.interactables.append(dict(kind="read", pos=p, data="exhibit"))

    def sofa(self, p):
        col = color.rgb32(120, 60, 50)
        self.box(p + Vec3(0, 0.22, 0), (1.5, 0.44, 0.8), col=col)
        self.box(p + Vec3(0, 0.55, 0.32), (1.5, 0.5, 0.18), col=col)
        for x in (-0.72, 0.72):
            self.box(p + Vec3(x, 0.35, 0), (0.16, 0.5, 0.8), col=col)
        self.collider(p + Vec3(0, 0.4, 0), (1.5, 0.8, 0.8), occludes=False)

    def locker(self, c, r, p):
        """自助取書櫃：一格一格小門，每格有編號。"""
        self.lockers += 1
        n = self.lockers
        side = next(d for d in self.open_sides(c, r))
        body = color.rgb32(200, 200, 205)
        self.box(p + Vec3(0, 1.1, 0), (CELL * 0.9, 2.2, CELL * 0.9), col=body)
        for row in range(4):
            for k in (-1, 1):
                off = Vec3(side.z, 0, -side.x) * (k * 0.42) + Vec3(0, 0.4 + row * 0.5, 0)
                self.box(p + side * (CELL * 0.45 + 0.01) + off, (0.02 if side.x else 0.78, 0.44, 0.78 if side.x else 0.02),
                         col=color.rgb32(170, 175, 182))
        self.quad(p + side * (CELL * 0.45 + 0.03) + Vec3(0, 2.05, 0), (0.6, 0.2),
                  self.text_tex([f"A{n:02d}"], w=128, h=48, bg=(30, 30, 30), sizes=[30]), rot=(0, facing_y(side), 0))
        self.collider(p + Vec3(0, 1.1, 0), (CELL * 0.9, 2.2, CELL * 0.9))
        self.interactables.append(dict(kind="locker", pos=p + side * CELL, data=n))

    def history(self, p):
        year, text = HISTORY[self.history_i % len(HISTORY)]
        self.history_i += 1
        tex = self.text_tex([year, text], w=220, h=280, bg=(70, 50, 30), sizes=[64, 20])
        for rot in (0, 180):
            self.quad(p + Vec3(0, 1.35, 0.03 if rot else -0.03), (0.95, 1.2), tex, rot=(0, rot, 0))
        self.box(p + Vec3(0, 0.35, 0), (0.08, 0.7, 0.08), col=color.rgb32(60, 50, 40))
        self.collider(p + Vec3(0, 1.0, 0), (1.0, 2.0, 0.2), occludes=False)
        self.interactables.append(dict(kind="read", pos=p, data=f"history:{year} {text}"))

    def computer(self, p, live=False):
        top = p + Vec3(0, 0.76, 0)
        self.box(top - Vec3(0, 0.02, 0), (1.4, 0.05, 0.8), self.t["wood"])
        self.box(p + Vec3(0, 0.37, 0.3), (1.4, 0.74, 0.05), col=color.rgb32(50, 50, 54))
        self.box(top + Vec3(0, 0.25, 0.2), (0.55, 0.36, 0.04), col=color.rgb32(25, 25, 28))
        if live:   # 這台還亮著，不合併，保持亮
            Entity(model="quad", position=top + Vec3(0, 0.25, 0.175), scale=(0.5, 0.32), rotation=(0, 0, 0),
                   texture=self.t["screen"], color=color.rgb(1.4, 1.4, 1.4))
            self.interactables.append(dict(kind="lab_pc", pos=p + Vec3(0, 0, -CELL * 0.5)))
        self.chair(p + Vec3(0, 0, -0.6), self.rng.uniform(-20, 20))
        self.collider(p + Vec3(0, 0.4, 0), (1.4, 0.8, 0.8), occludes=False)

    def make_door(self, c, r, p, up=False):
        side = next(self.open_sides(c, r))
        self.wall(c, r, p)
        door = Entity(model="cube", position=p + side * (CELL / 2 + 0.03) + Vec3(0, 1.1, 0),
                      scale=(1.2 if side.z else 0.06, 2.2, 0.06 if side.z else 1.2),
                      color=color.rgb32(48, 70, 60))
        lines = ["↑ 1F", "門從另一邊鎖上了"] if up else ["↓ B1 地下書庫", "閉館期間禁止進入"]
        self.quad(p + side * (CELL / 2 + 0.07) + Vec3(0, 2.55, 0), (1.1, 0.34),
                  self.text_tex(lines, w=256, h=80, bg=(20, 110, 60)), rot=(0, facing_y(side), 0))
        if up:
            return   # 上樓的門只是裝飾：下來了就回不去
        self.door = door
        self.door_side = side
        keypad = p + side * (CELL / 2 + 0.07) + Vec3(0, 1.2, 0) + Vec3(side.z, 0, -side.x) * 0.8
        self.box(keypad, (0.18, 0.26, 0.18), col=color.rgb32(30, 30, 30))
        self.keypad_light = Entity(model="cube", position=keypad + Vec3(0, 0.09, 0) + side * 0.1,
                                   scale=(0.05, 0.03, 0.03), color=color.red)

    def hanging_sign(self, p, lines):
        tex = self.text_tex(list(lines))
        for rot in (0, 180):
            self.quad(p + Vec3(0, 2.6, 0.02 if rot else -0.02), (1.3, 0.4), tex, rot=(0, rot, 0))
        for x in (-0.5, 0.5):
            self.box(p + Vec3(x, 2.95, 0), (0.015, 0.3, 0.015), col=color.rgb32(60, 60, 60))

    def ceiling_lights(self):
        for (c, r) in sorted(self.walkable | self.bank_cells()):
            if (c + r) % 2 or self.level[r][c] == "R":
                continue
            p = cell_pos(c, r)
            safe = (c, r) in self.spec["safe"]     # 夜讀區 24 小時都亮著，比較暖
            if "dead_ratio" in self.spec:
                roll = self.rng.random()
                state = ("dead" if roll < self.spec["dead_ratio"]
                         else "flicker" if roll < self.spec["dead_ratio"] + self.spec["flicker_ratio"] else "on")
            else:
                state = "dead" if (c, r) in self.spec["dead"] else "flicker" if (c, r) in self.spec["flicker"] else "on"
            panel = Entity(model="quad", position=p + Vec3(0, WALL_H - 0.01, 0), scale=(0.6, 1.2),
                           rotation=(-90, 0, 0), texture=self.t["panel"])
            pool = Entity(model="quad", position=p + Vec3(0, 0.02, 0), scale=4.2 if safe else 3.2,
                          rotation=(90, 0, 0), texture=self.t["glow"],
                          color=color.rgba32(255, 230, 180, 90) if safe else color.rgba32(220, 235, 255, 50))
            light = [panel, pool, state]
            self.set_light(light, state != "dead")
            self.lights.append(light)

    @staticmethod
    def set_light(light, on):
        panel, pool, _ = light
        panel.color = color.white if on else color.rgb32(70, 70, 70)
        pool.enabled = on


    # ---------- 可移動的密集書架 ----------
    def bank_cells(self):
        return {(c, r) for r, row in enumerate(self.level) for c, ch in enumerate(row) if ch == "k"}

    def build_banks(self):
        self.exam_book = None
        for spec in self.spec["banks"]:
            bank = dict(spec, units=[])
            z_mid = -(spec["row"] + (spec["length"] - 1) / 2) * CELL
            for i, label in enumerate(spec["labels"]):
                unit = Entity(position=(self.bank_x(bank, i, spec["aisle"]), 0, z_mid))
                length = spec["length"] * CELL - 0.1
                Entity(parent=unit, model="cube", position=(0, 1.3, 0), scale=(CELL * 0.92, 2.6, length),
                       texture=self.t["metal"], color=color.rgb(0.5, 0.55, 0.5))
                for side in (1, -1):
                    Entity(parent=unit, model="quad", position=(side * CELL * 0.465, 1.25, 0),
                           scale=(length, 2.4), rotation=(0, -90 * side, 0),
                           texture=self.book_tex[(i + side) % 6], texture_scale=(spec["length"], 1),
                           color=color.rgb(SHADE, SHADE, SHADE))
                front = length / 2 + 0.02
                Entity(parent=unit, model="quad", position=(0, 2.2, front), scale=(0.9, 0.3), rotation=(0, 180, 0),
                       texture=self.text_tex([f"{spec['name']}-{i + 1}", label], w=200, h=80,
                                             bg=(240, 240, 230), fg=(30, 30, 30), sizes=[30, 24]))
                Entity(parent=unit, model=Cylinder(resolution=10, radius=0.25, height=0.06, direction=(0, 0, 1)),
                       position=(0, 1.1, front), color=color.rgb32(70, 70, 72))
                Entity(parent=unit, model="cube", position=(0, 1.1, front + 0.07), scale=(0.04, 0.4, 0.04),
                       color=color.rgb32(70, 70, 72))
                hit = Entity(parent=unit, model="cube", position=(0, 1.3, 0), scale=(CELL * 0.92, 2.6, length),
                             collider="box", visible=False)
                self.solids.append(hit)
                if (spec["name"], i) == EXAM_BOOK:
                    self.exam_book = Entity(parent=unit, model="cube", position=(CELL * 0.48, 1.3, -1.2),
                                            scale=(0.1, 0.32, 0.24), color=color.rgb32(200, 160, 60))
                bank["units"].append(unit)
            self.banks.append(bank)
            self.open_aisle(bank, spec["aisle"], animate=False)

    @staticmethod
    def bank_x(bank, i, aisle):
        return (bank["col"] + i + (1 if i >= aisle else 0)) * CELL

    def bank_at(self, pos):
        """玩家站在哪一區書架的正前方，回傳 (區, 走道編號)。"""
        c, r = round(pos.x / CELL), round(-pos.z / CELL)
        for bank in self.banks:
            n = len(bank["units"])
            if r == bank["row"] - 1 and bank["col"] <= c <= bank["col"] + n:
                return bank, c - bank["col"]
        return None, None

    def open_aisle(self, bank, aisle, animate=True):
        bank["aisle"] = aisle
        for i, unit in enumerate(bank["units"]):
            x = self.bank_x(bank, i, aisle)
            if animate:
                unit.animate_x(x, duration=1.2)
            else:
                unit.x = x
        cols = range(bank["col"], bank["col"] + len(bank["units"]) + 1)
        rows = range(bank["row"], bank["row"] + bank["length"])
        for c in cols:
            for r in rows:
                self.walkable.discard((c, r))
        for r in rows:
            self.walkable.add((bank["col"] + aisle, r))
