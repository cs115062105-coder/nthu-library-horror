"""第一人稱玩家：取代 Ursina 內建 FirstPersonController 的移動和滑鼠視角。

內建的版本有兩個問題：
1. 撞牆時只要前進方向被擋住就整個不動，斜著貼牆走會卡住。這裡改成 x、z 分開檢查，可以沿著牆滑過去。
2. 滑鼠鎖定靠「每幀把游標拉回中間」。macOS 拉回去的位置常常差一截，滑鼠不動視角也會一直往下轉。
   這裡在 macOS 用 Panda3D 的 relative 滑鼠模式；不支援時就只在游標快到邊緣才拉回中間，平常只看前後兩幀的位置差。
"""
import math
import sys

import builtins

from panda3d.core import CollisionHandlerQueue, CollisionNode, CollisionSegment, CollisionTraverser, WindowProperties
from ursina import Vec3, application, clamp, held_keys, mouse, scene, time, window
from ursina.prefabs.first_person_controller import FirstPersonController

RADIUS = 0.35          # 玩家的「身體半徑」：離牆這麼近就不能再往前
DEG_PER_PIXEL = 0.12   # 滑鼠靈敏度（mouse_sensitivity 是 40 時）
MAX_PIXELS = 150       # 一幀超過這麼多像素的移動當成雜訊丟掉


class Ray:
    """自己的射線檢查。Ursina 內建的 raycast 會先把一個隱形物件「轉向」要打的方向，
    可是連續兩次方向剛好相反時（例如先往右、再往左）它轉不過去，射線還是往右打：
    明明左邊是空的卻說撞到東西，人就卡住。這裡改用線段，從起點直接畫到終點，不用轉向。"""

    def __init__(self):
        self.segment = CollisionSegment()
        node = CollisionNode("player_ray")
        node.set_into_collide_mask(0)
        node.add_solid(self.segment)
        self.np = builtins.render.attach_new_node(node)
        self.queue = CollisionHandlerQueue()
        self.trav = CollisionTraverser()
        self.trav.add_collider(self.np, self.queue)

    def cast(self, origin, direction, distance, ignore=()):
        """回傳最近碰到的距離；沒碰到回傳 None。"""
        self.segment.set_point_a(origin)
        self.segment.set_point_b(origin + direction * distance)
        self.trav.traverse(scene)
        if not self.queue.get_num_entries():
            return None
        self.queue.sort_entries()
        for e in self.queue.get_entries():
            ent = e.get_into_node_path().parent.getPythonTag("Entity")
            if ent in ignore:
                continue
            return (Vec3(*e.get_surface_point(builtins.render)) - origin).length()
        return None


RADIAL = [Vec3(math.cos(k * math.pi / 4), 0, math.sin(k * math.pi / 4)) for k in range(8)]


