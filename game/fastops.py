"""比 Ursina 內建版本快很多的「合併模型」和「一次拆掉很多東西」。

Ursina 的 Entity.combine() 每合併一組都會把整個場景的幾千個物件掃一遍，
destroy() 每拆一個也要在場景清單裡從頭找一次。一層樓有幾十組、上萬個小方塊，
換樓層就要等好幾十秒。這裡改成：
· combine：只走那一組自己底下的物件
· bulk_destroy：先標記，最後整理場景清單一次
結果和原本一模一樣，只是快。
"""
from ursina import Mesh, Vec3, destroy, scene
from ursina.mesh_importer import load_model


def _descendants(parent):
    out, stack = [], list(parent.children)
    while stack:
        e = stack.pop()
        out.append(e)
        stack.extend(e.children)
    return out


def combine(parent):
    """把 parent 底下所有有模型的物件合併成 parent 自己的一個 mesh（跟 Ursina 的 combine 一樣，不含法線）。"""
    verts, tris, uvs, cols, done = [], [], [], [], []
    o = 0
    for e in _descendants(parent):
        if not e.enabled or e.model is None or e.scripts or e.eternal:
            continue
        if not getattr(e.model, "vertices", None):
            e.model = load_model(e.model.name, use_deepcopy=True)
            e.origin = e.origin
            if not e.model:
                continue
        m = e.model.getTransform(parent).getMat()
        verts += [Vec3(*m.xformPoint(Vec3(*v))) for v in e.model.vertices]
        if not e.model.triangles:
            flat = list(range(len(e.model.vertices)))
        else:
            flat = []
            for t in e.model.triangles:
                if isinstance(t, int):
                    flat.append(t)
                elif len(t) == 3:
                    flat.extend(t)
                elif len(t) == 4:
                    flat.extend((t[0], t[1], t[2], t[2], t[3], t[0]))
        flat = [t + o for t in flat]
        tris += [(flat[i], flat[i + 1], flat[i + 2]) for i in range(0, len(flat) - 2, 3)]
        o += len(e.model.vertices)
        if e.model.uvs:
            ts, to = e.texture_scale, e.texture_offset
            uvs += [(uv[0] * ts[0] + to[0], uv[1] * ts[1] + to[1]) for uv in e.model.uvs]
        else:
            uvs += [(0, 0)] * len(e.model.vertices)
        if e.model.colors:
            cols += [tuple(c * k for c, k in zip(vc, e.color)) for vc in e.model.colors]
        else:
            cols += [e.color] * len(e.model.vertices)
        done.append(e)
    bulk_destroy(done)
    tex = parent.texture
    parent.model = Mesh(vertices=verts, triangles=tris, uvs=uvs, colors=cols, mode="triangle")
    parent.texture = tex
    return parent.model


def _special(e):
    """有聲音、動畫、提示框之類的東西，交給 Ursina 原本的 destroy 比較保險。"""
    return (hasattr(e, "on_destroy") or hasattr(e, "clip") or getattr(e, "animations", None)
            or getattr(e, "loose_children", None) or hasattr(e, "tooltip"))


def bulk_destroy(entities):
    """一次拆掉很多物件。場景清單只整理一次，不用每拆一個就從頭找。"""
    gone = set()
    slow = []
    parents = {}
    for e in entities:
        if not e or e.eternal or id(e) in gone:
            continue
        if _special(e):
            slow.append(e)
            continue
        gone.add(id(e))
        if e.collider and hasattr(e.collider, "remove"):
            e.collider.remove()
        scene.collidables.discard(e)
        p = getattr(e, "_parent", None)
        if p is not None and hasattr(p, "_children"):
            parents[id(p)] = p
        if e.hasPythonTag("Entity"):
            e.clearPythonTag("Entity")
        e.removeNode()
    for p in parents.values():
        if id(p) not in gone:
            p._children = [c for c in p._children if id(c) not in gone]
    if gone:
        scene.entities = [e for e in scene.entities if id(e) not in gone]
    for e in slow:
        destroy(e)


_cylinders = {}


def cylinder(**kw):
    """Ursina 的 Cylinder 每做一個都會偷偷生出幾十個隱形物件留在場景裡（一層樓上千個，每一幀都要被掃）。
    同樣尺寸的圓柱只做一次、把漏出來的物件清掉，之後直接用算好的頂點。"""
    from ursina.models.procedural.cylinder import Cylinder
    key = tuple(sorted((k, tuple(v) if isinstance(v, (list, tuple)) else v) for k, v in kw.items()))
    if key not in _cylinders:
        before = set(map(id, scene.entities))
        m = Cylinder(**kw)
        bulk_destroy([e for e in scene.entities if id(e) not in before])
        _cylinders[key] = (list(m.vertices), list(m.triangles) if m.triangles else None,
                           list(m.uvs) if m.uvs else None, list(m.normals) if m.normals else None, m.mode)
    v, t, u, n, mode = _cylinders[key]
    return Mesh(vertices=v, triangles=t, uvs=u, normals=n, mode=mode)


def unlist_static(entities):
    """不會自己動的東西（牆、書架、合併好的模型、碰撞箱）從 Ursina 的每幀清單拿掉。
    它們照樣會畫出來、照樣擋路（碰撞另外記在 scene.collidables），只是引擎每一幀不用再一個一個檢查。
    換樓層時由 World.unload 用 bulk_destroy 拆掉。"""
    drop = set()
    for e in entities:
        if not e or hasattr(e, "update") or getattr(e, "scripts", None):
            continue
        sh = e.shader
        if sh is not None and getattr(sh, "continuous_input", None):
            continue
        drop.add(id(e))
    if drop:
        scene.entities = [e for e in scene.entities if id(e) not in drop]
