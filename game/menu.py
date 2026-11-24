"""開始大廳：標題、難度選擇、故事介紹、操作說明。

背景是真的遊戲場景：鏡頭在 1F 大廳裡慢慢晃，遠處站著巡館的館員。
"""
import math

from ursina import Button, Entity, Slider, Text, camera, color, time, window

DIFFICULTIES = {
    "簡單": dict(help_after=60, speed=1.6, seconds=300, sight=9, flee=4.6, hits=18, fight_time=7.0,
               desc="館員走得慢、看不遠，一天有 5 分鐘。\n室友逃得慢，一下就打趴。"),
    "普通": dict(help_after=90, speed=2.0, seconds=240, sight=12, flee=5.2, hits=25, fight_time=7.0,
               desc="原本設計的體驗。\n一天 4 分鐘（18:00–22:00）。"),
    "困難": dict(help_after=120, speed=2.6, seconds=180, sight=15, flee=5.8, hits=32, fight_time=6.5,
               desc="館員眼睛很利，室友跑很快。\n手要按得夠快。"),
}

STORY = """期中考週。你和室友立下「擺爛聯盟」：這次期中考，誰都不准讀書。

隔天你睡到下午五點，室友早就出門了，你連他今天穿什麼都不知道。
報告明天要交、書也逾期了，只好去總圖——
結果室友的 IG 限動，背景就是總圖的落地窗。

說好一起擺爛，結果你偷卷？

一邊還書找文獻，一邊向路人打聽：他今天穿什麼外套、戴什麼帽子、背什麼書包。
在 4F 一整排讀書的學生裡認出他、抓住他、痛扁他。
然後……你撿到了他的成績單。"""

GOAL = """第一階段：抓到偷卷的室友
1F　櫃臺還書，答對館規題查到室友的預約；取書櫃號碼是一個謎語
　　問取書櫃旁的同學（猜謎）→ 室友的書包顏色
2F　問教授（清大常識題）→ 電腦密碼提示；登入電腦 → 室友戴的帽子
3F　聽錄音帶（嗶幾聲是展示櫃第一碼）；問阿伯（猜謎）→ 室友的外套顏色
4F　一堆同學在讀書：照三個線索認出室友，趁他低頭時靠近按 E，狂按 E 痛扁他
　　（認錯人會被館員警告）

第二階段：換你偷卷
5F、6F 的書架上有 3 本發光的考試用書，拿到後坐到桌子旁偷偷讀，讀完要答一題。
頭包繃帶的室友會在樓上巡邏，被他看到你在讀書就要隔天重來。

隱藏：湊齊三碼打開 4F 清華書房的展示櫃，結局會不一樣
會讓你重來：被館員警告三次、22:00 閉館、被室友抓包。線索和讀過的書都會記得。"""

CONTROLS = """WASD　　移動
滑鼠　　　看
Shift　　跑（館員看到會警告，室友聽到會逃）
Ctrl　　 躡手躡腳地走（不會發出聲音）
C　　　　躲到旁邊的桌子底下／出來
E　　　　互動、上下樓、抓室友、痛扁（狂按）
M　　　　小地圖開關
- / =　　 背景音樂音量（大廳左下也能調）
ESC　　　暫停（繼續／音樂音量／回大廳）

小提示
· 館員頭上冒「噓！」就是被警告了，一天三次就出局
· 左下角的聲音條滿了，館員會走過來看
· 掉書、手機響會把館員引開，趁機溜過去
· 右上角小地圖：館員走近時會出現紅點
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
    def __init__(self, on_start, on_quit, aim_camera, music=0.5, on_music=None):
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
        # 背景音樂音量（使用者要求）：0–100，拖了馬上生效，下次開遊戲會記得
        Text(parent=self.col, text="音樂", position=(0.16, -0.405), scale=0.9, color=color.light_gray)
        self.music = Slider(min=0, max=100, default=int(round(music * 100)), step=5, dynamic=True,
                            parent=self.col, position=(0.235, -0.415), scale=0.5)
        self.music.knob.color = ACCENT
        self.music.on_value_changed = lambda: on_music and on_music(self.music.value / 100)
        Text(parent=self.col, text="清大程設 Final Project 原型", position=(0.34, -0.47), origin=(0, 0),
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
