"""人物模型：用程式捏出來的低多邊形小人（圓滑的身體、臉、衣服細節）。

每個身體部位（頭、身體、手臂、大腿、小腿）各自是一個合併好的 mesh，
所以一個人只有十來個物件，館內幾十個人也不會卡。

Shape 用法：
    s = Shape()
    s.loft([(y, 半徑x, 半徑z), ...], 顏色)    # 沿 y 軸的一圈一圈，半徑 0 就是封口
    s.ellipsoid(中心, 半徑, 顏色)
    s.box(中心, 大小, 顏色, rot=(x, y, z))
    mesh = s.mesh()
同樣參數的模型會快取起來，第二個人以後不用重算。
"""
import math

from ursina import Mesh, Vec3

_cache = {}
FRONT = -1      # Ursina（左手座標）裡正面三角形的繞行方向


def _rot(rx, ry, rz):
    """Ursina 的旋轉（先 z、再 x、再 y，度）→ 3×3 矩陣（列向量）。"""
    cx, sx = math.cos(math.radians(rx)), math.sin(math.radians(rx))
    cy, sy = math.cos(math.radians(ry)), math.sin(math.radians(ry))
    cz, sz = math.cos(math.radians(rz)), math.sin(math.radians(rz))

    def apply(v):
        x, y, z = v
        x, y = x * cz + y * sz, -x * sz + y * cz          # z 軸
        y, z = y * cx - z * sx, y * sx + z * cx          # x 軸（正的往前低頭）
        x, z = x * cy + z * sy, -x * sy + z * cy          # y 軸
        return (x, y, z)
    return apply


def _norm(v):
    l = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / l, v[1] / l, v[2] / l)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


