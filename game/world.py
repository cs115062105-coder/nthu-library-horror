"""把格子地圖蓋成 3D 的清大總圖。

樓層照總圖官網的樓層導覽（https://www.lib.nthu.edu.tw/library/libtour.html）：
1F 借還書、自助取書、閱報區、清沙龍；2F 期刊、學位論文、校史展示、電腦教室；
3F 視聽、語言學習、小舞台、發呆區；4F 中文圖書 000–499、清華書房、清華故事牆；
5F 中文圖書 500–999；6F 西文圖書；B1 密集書庫。每層是 FLOORS 裡的一張格子圖。
"""
import math
import random

from ursina import Entity, Texture, Vec3, color, destroy, scene
from ursina.models.procedural.cone import Cone
from ursina.models.procedural.cylinder import Cylinder

import textures as tx

CELL = 2.0
WALL_H = 3.2
SHADE = 0.95    # 白天的圖書館：燈全開，只稍微壓一點亮度避免過曝

# #  牆          W  窗（看得到外面的月光）  B  開架書架    K  密集書庫
# T  閱覽桌      C  自習座位               S  總服務台    O  柱子
# G  玻璃隔間    R  感應閘門（可通過）      ,  大廳磨石子  .  地毯
# P  起點        M  館員起點               1–6 筆記       U/D 樓梯間往上／往下的門
# k  可移動的密集書架（由 banks 決定哪一道走道是開的）  x  斜面落地窗外面（只有看不見的碰撞，外觀由 curves 的玻璃牆負責）
# N  報紙／期刊架  E  展覽看板  Y  沙發  L  自助取書櫃  H  校史展板  Q  電腦桌  q  還開著的那台電腦
# V  視聽座位  v  還在播的那台  Z  小舞台  X  清華書房展示櫃  t  圓桌（輕學區）  h  一排排的椅子（清沙龍）
# k  白色電腦桌（電腦共學區）  m  整面期刊架  d  窗邊閱覽桌  c  白色圓沙發
ORDER = ["B1", "1F", "2F", "3F", "4F", "5F", "6F"]

# 各層格子圖照圖書館官網的樓層平面圖排：西南邊是弧形落地窗，北邊一整排是公務區，樓梯間在東南角。
# 1F：照官網平面圖的像素座標換算（38.4 px = 1 格）：西南斜面是入口，左邊聯合櫃臺、北邊自助取書區、
#     中間圓形的知識集展區、東邊輕學區、南邊清沙龍和逗留點，樓梯間在東南角。
LEVEL_1F = [
    "##########################",
    "#...QQ.....LLLLLLLL.######",
    "#...................######",
    "#.S.................######",
    "#.S....N............######",
    "#.S.......QQQQ......######",
    "#.S..O....O....O....O....W",
    "#.S....................t.W",
    "#.S......M...............W",
    "#.....................t..W",
    "x..N.....................W",
    "xx...O....O.........O..t.W",
    "xxx............E.........W",
    "xxxx...................1.W",
    "xxxx..................t..W",
    "xxxxx..P.................W",
    "xxxxxx....O....O....O..t.W",
    "xxxxxx..R................W",
    "xxxxxxx..R..Y...hhhh.t...W",
    "xxxxxxxx.....Y..hhhh.....W",
    "xxxxxxxx.................W",
    "xxxxxxxxx.O....O....#UD###",
    "xxxxxxxxxx..........######",
    "xxxxxxxxxx################",
]
# 2F：照官網平面圖換算（32 px = 1 格，柱距 160 px = 5 格）：西北電腦教室和電腦共學區，西南一條弧形的校史展示區，
#     中間資訊島，北邊熱門書刊，東邊現期期刊和窗邊閱覽桌，南邊學位論文書架，樓梯間在東南角。
LEVEL_2F = [
    "########################################",
    "######.......###########################",
    "######.QQQQQq###########################",
    "######.......###########################",
    "######.QQQQQQ###########################",
    "######.......###########################",
    "#######.###.############################",
    "####.........#GGGG######################",
    "####.........#GT.G######################",
    "####.kk...kk.#G..G######################",
    "####.........#GGGG######################",
    "####..t.O..t.###########################",
    "####.........#..........mmmmmmmmmmmmmm.W",
    "####.kk...kk...........................W",
    "####.....................N.N.N.N.....d.W",
    "####.........#.........................W",
    "##############....O....O....O....O....OW",
    "######.................................W",
    "######....................c...c....c.d.W",
    "####xxxx......H.2....................d.W",
    "####xxxxxx...............M.............W",
    "####xxxxxxx....H..O....O....O....O....OW",
    "####xxxxxxxxx..........................W",
    "####xxxxxxxxxx...H........c...c......d.W",
    "####xxxxxxxxxxx......................d.W",
    "####xxxxxxxxxxxx.......................W",
    "####xxxxxxxxxxxxx.O....O....O....O....OW",
    "####xxxxxxxxxxxxxx........BBBBBB.......W",
    "####xxxxxxxxxxxxxx...H...............d.W",
    "####xxxxxxxxxxxxxxx.......BBBBBB.P.....W",
    "####xxxxxxxxxxxxxxxx...................W",
    "#################################UD#####",
]
# 3F：視聽媒體與聆賞、語言學習區、簡報練習室、討論室、小舞台、發呆區
LEVEL_3F = [
    "############################################",
    "###########....#.###########################",
    "###########....#.###########################",
    "###########.T....###########################",
    "###########....#.###########################",
    "###########....#.###########################",
    "################.###########################",
    "########....####.###########################",
    "########....####.###########################",
    "########....####.###########################",
    "########....####.###########################",
    "##########.#####.#####.....#################",
    "#..........................................W",
    "#.............................S............W",
    "#.u.u..u..u.u..u..............S............W",
    "#.............................S............W",
    "#CCC5CCC.C..O....O....O....O....O....O.....W",
    "###########..............M...............e.W",
    "#xxxxxxxxxx.................BBBB.BBBB......W",
    "#xxxxxxxxxxx...VV.VV.....................e.W",
    "#xxxxxxxxxxxxx..............BBBB.BBBB......W",
    "#xxxxxxxxxxxxxxx.O....O....O....O....O.....W",
    "#xxxxxxxxxxxxxxxx..VV..VV................e.W",
    "#xxxxxxxxxxxxxxxxx..........BBBB.BBBB......W",
    "#xxxxxxxxxxxxxxxxxx......................e.W",
    "#xxxxxxxxxxxxxxxxxxx..VV.VV.BBBB.BBBB......W",
    "#xxxxxxxxxxxxxxxxxxxx.O....O....O....O.....W",
    "#xxxxxxxxxxxxxxxxxxxxx.....................W",
    "#xxxxxxxxxxxxxxxxxxxxx..VV.v.............e.W",
    "#xxxxxxxxxxxxxxxxxxxxxx......j..j..O.......W",
    "#xxxxxxxxxxxxxxxxxxxxxxx............P......W",
    "#####################################UD#####",
]
# 4F：中文圖書 000–499、閱覽區、討論室、清華書房、清華故事牆
LEVEL_4F = [
    "############################################",
    "#..#########################################",
    "#T.#########################################",
    "#..#########################################",
    "#.##########################################",
    "#.##########################################",
    "#.##########################################",
    "#.######.................###################",
    "#.######...n...n...n.....###################",
    "#.######.................###################",
    "#.######...n...n...n.....###################",
    "W.######....O....O....O..###################",
    "W.........6..................H.H.H.H...H...W",
    "W...n...n..................................W",
    "W........................r.................W",
    "W...n...n..................................W",
    "W.O....O....O....O....O....O....O....O.....W",
    "###########.................a..............W",
    "#xxxxxxxxxx...n..................BBBB.BBBB.W",
    "#xxxxxxxxxxx.....n.......M.................W",
    "#xxxxxxxxxxxxx...................BBBB.BBBB.W",
    "#xxxxxxxxxxxxxxx.O....O....O....O....O.....W",
    "#xxxxxxxxxxxxxxxx.n.......a................W",
    "#xxxxxxxxxxxxxxxxx...............BBBB.BBBB.W",
    "#xxxxxxxxxxxxxxxxxx..n.....................W",
    "#xxxxxxxxxxxxxxxxxxx.............BBBB.BBBB.W",
    "#xxxxxxxxxxxxxxxxxxxx.O....O....O....O.....W",
    "#xxxxxxxxxxxxxxxxxxxxxn....................W",
    "#xxxxxxxxxxxxxxxxxxxxx......BBBB.BBBB......W",
    "#xxxxxxxxxxxxxxxxxxxxxx.............P......W",
    "#xxxxxxxxxxxxxxxxxxxxxxx...................W",
    "#xxxxxxxxxxxxxxxxxxxxxxx...O....O....UD#####",
    "#xxxxxxxxxxxxxxxxxxxxxxxx............#######",
    "#xxxxxxxxxxxxxxxxxxxxxxxx...BBBB.BBBB#######",
    "#xxxxxxxxxxxxxxxxxxxxxxxxx...........#######",
    "#xxxxxxxxxxxxxxxxxxxxxxxxx...........#######",
    "###########################GGGGGGGGG.#######",
    "###########################................#",
    "###########################..............Y.#",
    "###########################..X.X..X....X...#",
    "###########################..............Y.#",
    "###########################................#",
    "############################################",
]
BLOCKED = set("#WBKTCSOGDUkNEYLHQqVvZXxthmdcuejnra")

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

# 書架端板上的分類號（中國圖書分類法）
CALL_NUMBERS = ["000 總類", "100 哲學", "200 宗教", "300 自然科學", "400 應用科學",
                "500 社會科學", "600 中國史地", "700 世界史地", "800 語言文學",
                "900 藝術", "529 考試用書", "R 參考書"]

# 4F 清華故事牆
STORY_WALL = [("1925", "國學研究院：四大導師"), ("1931", "梅貽琦：大學者，有大師之謂也"),
              ("1956", "梅貽琦校長在新竹復校"), ("1962", "梅校長長眠於梅園"),
              ("2026", "這張合照最後一排，有人偷偷在讀微積分")]
HISTORY = [("1911", "清華學堂在北京成立"), ("1928", "改名國立清華大學"), ("1956", "在新竹建校"),
           ("1971", "成立大學部"), ("2013", "旺宏館（學習資源中心）啟用")]

def pane_arc(x0, x1, gap0, gap1, depth=3.0, top=0.5, n=24):
    """自助取書區的玻璃房：從北牆鼓出來的弧形玻璃（中間比較平），gap0–gap1 留一個入口。回傳入口左右兩段。"""
    def y(x):
        return top + depth * math.sin(math.pi * (x - x0) / (x1 - x0)) ** 0.4
    xs = [x0 + (x1 - x0) * i / n for i in range(n + 1)]
    left = [(x, y(x)) for x in xs if x < gap0] + [(gap0, y(gap0))]
    right = [(gap1, y(gap1))] + [(x, y(x)) for x in xs if x > gap1]
    left[0] = (x0, top)
    right[-1] = (x1, top)
    return left, right


def ellipse_pts(center, a, b, rot, a0, a1, n=14):
    """橢圓上從角度 a0 到 a1 的一段弧（格子座標，y 朝下）；rot 是長軸轉的角度。"""
    cx, cy = center
    cr, sr = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    pts = []
    for i in range(n + 1):
        t = math.radians(a0 + (a1 - a0) * i / n)
        x, y = a * math.cos(t), b * math.sin(t)
        pts.append((round(cx + x * cr - y * sr, 2), round(cy + x * sr + y * cr, 2)))
    return pts


