"""隨機事件：每天隔一段時間發生一件，每次抽到的都不太一樣。

館內廣播、書從架上掉下來、某處手機在響、室友發了限時動態、遠處閃過室友的背影。
掉書和手機會把館員引過去，是溜過他身邊的好機會。
"""
import random

from ursina import Entity, Vec3, camera, color, curve, destroy, time

from world import CELL, cell_pos

ANNOUNCEMENTS = [
    "（叮咚）館內請勿飲食，珍奶也不行。謝謝合作。",
    "（叮咚）遺失物招領：學生證一張，主人自稱「完全沒讀書」，請到 1F 聯合櫃臺領取。",
    "（叮咚）提醒您，館內請保持安靜，也請勿奔跑。館員正在巡館。",
    "（叮咚）期中考週，請勿用書包佔位。佔位的書包將被移到失物招領處。",
    "（叮咚）4F 的同學，翻書請小聲一點，你翻得太認真了。",
]
STORIES = [
    "室友剛發了限時動態：「今天在宿舍睡一整天 😴」\n……背景是總圖的落地窗。",
    "室友剛發了限時動態：「讀書？那是什麼？能吃嗎」\n照片角落露出一本微積分。",
    "室友在群組說：「欸今天要不要一起打電動」\n訊息顯示的定位：清華大學圖書館。",
]


class Scares:
    def __init__(self, game):
        self.game = game
        self.figure = None
        self.figure_time = 0.0
        self.props = []        # 掉下來的書，換樓層時要清掉
        self.reset()

    def reset(self):
        """每天重新開始計時。"""
        self.timer = random.uniform(20, 35)
        self.last = None
        self.clear()

    def clear(self):
        if self.figure:
            destroy(self.figure)
            self.figure = None
        for p in self.props:
            destroy(p)
        self.props = []

    def update(self):
        g = self.game
        if self.figure:
            self.figure_time -= time.dt
            if self.figure_time <= 0 or (self.figure.position - g.player.position).length() < 5:
                destroy(self.figure)
                self.figure = None
        if g.in_safe_zone or g.hidden:
            return
        self.timer -= time.dt
        if self.timer <= 0:
            self.timer = random.uniform(30, 50)
            self.trigger()

    def trigger(self, name=None):
        events = {"books": self.books_event, "announce": self.announce_event, "ring": self.ring_event,
                  "story": self.story_event, "figure": self.figure_event}
        if name is None:
            name = random.choice([n for n in events if n != self.last])
        self.last = name
        if not events[name]():      # 這層樓沒辦法發生（例如沒有書架），改成廣播
            self.announce_event()

    # ---------- 各種事件 ----------
    def books_event(self):
        g = self.game
        cells = [cell for run in g.world.shelf_runs.values() for cell in run
                 if 2.5 < (cell_pos(*cell) - g.player.position).length() < 9]
        if not cells:
            return False
        p = cell_pos(*random.choice(cells))
        side = 1 if g.player.position.z > p.z else -1     # 朝玩家那一側掉
        for i in range(random.randint(4, 7)):
            start = p + Vec3(random.uniform(-0.8, 0.8), random.uniform(1.4, 2.0), side * 0.4)
            book = Entity(model="cube", position=start, scale=(0.22, 0.3, 0.06),
                          color=color.rgb32(random.randint(60, 170), random.randint(40, 90), random.randint(30, 80)))
            end = Vec3(start.x + random.uniform(-0.3, 0.3), 0.03, start.z + side * random.uniform(0.4, 1.2))
            delay = i * 0.08
            book.animate_position(end, duration=0.45, delay=delay, curve=curve.in_quad)
            book.animate_rotation((90, random.uniform(0, 360), 0), duration=0.45, delay=delay)
            self.props.append(book)
        g.later(lambda: g.play("thud"), 0.5)
        g.later(lambda: g.show_hint("有人把書架上的書撞掉了。館員往那邊走過去了。", 3), 0.6)
        g.librarian.investigate(p + Vec3(0, 0, side * CELL / 2))
        return True

    def announce_event(self):
        g = self.game
        g.play("chime")
        g.later(lambda: g.show_hint(random.choice(ANNOUNCEMENTS), 6), 1.2)
        return True

    def ring_event(self):
        """書桌上有人忘了關靜音，館員會過去處理。"""
        g = self.game
        spots = [p for p in g.world.hides if 4 < (p - g.player.position).length() < 16]
        if not spots:
            return False
        p = random.choice(spots)
        g.play("ring")
        g.later(lambda: g.play("ring"), 1.8)
        g.show_hint("某張桌上有手機在響。館員皺著眉頭走過去了。", 4)
        g.librarian.investigate(p + Vec3(0, 0, CELL))
        return True

    def story_event(self):
        g = self.game
        g.play("page")
        g.show_hint(random.choice(STORIES), 6)
        return True

    def figure_event(self):
        """在玩家正前方 7–11 公尺，閃過一個背著紅書包的背影（室友坐定 4F 之前才會出現）。"""
        g = self.game
        if g.roommate.active:
            return False
        fwd = camera.forward
        fwd = Vec3(fwd.x, 0, fwd.z).normalized()
        spots = []
        for cell in g.world.walkable - g.world.spec["safe"]:
            to = cell_pos(*cell) - g.player.position
            to.y = 0
            d = to.length()
            if 7 < d < 11 and (to / d).dot(fwd) > 0.9 and g.player_sees(cell_pos(*cell)):
                spots.append(cell)
        if not spots:
            return False
        pos = cell_pos(*random.choice(spots))
        f = Entity(position=pos)
        shirt, skin = color.rgb32(120, 125, 135), color.rgb32(235, 200, 170)
        Entity(parent=f, model="cube", position=(0, 1.15, 0), scale=(0.45, 0.75, 0.25), color=shirt)
        Entity(parent=f, model="cube", position=(0, 1.2, 0.18), scale=(0.38, 0.5, 0.16), color=color.rgb32(170, 50, 45))  # 書包
        for x in (-0.11, 0.11):
            Entity(parent=f, model="cube", position=(x, 0.4, 0), scale=(0.16, 0.8, 0.16), color=color.rgb32(40, 60, 100))
        Entity(parent=f, model="sphere", position=(0, 1.72, 0), scale=0.3, color=skin)
        f.look_at_2d(g.player.position, "y")
        f.rotation_y += 180          # 背對玩家，抱著書走開
        self.figure, self.figure_time = f, 2.2
        g.show_hint("那個紅書包……是室友？！一眨眼就不見了。", 3)
        return True