class Shape:
    def __init__(self):
        self.v, self.t, self.c, self.n = [], [], [], []

    def _col(self, col):
        if isinstance(col[0], int) or max(col[:3]) > 1.0:
            col = tuple(x / 255 for x in col[:3])
        return (col[0], col[1], col[2], 1.0)

    def loft(self, rings, col, seg=14, at=(0, 0, 0), rot=(0, 0, 0), deform=None):
        """rings：[(y, rx, rz) 或 (y, rx, rz, cx, cz), ...]，從下到上或從上到下都可以。
        deform(x, y, z) → (x, y, z)：在旋轉／平移之前，對每個點做變形（剪髮際線、V 領）。"""
        R = _rot(*rot)
        grid = []
        for ring in rings:
            y, rx, rz = ring[:3]
            cx, cz = (ring[3], ring[4]) if len(ring) > 3 else (0.0, 0.0)
            row = []
            for j in range(seg):
                a = 2 * math.pi * j / seg
                p = (cx + rx * math.sin(a), y, cz + rz * math.cos(a))
                if deform:
                    p = deform(*p)
                row.append(p)
            grid.append((row, (cx, y, cz)))
        base = len(self.v)
        col = self._col(col)
        nr = len(grid)
        for i, (row, center) in enumerate(grid):
            for j, p in enumerate(row):
                du = _sub(row[(j + 1) % seg], row[j - 1])
                dv = _sub(grid[min(i + 1, nr - 1)][0][j], grid[max(i - 1, 0)][0][j])
                n = _cross(dv, du)
                if abs(n[0]) + abs(n[1]) + abs(n[2]) < 1e-9:      # 封口的尖端
                    other = grid[1][1] if i == 0 else grid[-2][1]
                    n = _sub(center, other)
                out = _sub(p, center)
                if out[0] * n[0] + out[1] * n[1] + out[2] * n[2] < 0 and (abs(out[0]) + abs(out[2])) > 1e-6:
                    n = (-n[0], -n[1], -n[2])
                q = R(p)
                self.v.append((q[0] + at[0], q[1] + at[1], q[2] + at[2]))
                self.n.append(_norm(R(n)))
                self.c.append(col)
        for i in range(nr - 1):
            for j in range(seg):
                a, b = base + i * seg + j, base + i * seg + (j + 1) % seg
                c, d = a + seg, b + seg
                self.t += [(a, b, d), (a, d, c)]
        return self

    def ellipsoid(self, center, radii, col, seg=14, rings=9, rot=(0, 0, 0), deform=None):
        rx, ry, rz = radii
        rows = []
        for i in range(rings + 1):
            th = math.pi * i / rings
            rows.append((ry * math.cos(th), rx * math.sin(th), rz * math.sin(th)))
        return self.loft(rows, col, seg, at=center, rot=rot, deform=deform)

    def tube(self, y0, y1, r0, r1, col, seg=12, at=(0, 0, 0), rot=(0, 0, 0), sx=1.0):
        """兩端封口、稍微圓頭的管子（手臂、腿）。"""
        k = 0.35
        rows = [(y0 - r0 * k * math.copysign(1, y1 - y0), 0, 0),
                (y0, r0 * sx, r0), (y1, r1 * sx, r1),
                (y1 + r1 * k * math.copysign(1, y1 - y0), 0, 0)]
        mid = [(y0 - r0 * k * 0.6 * math.copysign(1, y1 - y0), r0 * 0.8 * sx, r0 * 0.8)]
        end = [(y1 + r1 * k * 0.6 * math.copysign(1, y1 - y0), r1 * 0.8 * sx, r1 * 0.8)]
        return self.loft(rows[:1] + mid + rows[1:3] + end + rows[3:], col, seg, at=at, rot=rot)

    def box(self, center, size, col, rot=(0, 0, 0)):
        R = _rot(*rot)
        col = self._col(col)
        hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
        faces = [((1, 0, 0), [(hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, -hy, hz)]),
                 ((-1, 0, 0), [(-hx, -hy, hz), (-hx, hy, hz), (-hx, hy, -hz), (-hx, -hy, -hz)]),
                 ((0, 1, 0), [(-hx, hy, -hz), (-hx, hy, hz), (hx, hy, hz), (hx, hy, -hz)]),
                 ((0, -1, 0), [(-hx, -hy, hz), (-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz)]),
                 ((0, 0, 1), [(hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz), (-hx, -hy, hz)]),
                 ((0, 0, -1), [(-hx, -hy, -hz), (-hx, hy, -hz), (hx, hy, -hz), (hx, -hy, -hz)])]
        for n, quad in faces:
            base = len(self.v)
            for p in quad:
                q = R(p)
                self.v.append((q[0] + center[0], q[1] + center[1], q[2] + center[2]))
                self.n.append(R(n))
                self.c.append(col)
            self.t += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
        return self

    def mesh(self):
        if not getattr(self, "_oriented", False):     # 每個三角形都轉成「從外面看是正面」，背面才能被剔除
            tris = []
            for a, b, c in self.t:
                g = _cross(_sub(self.v[b], self.v[a]), _sub(self.v[c], self.v[a]))
                n = self.n[a]
                if (g[0] * n[0] + g[1] * n[1] + g[2] * n[2]) * FRONT < 0:
                    b, c = c, b
                tris.append((a, b, c))
            self.t, self._oriented = tris, True
        return Mesh(vertices=[Vec3(*p) for p in self.v], triangles=self.t, colors=self.c,
                    normals=[Vec3(*n) for n in self.n])


def cached(key, build):
    """同一組參數只捏一次；回傳新的 Mesh（每個 Entity 要自己的一份）。"""
    s = _cache.get(key)
    if s is None:
        s = _cache[key] = build()
    return s.mesh()


# ---------------------------------------------------------------- 身體各部位
# 座標都是相對於 npc.Person 的關節：hip 在離地 0.85，torso 從 hip 往上，頭的關節在 torso 的 0.86，
# 手臂關節在 (±0.245, 0.64)，腿的關節在 (±0.1, 0)、膝蓋在腿往下 0.42。臉朝 +z。

TORSO = [(-0.02, 0.150, 0.098), (0.10, 0.148, 0.095), (0.24, 0.150, 0.098), (0.40, 0.175, 0.108),
         (0.54, 0.192, 0.112), (0.62, 0.185, 0.105), (0.68, 0.140, 0.085), (0.72, 0.070, 0.058), (0.725, 0.0, 0.0)]


def torso_front(y):
    """身體正面在高度 y 的 z（放領帶、名牌用）。"""
    for (y0, _, z0), (y1, _, z1) in zip(TORSO, TORSO[1:]):
        if y0 <= y <= y1:
            return z0 + (z1 - z0) * (y - y0) / (y1 - y0)
    return 0.1


def shirt_shape(collar=True):
    """上衣（白色，實際顏色用 Entity.color 染）。"""
    def build():
        s = Shape().loft(TORSO, (255, 255, 255), seg=16)
        for x in (-1, 1):
            s.ellipsoid((x * 0.185, 0.6, 0), (0.07, 0.066, 0.078), (255, 255, 255), seg=12, rings=7)
        if collar:
            for x in (-1, 1):
                s.box((x * 0.045, 0.705, 0.06), (0.07, 0.05, 0.012), (255, 255, 255), rot=(-25, x * 25, x * -35))
        return s
    return cached(("shirt", collar), build)


