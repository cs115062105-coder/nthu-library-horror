"""開始大廳：標題、難度選擇、故事介紹、操作說明。

背景是真的遊戲場景：鏡頭在書庫走道裡慢慢晃，走道盡頭站著「它」。
"""
import math

from ursina import Button, Entity, Text, camera, color, time

DIFFICULTIES = {
    "簡單": dict(speed=2.0, seconds=240, sight=13, drain=0.7,
               desc="它走得慢，有 4 分鐘，手電筒照得比較遠。\n第一次玩選這個。"),
    "普通": dict(speed=2.6, seconds=180, sight=10, drain=1.0,
               desc="原本設計的體驗。\n3 分鐘內找齊筆記。"),
    "困難": dict(speed=3.5, seconds=150, sight=7, drain=1.4,
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

GOAL = """目標：在清大總圖一層一層往上找室友留下的線索，最後下到 B1 找到《考古題之書》。

1F　夜讀區讀室友的筆記 → 聯合櫃臺電腦查預約 → 打開自助取書櫃，拿到館員門卡
2F　照校史展示區的提示，登入電腦教室最裡面那台電腦，開通樓梯門禁
3F　到視聽聆賞席聽還在播的錄音帶，數清楚嗶了幾聲（第一碼）
4F　「300 科學類」書架上的便條（第二碼）、討論室白板（第三碼）
　　→ 打開清華書房的展示櫃，拿到 B1 通行證
B1　從東南角樓梯間一路往下，轉動密集書架的手輪，找到《考古題之書》就過關
（5F、6F 還在蓋）

會讓你重來的事
・被「它」抓到。它只在你沒看著它的時候移動
・左上角的時鐘走到 03:00
重來時你會留在同一層，拿到的東西和讀過的筆記都記得。
每開一局，取書櫃號碼和密碼都不一樣。"""

CONTROLS = """WASD　　移動
滑鼠　　　看
Shift　　跑（很吵，會引它過來）
Ctrl　　 躡手躡腳地走（不會發出聲音）
C　　　　躲到旁邊的桌子底下／出來
E　　　　讀筆記、用電腦、開櫃子、上下樓
F　　　　開關手電筒
ESC　　　回到大廳

小提示
・夜讀區燈是亮的，它進不來
・左下角的聲音條滿了，它就會聽到你，速度變快
・手電筒會耗電，沒電就看不清它。地上的電池走過去就會撿起來
・躲在桌子底下它找不到你，但時間還是在走
・心跳聲越快，它越近；燈管亂閃，代表它就在附近"""

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
