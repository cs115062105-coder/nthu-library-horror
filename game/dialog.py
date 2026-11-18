"""畫面下方的對話框：誰在說話、說什麼，可以接一題選擇題。

talk(lines, quiz=None, on_right=None, on_wrong=None, on_done=None)
· lines：[(說話的人, 台詞), ...]，空白鍵／E／Enter／點一下 下一句
· quiz：(題目, [選項], 正確索引)，最後一句講完出題，按 1–4 作答
"""
from ursina import Entity, Text, camera, color, time

COLORS = {"你": (230, 120, 30), "室友": (70, 120, 200), "館員": (40, 130, 90), "旁白": (120, 120, 128),
          "教授": (130, 80, 160), "學生": (60, 140, 160), "市民": (160, 110, 60), "櫃臺館員": (40, 130, 90)}


def wrap(s, width=30):
    return "\n".join(line[i:i + width] for line in s.split("\n") for i in range(0, max(len(line), 1), width))


class Dialog:
    def __init__(self):
        self.root = Entity(parent=camera.ui, z=-0.65, enabled=False)
        Entity(parent=self.root, model="quad", color=color.rgba32(15, 15, 20, 230), position=(0, -0.33), scale=(1.5, 0.27))
        self.name_bg = Entity(parent=self.root, model="quad", position=(-0.6, -0.18), scale=(0.2, 0.055), z=-0.01)
        self.name = Text(parent=self.root, position=(-0.6, -0.18), origin=(0, 0), scale=1.2, color=color.white, z=-0.02)
        self.text = Text(parent=self.root, position=(-0.7, -0.235), scale=1.35, color=color.rgb32(240, 236, 226),
                         line_height=1.25, z=-0.02)
        self.tip = Text(parent=self.root, position=(0.72, -0.45), origin=(0.5, 0), scale=0.75, z=-0.02,
                        color=color.rgb32(170, 170, 170))
        self.lines, self.i, self.shown = [], 0, 0.0
        self.quiz = None
        self.asking = False
        self.lock = 0.0
        self.cb = {}
        Entity(parent=self.root, update=self.update)

    @property
    def active(self):
        return self.root.enabled

    def talk(self, lines, quiz=None, on_right=None, on_wrong=None, on_done=None, lock=0.6):
        self.lines, self.i, self.shown = list(lines), 0, 0.0
        self.quiz, self.asking = quiz, False
        self.cb = dict(right=on_right, wrong=on_wrong, done=on_done)
        self.lock = lock         # 剛打開的一下子不吃按鍵：狂按 E 痛扁時不會不小心跳過對話
        self.root.enabled = True
        self.show_line()

    def show_line(self):
        who, _ = self.lines[self.i]
        self.name.text = who
        self.name_bg.color = color.rgb32(*COLORS.get(who, (90, 90, 96)))
        self.name_bg.scale_x = 0.05 + 0.045 * len(who)
        self.tip.text = "空白鍵／E：下一句"
        self.shown = 0.0

    def ask(self):
        q, options, _ = self.quiz
        self.asking = True
        self.shown = 999
        self.text.text = wrap(q) + "\n" + "　".join(f"{k + 1}. {o}" for k, o in enumerate(options))
        self.tip.text = "按數字鍵 1–4 作答"

    def close(self, which):
        self.root.enabled = False
        fn = self.cb.get(which)
        done = self.cb.get("done")
        self.cb = {}
        if fn:
            fn()
        if done and which != "done":
            done()
        elif done and which == "done":
            pass

    def input(self, key):
        if self.lock > 0:
            return
        if self.asking:
            if key in "1234" and len(key) == 1:
                k = int(key) - 1
                if k < len(self.quiz[1]):
                    self.close("right" if k == self.quiz[2] else "wrong")
            return
        if key not in ("space", "enter", "e", "left mouse down"):
            return
        words = self.lines[self.i][1]
        if self.shown < len(words):
            self.shown = len(words)
            return
        self.i += 1
        if self.i < len(self.lines):
            self.show_line()
        elif self.quiz:
            self.ask()
        else:
            self.close("done")

    def update(self):
        self.lock -= time.dt
        if self.asking or not self.lines:
            return
        words = self.lines[self.i][1]
        self.shown = min(len(words), self.shown + time.dt * 30)
        self.text.text = wrap(words[:int(self.shown)])