def body_shape(skin, pants):
    """不換色的部分：脖子、褲子的屁股。"""
    def build():
        s = Shape()
        s.loft([(0.64, 0.05, 0.05), (0.86, 0.048, 0.05)], skin, seg=10)
        s.loft([(-0.15, 0.0, 0.0), (-0.12, 0.12, 0.08), (-0.05, 0.158, 0.103), (0.06, 0.153, 0.1)], pants, seg=16)
        s.box((0, 0.045, 0), (0.31, 0.03, 0.205), (40, 32, 28))      # 皮帶
        s.box((0, 0.045, 0.103), (0.035, 0.026, 0.006), (190, 170, 110))
        return s
    return cached(("body", skin, pants), build)


def head_shape(skin, hair, style="short", glasses=True):
    def build():
        s = Shape()
        C = (0, 0.05, 0)
        s.ellipsoid(C, (0.122, 0.148, 0.132), skin, seg=16, rings=10)
        s.ellipsoid((0, -0.035, 0.035), (0.085, 0.06, 0.09), skin, seg=12, rings=7)     # 下巴
        for x in (-1, 1):
            s.ellipsoid((x * 0.122, 0.04, -0.005), (0.018, 0.034, 0.028), skin, seg=8, rings=5)   # 耳朵
            s.ellipsoid((x * 0.045, 0.058, 0.118), (0.021, 0.014, 0.012), (250, 250, 248), seg=8, rings=5)
            s.ellipsoid((x * 0.045, 0.057, 0.127), (0.0105, 0.0115, 0.006), (35, 30, 30), seg=8, rings=5)
            s.box((x * 0.047, 0.088, 0.122), (0.04, 0.009, 0.01), hair, rot=(0, 0, x * -8))      # 眉毛
            s.ellipsoid((x * 0.07, 0.0, 0.108), (0.02, 0.013, 0.008), (240, 150, 140), seg=8, rings=4)  # 腮紅
        dark = tuple(int(c * 0.9) for c in skin[:3])
        s.ellipsoid((0, 0.028, 0.135), (0.016, 0.026, 0.018), dark, seg=8, rings=5)       # 鼻子
        s.box((0, -0.03, 0.118), (0.038, 0.007, 0.01), (160, 80, 80))                      # 嘴巴
        _hair(s, C, hair, style)
        if glasses:
            g = (25, 25, 30)
            for x in (-1, 1):
                cx = x * 0.047
                s.box((cx, 0.08, 0.141), (0.062, 0.007, 0.007), g)
                s.box((cx, 0.035, 0.141), (0.062, 0.007, 0.007), g)
                s.box((cx - 0.031, 0.0575, 0.141), (0.007, 0.052, 0.007), g)
                s.box((cx + 0.031, 0.0575, 0.141), (0.007, 0.052, 0.007), g)
                s.box((x * 0.103, 0.072, 0.07), (0.006, 0.006, 0.145), g, rot=(0, -x * 16.7, 0))   # 鏡腳
            s.box((0, 0.07, 0.141), (0.03, 0.006, 0.006), g)
        return s
    return cached(("head", skin, hair, style, glasses), build)


def _hair(s, C, hair, style):
    hx, hy, hz = 0.122, 0.148, 0.132
    front = 0.085 if style != "bangs" else 0.03          # 額頭髮際線的高度（相對頭中心）
    back = -0.075 if style != "long" else -0.2

    def cut(x, y, z):
        """髮際線以下的點縮回頭裡面，頭髮就只剩上面一塊。"""
        t = min(max((z / hz + 1) / 2, 0.0), 1.0)         # 0 = 後腦，1 = 額頭
        line = back + (front - back) * t ** 1.6
        side = abs(x) / hx
        if side > 0.75 and z > -0.02:                     # 耳朵上面剪高一點
            line = max(line, 0.0)
        if y < line:
            return (x * 0.86, y * 0.86, z * 0.86)
        return (x, y, z)
    s.ellipsoid(C, (hx * 1.09, hy * 1.07, hz * 1.09), hair, seg=18, rings=12, deform=cut)
    if style == "side":                                   # 旁分：前面一撮
        s.ellipsoid((C[0] + 0.035, C[1] + 0.105, 0.09), (0.085, 0.04, 0.06), hair, seg=12, rings=6, rot=(0, 0, -12))
    elif style == "bun":
        s.ellipsoid((C[0], C[1] + 0.1, -0.12), (0.06, 0.06, 0.06), hair, seg=12, rings=7)
    elif style == "long":
        s.loft([(0.06, 0.13, 0.08, 0, -0.05), (-0.12, 0.13, 0.07, 0, -0.07), (-0.2, 0.12, 0.05, 0, -0.08),
                (-0.205, 0.0, 0.0, 0, -0.08)], hair, seg=14, at=C,
               deform=lambda x, y, z: (x, y, min(z, 0.02)))
    elif style == "bangs":
        s.ellipsoid((C[0], C[1] + 0.06, 0.1), (0.11, 0.05, 0.05), hair, seg=12, rings=6)


