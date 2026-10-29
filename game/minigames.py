"""畫面上的小遊戲：玩的時候人停在原地，館員和時鐘也暫停。

PrimeWall（2F 電腦教室）：室友的電腦裝了「防偷看程式」，數字牆一面一面壓過來，
    按 2、3、5、7 把牆上的數字除到剩 1 就能打破它（像 Wall Prime）。
GateRun（3F 聽完錄音帶後）：在群組揪人一起去扁他。人數從 1 開始，每一排有左右兩扇門，
    門上寫著 ×3、+50、-20、÷2……用 A／D 選邊，最後揪到越多人，痛扁時每一下越痛。

兩個小遊戲都是：start() 開始，update() 每幀呼叫，key(k) 處理按鍵，結束時呼叫 on_done(結果)。
"""
import random

from ursina import Entity, Text, camera, color, destroy, time

PRIMES = (2, 3, 5, 7)
PANEL = color.rgba32(15, 20, 30, 235)


class MiniGame:
    def __init__(self, game, on_done):
        self.game = game
        self.on_done = on_done
        self.root = Entity(parent=camera.ui, z=-0.7)
        Entity(parent=self.root, model="quad", scale=(1.3, 0.9), color=PANEL, z=0.2)
        self.title = Text(parent=self.root, position=(0, 0.4), origin=(0, 0), scale=1.4,
                          color=color.rgb32(255, 200, 90))
        self.help = Text(parent=self.root, position=(0, -0.4), origin=(0, 0), scale=0.9,
                         color=color.rgb32(200, 200, 210))
        self.done = False

    def finish(self, result, delay=1.5):
        if self.done:
            return
        self.done = True
        self.game.later(lambda: (self.close(), self.on_done(result)), delay)

    def close(self):
        destroy(self.root)