class Player(FirstPersonController):
    def __init__(self, **kwargs):
        self.relative = False
        self.last = None
        self.skip = 2
        self.stuck_time = 0.0
        self.unstick = None      # 卡在東西裡面時要回到的位置（由遊戲設定）
        self.ray = Ray()
        super().__init__(**kwargs)

    # ---------- 滑鼠 ----------
    def on_enable(self):
        super().on_enable()
        mouse.enabled = False    # 不讓 Ursina 自己把游標拉回中間，改由這裡處理
        self.grab_mouse()

    def on_disable(self):
        super().on_disable()
        mouse.enabled = True
        self.relative = False

    def grab_mouse(self):
        win = application.base.win if application.base else None
        if not win:
            return
        # Ursina 自己的 window 也是一份 WindowProperties，它之後每次更新視窗都會整份重新送出去。
        # 所以滑鼠模式要寫在它身上，不然會被蓋回 M_confined。
        window.set_cursor_hidden(True)
        window.set_mouse_mode(WindowProperties.M_relative if sys.platform == "darwin" else WindowProperties.M_confined)
        win.requestProperties(window)
        self.relative = sys.platform == "darwin"
        self.last = None
        self.skip = 2

    def mouse_delta(self):
        """這一幀滑鼠移動了多少：一律用「這次讀到的位置減上次讀到的位置」。
        以前每幀都把游標拉回中間、再看它離中間多遠；可是 Mac 拉回去的位置常常差了一截（例如標題列的高度），
        滑鼠沒動也每幀算成往下移，視角就一直往下轉。現在只有游標快碰到視窗邊緣才拉回中間，
        而且拉回後下一幀重新取參考點，不假設它真的停在正中間。"""
        win = application.base.win
        if not win or not win.getProperties().getForeground():
            self.last = None
            return 0, 0
        if self.relative and win.getProperties().getMouseMode() != WindowProperties.M_relative:
            self.relative = False     # 系統不支援 relative 模式，改用「碰到邊緣才拉回中間」
        p = win.getPointer(0)
        x, y = p.getX(), p.getY()
        if self.last is None:
            dx = dy = 0
        else:
            dx, dy = x - self.last[0], y - self.last[1]
        self.last = (x, y)
        if not self.relative:
            w, h = win.getXSize(), win.getYSize()
            if abs(x - w / 2) > w / 4 or abs(y - h / 2) > h / 4:
                win.movePointer(0, w // 2, h // 2)
                self.last = None      # 拉回去之後實際停在哪裡，下一幀讀了才算數
        if self.skip > 0:          # 剛鎖定滑鼠的前幾幀位置還不準
            self.skip -= 1
            return 0, 0
        if abs(dx) > MAX_PIXELS or abs(dy) > MAX_PIXELS:
            return 0, 0
        return dx, dy

    # ---------- 每幀 ----------
    def update(self):
        dx, dy = self.mouse_delta()
        k = DEG_PER_PIXEL * self.mouse_sensitivity[0] / 40
        self.rotation_y += dx * k
        self.camera_pivot.rotation_x = clamp(self.camera_pivot.rotation_x + dy * k, -85, 85)

        self.direction = Vec3(self.forward * (held_keys["w"] - held_keys["s"])
                              + self.right * (held_keys["d"] - held_keys["a"])).normalized()
        before = Vec3(self.position)
        self.slide(self.direction * self.speed * time.dt)
        self.y = 0               # 每層樓地板都是平的
        self.check_stuck(before)

    def blocked(self, along, dist):
        """往 along 方向走 dist 會不會撞到東西。
        1. 在腳、腰、頭三個高度，從身體中間和左右兩側往前打射線。
        2. 斜的牆（落地窗、玻璃房、弧形矮櫃）會從身體斜前方擠進來，前方的射線看不到，
           所以再看走過去之後身體四周八個方向有沒有東西貼得比現在更近；只准越走越鬆，不准越走越擠。"""
        side = Vec3(along.z, 0, -along.x) * (RADIUS * 0.8)
        for h in (0.3, 1.0, 1.7):
            for off in (side, -side, Vec3(0, 0, 0)):
                if self.ray.cast(self.position + Vec3(0, h, 0) + off, along, dist + RADIUS, self.ignore_list) is not None:
                    return True
        after = self.clearance(self.position + along * dist)
        return after < RADIUS * 0.95 and after < self.clearance(self.position) - 1e-3

    def clearance(self, pos):
        """從 pos 往八個方向看，最近的東西有多遠（最多看到 RADIUS）。"""
        best = RADIUS
        for h in (0.3, 1.0):
            for k in range(8):
                hit = self.ray.cast(pos + Vec3(0, h, 0), RADIAL[k], RADIUS, self.ignore_list)
                if hit is not None:
                    best = min(best, hit)
        return best

    def slide(self, move):
        for axis in (Vec3(1, 0, 0), Vec3(0, 0, 1)):
            amount = move.x if axis.x else move.z
            if abs(amount) < 1e-6:
                continue
            along = axis if amount > 0 else -axis
            if not self.blocked(along, abs(amount)):
                self.position += along * abs(amount)

    def check_stuck(self, before):
        """按著方向鍵卻一直動不了，而且四個方向都被擋住超過 1.5 秒，就是卡進桌子或牆裡了，把人送回最近的走道。"""
        trying = self.direction.length() > 0 and self.speed > 0
        if trying and (self.position - before).length() < 1e-4 and all(
                self.blocked(d, 0.05) for d in (Vec3(1, 0, 0), Vec3(-1, 0, 0), Vec3(0, 0, 1), Vec3(0, 0, -1))):
            self.stuck_time += time.dt
            if self.stuck_time > 1.5 and self.unstick:
                self.position = self.unstick(self.position)
                self.stuck_time = 0.0
        else:
            self.stuck_time = 0.0

    def input(self, key):
        pass                     # 不能跳