def sleeve_shape():
    """手臂的袖子（染色）：上臂 + 前臂，微微往前彎。"""
    def build():
        s = Shape()
        s.tube(0.0, -0.3, 0.062, 0.055, (255, 255, 255), seg=12)
        s.tube(-0.28, -0.52, 0.054, 0.047, (255, 255, 255), seg=12, rot=(-8, 0, 0))
        return s
    return cached(("sleeve",), build)


def hand_shape(skin):
    def build():
        s = Shape()
        s.loft([(-0.52, 0.04, 0.04), (-0.55, 0.035, 0.035)], skin, seg=10, rot=(-8, 0, 0))   # 手腕
        s.ellipsoid((0, -0.6, 0.012), (0.034, 0.055, 0.042), skin, seg=10, rings=7, rot=(-8, 0, 0))
        s.ellipsoid((0.0, -0.585, 0.045), (0.016, 0.03, 0.016), skin, seg=8, rings=5, rot=(-8, 0, 0))   # 大拇指
        return s
    return cached(("hand", skin), build)


def thigh_shape(pants):
    def build():
        return Shape().tube(0.02, -0.42, 0.088, 0.068, pants, seg=12)
    return cached(("thigh", pants), build)


def shin_shape(pants, shoes):
    def build():
        s = Shape()
        s.tube(0.0, -0.36, 0.066, 0.056, pants, seg=12)
        s.loft([(-0.36, 0.052, 0.052), (-0.37, 0.058, 0.058), (-0.39, 0.0, 0.0)], pants, seg=12)   # 褲管
        s.ellipsoid((0, -0.395, 0.035), (0.058, 0.04, 0.105), shoes, seg=12, rings=7)
        s.box((0, -0.428, 0.035), (0.11, 0.014, 0.21), tuple(int(c * 0.6) for c in shoes[:3]))   # 鞋底
        return s
    return cached(("shin", pants, shoes), build)


# ---------------------------------------------------------------- 配件

def cap_shape(col):
    def build():
        s = Shape()
        s.ellipsoid((0, 0.08, -0.005), (0.138, 0.11, 0.148), col, seg=16, rings=10,
                    deform=lambda x, y, z: (x, max(y, -0.0), z))
        s.ellipsoid((0, 0.075, 0.15), (0.11, 0.012, 0.085), col, seg=12, rings=5)      # 帽簷
        s.ellipsoid((0, 0.19, -0.005), (0.018, 0.01, 0.018), col, seg=8, rings=4)
        return s
    return cached(("cap", col), build)


def beanie_shape(col):
    def build():
        s = Shape()
        s.ellipsoid((0, 0.09, -0.01), (0.135, 0.13, 0.145), col, seg=16, rings=10,
                    deform=lambda x, y, z: (x, max(y, -0.03), z))
        s.loft([(-0.04, 0.137, 0.147), (0.0, 0.14, 0.15)], tuple(int(c * 0.85) for c in col[:3]), seg=16,
               at=(0, 0.09, -0.01))     # 反摺
        s.ellipsoid((0, 0.235, -0.01), (0.04, 0.04, 0.04), (245, 245, 245), seg=10, rings=6)
        return s
    return cached(("beanie", col), build)


