"""開始大廳：標題、難度選擇、故事介紹、操作說明。

背景是真的遊戲場景：鏡頭在 1F 大廳裡慢慢晃，遠處站著巡館的館員。
"""
import math

from ursina import Button, Entity, Text, camera, color, time, window

DIFFICULTIES = {
    "簡單": dict(speed=1.6, seconds=300, sight=9, flee=4.6, hits=18, fight_time=7.0,
               desc="館員走得慢、看不遠，一天有 5 分鐘。\n室友逃得慢，一下就打趴。"),
    "普通": dict(speed=2.0, seconds=240, sight=12, flee=5.2, hits=25, fight_time=7.0,
               desc="原本設計的體驗。\n一天 4 分鐘（18:00–22:00）。"),
    "困難": dict(speed=2.6, seconds=180, sight=15, flee=5.8, hits=32, fight_time=6.5,
               desc="館員眼睛很利，室友跑很快。\n手要按得夠快。"),
}

STORY = """期中考週。你和室友立下「擺爛聯盟」：
這次期中考，誰都不准讀書。

傍晚六點，室友說他要在宿舍睡一整天。
但他的 IG 限動，背景是總圖的落地窗。

說好一起擺爛，結果你偷卷？

你衝進清大總圖。館員在巡館，館內不准奔跑，
而他每隔幾秒就會抬頭張望一次。
今天 22:00 閉館前，一定要抓到他。"""

GOAL = """目標：照著室友留下的線索一層一層往上找，在 4F 抓到他、痛扁他。

1F　聯合櫃臺電腦查室友的預約 → 打開自助取書櫃，找到 2F 電腦教室的預約單
2F　照校史展示區的提示登入電腦教室的電腦，再破解「防偷看程式」：
　　按 2／3／5／7 把數字牆分解成質數
3F　到視聽聆賞席聽還在播的錄音帶（嗶幾聲就是展示櫃的第一碼）
　　聽完在群組揪人：A／D 選門，揪越多人，痛扁時每一下越痛
4F　室友就在某張桌子讀書！趁他低頭時躡手躡腳靠近，按 E 抓住他
　　抓到後狂按 E 痛扁他，時間內打趴就過關
隱藏：湊齊三碼打開清華書房的展示櫃，結局會不一樣
（B1 是館員專用；5F、6F 還在蓋）

會讓你重來的事
· 被館員警告三次（館內奔跑、太吵）就會被請出去
· 時鐘走到 22:00 閉館
重來時是隔天，你會留在同一層，查到的線索都記得。
每開一局，取書櫃號碼和密碼都不一樣。"""

CONTROLS = """WASD　　移動
滑鼠　　　看
Shift　　跑（館員看到會警告，室友聽到會逃）
Ctrl　　 躡手躡腳地走（不會發出聲音）
C　　　　躲到旁邊的桌子底下／出來
E　　　　互動、上下樓、抓室友、痛扁（狂按）
ESC　　　回到大廳

小提示
· 館員頭上冒「噓！」就是被警告了，一天三次就出局
· 左下角的聲音條滿了，館員會走過來看
· 掉書、手機響會把館員引開，趁機溜過去
· 室友抬頭張望時會看到你；低頭讀書時只聽得到跑步聲
· 他逃跑時追上去碰到他也算抓到"""

ACCENT = color.rgb32(200, 90, 20)
IDLE = color.rgba32(25, 25, 28, 230)


def _button(parent, text, y, on_click, x=0.34, width=0.36):
    b = Button(parent=parent, text=text, position=(x, y), scale=(width, 0.065),
               color=IDLE, highlight_color=color.rgba32(140, 70, 20, 240),
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
        # 左邊一欄貼著畫面左緣排，右邊說明面板貼著右緣：Mac 的 16:10 螢幕比較窄也不會被切掉
        self.col = Entity(parent=self.root)
        # 左半邊壓暗，字比較清楚
        Entity(parent=self.col, model="quad", position=(0.34, 0), scale=(0.9, 1.2),
               color=color.rgba32(0, 0, 0, 170), z=0.1)
        Text(parent=self.col, text="偷卷仔，給我站住！", position=(0.34, 0.36), origin=(0, 0), scale=2.3,
             color=color.rgb32(225, 218, 200))
        Text(parent=self.col, text="NTHU Library · Catch the Secret Studier", position=(0.34, 0.285), origin=(0, 0),
             scale=1.0, color=color.rgb32(150, 145, 135))
        Text(parent=self.col, text="說好一起擺爛，結果你偷卷？", position=(0.34, 0.235), origin=(0, 0),
             scale=0.9, color=ACCENT)

        _button(self.col, "開始遊戲", 0.14, self.start)
        Text(parent=self.col, text="難度", position=(0.16, 0.075), scale=0.9, color=color.light_gray)
        self.diff_buttons = {}
        for i, name in enumerate(DIFFICULTIES):
            self.diff_buttons[name] = _button(self.col, name, 0.02, lambda n=name: self.pick(n),
                                              x=0.22 + i * 0.12, width=0.11)
        self.diff_desc = Text(parent=self.col, position=(0.16, -0.03), scale=0.75,
                              color=color.rgb32(180, 175, 165))
        _button(self.col, "怎麼過關", -0.13, lambda: self.show_panel("怎麼過關", GOAL))
        _button(self.col, "故事介紹", -0.205, lambda: self.show_panel("故事", STORY))
        _button(self.col, "操作說明", -0.28, lambda: self.show_panel("操作", CONTROLS))
        _button(self.col, "離開", -0.355, on_quit)
        Text(parent=self.col, text="清大程設 Final Project 原型", position=(0.34, -0.45), origin=(0, 0),
             scale=0.7, color=color.rgb32(90, 88, 84))

        self.panel = Entity(parent=camera.ui, z=-0.6, enabled=False)
        Entity(parent=self.panel, model="quad", scale=(0.95, 0.82), position=(0, 0),
               color=color.rgba32(12, 12, 14, 220))
        self.panel_title = Text(parent=self.panel, position=(-0.42, 0.35), scale=1.6, color=ACCENT)
        self.panel_text = Text(parent=self.panel, position=(-0.42, 0.27), scale=0.85,
                               color=color.rgb32(220, 214, 200), line_height=1.3)
        _button(self.panel, "返回", -0.34, self.hide_panel, x=0, width=0.2)
        self.pick(self.difficulty)
        self.driver = Entity(update=self.update)

    def layout(self):
        """依螢幕寬高比擺放左欄和說明面板。"""
        half = window.aspect_ratio / 2
        self.col.x = -half
        left, right = -half + 0.57, half - 0.03     # 面板可以用的範圍：按鈕右邊到畫面右緣
        s = min(1.0, (right - left) / 0.95)
        self.panel.scale = s
        self.panel.x = right - 0.475 * s

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
        self.layout()
        self.aim_camera(forward=min(self.t * 0.08, 3.0), sway=math.sin(self.t * 0.25) * 6)