FLOORS = {
    "1F": dict(level=LEVEL_1F, floor="tile", banks=[], safe=set(),
               hanging={(3, 6): ("聯合櫃臺", "Service Counter"), (13, 4): ("自助取書區", "Smart Bookshelves · Self Pick-up"),
                        (11, 4): ("資訊島", "Information Retrieval"), (7, 3): ("新知 · 閱報", "New Arrivals · Newspapers"),
                        (15, 10): ("知識集 · 主題展", "The Circle · Exhibition"), (22, 10): ("輕學區", "Light Up Zone"),
                        (18, 17): ("清沙龍", "Idea Hub"), (12, 17): ("逗留點", "Meeting Point"),
                        (8, 14): ("入館服務", "Reception"), (21, 19): ("樓梯間", "Stairs"), (3, 9): ("自助還書", "Book Drop")},
               posters=[((0, 5), (1, 0), "missing"), ((8, 0), (0, 1), "notice"), ((20, 4), (-1, 0), "missing"),
                        ((12, 23), (0, -1), "notice")],
               # 照 1F 實景照片：深灰地磚、白牆、白色平頂天花板配嵌燈、整面落地窗、淡紫色指示牌
               wall_tex="wallw", ceiling_tex="plaster", white=True, full_windows=True,
               sign_colors=((236, 236, 246), (72, 58, 128)),
               plank_ceiling=(0, 1, 4.6, 9.5),     # 聯合櫃臺上方的木條天花板
               grid_ceilings=[(20.5, 6, 25, 20.5), (14.5, 17.5, 20.5, 20.5)],   # 輕學區、清沙龍上方的深色格柵
               soffit=dict(center=(18, 22.5), radii=(3.2, 4.0, 4.8), a0=200, a1=340),   # 清沙龍一層層的弧形燈槽
               ropes=[[(7.2, 18.2), (7.9, 19.0), (8.6, 19.8)], [(9.8, 17.0), (10.6, 17.6)]],   # 入館閘門旁的紅色伸縮圍欄
               tvs=[((10, 16), (-1, 0))],          # 柱子上的公告螢幕
               pickup_gates=[(12.3, 13.7)],        # 自助取書區入口的紅白防盜門（接在玻璃房的開口兩邊）
               # 知識集：黑色地毯圓區、天花板上發光的白色環、從地上彎上去的白色弧形骨架、木色展示板
               circle=dict(center=(14.73, 11.6), radius=3.9, carpet=(38, 42, 64), halo=(0.95, 1.05, 1.35),
                           boards=[(11.7, 11.4, 90), (12.2, 13.3, 60), (13.5, 14.6, 25), (17.9, 14.0, -40)]),
               # 平面圖上的斜線和弧線（格子座標，可以有小數）：斜面落地窗、自助取書區的玻璃房、白色弧形矮櫃
               curves=[{'kind': 'glass', 'pts': [(1.58, 10.81), (9.4, 22.4)]},
                       {'kind': 'pane', 'pts': pane_arc(9.6, 19.4, 12.3, 13.7)[0]},
                       {'kind': 'pane', 'pts': pane_arc(9.6, 19.4, 12.3, 13.7)[1]},
                       {'kind': 'low', 'h': 0.55, 'pts': [(7.7, 7.56), (9.66, 6.91), (12.26, 5.73), (14.86, 5.21), (17.21, 5.34), (18.51, 5.99)]},
                       {'kind': 'low', 'h': 0.9, 'pts': [(15.78, 9.79), (16.28, 10.2), (16.63, 10.74), (16.8, 11.36), (16.78, 12.01), (16.55, 12.61), (16.15, 13.12), (15.61, 13.48), (14.99, 13.66), (14.35, 13.64), (13.74, 13.42), (13.22, 13.03), (12.86, 12.5), (12.67, 11.88), (12.68, 11.23)]},
                       {'kind': 'low', 'h': 1.0, 'pts': [(8.22, 17.48), (7.95, 17.22), (7.84, 16.86), (7.9, 16.48), (8.13, 16.19), (8.48, 16.03), (8.86, 16.06), (9.18, 16.26), (9.37, 16.59), (9.38, 16.96), (9.21, 17.3)]}]),
    "2F": dict(level=LEVEL_2F, floor="stripes", banks=[], safe=set(),
               wall_tex="wallw", ceiling_tex="plaster", white=True, band_windows=True,
               sign_colors=((236, 236, 246), (72, 58, 128)),
               shelf_labels=["學位論文 Theses"],
               hanging={(33, 30): ("樓梯間", "Stairs"), (9, 3): ("電腦教室", "Computer Lab II"),
                        (8, 8): ("電腦共學區", "Computer Lab I"), (15, 12): ("討論室", "Discussion Rooms"),
                        (16, 15): ("資訊島", "Information Retrieval"), (30, 13): ("熱門書刊區", "Popular Books and Periodicals"),
                        (30, 20): ("現期期刊", "Current Periodicals"), (25, 28): ("本校學位論文", "NTHU Theses"),
                        (11, 18): ("校史展示區", "University History")},
               posters=[((3, 10), (1, 0), "missing"), ((20, 31), (0, -1), "notice"), ((13, 15), (1, 0), "missing")],
               # 照 2F 實景照片：灰色條紋地毯、校史展示區的木條天花板、電腦教室的方格天花板、窗邊的格柵天花板
               slat_cells=[(4, 15), (4, 16), (4, 17), (5, 15), (5, 16), (5, 17), (5, 18), (6, 15), (6, 16), (6, 17), (6, 18), (7, 15), (7, 16), (7, 17), (7, 18), (8, 15), (8, 16), (8, 17), (8, 18), (8, 19), (9, 15), (9, 16), (9, 17), (9, 18), (9, 19), (10, 15), (10, 16), (10, 17), (10, 18), (10, 19), (10, 20), (11, 15), (11, 16), (11, 17), (11, 18), (11, 19), (11, 20), (11, 21), (12, 15), (12, 16), (12, 17), (12, 18), (12, 19), (12, 20), (12, 21), (13, 16), (13, 17), (13, 18), (13, 19), (13, 20), (13, 21), (13, 22), (14, 17), (14, 18), (14, 19), (14, 20), (14, 21), (14, 22), (14, 23), (15, 17), (15, 18), (15, 19), (15, 20), (15, 21), (15, 22), (15, 23), (15, 24), (16, 18), (16, 19), (16, 20), (16, 21), (16, 22), (16, 23), (16, 24), (16, 25), (17, 19), (17, 20), (17, 21), (17, 22), (17, 23), (17, 24), (17, 25), (17, 26), (18, 20), (18, 21), (18, 22), (18, 23), (18, 24), (18, 25), (18, 26), (18, 27), (18, 28), (19, 21), (19, 22), (19, 23), (19, 24), (19, 25), (19, 26), (19, 27), (19, 28), (19, 29), (20, 22), (20, 23), (20, 24), (20, 25), (20, 26), (20, 27), (20, 28), (20, 29), (20, 30), (21, 23), (21, 24), (21, 25), (21, 26), (21, 27), (21, 28), (21, 29), (21, 30), (22, 24), (22, 25), (22, 26), (22, 27), (22, 28), (22, 29), (22, 30), (23, 26), (23, 27), (23, 28), (23, 29), (23, 30), (24, 27), (24, 28), (24, 29), (24, 30), (25, 29), (25, 30)],
               ceiling_regions=[("ceiling", 5.5, 0.5, 12.5, 5.5)],
               grid_ceilings=[(34.5, 11.5, 39, 30.5)],
               tri_lights=[(6, 8), (10, 8), (6, 12), (10, 12), (8, 14)],
               label_counter=dict(a=(7.6, 18.0), b=(11.6, 19.6), lines=("校史展示區", "University History")),
               curves=[{'kind': 'glass', 'pts': [[5.41, 17.71], [6.39, 18.11], [7.34, 18.55], [8.28, 19.03], [9.2, 19.54], [10.1, 20.08], [10.98, 20.66], [11.84, 21.27], [12.68, 21.92], [13.48, 22.59], [14.27, 23.29], [15.02, 24.03], [15.75, 24.79], [16.45, 25.58], [17.12, 26.39], [17.75, 27.23], [18.36, 28.09], [18.93, 28.97], [19.47, 29.88], [19.97, 30.8], [20.44, 31.75]]},
                       {'kind': 'low', 'h': 2.4, 'pts': [[13.24, 16.19], [13.93, 16.66], [14.62, 17.14], [15.29, 17.65], [15.94, 18.17], [16.59, 18.7], [17.22, 19.26]]},
                       {'kind': 'low', 'h': 2.4, 'pts': [[18.87, 20.85], [19.42, 21.44], [19.95, 22.03], [20.48, 22.64], [20.98, 23.27], [21.47, 23.9]]},
                       {'kind': 'low', 'h': 2.4, 'pts': [[22.79, 25.78], [23.29, 26.58], [23.78, 27.4], [24.23, 28.23], [24.67, 29.07], [25.07, 29.92], [25.46, 30.79]]},
                       {'kind': 'glow', 'h': 2.6, 'pts': ellipse_pts((18.0, 26.0), 1.9, 1.9, 0, 225, 385)},    # 校史展示區發光的弧牆
                       {'kind': 'low', 'h': 1.0, 'pts': ellipse_pts((17.1, 15.75), 2.5, 1.6, -29, 35, 145)},   # 資訊島的橢圓矮櫃
                       {'kind': 'low', 'h': 1.0, 'pts': ellipse_pts((17.1, 15.75), 2.5, 1.6, -29, 215, 325)}]),
    "3F": dict(level=LEVEL_3F, floor="stripes3", banks=[], safe=set(),
               wall_tex="wallw", ceiling_tex="plaster", white=True, band_windows=True, white_shelves=True,
               sign_colors=((236, 236, 246), (72, 58, 128)), blind_col=(58, 58, 64, 240),
               shelf_labels=["DVD 影片", "CD 音樂"],
               hanging={(37, 30): ("樓梯間", "Stairs"), (20, 20): ("視聽聆賞席", "Viewing Carrels"),
                        (32, 22): ("媒體區", "Audio-Visual Collection"), (41, 21): ("發呆區", "Relaxing and Inspiration"),
                        (31, 28): ("電視區", "TV Area"), (8, 13): ("多人聆賞席", "Group Carrels"),
                        (4, 15): ("語言學習區", "Language Learning"), (10, 12): ("小舞台", "Practice Room"),
                        (14, 12): ("簡報練習室", "Presentation Rehearsal Studio"), (19, 12): ("怡嚴音樂聆賞室", "Yee-Yen Listening Room"),
                        (16, 6): ("團體室 · 紅氣球", "Group Room"), (28, 13): ("服務台", "Information Desk"),
                        (21, 13): ("資訊島", "Information Retrieval")},
               posters=[((1, 13), (-1, 0), "missing"), ((20, 12), (0, -1), "notice"), ((30, 30), (0, 1), "missing")],
               # 照 3F 實景照片：深咖啡條紋地毯、白色天花板、整面窗配深色捲簾、小舞台是木地板
               floor_regions=[("wood", 8, 7, 12, 11)], practice_room=(8, 7, 11, 10),
               bell_lights=[(15, 18), (18, 21), (21, 23), (24, 24), (24, 27)],
               curves=[{'kind': 'glass', 'pts': [(10.5, 16.5), (10.53, 17.98), (11.82, 18.61), (13.07, 19.3), (14.29, 20.05), (15.47, 20.87), (16.61, 21.74), (17.7, 22.66), (18.75, 23.64), (19.74, 24.67), (20.68, 25.75), (21.57, 26.88), (22.39, 28.05), (23.16, 29.25), (23.87, 30.5)]},
                       {'kind': 'low', 'h': 1.0, 'pts': ellipse_pts((21.08, 15.79), 2.3, 1.4, 25, 35, 145)},    # 資訊島
                       {'kind': 'low', 'h': 1.0, 'pts': ellipse_pts((21.08, 15.79), 2.3, 1.4, 25, 215, 325)}]),
    "4F": dict(level=LEVEL_4F, floor="stripes4", banks=[], safe=set(),
               wall_tex="wallw", ceiling_tex="slats", white=True, band_windows=True, white_shelves=True,
               sign_colors=((236, 236, 246), (72, 58, 128)),
               shelf_labels=["000 總類", "010 目錄學", "100 哲學類", "200 宗教類", "300 科學類",
                             "310 數學", "400 應用科學類", "410 醫藥", "490 商業"],
               history=STORY_WALL, whiteboard=(3, 2),
               hanging={(37, 30): ("樓梯間", "Stairs"), (1, 5): ("討論室", "Discussion Room"),
                        (32, 13): ("清華故事牆", "NTHU Story Wall"), (35, 22): ("中文圖書 000–499", "Oriental Language Books"),
                        (21, 13): ("資訊島", "Information Retrieval"), (6, 14): ("閱覽區", "Reading Area"),
                        (21, 22): ("閱覽區", "Reading Area"), (33, 38): ("清華書房 · 推薦閱讀", "NTHU Mini-Library")},
               posters=[((5, 16), (0, 1), "missing"), ((26, 12), (0, -1), "notice"), ((36, 34), (1, 0), "missing")],
               # 照 4F 實景照片：深色木條天花板、灰褐條紋地毯、白書架黃色側牌、NTHU 字母書牆、雲朵閱覽桌
               wall_texts=[((27, 12), (0, -1), ("清華圖書館 百年物語", "Visit the Library. Read a Story"))],
               nthu_wall=(27, 35, 36),
               halo=dict(center=(21.04, 15.47), radius=2.4),
               curves=[{'kind': 'glass', 'pts': [(10.5, 17.5), (10.83, 18.04), (12.07, 18.68), (13.28, 19.37), (14.46, 20.12), (15.59, 20.93), (16.69, 21.79), (17.75, 22.71), (18.76, 23.67), (19.72, 24.68), (20.63, 25.74), (21.49, 26.84), (22.3, 27.98), (23.05, 29.15), (23.74, 30.36), (24.38, 31.61), (24.95, 32.88), (25.46, 34.18), (25.91, 35.5)]},
                       {'kind': 'low', 'h': 1.3, 'pts': [(12.53, 16.46), (17.14, 16.46), (19.09, 17.77)]},     # 閱覽區的矮書櫃隔間
                       {'kind': 'low', 'h': 1.3, 'pts': [(20.51, 18.84), (22.11, 20.61), (24.23, 22.91), (25.48, 24.51), (25.65, 27.17)]},
                       {'kind': 'low', 'h': 1.3, 'pts': [(25.65, 29.3), (25.65, 31.07), (26.89, 35.86)]},
                       {'kind': 'low', 'h': 1.0, 'pts': ellipse_pts((21.04, 15.47), 2.3, 1.6, 25, 35, 145)},    # 資訊島
                       {'kind': 'low', 'h': 1.0, 'pts': ellipse_pts((21.04, 15.47), 2.3, 1.6, 25, 215, 325)}]),
    "B1": dict(level=LEVEL_B1, banks=BANKS_B1, floor="stone", safe=set(),
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
        self.hides = []         # 可以躲進去的桌子底下（位置）
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
            "tile": t(tx.tile()), "wallw": t(tx.white_wall()), "plaster": t(tx.plaster()), "planks": t(tx.planks()),
            "cubbies": t(tx.cubbies(0)), "grid": t(tx.grid()),
            "stripes": t(tx.stripes()), "blind": t(tx.blind()),
            "stripes3": t(tx.stripes((58, 48, 44), (196, 192, 186), 18)),
            "stripes4": t(tx.stripes((128, 120, 112), (66, 56, 52), 19)), "slats": t(tx.slats()),
            "nthu": t(tx.nthu_letters(self.font_path), "bilinear"),
            "missing": t(tx.poster_missing(self.font_path), "bilinear"),
            "notice": t(tx.poster_notice(self.font_path), "bilinear"),
        }
        self.book_tex = [t(tx.books(i)) for i in range(6)]
        self.t["covers"] = [t(tx.covers(i)) for i in range(4)]
        self.t["mags"] = [t(tx.magazines(i)) for i in range(4)]
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
        ceiling = self.spec.get("ceiling_tex", "ceiling")
        k = 1 if ceiling in ("plaster", "slats") else 3    # 嵌燈兩公尺一盞；礦纖板 60 公分一塊
        Entity(model="quad", position=center + Vec3(0, WALL_H, 0), scale=(w, d), rotation_x=-90,
               texture=self.t[ceiling], texture_scale=(self.cols * k, self.rows * k),
               color=color.rgb(0.95, 0.95, 0.95) if ceiling in ("plaster", "slats") else color.rgb(0.85, 0.85, 0.85))
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
                elif ch == "t":
                    self.round_table(c, r, p)
                elif ch == "h":
                    self.chair_rows(p)
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
                elif ch in "123456":
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
                elif ch in "Vv":
                    self.booth(p, live=ch == "v")
                elif ch == "Z":
                    self.stage(c, r, p)
                elif ch == "X":
                    self.case(p)
                elif ch == "k":
                    self.pc_desk(p)
                elif ch == "m":
                    self.magazine_wall(c, r, p)
                elif ch == "d":
                    self.window_desk(c, r, p)
                elif ch == "c":
                    self.tub_chairs(p)
                elif ch == "u":
                    self.group_booth(p)
                elif ch == "e":
                    self.egg_chair(p)
                elif ch == "j":
                    self.tv_booth(p)
                elif ch == "n":
                    self.cloud_desk(p)
                elif ch == "r":
                    self.round_sofa(p)
                elif ch == "a":
                    self.armchairs(p)
                elif ch == "x":
                    self.collider(p + Vec3(0, WALL_H / 2, 0), (CELL, WALL_H, CELL), occludes=False)
        self.curves()
        if "circle" in self.spec:
            self.circle(self.spec["circle"])
        for name, *rect in self.spec.get("floor_regions", []):
            self.floor_region(name, *rect)
        if "practice_room" in self.spec:
            self.practice_room(*self.spec["practice_room"])
        for cell in self.spec.get("bell_lights", []):
            self.bell_light(cell_pos(*cell))
        for (c, r), d, lines in self.spec.get("wall_texts", []):
            self.wall_text(cell_pos(c, r), Vec3(d[0], 0, -d[1]), lines)
        if "nthu_wall" in self.spec:
            self.nthu_wall(*self.spec["nthu_wall"])
        if "halo" in self.spec:
            self.halo(**self.spec["halo"])
        for cell in self.spec.get("slat_cells", []):
            self.slat_ceiling(*cell)
        for name, *rect in self.spec.get("ceiling_regions", []):
            self.ceiling_region(name, *rect)
        for cell in self.spec.get("tri_lights", []):
            self.tri_light(cell_pos(*cell))
        if "label_counter" in self.spec:
            self.label_counter(**self.spec["label_counter"])
        if "plank_ceiling" in self.spec:
            self.plank_ceiling(*self.spec["plank_ceiling"])
        for rect in self.spec.get("grid_ceilings", []):
            self.grid_ceiling(*rect)
        if "soffit" in self.spec:
            self.soffit(**self.spec["soffit"])
        for g0, g1 in self.spec.get("pickup_gates", []):
            arc = pane_arc(9.6, 19.4, g0, g1)
            self.pickup_gate(*arc[0][-1])
            self.pickup_gate(*arc[1][0])
        for pts in self.spec.get("ropes", []):
            self.rope(pts)
        for (c, r), d in self.spec.get("tvs", []):
            self.tv(cell_pos(c, r), Vec3(d[0], 0, -d[1]))
        for (c, r), lines in self.spec["hanging"].items():
            self.hanging_sign(cell_pos(c, r), lines)
        for (c, r), (dc, dr), kind in self.spec["posters"]:
            dvec = Vec3(dc, 0, -dr)
            self.quad(cell_pos(c, r) + dvec * (CELL / 2 + 0.01) + Vec3(self.rng.uniform(-0.4, 0.4), 1.55, 0),
                      (0.6, 0.85), self.t[kind], rot=(0, facing_y(dvec), self.rng.uniform(-4, 4)))
        self.ceiling_lights()

    def curves(self):
        """平面圖上的斜線和弧線，用很多段細長方塊接起來：玻璃是整面落地窗，low 是展示架、長椅這類矮牆。
        矮牆經過的格子從 walkable 拿掉，館員和室友才不會穿過去。"""
        white = self.spec.get("white")
        for spec in self.spec.get("curves", []):
            glass = spec["kind"] == "glass"
            pane = spec["kind"] == "pane"
            h = WALL_H if glass or pane else spec.get("h", 1.0)
            pts = [Vec3(c * CELL, 0, -r * CELL) for c, r in spec["pts"]]
            for a, b in zip(pts, pts[1:]):
                d = b - a
                rot = math.degrees(math.atan2(d.x, d.z))
                mid = (a + b) / 2
                if pane:   # 室內的玻璃隔間：透明玻璃，上面一圈白色的弧形框，下面一條白色底座
                    Entity(model="cube", position=mid + Vec3(0, h / 2, 0), rotation_y=rot, scale=(0.05, h, d.length() + 0.02),
                           collider="box", color=color.rgba32(170, 200, 210, 40))
                    Entity(model="cube", position=mid + Vec3(0, h - 0.35, 0), rotation_y=rot, scale=(0.35, 0.7, d.length() + 0.1),
                           color=color.rgb32(245, 245, 245))
                    Entity(model="cube", position=mid + Vec3(0, 0.06, 0), rotation_y=rot, scale=(0.2, 0.12, d.length() + 0.1),
                           color=color.rgb32(235, 235, 235))
                    continue
                if spec["kind"] == "glow":   # 2F 校史展示區：整面會發光的白色弧牆
                    Entity(model="cube", position=mid + Vec3(0, h / 2, 0), rotation_y=rot, scale=(0.25, h, d.length() + 0.08),
                           collider="box", color=color.rgb(1.35, 1.35, 1.3))
                    continue
                seg = Entity(model="cube", position=mid + Vec3(0, h / 2, 0), rotation_y=rot,
                             scale=(0.2 if glass else 0.3, h, d.length() + 0.08), collider="box",
                             texture=self.t["window"] if glass else (None if white else self.t["wood"]),
                             texture_scale=(d.length() / CELL, 1) if glass else (1, 1),
                             color=color.rgb(SHADE, SHADE, SHADE) if glass else
                             (color.rgb32(238, 238, 236) if white else color.rgb32(200, 190, 170)))
                if glass:
                    self.solids.append(seg)
                elif white:   # 白色矮櫃上面一層淺灰檯面
                    Entity(model="cube", position=mid + Vec3(0, h + 0.02, 0), rotation_y=rot,
                           scale=(0.38, 0.04, d.length() + 0.1), color=color.rgb32(205, 208, 212))
            if not glass:
                for cell in list(self.walkable):
                    if any(self.seg_dist(cell, p, q) < (0.4 if pane else 0.6) for p, q in zip(spec["pts"], spec["pts"][1:])):
                        self.walkable.discard(cell)

    @staticmethod
    def seg_dist(cell, p, q):
        """格子中心到線段 pq 的距離（格子座標）。"""
        (x, y), (x1, y1), (x2, y2) = cell, p, q
        dx, dy = x2 - x1, y2 - y1
        t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy or 1)))
        return math.hypot(x - x1 - t * dx, y - y1 - t * dy)

    def open_sides(self, c, r):
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if self.char(c + dc, r + dr) not in "#W":
                yield Vec3(dc, 0, -dr)

    def wall(self, c, r, p):
        if not any(True for _ in self.open_sides(c, r)):
            return   # 被牆包住的格子看不到，不用蓋
        self.box(p + Vec3(0, WALL_H / 2, 0), (CELL, WALL_H, CELL), self.t[self.spec.get("wall_tex", "wall")])
        self.collider(p + Vec3(0, WALL_H / 2, 0), (CELL, WALL_H, CELL))

    def window(self, c, r, p):
        if self.spec.get("band_windows"):
            self.band_window(c, r, p)
            return
        if self.spec.get("full_windows"):
            self.full_window(c, r, p)
            return
        self.box(p + Vec3(0, 0.45, 0), (CELL, 0.9, CELL), self.t["wall"], tscale=(1, 0.3))
        self.box(p + Vec3(0, WALL_H - 0.15, 0), (CELL, 0.3, CELL), self.t["wall"], tscale=(1, 0.1))
        self.box(p + Vec3(0, 1.85, 0), (CELL, 1.9, CELL * 0.6), self.t["window"])
        for side in self.open_sides(c, r):
            self.box(p + side * (CELL / 2) + Vec3(0, 0.92, 0), (CELL if side.z else 0.3, 0.05, 0.3 if side.z else CELL),
                     col=color.rgb32(170, 165, 150))
            pool = self.quad(p + side * (CELL * 0.9) + Vec3(0, 0.015, 0), (CELL * 1.4, CELL * 1.1),
                             self.t["glow"], col=color.rgba32(255, 240, 200, 90), rot=(90, 0, 0))   # 窗邊的陽光
        self.collider(p + Vec3(0, WALL_H / 2, 0), (CELL, WALL_H, CELL))

    def full_window(self, c, r, p):
        """1F 輕學區那種從地板到天花板的整面落地窗：黑色窗框，中間一條橫框。"""
        frame = color.rgb32(50, 52, 56)
        sides = list(self.open_sides(c, r))
        across_x = any(side.x for side in sides)     # 窗戶朝東西：玻璃沿著 z 方向排
        self.box(p + Vec3(0, WALL_H / 2, 0), (0.3, WALL_H, CELL) if across_x else (CELL, WALL_H, 0.3), self.t["window"])
        for side in sides:
            face = p + side * (CELL * 0.16)
            along = Vec3(side.z, 0, side.x)
            for k in (-0.5, 0, 0.5):
                self.box(face + along * (k * CELL) + Vec3(0, WALL_H / 2, 0),
                         (0.07 if side.z else 0.05, WALL_H, 0.05 if side.z else 0.07), col=frame)
            for y in (0.04, 2.25, WALL_H - 0.05):
                self.box(face + Vec3(0, y, 0), (CELL if side.z else 0.06, 0.07, 0.06 if side.z else CELL), col=frame)
            self.quad(p + side * (CELL * 0.9) + Vec3(0, 0.015, 0), (CELL * 1.4, CELL * 1.3),
                      self.t["glow"], col=color.rgba32(255, 245, 220, 80), rot=(90, 0, 0))   # 窗邊的陽光
        self.collider(p + Vec3(0, WALL_H / 2, 0), (CELL, WALL_H, CELL))

    def band_window(self, c, r, p):
        """2F 窗邊：白色窗台，上面一整排玻璃，上半截拉下米白色的捲簾。"""
        sides = list(self.open_sides(c, r))
        across_x = any(side.x for side in sides)
        thin = (lambda t, h, y: self.box(p + Vec3(0, y, 0), (t, h, CELL) if across_x else (CELL, h, t)))
        self.box(p + Vec3(0, 0.4, 0), (0.5, 0.8, CELL) if across_x else (CELL, 0.8, 0.5), self.t["wallw"], tscale=(1, 0.3))
        self.box(p + Vec3(0, WALL_H - 0.2, 0), (0.5, 0.4, CELL) if across_x else (CELL, 0.4, 0.5), col=color.rgb32(240, 240, 240))
        self.box(p + Vec3(0, 1.85, 0), (0.1, 2.1, CELL) if across_x else (CELL, 2.1, 0.1), self.t["window"])
        for side in sides:
            face = p + side * 0.12
            along = Vec3(side.z, 0, side.x)
            self.box(face + Vec3(0, 0.81, 0), (0.3, 0.03, CELL) if across_x else (CELL, 0.03, 0.3), col=color.rgb32(225, 225, 225))
            drop = 0.5 + 0.5 * ((c * 3 + r * 5) % 3) / 2     # 每一片捲簾拉下來的長度不太一樣
            self.box(face + Vec3(0, WALL_H - 0.4 - drop / 2, 0), (0.02, drop, CELL * 0.98) if across_x else (CELL * 0.98, drop, 0.02),
                     self.t["blind"], col=color.rgba32(*self.spec.get("blind_col", (255, 255, 255, 230))))
            for k in (-0.5, 0.5):
                self.box(face + along * (k * CELL) + Vec3(0, 1.85, 0), (0.06, 2.1, 0.06), col=color.rgb32(70, 72, 76))
            self.quad(p + side * (CELL * 0.9) + Vec3(0, 0.015, 0), (CELL * 1.4, CELL * 1.1),
                      self.t["glow"], col=color.rgba32(255, 245, 220, 70), rot=(90, 0, 0))   # 窗邊的陽光
        self.collider(p + Vec3(0, WALL_H / 2, 0), (CELL, WALL_H, CELL))

    def pc_desk(self, p):
        """電腦共學區：白色 A 字腳長桌，中間一片霧面隔板，兩邊各一台懸臂螢幕和白色旋轉椅。"""
        white, steel = color.rgb32(242, 242, 240), color.rgb32(190, 192, 196)
        top = p + Vec3(0, 0.75, 0)
        self.box(top - Vec3(0, 0.02, 0), (CELL * 1.01, 0.05, 1.5), col=white)
        for x in (-0.85, 0.85):     # A 字腳
            for lean in (-1, 1):
                leg = self.box(p + Vec3(x, 0.37, lean * 0.3), (0.05, 0.8, 0.05), col=white)
                leg.rotation_x = lean * 22
        self.box(top + Vec3(0, 0.3, 0), (CELL * 0.98, 0.6, 0.03), col=color.rgba32(225, 230, 232, 200))
        for side in (1, -1):
            self.box(top + Vec3(0, 0.22, side * 0.1), (0.03, 0.42, 0.03), col=steel)
            self.box(top + Vec3(0, 0.42, side * 0.2), (0.55, 0.34, 0.03), col=color.rgb32(25, 25, 28))
            Entity(model="quad", position=top + Vec3(0, 0.42, side * 0.22), scale=(0.5, 0.3), rotation_y=0 if side > 0 else 180,
                   texture=self.t["screen"], color=color.rgb(1.1, 1.1, 1.1))
            if self.rng.random() < 0.85:
                self.swivel_chair(p + Vec3(self.rng.uniform(-0.3, 0.3), 0, side * 1.05),
                                  (0 if side > 0 else 180) + self.rng.uniform(-25, 25))
        self.clutter(top, 0.6)
        self.collider(p + Vec3(0, 0.5, 0), (CELL, 1.0, 1.5), occludes=False)

    def magazine_wall(self, c, r, p):
        """期刊區：靠牆的一整面長木櫃，斜板上立著一本本雜誌。"""
        face = next((s for s in self.open_sides(c, r) if self.char(c + int(s.x), r - int(s.z)) not in BLOCKED), Vec3(0, 0, -1))
        back = p - face * (CELL * 0.3)
        self.box(back + Vec3(0, 1.1, 0), (CELL, 2.2, 0.8) if face.z else (0.8, 2.2, CELL), col=color.rgb32(196, 160, 112))
        self.quad(back + face * 0.41 + Vec3(0, 1.1, 0), (CELL * 0.98, 2.1), self.t["mags"][(c + r) % 4],
                  rot=(0, facing_y(face), 0))
        self.collider(back + Vec3(0, 1.1, 0), (CELL, 2.2, 0.8) if face.z else (0.8, 2.2, CELL))

    def window_desk(self, c, r, p):
        """窗邊閱覽桌：面窗的長桌，兩邊白色隔板，桌上一條燈。"""
        east = Vec3(1, 0, 0)
        top = p + Vec3(0, 0.75, 0)
        self.box(top - Vec3(0, 0.02, 0), (0.9, 0.05, CELL * 0.98), col=color.rgb32(222, 196, 156))
        self.box(p + Vec3(0.4, 0.37, 0), (0.05, 0.74, CELL * 0.9), col=color.rgb32(235, 235, 235))
        for z in (-0.98, 0.98):
            self.box(top + Vec3(0, 0.25, z), (0.9, 0.5, 0.03), col=color.rgb32(238, 238, 236))
        self.box(top + Vec3(0.38, 0.45, 0), (0.06, 0.04, CELL * 0.9), col=color.rgb(1.3, 1.3, 1.25))
        self.clutter(top, 0.2)
        if self.rng.random() < 0.85:
            self.swivel_chair(p - east * 0.75 + Vec3(0, 0, self.rng.uniform(-0.3, 0.3)), 90 + self.rng.uniform(-20, 20))
        self.hides.append(p)
        self.collider(p + Vec3(0, 0.45, 0), (0.9, 0.9, CELL * 0.98), occludes=False)

    def tub_chairs(self, p):
        """期刊區的白色桶狀單人椅，兩張對坐，中間一張鍍鉻小圓桌。"""
        for side in (1, -1):
            ch = Entity(parent=self.group(None), position=p + Vec3(side * 0.6, 0, 0), rotation_y=90 * side + self.rng.uniform(-15, 15))
            Entity(parent=ch, model=Cylinder(resolution=12, radius=0.38, height=0.42), color=color.rgb32(242, 242, 242))
            Entity(parent=ch, model="cube", position=(0, 0.6, 0.25), scale=(0.72, 0.36, 0.2), color=color.rgb32(242, 242, 242))
            Entity(parent=ch, model="cube", position=(0, 0.44, 0), scale=(0.6, 0.06, 0.55), color=color.rgb32(210, 210, 212))
        Entity(parent=self.group(None), model=Cylinder(resolution=12, radius=0.25, height=0.03), position=p + Vec3(0, 0.5, 0),
               color=color.rgb32(200, 202, 206))
        self.box(p + Vec3(0, 0.25, 0), (0.04, 0.5, 0.04), col=color.rgb32(200, 202, 206))
        self.collider(p + Vec3(0, 0.4, 0), (CELL * 0.9, 0.8, 1.0), occludes=False)

    def slat_ceiling(self, c, r):
        """校史展示區上面的木條天花板。"""
        self.quad(cell_pos(c, r) + Vec3(0, WALL_H - 0.03, 0), (CELL, CELL), self.t["planks"], rot=(-90, 0, 0))

    def ceiling_region(self, name, c0, r0, c1, r1):
        """某一區換一種天花板，例如電腦教室的礦纖板。"""
        x0, x1 = (c0 - 0.5) * CELL, (c1 - 0.5) * CELL
        z0, z1 = -(r0 - 0.5) * CELL, -(r1 - 0.5) * CELL
        w, d = abs(x1 - x0), abs(z1 - z0)
        Entity(model="quad", position=Vec3((x0 + x1) / 2, WALL_H - 0.02, (z0 + z1) / 2), scale=(w, d), rotation_x=-90,
               texture=self.t[name], texture_scale=(w / CELL * 3, d / CELL * 3), color=color.rgb(0.9, 0.9, 0.9))

    def tri_light(self, p):
        """電腦共學區的三叉吊燈：一根吊桿，三支白色燈管往外伸。"""
        hub = p + Vec3(0, WALL_H - 0.7, 0)
        self.box(hub + Vec3(0, 0.35, 0), (0.02, 0.7, 0.02), col=color.rgb32(60, 60, 60))
        for k in range(3):
            arm = Entity(parent=self.group(None), position=hub, rotation_y=k * 120 + 15)
            self.box((0, 0, 0.55), (0.08, 0.06, 1.1), col=color.rgb32(245, 245, 245), parent=arm)
            self.box((0, -0.035, 0.55), (0.05, 0.01, 1.0), col=color.rgb(1.5, 1.5, 1.45), parent=arm)

    def label_counter(self, a, b, lines):
        """校史展示區入口的白色發光長櫃，正面寫著區名。"""
        pa, pb = Vec3(a[0] * CELL, 0, -a[1] * CELL), Vec3(b[0] * CELL, 0, -b[1] * CELL)
        d = pb - pa
        rot = math.degrees(math.atan2(d.x, d.z))
        mid = (pa + pb) / 2
        Entity(model="cube", position=mid + Vec3(0, 0.5, 0), rotation_y=rot, scale=(0.6, 1.0, d.length()),
               collider="box", color=color.rgb(1.25, 1.25, 1.22))
        normal = Vec3(-d.z, 0, d.x).normalized()      # 朝東北，面向走道
        tex = self.text_tex(list(lines), w=320, h=64, bg=(250, 250, 250), fg=(30, 30, 34), sizes=[36, 14])
        self.quad(mid + normal * 0.31 + Vec3(0, 0.55, 0), (3.0, 0.6), tex, rot=(0, math.degrees(math.atan2(-normal.x, -normal.z)), 0))
        for cell in list(self.walkable):
            if self.seg_dist(cell, a, b) < 0.6:
                self.walkable.discard(cell)

    def shelf(self, c, r, p, run):
        self.shelf_runs.setdefault(run, []).append((c, r))
        tex = self.book_tex[(c * 7 + r * 3) % len(self.book_tex)]
        white = self.spec.get("white_shelves")    # 3F／4F 是白色的書架，側面一塊黃色的分類牌
        self.box(p + Vec3(0, 1.1, 0), (CELL, 2.2, 0.62), None if white else self.t["metal"],
                 col=color.rgb32(238, 238, 236) if white else color.white)
        for side in (1, -1):
            self.quad(p + Vec3(0, 1.08, side * 0.315), (CELL * 0.98, 2.1), tex,
                      rot=(0, 0 if side < 0 else 180, 0))
        for dc in (-1, 1):
            if self.char(c + dc, r) != "B":
                end = Vec3(dc, 0, 0)
                self.box(p + end * (CELL / 2) + Vec3(0, 1.1, 0), (0.06, 2.24, 0.66),
                         col=color.rgb32(240, 240, 238) if white else color.rgb32(90, 96, 100))
                labels = self.spec.get("shelf_labels", CALL_NUMBERS)
                label = labels[(run - 1) % len(labels)]
                code, name = label.split(" ")
                self.quad(p + end * (CELL / 2 + 0.035) + Vec3(0, 1.75, 0), (0.5, 0.26),
                          self.text_tex([code, name], w=160, h=80, bg=(245, 200, 40) if white else (30, 34, 40),
                                        fg=(40, 36, 30) if white else (235, 235, 225), sizes=[30, 20]),
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

    def shell_chair(self, pos, rot, col):
        """1F 那種一體成型的塑膠殼椅：彎彎的椅背，四支細鐵腳。"""
        ch = Entity(parent=self.group(None), position=pos, rotation_y=rot)
        leg = color.rgb32(180, 182, 186)
        self.box((0, 0.46, 0), (0.44, 0.05, 0.42), col=col, parent=ch)
        self.box((0, 0.72, 0.2), (0.42, 0.48, 0.04), col=col, parent=ch)
        self.box((0, 0.72, 0.2), (0.44, 0.48, 0.035), col=col, parent=ch).rotation_x = -8
        for x in (-0.18, 0.18):
            for z in (-0.17, 0.17):
                self.box((x, 0.22, z), (0.025, 0.46, 0.025), col=leg, parent=ch)

    def floor_lamp(self, pos):
        """輕學區窗邊的黑色落地燈。"""
        black = color.rgb32(35, 35, 38)
        self.box(pos + Vec3(0, 0.02, 0), (0.35, 0.04, 0.35), col=black)
        self.box(pos + Vec3(0, 0.95, 0), (0.035, 1.9, 0.035), col=black)
        Entity(parent=self.group(None), model=Cone(resolution=10, radius=0.22, height=0.28, add_bottom=False),
               position=pos + Vec3(0, 1.98, 0), color=black, rotation_x=180, double_sided=True)

    def round_table(self, c, r, p):
        """輕學區：白色圓桌（一支中柱、十字腳），旁邊擺黑白兩色的殼椅。"""
        self.hides.append(p)
        top = p + Vec3(0, 0.74, 0)
        Entity(parent=self.group(None), model=Cylinder(resolution=16, radius=0.55, height=0.04),
               position=top - Vec3(0, 0.04, 0), color=color.rgb32(222, 200, 165))
        self.box(p + Vec3(0, 0.36, 0), (0.07, 0.72, 0.07), col=color.rgb32(190, 192, 196))
        for rot in (45, 135):
            self.box(p + Vec3(0, 0.03, 0), (0.9, 0.04, 0.06), col=color.rgb32(190, 192, 196)).rotation_y = rot
        for k in range(4):
            if self.rng.random() < 0.8:
                ang = math.radians(k * 90 + self.rng.uniform(-20, 20))
                col = color.rgb32(245, 245, 245) if self.rng.random() < 0.5 else color.rgb32(40, 42, 46)
                self.shell_chair(p + Vec3(math.sin(ang), 0, math.cos(ang)) * 0.85, math.degrees(ang) + self.rng.uniform(-15, 15), col)
        if self.char(c + 2, r) == "W" or self.char(c + 1, r) == "W":
            self.floor_lamp(p + Vec3(CELL * 0.55, 0, 0.5))
        self.clutter(top + Vec3(0, 0.0, 0), 0.25)
        self.collider(p + Vec3(0, 0.4, 0), (1.1, 0.8, 1.1), occludes=False)

    def chair_rows(self, p):
        """清沙龍：一排排紅、白、橘、藍的殼椅，面向北邊的白板。"""
        cols = [color.rgb32(185, 40, 35), color.rgb32(240, 240, 240), color.rgb32(215, 105, 45), color.rgb32(30, 95, 140),
                color.rgb32(35, 36, 40)]
        for i, x in enumerate((-0.6, 0, 0.6)):
            for j, z in enumerate((0.45, -0.45)):
                if self.rng.random() < 0.92:
                    self.shell_chair(p + Vec3(x, 0, z), 180 + self.rng.uniform(-6, 6),
                                     cols[(i + int(p.x)) % 4] if self.rng.random() < 0.6 else self.rng.choice(cols))
        self.collider(p + Vec3(0, 0.5, 0), (CELL * 0.9, 1.0, CELL * 0.9), occludes=False)

    def circle(self, spec):
        """知識集：黑色地毯圓區，天花板一圈發光的白色環，三條白色弧形骨架從地上彎上去接到環上，木色展示板。"""
        cx, cy = spec["center"]
        R = spec["radius"] * CELL
        center = Vec3(cx * CELL, 0, -cy * CELL)
        Entity(model=Cylinder(resolution=48, radius=R, height=0.02), position=center + Vec3(0, 0.005, 0),
               color=color.rgb32(*spec.get("carpet", (30, 31, 34))))
        Entity(model=Cylinder(resolution=48, radius=R + 0.08, height=0.012), position=center,
               color=color.rgb32(170, 172, 176))   # 不鏽鋼收邊
        halo_r, n = R * 0.9, 40
        for i in range(n):   # 天花板的白色光環
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            p0 = center + Vec3(math.cos(a0), 0, math.sin(a0)) * halo_r
            p1 = center + Vec3(math.cos(a1), 0, math.sin(a1)) * halo_r
            seg = Entity(model="cube", position=(p0 + p1) / 2 + Vec3(0, WALL_H - 0.3, 0), scale=(1.1, 0.45, (p1 - p0).length() + 0.05),
                         color=color.rgb(*spec.get("halo", (1.25, 1.25, 1.3))))
            seg.look_at(p1 + Vec3(0, WALL_H - 0.3, 0))
            seg.rotation_x = 0
        for start in (200, 320, 80):   # 白色弧形骨架：從地毯邊緣斜斜地彎上去
            prev = None
            for k in range(9):
                t = k / 8
                a = math.radians(start + 50 * t)
                rad = R * (1.0 - 0.1 * t)
                pt = center + Vec3(math.cos(a) * rad, (WALL_H - 0.5) * math.sin(t * math.pi / 2), math.sin(a) * rad)
                if prev is not None:
                    seg = Entity(model="cube", position=(prev + pt) / 2, scale=(0.35, 0.06, (pt - prev).length() + 0.08),
                                 color=color.rgb32(245, 245, 245))
                    seg.look_at(pt)
                prev = pt
        for k, (c, r, rot) in enumerate(spec["boards"]):
            self.cover_board(Vec3(c * CELL, 0, -r * CELL), rot, k)

    def cover_board(self, p, rot, k):
        """木色展示板：兩面都貼著書的封面，底下一個木頭底座。"""
        b = Entity(position=p, rotation_y=rot)
        Entity(parent=b, model="cube", position=(0, 1.15, 0), scale=(0.9, 1.9, 0.12), color=color.rgb32(214, 190, 150))
        for side in (1, -1):
            Entity(parent=b, model="quad", position=(0, 1.15, side * 0.065), scale=(0.88, 1.85),
                   texture=self.t["covers"][(k + (side > 0)) % 4], rotation_y=0 if side < 0 else 180)
        Entity(parent=b, model="cube", position=(0, 0.1, 0), scale=(0.75, 0.2, 0.35), color=color.rgb32(200, 175, 135))
        Entity(parent=b, model="cube", position=(0, 0.6, 0), scale=(0.95, 0.03, 0.25), color=color.rgb32(185, 160, 125), collider="box")
        self.collider(p + Vec3(0, 1.0, 0), (0.95, 2.0, 0.95), occludes=False).rotation_y = rot

    def info_desk(self, p):
        """1F 資訊島：一長條淺木色桌面、不鏽鋼桌腳、懸臂螢幕，配白色旋轉椅。"""
        top = p + Vec3(0, 0.78, 0)
        self.box(top - Vec3(0, 0.02, 0), (CELL * 1.01, 0.05, 0.85), col=color.rgb32(225, 200, 160))
        self.box(p + Vec3(0, 0.38, 0), (0.08, 0.76, 0.08), col=color.rgb32(185, 188, 192))
        self.box(top + Vec3(0, 0.02, 0.15), (0.22, 0.02, 0.16), col=color.rgb32(60, 60, 62))
        self.box(top + Vec3(0, 0.25, 0.22), (0.03, 0.45, 0.03), col=color.rgb32(185, 188, 192))
        self.box(top + Vec3(0, 0.42, 0.15), (0.55, 0.34, 0.03), col=color.rgb32(25, 25, 28))
        Entity(model="quad", position=top + Vec3(0, 0.42, 0.13), scale=(0.5, 0.3),
               texture=self.t["screen"], color=color.rgb(1.2, 1.2, 1.2))
        self.swivel_chair(p + Vec3(self.rng.uniform(-0.3, 0.3), 0, -0.75), self.rng.uniform(-25, 25))
        self.collider(p + Vec3(0, 0.4, 0), (CELL, 0.8, 0.85), occludes=False)

    def swivel_chair(self, pos, rot):
        """白色辦公旋轉椅：殼椅加上五爪腳和輪子。"""
        ch = Entity(parent=self.group(None), position=pos, rotation_y=rot)
        white, steel = color.rgb32(240, 240, 240), color.rgb32(185, 188, 192)
        self.box((0, 0.5, 0), (0.46, 0.05, 0.44), col=white, parent=ch)
        self.box((0, 0.78, -0.2), (0.44, 0.5, 0.04), col=white, parent=ch)
        self.box((0, 0.27, 0), (0.05, 0.45, 0.05), col=steel, parent=ch)
        for k in range(5):
            leg = self.box((0, 0.04, 0), (0.04, 0.03, 0.6), col=steel, parent=ch)
            leg.rotation_y = k * 72

    def grid_ceiling(self, c0, r0, c1, r1):
        """深色的鋁格柵天花板。"""
        x0, x1 = (c0 - 0.5) * CELL, (c1 - 0.5) * CELL
        z0, z1 = -(r0 - 0.5) * CELL, -(r1 - 0.5) * CELL
        w, d = abs(x1 - x0), abs(z1 - z0)
        Entity(model="quad", position=Vec3((x0 + x1) / 2, WALL_H - 0.03, (z0 + z1) / 2), scale=(w, d), rotation_x=-90,
               texture=self.t["grid"], texture_scale=(w / 2, d / 2))

    def soffit(self, center, radii, a0, a1):
        """清沙龍上方一圈一圈往下降的白色弧形天花板，每層邊緣一條燈。"""
        cx, cy = center
        c = Vec3(cx * CELL, 0, -cy * CELL)
        for i, rad in enumerate(sorted(radii, reverse=True)):
            y = WALL_H - 0.15 - i * 0.12
            rad *= CELL
            n = 18
            for k in range(n):
                t0 = math.radians(a0 + (a1 - a0) * k / n)
                t1 = math.radians(a0 + (a1 - a0) * (k + 1) / n)
                p0 = c + Vec3(math.cos(t0) * rad, y, -math.sin(t0) * rad)
                p1 = c + Vec3(math.cos(t1) * rad, y, -math.sin(t1) * rad)
                seg = Entity(model="cube", position=(p0 + p1) / 2, scale=(0.9, 0.12 + i * 0.12, (p1 - p0).length() + 0.05),
                             color=color.rgb32(244, 244, 244))
                seg.look_at(p1)
                lit = Entity(model="cube", position=(p0 + p1) / 2 - Vec3(0, 0.07 + i * 0.06, 0),
                             scale=(0.08, 0.02, (p1 - p0).length() + 0.05), color=color.rgb(1.4, 1.4, 1.3))
                lit.look_at(p1 - Vec3(0, 0.07 + i * 0.06, 0))
                off = (seg.right * 0.42)
                lit.position += off

    def rope(self, pts):
        """不鏽鋼立柱拉紅色伸縮帶（只是裝飾，人可以從旁邊繞過去）。"""
        steel = color.rgb32(190, 192, 196)
        ps = [Vec3(c * CELL, 0, -r * CELL) for c, r in pts]
        for p in ps:
            self.box(p + Vec3(0, 0.02, 0), (0.3, 0.04, 0.3), col=steel)
            self.box(p + Vec3(0, 0.48, 0), (0.06, 0.95, 0.06), col=steel)
        for a, b in zip(ps, ps[1:]):
            band = Entity(model="cube", position=(a + b) / 2 + Vec3(0, 0.88, 0), scale=(0.01, 0.06, (b - a).length()),
                          color=color.rgb32(200, 30, 35))
            band.look_at(b + Vec3(0, 0.88, 0))

    def tv(self, p, d):
        """柱子上一上一下兩台公告螢幕。"""
        face = p + d * 0.53
        for y, lines, bg in ((2.05, ["圖書館內請保持安靜", "Please keep quiet"], (240, 200, 40)),
                             (1.35, ["期中考週", "館藏區 22:00 閉館"], (245, 245, 240))):
            self.box(face + Vec3(0, y, 0), (0.06 if d.x else 0.95, 0.58, 0.95 if d.x else 0.06), col=color.rgb32(20, 20, 22))
            Entity(model="quad", position=face + d * 0.035 + Vec3(0, y, 0), scale=(0.85, 0.5),
                   rotation=(0, facing_y(d), 0), color=color.rgb(1.1, 1.1, 1.1),
                   texture=self.text_tex(lines, w=200, h=118, bg=bg, fg=(40, 30, 30), sizes=[24, 18]))

    def pickup_gate(self, x, y):
        """自助取書區門口那種紅邊白板的防盜門。"""
        p = Vec3(x * CELL, 0, -y * CELL)
        self.box(p + Vec3(0, 0.85, 0), (0.08, 1.7, 0.5), col=color.rgb32(245, 245, 245))
        for z in (-0.25, 0.25):
            self.box(p + Vec3(0, 0.85, z), (0.1, 1.72, 0.04), col=color.rgb32(170, 30, 35))
        self.box(p + Vec3(0, 1.72, 0), (0.1, 0.03, 0.5), col=color.rgb(0.6, 0.7, 1.4))

    def plank_ceiling(self, c0, r0, c1, r1):
        """聯合櫃臺上面那片木條天花板，邊緣一圈白色的弧形燈槽。"""
        x0, x1 = (c0 - 0.5) * CELL, (c1 - 0.5) * CELL
        z0, z1 = -(r0 - 0.5) * CELL, -(r1 - 0.5) * CELL
        center = Vec3((x0 + x1) / 2, WALL_H - 0.02, (z0 + z1) / 2)
        w, d = abs(x1 - x0), abs(z1 - z0)
        Entity(model="quad", position=center, scale=(w, d), rotation_x=-90, texture=self.t["planks"],
               texture_scale=(w / 2, d / 2))
        Entity(model="cube", position=Vec3(x1, WALL_H - 0.3, center.z), scale=(0.3, 0.6, d), color=color.rgb32(240, 240, 240))
        Entity(model="cube", position=Vec3(x1 + 0.16, WALL_H - 0.6, center.z), scale=(0.04, 0.03, d), color=color.rgb(1.4, 1.4, 1.35))

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
        self.hides.append(p)
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
        self.hides.append(p)
        top = p + Vec3(0, 0.76, 0)
        if self.spec.get("white"):   # 白色桌面、霧面玻璃隔板、白色旋轉椅
            self.box(top - Vec3(0, 0.02, 0), (1.2, 0.05, 0.7), col=color.rgb32(240, 240, 238))
            for x in (-0.6, 0.6):
                self.box(p + Vec3(x, 0.65, 0), (0.04, 1.3, 0.75), col=color.rgba32(222, 230, 232, 190))
            self.box(p + Vec3(0, 1.0, -0.36), (1.2, 0.5, 0.04), col=color.rgba32(222, 230, 232, 190))
            self.box(top + Vec3(0, 0.22, -0.25), (0.5, 0.32, 0.03), col=color.rgb32(22, 22, 26))
            self.swivel_chair(p + Vec3(0, 0, 0.6), self.rng.uniform(-20, 20))
        else:
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
        if self.spec.get("white"):
            self.white_counter(c, r, p)
            return
        self.box(p + Vec3(0, 0.55, 0), (1.0, 1.1, CELL), self.t["wood"], tscale=(1, 2))
        self.box(p + Vec3(0, 1.12, 0), (1.15, 0.05, CELL * 1.02), col=color.rgb32(210, 205, 195))
        self.box(p + Vec3(0.1, 1.35, 0.3), (0.05, 0.38, 0.55), col=color.rgb32(30, 30, 32))
        self.quad(p + Vec3(0.13, 1.35, 0.3), (0.5, 0.32), self.t["screen"], rot=(0, -90, 0))
        self.collider(p + Vec3(0, 0.55, 0), (1.0, 1.1, CELL), occludes=False)

    def white_counter(self, c, r, p):
        """1F 聯合櫃臺：白色人造石的弧形服務台，一格一個窗口：螢幕、號碼牌、外側一張白色高腳椅。"""
        n = sum(1 for rr in range(r) if self.char(c, rr) == "S") + 1
        white = color.rgb32(242, 242, 240)
        self.box(p + Vec3(0, 0.5, 0), (1.0, 1.0, CELL * 1.01), col=white)
        self.box(p + Vec3(0.05, 1.02, 0), (1.15, 0.05, CELL * 1.02), col=color.rgb32(250, 250, 250))
        self.box(p + Vec3(0.45, 0.06, 0), (0.12, 0.08, CELL), col=color.rgb(1.3, 1.3, 1.25))   # 底下的間接照明
        self.box(p + Vec3(-0.1, 1.33, 0.2), (0.04, 0.38, 0.55), col=color.rgb32(25, 25, 28))
        self.quad(p + Vec3(-0.075, 1.33, 0.2), (0.5, 0.32), self.t["screen"], rot=(0, -90, 0))
        self.box(p + Vec3(0.3, 1.2, -0.45), (0.04, 0.3, 0.35), col=white)
        self.quad(p + Vec3(0.33, 1.2, -0.45), (0.3, 0.26),
                  self.text_tex([str(n)], w=64, h=56, bg=(250, 250, 250), fg=(60, 40, 110), sizes=[40]), rot=(0, -90, 0))
        self.shell_chair(p + Vec3(0.95, 0, -0.45), -90 + self.rng.uniform(-20, 20), color.rgb32(240, 240, 240))
        self.collider(p + Vec3(0, 0.55, 0), (1.0, 1.1, CELL), occludes=False)

    def pillar(self, p):
        if self.spec.get("white"):   # 1F 是光滑的白色圓柱
            Entity(parent=self.group(None), model=Cylinder(resolution=20, radius=0.5, height=WALL_H),
                   position=p, color=color.rgb32(238, 238, 236))
        else:
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
        if self.spec.get("white"):   # 1F 入館：不鏽鋼立柱夾著兩片玻璃擺動門
            steel = color.rgb32(185, 188, 192)
            for x in (-0.9, 0.9):
                self.box(p + Vec3(x, 0.55, 0), (0.22, 1.1, 0.5), col=steel)
                self.box(p + Vec3(x, 1.11, 0), (0.24, 0.02, 0.52), col=color.rgb32(60, 200, 120))
                self.box(p + Vec3(x * 0.5, 0.65, 0), (0.75, 0.9, 0.03), col=color.rgba32(190, 215, 225, 70))
                self.box(p + Vec3(x * 0.5, 1.1, 0), (0.75, 0.03, 0.04), col=steel)
                self.collider(p + Vec3(x, 0.55, 0), (0.22, 1.1, 0.5), occludes=False)
            return
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
        # 1. 「300 科學類」那排書架上，一本凸出來的書
        labels = self.spec.get("shelf_labels", CALL_NUMBERS)
        run = next(i for i in sorted(self.shelf_runs) if labels[(i - 1) % len(labels)].startswith("300"))
        cells = self.shelf_runs[run]
        c, r = cells[len(cells) // 2]
        p = cell_pos(c, r)
        Entity(model="cube", position=p + Vec3(0.3, 1.32, -0.36), scale=(0.07, 0.3, 0.22),
               color=color.rgb32(150, 40, 35))
        Entity(model="quad", position=p + Vec3(0.3, 1.52, -0.36), scale=(0.05, 0.06), rotation=(0, 0, 0),
               color=color.rgb32(240, 235, 210))   # 書頁間露出的紙條
        self.clues["book"] = cell_pos(c, r + 1)
        # 2. 討論室的白板（數字每局不同，開局時才畫上去）
        wall = self.spec["whiteboard"]
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
        if self.spec.get("white"):
            self.cover_board(p, 0, 3)
            self.interactables.append(dict(kind="read", pos=p, data="exhibit"))
            return
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
        side = next(Vec3(dc, 0, -dr) for dc, dr in ((0, 1), (0, -1), (1, 0), (-1, 0))
                    if self.char(c + dc, r + dr) not in BLOCKED)   # 櫃門朝向走道，不是朝向隔壁的櫃子
        body = color.rgb32(200, 200, 205)
        self.box(p + Vec3(0, 1.1, 0), (CELL * 0.9, 2.2, CELL * 0.9), col=color.rgb32(240, 240, 240) if self.spec.get("white") else body)
        if self.spec.get("white"):   # 實景是白色的開放格子櫃，看得到裡面的書
            self.quad(p + side * (CELL * 0.45 + 0.015) + Vec3(0, 1.1, 0), (CELL * 0.88, 2.15), self.t["cubbies"],
                      rot=(0, facing_y(side), 0))
        for row in range(4 if not self.spec.get("white") else 0):
            for k in (-1, 1):
                off = Vec3(side.z, 0, -side.x) * (k * 0.42) + Vec3(0, 0.4 + row * 0.5, 0)
                self.box(p + side * (CELL * 0.45 + 0.01) + off, (0.02 if side.x else 0.78, 0.44, 0.78 if side.x else 0.02),
                         col=color.rgb32(170, 175, 182))
        self.quad(p + side * (CELL * 0.45 + 0.03) + Vec3(0, 2.05, 0), (0.6, 0.2),
                  self.text_tex([f"A{n:02d}"], w=128, h=48, bg=(30, 30, 30), sizes=[30]), rot=(0, facing_y(side), 0))
        self.collider(p + Vec3(0, 1.1, 0), (CELL * 0.9, 2.2, CELL * 0.9))
        self.interactables.append(dict(kind="locker", pos=p + side * CELL, look=p + side * (CELL * 0.45) + Vec3(0, 1.2, 0), data=n))

    def history(self, p):
        panels = self.spec.get("history", HISTORY)
        year, text = panels[self.history_i % len(panels)]
        self.history_i += 1
        if self.spec.get("white"):   # 白色的展示板，黑字
            tex = self.text_tex([year, text], w=220, h=280, bg=(246, 246, 244), fg=(40, 40, 44), sizes=[64, 20])
        else:
            tex = self.text_tex([year, text], w=220, h=280, bg=(70, 50, 30), sizes=[64, 20])
        c, r = round(p.x / CELL), round(-p.z / CELL)
        if self.char(c, r - 1) == "#":   # 4F 故事牆：用細線吊在白牆上的照片展板，上面一排軌道燈
            wall = p + Vec3(0, 0, CELL / 2)
            self.quad(wall + Vec3(0, 1.55, -0.04), (0.95, 1.2), tex)
            for x in (-0.4, 0.4):
                self.box(wall + Vec3(x, 2.5, -0.03), (0.01, 0.7, 0.01), col=color.rgb32(120, 120, 120))
            self.box(wall + Vec3(0, WALL_H - 0.25, -0.5), (CELL, 0.04, 0.04), col=color.rgb32(30, 30, 30))
            self.box(wall + Vec3(0, WALL_H - 0.4, -0.5), (0.12, 0.2, 0.12), col=color.rgb(1.4, 1.4, 1.35))
            self.collider(p + Vec3(0, 1.0, CELL / 2 - 0.1), (1.0, 2.0, 0.2), occludes=False)
        else:
            for rot in (0, 180):
                self.quad(p + Vec3(0, 1.35, 0.03 if rot else -0.03), (0.95, 1.2), tex, rot=(0, rot, 0))
            self.box(p + Vec3(0, 0.35, 0), (0.08, 0.7, 0.08), col=color.rgb32(60, 50, 40))
            self.collider(p + Vec3(0, 1.0, 0), (1.0, 2.0, 0.2), occludes=False)
        self.interactables.append(dict(kind="read", pos=p, data=f"history:{year} {text}"))

    def computer(self, p, live=False):
        if self.spec.get("white"):
            self.info_desk(p)
            if live:   # 這台還亮著
                Entity(model="quad", position=p + Vec3(0, 1.2, 0.125), scale=(0.5, 0.3),
                       texture=self.t["screen"], color=color.rgb(1.6, 1.6, 1.6))
                self.interactables.append(dict(kind="lab_pc", pos=p + Vec3(0, 0, -CELL * 0.5)))
            return
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

    # ---------- 3F／4F 的設施 ----------
    def booth(self, p, live=False):
        """視聽座位：小螢幕加耳機。還在播的那台螢幕是亮的。"""
        if self.spec.get("white"):
            self.white_booth(p, live)
            return
        top = p + Vec3(0, 0.76, 0)
        self.box(top - Vec3(0, 0.02, 0), (1.4, 0.05, 0.8), self.t["wood"])
        for x in (-0.7, 0.7):
            self.box(p + Vec3(x, 0.7, 0), (0.04, 1.4, 0.8), col=color.rgb32(70, 60, 80))
        self.box(top + Vec3(0, 0.28, 0.25), (0.75, 0.45, 0.04), col=color.rgb32(20, 20, 24))
        for x in (-0.12, 0.12):   # 耳機
            self.box(top + Vec3(0.4 + x * 0.4, 0.06, -0.1), (0.07, 0.12, 0.1), col=color.rgb32(30, 30, 30))
        self.box(top + Vec3(0.4, 0.13, -0.1), (0.14, 0.02, 0.03), col=color.rgb32(30, 30, 30))
        if live:
            Entity(model="quad", position=top + Vec3(0, 0.28, 0.225), scale=(0.68, 0.4),
                   texture=self.text_tex(["▶ 錄音帶", "03:00"], w=200, h=120, bg=(20, 40, 90), sizes=[34, 30]),
                   color=color.rgb(1.4, 1.4, 1.4))
            self.interactables.append(dict(kind="tape", pos=p + Vec3(0, 0, -CELL * 0.5)))
        self.chair(p + Vec3(0, 0, -0.6), self.rng.uniform(-20, 20))
        self.collider(p + Vec3(0, 0.7, 0), (1.4, 1.4, 0.8), occludes=False)

    def white_booth(self, p, live):
        """3F 視聽聆賞席：白色弧形桌、霧面隔板、螢幕和耳機，配一張橘色的蛋殼椅。"""
        top = p + Vec3(0, 0.76, 0)
        self.box(top - Vec3(0, 0.02, 0), (1.5, 0.05, 0.85), col=color.rgb32(236, 228, 214))
        self.box(p + Vec3(0, 0.37, 0.25), (1.2, 0.74, 0.3), col=color.rgb32(228, 214, 190))
        for x in (-0.74, 0.74):
            self.box(top + Vec3(x, 0.3, 0.05), (0.03, 0.6, 0.75), col=color.rgba32(225, 232, 234, 190))
        self.box(top + Vec3(0, 0.28, 0.25), (0.75, 0.45, 0.04), col=color.rgb32(20, 20, 24))
        for x in (-0.12, 0.12):   # 耳機
            self.box(top + Vec3(0.45 + x * 0.4, 0.06, -0.1), (0.07, 0.12, 0.1), col=color.rgb32(30, 30, 30))
        if live:
            Entity(model="quad", position=top + Vec3(0, 0.28, 0.225), scale=(0.68, 0.4),
                   texture=self.text_tex(["▶ 錄音帶", "03:00"], w=200, h=120, bg=(20, 40, 90), sizes=[34, 30]),
                   color=color.rgb(1.4, 1.4, 1.4))
            self.interactables.append(dict(kind="tape", pos=p + Vec3(0, 0, -CELL * 0.5)))
        else:
            Entity(model="quad", position=top + Vec3(0, 0.28, 0.225), scale=(0.68, 0.4), texture=self.t["screen"])
        self.egg_seat(p + Vec3(0, 0, -0.65), 180 + self.rng.uniform(-25, 25), color.rgb32(222, 98, 40))
        self.collider(p + Vec3(0, 0.7, 0), (1.5, 1.4, 0.85), occludes=False)

    def egg_seat(self, pos, rot, col):
        """蛋殼椅：圓圓的椅身包住你，下面一支鍍鉻腳。"""
        ch = Entity(parent=self.group(None), position=pos, rotation_y=rot)
        steel = color.rgb32(195, 198, 202)
        Entity(parent=ch, model="sphere", position=(0, 0.62, 0), scale=(0.72, 0.5, 0.66), color=col)
        Entity(parent=ch, model="cube", position=(0, 0.95, -0.25), scale=(0.66, 0.65, 0.16), color=col)
        Entity(parent=ch, model="cube", position=(0, 0.3, 0), scale=(0.05, 0.4, 0.05), color=steel)
        for k in range(5):
            Entity(parent=ch, model="cube", position=(0, 0.04, 0), scale=(0.04, 0.03, 0.6), rotation_y=k * 72, color=steel)

    def egg_chair(self, p):
        """3F 發呆區：面向窗戶的灰紫色高背蛋椅，下面一塊鍍鉻圓盤。"""
        rot = -90 + self.rng.uniform(-30, 30)   # 背對大廳、面向東邊的窗
        ch = Entity(parent=self.group(None), position=p, rotation_y=rot)
        col, steel = color.rgb32(92, 88, 104), color.rgb32(200, 202, 206)
        Entity(parent=ch, model=Cylinder(resolution=16, radius=0.32, height=0.03), color=steel)
        Entity(parent=ch, model="cube", position=(0, 0.22, 0), scale=(0.06, 0.4, 0.06), color=steel)
        Entity(parent=ch, model="sphere", position=(0, 0.5, 0.02), scale=(0.8, 0.3, 0.75), color=col)
        Entity(parent=ch, model="sphere", position=(0, 1.0, 0.3), scale=(0.85, 1.05, 0.25), color=col)
        for x in (-0.38, 0.38):
            Entity(parent=ch, model="sphere", position=(x, 0.75, 0.05), scale=(0.18, 0.45, 0.55), color=col)
        self.collider(p + Vec3(0, 0.6, 0), (1.0, 1.2, 1.0), occludes=False)

    def group_booth(self, p):
        """3F 多人聆賞席：白色的圓形矮牆圍成一個小包廂，開口朝南，裡面一圈軟墊和一台螢幕。"""
        n, R = 10, 0.95
        white = color.rgb32(240, 240, 238)
        for k in range(n):     # 開口在南邊：角度 0 是北，留 90 度
            a0, a1 = math.radians(135 + 270 * k / n), math.radians(135 + 270 * (k + 1) / n)
            q0 = p + Vec3(math.sin(a0), 0, math.cos(a0)) * R
            q1 = p + Vec3(math.sin(a1), 0, math.cos(a1)) * R
            seg = Entity(parent=self.group(None), model="cube", position=(q0 + q1) / 2 + Vec3(0, 0.75, 0),
                         scale=(0.1, 1.5, (q1 - q0).length() + 0.04), color=white)
            seg.look_at((q1 + Vec3(0, 0.75, 0)))
            seg.rotation_x = 0
        Entity(parent=self.group(None), model=Cylinder(resolution=16, radius=0.75, height=0.42), position=p,
               color=color.rgb32(120, 112, 140))
        Entity(parent=self.group(None), model=Cylinder(resolution=16, radius=0.45, height=0.44), position=p,
               color=color.rgb32(230, 230, 228))
        self.box(p + Vec3(0, 1.1, R - 0.12), (0.7, 0.42, 0.04), col=color.rgb32(20, 20, 24))
        self.collider(p + Vec3(0, 0.75, 0), (CELL * 0.95, 1.5, CELL * 0.95), occludes=False)

    def tv_booth(self, p):
        """3F 電視區：米白色沙發，前面一張木頭圓桌上放電視，旁邊兩片霧面玻璃。"""
        Entity(parent=self.group(None), model=Cylinder(resolution=20, radius=0.75, height=0.55), position=p + Vec3(0, 0, -0.3),
               color=color.rgb32(222, 196, 158))
        self.box(p + Vec3(0, 0.85, -0.3), (0.95, 0.58, 0.05), col=color.rgb32(18, 18, 20))
        self.quad(p + Vec3(0, 0.85, -0.33), (0.88, 0.5), self.t["screen"], rot=(0, 0, 0))
        self.box(p + Vec3(0, 0.6, -0.3), (0.3, 0.05, 0.2), col=color.rgb32(25, 25, 28))
        sofa = color.rgb32(236, 228, 206)
        self.box(p + Vec3(0, 0.22, 0.75), (1.3, 0.44, 0.7), col=sofa)
        self.box(p + Vec3(0, 0.6, 1.05), (1.3, 0.45, 0.18), col=sofa)
        for x in (-0.6, 0.6):
            self.box(p + Vec3(x, 0.35, 0.75), (0.16, 0.5, 0.7), col=sofa)
        for x in (-0.95, 0.95):
            self.box(p + Vec3(x, 0.9, 0.2), (0.04, 1.8, 1.4), col=color.rgba32(220, 230, 232, 170))
        self.collider(p + Vec3(0, 0.6, 0.2), (CELL, 1.2, CELL * 0.9), occludes=False)

    def cloud_desk(self, p):
        """4F 閱覽區的雲朵桌：三片圓弧拼成的淺木色桌面，中間 Y 字形的霧面隔板和檯燈，配白色椅子。"""
        self.hides.append(p)
        top = p + Vec3(0, 0.75, 0)
        wood = color.rgb32(230, 208, 172)
        for k in range(3):
            a = math.radians(k * 120 + 30)
            off = Vec3(math.sin(a), 0, math.cos(a)) * 0.45
            Entity(parent=self.group(None), model=Cylinder(resolution=14, radius=0.55, height=0.04), position=top + off - Vec3(0, 0.04, 0),
                   color=wood)
            self.box(top + off * 0.5 + Vec3(0, -0.38, 0), (0.5, 0.7, 0.04), col=color.rgb32(222, 196, 160)).rotation_y = k * 120 + 30
            arm = self.box(top + off * 0.55 + Vec3(0, 0.25, 0), (0.03, 0.5, 0.8), col=color.rgba32(225, 232, 234, 180))
            arm.rotation_y = k * 120 + 90
            seat = p + Vec3(math.sin(a + math.pi / 3), 0, math.cos(a + math.pi / 3)) * 1.0
            if self.rng.random() < 0.8:
                self.shell_chair(seat, math.degrees(a + math.pi / 3) + 180 + self.rng.uniform(-15, 15), color.rgb32(242, 242, 242))
        self.lamp(top + Vec3(0.1, 0, 0.1))
        self.clutter(top, 0.35)
        self.collider(p + Vec3(0, 0.45, 0), (1.6, 0.9, 1.6), occludes=False)

    def round_sofa(self, p):
        """4F 的紅色圓形沙發，中間一個米白色的圓靠背。"""
        Entity(parent=self.group(None), model=Cylinder(resolution=24, radius=1.0, height=0.42), position=p, color=color.rgb32(205, 58, 40))
        Entity(parent=self.group(None), model=Cylinder(resolution=20, radius=0.5, height=0.85), position=p, color=color.rgb32(238, 232, 220))
        self.collider(p + Vec3(0, 0.45, 0), (CELL, 0.9, CELL), occludes=False)

    def armchairs(self, p):
        """酒紅色單人沙發兩張，中間一張白色小圓几。"""
        col = color.rgb32(112, 30, 30)
        for side in (1, -1):
            ch = Entity(parent=self.group(None), position=p + Vec3(side * 0.65, 0, 0), rotation_y=side * 90 + self.rng.uniform(-20, 20))
            Entity(parent=ch, model="cube", position=(0, 0.4, 0), scale=(0.75, 0.2, 0.7), color=col)
            Entity(parent=ch, model="cube", position=(0, 0.72, 0.3), scale=(0.8, 0.5, 0.14), color=col)
            for x in (-0.38, 0.38):
                Entity(parent=ch, model="cube", position=(x, 0.55, 0), scale=(0.12, 0.3, 0.65), color=col)
            Entity(parent=ch, model="cube", position=(0, 0.15, 0), scale=(0.05, 0.3, 0.05), color=color.rgb32(190, 192, 196))
        Entity(parent=self.group(None), model=Cylinder(resolution=14, radius=0.3, height=0.03), position=p + Vec3(0, 0.55, 0),
               color=color.rgb32(245, 245, 245))
        self.box(p + Vec3(0, 0.27, 0), (0.04, 0.55, 0.04), col=color.rgb32(190, 192, 196))
        self.collider(p + Vec3(0, 0.45, 0), (CELL * 0.95, 0.9, 1.1), occludes=False)

    def floor_region(self, name, c0, r0, c1, r1):
        """某一區換一種地板，例如 3F 小舞台的木地板。"""
        x0, x1 = (c0 - 0.5) * CELL, (c1 - 0.5) * CELL
        z0, z1 = -(r0 - 0.5) * CELL, -(r1 - 0.5) * CELL
        w, d = abs(x1 - x0), abs(z1 - z0)
        Entity(model="quad", position=Vec3((x0 + x1) / 2, 0.006, (z0 + z1) / 2), scale=(w, d), rotation_x=90,
               texture=self.t[name], texture_scale=(w / CELL * 2, d / CELL * 2))

    def practice_room(self, c0, r0, c1, r1):
        """3F 小舞台：木紋牆板、北牆一面投影布幕，南邊兩排弧形的咖啡色軟墊階梯。"""
        x0, x1 = (c0 - 0.5) * CELL, (c1 + 0.5) * CELL
        z0, z1 = -(r0 - 0.5) * CELL, -(r1 + 0.5) * CELL
        w, d = x1 - x0, z0 - z1
        wood = color.rgb32(206, 170, 128)
        self.quad(Vec3(x0 + 0.02, WALL_H / 2, (z0 + z1) / 2), (d, WALL_H), self.t["wood"], col=wood, rot=(0, -90, 0))
        self.quad(Vec3(x1 - 0.02, WALL_H / 2, (z0 + z1) / 2), (d, WALL_H), self.t["wood"], col=wood, rot=(0, 90, 0))
        self.quad(Vec3((x0 + x1) / 2, WALL_H / 2, z0 - 0.02), (w, WALL_H), col=color.rgb32(240, 238, 232), rot=(0, 180, 0))
        self.quad(Vec3((x0 + x1) / 2, 1.6, z0 - 0.04), (w * 0.5, 1.4), col=color.rgb(1.15, 1.15, 1.15), rot=(0, 180, 0))
        self.box(Vec3((x0 + x1) / 2, 2.33, z0 - 0.05), (w * 0.52, 0.06, 0.04), col=color.rgb32(30, 30, 30))
        self.box(Vec3((x0 + x1) / 2, WALL_H - 0.3, (z0 + z1) / 2), (0.5, 0.25, 0.4), col=color.rgb32(245, 245, 245))   # 投影機
        for k, zz in enumerate((z1 + 1.6, z1 + 0.7)):     # 兩排弧形軟墊
            n = 8
            for i in range(n):
                t = (i + 0.5) / n - 0.5
                pos = Vec3((x0 + x1) / 2 + t * (w - 0.6), 0.08 + k * 0.12, zz - 0.8 * (1 - (2 * t) ** 2) * 0.5)
                self.box(pos, ((w - 0.6) / n - 0.04, 0.16 + k * 0.24, 0.55), col=color.rgb32(120, 92, 82)).rotation_y = -t * 40

    def bell_light(self, p):
        """3F 的白色鐘形吊燈。"""
        self.box(p + Vec3(0, WALL_H - 0.5, 0), (0.015, 1.0, 0.015), col=color.rgb32(200, 200, 200))
        Entity(parent=self.group(None), model=Cone(resolution=12, radius=0.3, height=0.45, add_bottom=False),
               position=p + Vec3(0, WALL_H - 1.45, 0), color=color.rgb32(245, 245, 245), double_sided=True)
        self.box(p + Vec3(0, WALL_H - 1.47, 0), (0.18, 0.04, 0.18), col=color.rgb(1.5, 1.5, 1.4))

    def wall_text(self, p, d, lines):
        """直接印在白牆上的大字，例如 4F 故事牆的標題。"""
        tex = self.text_tex(list(lines), w=384, h=96, bg=(244, 244, 242), fg=(70, 70, 72), sizes=[40, 18])
        self.quad(p + d * (CELL / 2 - 0.02) + Vec3(0, 1.9, 0), (2.6, 0.65), tex, rot=(0, facing_y(-d), 0))

    def nthu_wall(self, c0, c1, r):
        """4F 清華書房外面那片玻璃牆：銀色書架拼成 N T H U 四個大字，兩面都看得到。"""
        x0, x1 = (c0 - 0.5) * CELL, (c1 + 0.5) * CELL
        mid = Vec3((x0 + x1) / 2, 1.5, -r * CELL)
        for side in (1, -1):
            self.quad(mid + Vec3(0, 0, side * 0.06), (x1 - x0, 2.6), self.t["nthu"], rot=(0, 0 if side > 0 else 180, 0))

    def halo(self, center, radius):
        """4F 資訊島上面那圈發光的圓形燈槽。"""
        cx, cy = center
        c = Vec3(cx * CELL, WALL_H - 0.35, -cy * CELL)
        R, n = radius * CELL, 32
        for i in range(n):
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            p0, p1 = c + Vec3(math.cos(a0), 0, math.sin(a0)) * R, c + Vec3(math.cos(a1), 0, math.sin(a1)) * R
            seg = Entity(model="cube", position=(p0 + p1) / 2, scale=(0.9, 0.55, (p1 - p0).length() + 0.05),
                         color=color.rgb(1.3, 1.3, 1.45))
            seg.look_at(p1)
            seg.rotation_x = 0

    def stage(self, c, r, p):
        """3F 小舞台：木頭平台，左上角放一台鋼琴和麥克風架。"""
        self.box(p + Vec3(0, 0.2, 0), (CELL, 0.4, CELL), self.t["wood"], tscale=(2, 2))
        if self.char(c - 1, r) != "Z" and self.char(c, r - 1) != "Z":
            self.box(p + Vec3(0.2, 0.95, 0.2), (1.5, 1.1, 0.6), col=color.rgb32(15, 15, 18))
            self.box(p + Vec3(0.2, 0.92, -0.18), (1.4, 0.06, 0.2), col=color.rgb32(235, 235, 230))
        if self.char(c + 1, r) != "Z" and self.char(c, r + 1) != "Z":
            self.box(p + Vec3(0, 1.1, 0), (0.03, 1.4, 0.03), col=color.rgb32(40, 40, 40))
            self.box(p + Vec3(0, 1.82, 0), (0.06, 0.12, 0.06), col=color.rgb32(70, 70, 70))
        self.collider(p + Vec3(0, 0.5, 0), (CELL, 1.0, CELL), occludes=False)

    def case(self, p):
        """清華書房的玻璃展示櫃。第一個上了密碼鎖。"""
        self.box(p + Vec3(0, 0.4, 0), (1.6, 0.8, 0.9), self.t["wood"])
        for i in range(5):
            self.box(p + Vec3(-0.55 + i * 0.27, 0.95, 0), (0.18, 0.28, 0.12), col=color.rgb32(*tx.BOOK_COLORS[i * 2 + 1]))
        self.box(p + Vec3(0, 1.1, 0), (1.6, 0.6, 0.9), col=color.rgba32(150, 190, 200, 40))
        self.collider(p + Vec3(0, 0.7, 0), (1.6, 1.4, 0.9), occludes=False)
        if not any(i["kind"] == "case" for i in self.interactables):
            self.box(p + Vec3(0.4, 0.55, -0.46), (0.2, 0.25, 0.04), col=color.rgb32(40, 40, 44))   # 密碼鎖
            self.interactables.append(dict(kind="case", pos=p + Vec3(0, 0, -CELL * 0.7)))

    def hanging_sign(self, p, lines):
        bg, fg = self.spec.get("sign_colors", ((28, 58, 52), (235, 235, 225)))
        tex = self.text_tex(list(lines), bg=bg, fg=fg)
        for rot in (0, 180):
            self.quad(p + Vec3(0, 2.6, 0.02 if rot else -0.02), (1.3, 0.4), tex, rot=(0, rot, 0))
        for x in (-0.5, 0.5):
            self.box(p + Vec3(x, 2.95, 0), (0.015, 0.3, 0.015), col=color.rgb32(60, 60, 60))

    def ceiling_lights(self):
        for (c, r) in sorted(self.walkable | self.bank_cells()):
            if (c + r) % 2 or self.level[r][c] == "R":
                continue
            p = cell_pos(c, r)
            safe = (c, r) in self.spec["safe"]     # 夜讀區的燈比較暖
            state = "on"                           # 白天：燈全部是好的
            strip = self.spec.get("ceiling_tex") in ("plaster", "slats")     # 1F 以上是細長的線型燈
            panel = Entity(model="quad", position=p + Vec3(0, WALL_H - 0.01, 0), scale=(0.12, 1.8) if strip else (0.6, 1.2),
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