def backpack_shape(col):
    def build():
        dark = tuple(int(c * 0.7) for c in col[:3])
        s = Shape()
        s.loft([(-0.0, 0.0, 0.0, 0, 0), (0.02, 0.15, 0.07), (0.38, 0.16, 0.075), (0.46, 0.13, 0.06), (0.48, 0.0, 0.0)],
               col, seg=14)
        s.loft([(0.03, 0.12, 0.04, 0, -0.07), (0.2, 0.12, 0.045, 0, -0.07), (0.22, 0.0, 0.0, 0, -0.07)], dark, seg=12)
        s.box((0, 0.29, -0.077), (0.2, 0.01, 0.006), (200, 200, 200))   # 拉鍊
        for x in (-1, 1):   # 肩帶：從背後繞過肩膀到胸前
            s.box((x * 0.1, 0.585, 0.14), (0.045, 0.018, 0.3), dark)
            s.box((x * 0.11, 0.43, 0.29), (0.045, 0.3, 0.015), dark, rot=(-6, 0, 0))
        return s
    return cached(("backpack", col), build)


def vest_shape(col):
    """館員的針織背心：V 領、鈕扣、胸前名牌和一支筆。"""
    def build():
        s = Shape()
        rings = [(y, rx + 0.014, rz + 0.014) for y, rx, rz in TORSO[:7]] + [(0.7, 0.115, 0.08)]

        def vneck(x, y, z):
            if z > 0 and y > 0.36 and abs(x) < (y - 0.36) * 0.3:
                return (x * 0.9, y, z * 0.85)      # V 領：前面這塊縮進去，露出裡面的襯衫
            return (x, y, z)
        rings[0] = (-0.005, 0.163, 0.11)
        s.loft(rings, col, seg=20, deform=vneck)
        rib = tuple(int(c * 0.8) for c in col[:3])
        s.loft([(-0.01, 0.166, 0.113), (0.03, 0.166, 0.113)], rib, seg=20)     # 下襬的羅紋
        for i, y in enumerate((0.25, 0.17, 0.09)):
            s.ellipsoid((0, y, torso_front(y) + 0.014), (0.011, 0.011, 0.006), (235, 230, 215), seg=8, rings=4)
        z = torso_front(0.47) + 0.016
        s.box((0.095, 0.47, z), (0.075, 0.048, 0.006), (250, 250, 250), rot=(-8, 0, 0))     # 名牌
        s.box((0.095, 0.487, z + 0.003), (0.075, 0.012, 0.004), (40, 110, 80), rot=(-8, 0, 0))
        s.box((0.085, 0.465, z + 0.004), (0.045, 0.006, 0.003), (90, 90, 90), rot=(-8, 0, 0))
        s.box((-0.1, 0.44, torso_front(0.44) + 0.016), (0.012, 0.09, 0.012), (30, 60, 140), rot=(-8, 0, 0))   # 筆
        return s
    return cached(("vest", col), build)


def tie_shape(col):
    def build():
        s = Shape()
        s.box((0, 0.665, torso_front(0.66) + 0.012), (0.035, 0.03, 0.02), col)       # 領結
        steps = 8
        for i in range(steps):
            y = 0.64 - i * 0.032
            w = 0.022 + 0.018 * i / steps
            s.box((0, y, torso_front(y) + 0.009), (w, 0.036, 0.008), col)
        s.box((0, 0.64 - steps * 0.032 + 0.008, torso_front(0.4) + 0.009), (0.028, 0.028, 0.008), col, rot=(0, 0, 45))
        return s
    return cached(("tie", col), build)


def book_stack():
    def build():
        s = Shape()
        for i, c in enumerate(((150, 40, 40), (40, 80, 140), (200, 170, 70))):
            s.box((0, 0.12 - i * 0.045, 0), (0.17, 0.04, 0.24 - i * 0.02), c, rot=(0, i * 6 - 6, 0))
            s.box((0.004, 0.12 - i * 0.045, 0), (0.17, 0.032, 0.235 - i * 0.02), (245, 240, 225), rot=(0, i * 6 - 6, 0))
        return s
    return cached(("books",), build)


def bandage_shape():
    """被揍過的室友：頭上一圈繃帶，臉上一塊 OK 繃。"""
    def build():
        s = Shape()
        s.loft([(0.07, 0.128, 0.138), (0.075, 0.131, 0.141), (0.125, 0.122, 0.13), (0.13, 0.118, 0.126)],
               (245, 245, 242), seg=18, at=(0, 0.0, 0))
        s.box((0.07, 0.005, 0.12), (0.045, 0.016, 0.01), (235, 195, 170), rot=(0, 25, 30))
        s.box((0.07, 0.005, 0.12), (0.045, 0.016, 0.01), (235, 195, 170), rot=(0, 25, -30))
        return s
    return cached(("bandage",), build)
