"""隨機驚嚇事件：每一輪隔一段時間發生一件，每次抽到的都不太一樣。

停電、書從架上掉下來、閉館廣播、遠處閃過室友的身影、某處的手機在響。
事件只負責嚇人，不會直接讓玩家輸；但停電時看不清楚，它就有機會靠近。
"""
import random

from ursina import Entity, Vec3, camera, color, curve, destroy, time

from world import CELL, World, cell_pos

ANNOUNCEMENTS = [
    "（叮咚）各位同學，圖書館已經閉館，請盡速離開。……陳○○同學，請到 B1 服務台。",
    "（叮咚）現在時間，凌晨兩點四十分。現在時間，凌晨兩點四十分。現在時間……",
    "（叮咚）提醒您，館內請保持安靜。它聽得到。",
    "（叮咚）遺失物招領：學生證一張，姓名……是你的名字。",
]


class Scares:
    def __init__(self, game):
        self.game = game
        self.figure = None
        self.figure_time = 0.0
        self.props = []        # 掉下來的書，換樓層時要清掉
        self.reset()

    def reset(self):
        """每一輪重新開始計時。"""
        self.timer = random.uniform(25, 40)
        self.blackout = 0.0
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
        if self.blackout > 0:
            self.blackout -= time.dt
            if self.blackout <= 0:
                self.lights_back()
        if self.figure:
            self.figure_time -= time.dt
            if self.figure_time <= 0 or (self.figure.position - g.player.position).length() < 5:
                destroy(self.figure)
                self.figure = None
        if g.in_safe_zone or g.hidden:
            return
        self.timer -= time.dt
        if self.timer <= 0:
            self.timer = random.uniform(35, 60)
            self.trigger()

    def trigger(self, name=None):
        events = {"blackout": self.blackout_event, "books": self.books_event, "announce": self.announce_event,
                  "figure": self.figure_event, "ring": self.ring_event}
        if name is None:
            name = random.choice([n for n in events if n != self.last])
        self.last = name
        if not events[name]():      # 這層樓沒辦法發生（例如沒有書架），改成廣播
            self.announce_event()

    # ---------- 各種事件 ----------
    def blackout_event(self):
        for light in self.game.world.lights:
            World.set_light(light, False)
        self.blackout = 7.0
        hum = self.game.sounds.get("hum")
        if hum:
            hum.stop()
        self.game.show_hint("啪。整層樓的燈都熄了。", 3)
        return True

    def lights_back(self):
        for light in self.game.world.lights:
            World.set_light(light, light[2] != "dead")
        hum = self.game.sounds.get("hum")
        if hum:
            hum.play()
        self.game.show_hint("燈又亮了。……它剛剛在哪？", 3)

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
        g.later(lambda: g.show_hint("書架上的書自己掉了下來。", 3), 0.6)
        return True

    def announce_event(self):
        g = self.game
        g.play("chime")
        g.later(lambda: g.show_hint(random.choice(ANNOUNCEMENTS), 6), 1.2)
        return True

    def figure_event(self):
        """在玩家正前方 7–11 公尺、看得到的地方，閃過一個人影。"""
        g = self.game
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
        dark, skin = color.rgb32(30, 34, 46), color.rgb32(170, 160, 150)
        Entity(parent=f, model="cube", position=(0, 1.15, 0), scale=(0.45, 0.75, 0.25), color=dark)
        Entity(parent=f, model="cube", position=(0, 1.2, 0.18), scale=(0.35, 0.45, 0.15), color=color.rgb32(90, 30, 30))  # 書包
        for x in (-0.11, 0.11):
            Entity(parent=f, model="cube", position=(x, 0.4, 0), scale=(0.14, 0.8, 0.14), color=dark)
        Entity(parent=f, model="sphere", position=(0, 1.72, 0), scale=0.26, color=skin)
        f.look_at_2d(g.player.position, "y")
        f.rotation_y += 180          # 背對玩家，像是正要走開
        self.figure, self.figure_time = f, 2.2
        g.show_hint("……那是室友嗎？", 3)
        return True

    def ring_event(self):
        g = self.game
        g.play("ring")
        g.later(lambda: g.play("ring"), 1.8)
        g.show_hint("不知道哪裡有手機在響。……是室友的鈴聲。", 4)
        return True
