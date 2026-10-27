"""開始大廳：標題、難度選擇、故事介紹、操作說明。

背景是真的遊戲場景：鏡頭在書庫走道裡慢慢晃，走道盡頭站著「它」。
"""
import math

from ursina import Button, Entity, Text, camera, color, time

DIFFICULTIES = {
    "簡單": dict(speed=2.0, seconds=240, sight=13,
               desc="它走得慢，有 4 分鐘，手電筒照得比較遠。\n第一次玩選這個。"),
    "普通": dict(speed=2.6, seconds=180, sight=10,
               desc="原本設計的體驗。\n3 分鐘內找齊筆記。"),
    "困難": dict(speed=3.5, seconds=150, sight=7,
               desc="它很快，只有 2 分半，手電筒照不遠。\n別眨眼。"),
}

STORY = """期中考週，傳說總圖地下書庫藏著一本「考古題之書」，
誰拿到，誰就 all pass。

你跟室友半夜躲在 24 小時夜讀區，打算等館員下班後溜進去。
你不小心睡著了。醒來時是凌晨 2:40，室友的位子空了，
通往館藏區的門……沒有鎖。

書架之間有「東西」。
你看著它，它就不動；你一轉頭，它就靠近。

凌晨 3:00 一到，一切會重來。
但你會記得上一輪讀過的筆記。"""

GOAL = """目標：找出三碼密碼，打開「B1 地下書庫」的門。

1. 從夜讀區出發，穿過感應閘門進入館藏區
2. 找到室友留下的 3 張筆記（走近按 E）
　 筆記不會直接給答案，只告訴你密碼藏在哪
3. 照筆記去找：分類號書架上的書、服務台的電腦、
　 討論室的白板……找到就按 E，得到一碼密碼
4. 三碼都找到後，到密集書庫最裡面的門按 E，過關

會讓你重來的事
・被「它」抓到。它只在你沒看著它的時候移動
・左上角的時鐘走到 03:00
重來時，讀過的筆記和找到的密碼你都記得。
每開一局，密碼都不一樣。"""

CONTROLS = """WASD　　移動
滑鼠　　　看
Shift　　跑
E　　　　讀筆記／輸入密碼
F　　　　開關手電筒
ESC　　　回到大廳

小提示
・夜讀區燈是亮的，它進不來
・手電筒關掉時你看不清它，它就會動
・心跳聲越快，它越近
・燈管開始亂閃，代表它就在附近"""

ACCENT = color.rgb32(150, 30, 30)
IDLE = color.rgba32(25, 25, 28, 230)


def _button(parent, text, y, on_click, x=-0.55, width=0.36):
    b = Button(parent=parent, text=text, position=(x, y), scale=(width, 0.065),
               color=IDLE, highlight_color=color.rgba32(90, 20, 20, 240),
               pressed_color=ACCENT, radius=0.1)
    b.text_entity.scale *= 0.9
    b.on_click = on_click
    return b


class Lobby:
    def __init__(self, on_start, on_quit, aim_camera):
        self.on_start = on_start
        self.aim_camera = aim_camera      # 背景鏡頭由遊戲決定要擺在哪
        self.difficulty = "普通"
        self.t = 0.0
        self.root = Entity(parent=camera.ui, z=-0.5)
        # 左半邊壓暗，字比較清楚
        Entity(parent=self.root, model="quad", position=(-0.55, 0), scale=(0.9, 1.2),
               color=color.rgba32(0, 0, 0, 170), z=0.1)
        Text(parent=self.root, text="總圖不打烊", position=(-0.55, 0.36), origin=(0, 0), scale=3.6,
             color=color.rgb32(225, 218, 200))
        Text(parent=self.root, text="NTHU Library · After Dark", position=(-0.55, 0.285), origin=(0, 0),
             scale=1.0, color=color.rgb32(150, 145, 135))
        Text(parent=self.root, text="凌晨 2:40。你只有到 3:00 的時間。", position=(-0.55, 0.235), origin=(0, 0),
             scale=0.9, color=ACCENT)

        _button(self.root, "開始遊戲", 0.14, self.start)
        Text(parent=self.root, text="難度", position=(-0.73, 0.075), scale=0.9, color=color.light_gray)
        self.diff_buttons = {}
        for i, name in enumerate(DIFFICULTIES):
            self.diff_buttons[name] = _button(self.root, name, 0.02, lambda n=name: self.pick(n),
                                              x=-0.67 + i * 0.12, width=0.11)
        self.diff_desc = Text(parent=self.root, position=(-0.73, -0.03), scale=0.75,
                              color=color.rgb32(180, 175, 165))
        _button(self.root, "怎麼過關", -0.13, lambda: self.show_panel("怎麼過關", GOAL))
        _button(self.root, "故事介紹", -0.205, lambda: self.show_panel("故事", STORY))
        _button(self.root, "操作說明", -0.28, lambda: self.show_panel("操作", CONTROLS))
        _button(self.root, "離開", -0.355, on_quit)
        Text(parent=self.root, text="清大程設 Final Project 原型", position=(-0.55, -0.45), origin=(0, 0),
             scale=0.7, color=color.rgb32(90, 88, 84))

        self.panel = Entity(parent=camera.ui, z=-0.6, enabled=False)
        Entity(parent=self.panel, model="quad", scale=(0.95, 0.82), position=(0.32, 0),
               color=color.rgba32(12, 12, 14, 220))
        self.panel_title = Text(parent=self.panel, position=(-0.1, 0.35), scale=1.6, color=ACCENT)
        self.panel_text = Text(parent=self.panel, position=(-0.1, 0.27), scale=0.85,
                               color=color.rgb32(220, 214, 200), line_height=1.3)
        _button(self.panel, "返回", -0.34, self.hide_panel, x=0.32, width=0.2)
        self.pick(self.difficulty)
        self.driver = Entity(update=self.update)

    @property
    def settings(self):
        return DIFFICULTIES[self.difficulty]

    def pick(self, name):
        self.difficulty = name
        for n, b in self.diff_buttons.items():
            b.color = ACCENT if n == name else IDLE
        self.diff_desc.text = DIFFICULTIES[name]["desc"]

    def show_panel(self, title, text):
        self.panel_title.text = title
        self.panel_text.text = text
        self.panel.enabled = True

    def hide_panel(self):
        self.panel.enabled = False

    def start(self):
        self.hide()
        self.on_start(self.settings, self.difficulty)

    def show(self):
        self.root.enabled = True
        self.driver.enabled = True
        self.t = 0.0
        self.show_panel("怎麼過關", GOAL)   # 一進大廳就先看到目標

    def hide(self):
        self.root.enabled = False
        self.panel.enabled = False
        self.driver.enabled = False

    def update(self):
        """背景鏡頭：在走道裡極慢地往前飄，左右輕輕晃。"""
        self.t += time.dt
        self.aim_camera(forward=min(self.t * 0.08, 3.0), sway=math.sin(self.t * 0.25) * 6)