class PrimeWall(MiniGame):
    def __init__(self, game, on_done, walls=5):
        super().__init__(game, on_done)
        self.title.text = "防偷看程式：把數字牆分解成質數！"
        self.help.text = "按 2　3　5　7 除掉一個質因數，除到剩 1 牆就破了。按錯會被扣時間。　Esc 放棄"
        rng = random.Random()
        self.walls = []
        for i in range(walls):          # 越後面的牆，質因數越多
            n = 1
            for _ in range(2 + i // 2 + (1 if i == walls - 1 else 0)):
                n *= rng.choice(PRIMES)
            self.walls.append(n)
        self.i = 0
        self.track = Entity(parent=self.root, model="quad", position=(0, 0.02), z=0.1, scale=(1.1, 0.5),
                            color=color.rgba32(40, 50, 65, 255))
        self.player = Entity(parent=self.root, model="quad", position=(-0.48, 0.02), scale=(0.06, 0.2),
                             color=color.rgb32(90, 170, 240))
        Text(parent=self.root, text="你", position=(-0.48, -0.12), origin=(0, 0), scale=0.9)
        self.wall = Entity(parent=self.root, model="quad", position=(0.5, 0.02), scale=(0.16, 0.42),
                           color=color.rgb32(170, 90, 60))
        self.number = Text(parent=self.root, position=(0.5, 0.02), z=-0.1, origin=(0, 0), scale=2.2, color=color.white)
        self.log = Text(parent=self.root, position=(0, 0.3), origin=(0, 0), scale=1.0, color=color.rgb32(220, 220, 220))
        self.count = Text(parent=self.root, position=(0, -0.3), origin=(0, 0), scale=1.0, color=color.rgb32(160, 220, 160))
        self.next_wall()

    def next_wall(self):
        self.n = self.walls[self.i]
        self.factors = []
        self.limit = max(5.5, 9.0 - self.i * 0.7)   # 牆走到你面前要幾秒
        self.left = self.limit
        self.wall.color = color.rgb32(170, 90, 60)
        self.log.text = f"第 {self.i + 1} 面牆：{self.n}"
        self.count.text = f"已打破 {self.i} / {len(self.walls)}"
        self.number.text = str(self.n)

    def update(self):
        if self.done:
            return
        self.left -= time.dt
        progress = 1 - max(0.0, self.left) / self.limit
        self.wall.x = self.number.x = 0.5 - progress * 0.9
        if self.left <= 0:
            self.wall.color = color.rgb32(200, 40, 40)
            self.log.text = "牆把你推出去了……（防偷看程式：登入失敗）"
            self.game.play("sting", volume=0.4)
            self.finish(False)

    def key(self, k):
        if self.done:
            return
        if k == "escape":
            self.log.text = "你放棄了。"
            self.finish(False, 0.5)
            return
        if k not in ("2", "3", "5", "7"):
            return
        p = int(k)
        if self.n % p:
            self.left -= 1.5
            self.game.play("shh", volume=0.4)
            self.log.text = f"{self.n} 不能被 {p} 整除！（-1.5 秒）"
            return
        self.n //= p
        self.factors.append(p)
        self.game.play("punch", volume=0.5)
        self.number.text = str(self.n)
        self.log.text = f"{self.walls[self.i]} = " + " × ".join(map(str, self.factors)) + (" × …" if self.n > 1 else "")
        if self.n == 1:
            self.game.play("thud")
            self.i += 1
            if self.i == len(self.walls):
                self.count.text = f"已打破 {self.i} / {len(self.walls)}"
                self.log.text = "防偷看程式被你拆光了！"
                self.wall.enabled = self.number.enabled = False
                self.finish(True)
            else:
                self.next_wall()


OPS = [("×", 2), ("×", 3), ("+", 20), ("+", 50), ("+", 100), ("-", 20), ("-", 50), ("÷", 2), ("÷", 3)]


def apply(n, op):
    sign, k = op
    if sign == "×":
        return n * k
    if sign == "+":
        return n + k
    if sign == "-":
        return max(0, n - k)
    return n // k


class GateRun(MiniGame):
    ROWS = 7
    TRAVEL = 2.4     # 一排門從上面走到你面前要幾秒

    def __init__(self, game, on_done):
        super().__init__(game, on_done)
        self.title.text = "在群組揪人一起去扁他！"
        self.help.text = "A／D（或 ←／→）選左邊或右邊的門，經過門時人數會跟著變。"
        self.count = 1
        self.lane = 0                    # 0 左、1 右
        self.rows = []
        self.spawned = 0
        self.timer = 0.5
        for x in (-0.25, 0.25):
            Entity(parent=self.root, model="quad", position=(x, 0.02), z=0.1, scale=(0.46, 0.66),
                   color=color.rgba32(40, 50, 65, 255))
        self.runner = Entity(parent=self.root, model="circle", position=(-0.25, -0.26), z=-0.05, scale=0.06,
                             color=color.rgb32(90, 170, 240))
        self.label = Text(parent=self.root, position=(-0.25, -0.33), origin=(0, 0), scale=1.2, color=color.white)
        self.refresh()

    def refresh(self):
        self.runner.x = self.label.x = -0.25 if self.lane == 0 else 0.25
        self.label.text = f"{self.count} 人"

    def make_row(self):
        good = [o for o in OPS if o[0] in "×+"]
        ops = [random.choice(OPS), random.choice(good)]
        random.shuffle(ops)
        row = Entity(parent=self.root, y=0.33, z=-0.05)
        for x, op in zip((-0.25, 0.25), ops):
            bad = op[0] in "-÷"
            Entity(parent=row, model="quad", x=x, scale=(0.42, 0.08),
                   color=color.rgba32(200, 70, 60, 220) if bad else color.rgba32(60, 170, 110, 220))
            Text(parent=row, text=f"{op[0]}{op[1]}", x=x, origin=(0, 0), scale=1.4, z=-0.05)
        self.rows.append((row, ops))

    def update(self):
        if self.done:
            return
        self.timer -= time.dt
        if self.timer <= 0 and self.spawned < self.ROWS:
            self.make_row()
            self.spawned += 1
            self.timer = self.TRAVEL * 0.55
        for row, ops in list(self.rows):
            row.y -= time.dt * 0.59 / self.TRAVEL
            if row.y <= -0.26:            # 走到你面前：套用你這一邊的門
                self.count = apply(self.count, ops[self.lane])
                self.game.play("punch" if ops[self.lane][0] in "×+" else "shh", volume=0.4)
                self.rows.remove((row, ops))
                destroy(row)
                self.refresh()
        if self.spawned == self.ROWS and not self.rows:
            self.title.text = f"揪到 {self.count} 個人！"
            self.finish(self.count)

    def key(self, k):
        if k in ("a", "left arrow"):
            self.lane = 0
        elif k in ("d", "right arrow"):
            self.lane = 1
        self.refresh()
