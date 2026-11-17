"""右上角的小地圖：整層樓的格子圖，北邊朝上。

· 走得到的地方是淺色，書架、牆、桌子是深色
· 綠色方塊是樓梯
· 橘色箭頭是你，箭頭指著你面向的方向
· 館員走到附近（聽得到腳步聲的距離）才會出現紅點，遠的看不到
按 M 可以開關。
"""
from PIL import Image
from ursina import Entity, Mesh, Text, Texture, camera, color, window

from world import CELL

SIZE = 0.3          # 小地圖最長的那一邊，佔畫面高度的幾成
NEAR = 14           # 館員離你幾公尺內才會出現在地圖上


def to_grid(pos):
    """3D 座標換成格子座標（可以是小數）。"""
    return pos.x / CELL, -pos.z / CELL


def triangle():
    return Mesh(vertices=[(0, 0.5, 0), (-0.38, -0.45, 0), (0.38, -0.45, 0)], triangles=[(0, 1, 2)], mode="triangle")


class Minimap:
    def __init__(self):
        self.root = Entity(parent=camera.ui, z=-0.1)
        self.frame = Entity(parent=self.root, model="quad", color=color.rgba32(20, 20, 24, 110))
        self.map = Entity(parent=self.root, model="quad", z=-0.01)
        self.title = Text(parent=self.root, origin=(0.5, 0.5), scale=0.9, color=color.rgb32(30, 30, 36))
        self.you = Entity(parent=self.root, model=triangle(), color=color.rgb32(235, 110, 30), z=-0.03,
                          scale=0.022, double_sided=True)
        self.guard = Entity(parent=self.root, model="circle", color=color.rgb32(220, 40, 40), z=-0.02, scale=0.016)
        self.on = True
        self.cols = self.rows = 1

    def load(self, world):
        """換樓層時重畫一張地圖。一格畫成 4×4 個像素。"""
        level = world.level
        self.rows, self.cols = len(level), len(level[0])
        k = 4
        img = Image.new("RGBA", (self.cols * k, self.rows * k), (0, 0, 0, 0))
        stairs = {(round(s["pos"].x / CELL), round(-s["pos"].z / CELL)) for s in world.stairs.values()}
        for r in range(self.rows):
            for c in range(self.cols):
                ch = level[r][c]
                if (c, r) in stairs:
                    col = (60, 170, 90, 255)
                elif (c, r) in world.walkable:
                    col = (236, 234, 228, 235)
                elif ch == "x":          # 建築物外面
                    continue
                else:
                    col = (66, 66, 74, 240)
                for y in range(k):
                    for x in range(k):
                        img.putpixel((c * k + x, r * k + y), col)
        self.map.texture = Texture(img, filtering=None)
        w, h = self.cols / max(self.cols, self.rows) * SIZE, self.rows / max(self.cols, self.rows) * SIZE
        self.w, self.h = w, h
        self.map.scale = (w, h)
        self.frame.scale = (w + 0.012, h + 0.04)
        self.frame.y = 0.014
        self.title.text = world.floor
        self.title.position = (w / 2, h / 2 + 0.032)

    def spot(self, pos):
        """3D 座標換成小地圖上的位置。"""
        c, r = to_grid(pos)
        return ((c + 0.5) / self.cols - 0.5) * self.w, (0.5 - (r + 0.5) / self.rows) * self.h

    def update(self, player, librarian):
        self.root.x = window.aspect_ratio / 2 - self.w / 2 - 0.025
        self.root.y = 0.5 - self.h / 2 - 0.045
        self.you.position = (*self.spot(player.position), -0.03)
        self.you.rotation_z = player.rotation_y
        g = librarian.root.position
        near = (g - player.position).length() < NEAR
        self.guard.enabled = near
        if near:
            self.guard.position = (*self.spot(g), -0.02)

    def show(self, on):
        self.root.enabled = on and self.on

    def toggle(self):
        self.on = not self.on
        self.root.enabled = self.on
