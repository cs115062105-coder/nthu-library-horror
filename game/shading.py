"""場景用的簡單光影 shader：讓方塊的每一面有不同亮度，牆角和地板交界暗一點，看起來比較立體。

Ursina 預設的 shader 不算光，所有面都一樣亮，東西看起來像貼紙。這個 shader：
· 用螢幕上的偏微分算出每個面的法線（不用模型自己帶法線，合併過的 mesh 也能用）
· 一盞從天花板斜照下來的主光、一盞補光，再加一點環境光
· 牆面靠近地板和天花板的地方壓暗一點，假裝有陰影（假的環境光遮蔽）
· 跟原本的一樣有霧
會發光的東西（顏色調得比 1 還亮的燈、螢幕）不算光，保持亮。
"""
import os
import re
import sys

from ursina import Vec2, Vec3, color
from ursina.shader import Shader

# Mac 的 Panda3D 預設只開 OpenGL 2.1，看不懂 #version 140 的 shader，會整個退回沒有光影的畫面。
# 所以在 Mac 上把 shader 自動翻成舊版（GLSL 1.20）的寫法，內容完全一樣，Windows/Linux 不受影響。
OLD_GLSL = sys.platform == "darwin" or os.environ.get("TJ_GLSL120") == "1"


def _v(src):
    """頂點 shader：in → attribute、out → varying。"""
    if not OLD_GLSL:
        return src
    src = src.replace("#version 140", "#version 120")
    src = re.sub(r"^in ", "attribute ", src, flags=re.M)
    return re.sub(r"^out ", "varying ", src, flags=re.M)


def _f(src):
    """片段 shader：in → varying，輸出改成 gl_FragColor，texture() → texture2D()。"""
    if not OLD_GLSL:
        return src
    src = src.replace("#version 140", "#version 120")
    src = re.sub(r"^in ", "varying ", src, flags=re.M)
    m = re.search(r"^out vec4 (\w+);\n", src, flags=re.M)
    if m:
        src = src.replace(m.group(0), "")
        src = re.sub(r"\b%s\b" % m.group(1), "gl_FragColor", src)
    return re.sub(r"\btexture\(", "texture2D(", src)

lit_shader = Shader(name="library_lit", language=Shader.GLSL, vertex=_v("""\
#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
in vec4 p3d_Color;
uniform vec2 texture_scale;
uniform vec2 texture_offset;
out vec2 uvs;
out vec4 vertex_color;
out vec3 world_pos;

void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uvs = p3d_MultiTexCoord0 * texture_scale + texture_offset;
    vertex_color = p3d_Color;
    world_pos = (p3d_ModelMatrix * p3d_Vertex).xyz;
}
"""), fragment=_f("""\
#version 140
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform vec3 camera_world_position;
uniform vec4 fog_color;
uniform float fog_start;
uniform float fog_end;
uniform float wall_height;
in vec2 uvs;
in vec4 vertex_color;
in vec3 world_pos;
out vec4 color;

void main() {
    color = texture(p3d_Texture0, uvs) * p3d_ColorScale * vertex_color;
    vec3 n = normalize(cross(dFdx(world_pos), dFdy(world_pos)));
    vec3 to_cam = camera_world_position - world_pos;
    if (dot(n, to_cam) < 0.0) n = -n;

    vec3 key = normalize(vec3(0.35, 1.0, 0.25));
    vec3 fill = normalize(vec3(-0.5, 0.3, -0.8));
    float light = 0.74 + 0.12 * abs(n.y) + 0.20 * max(dot(n, key), 0.0) + 0.08 * max(dot(n, fill), 0.0);
    if (n.y < -0.5) light += 0.12;     // 天花板：被白色地板和牆反射的光照亮，不要灰灰的
    else if (abs(n.y) < 0.5) light += 0.05;   // 牆面也亮一點，影片裡是乾淨的白牆

    if (abs(n.y) < 0.5) {      // 牆、書架側面：靠地板和天花板的地方暗一點
        float y = world_pos.y;
        light *= mix(0.72, 1.0, smoothstep(0.0, 0.55, y));
        light *= mix(0.85, 1.0, smoothstep(0.0, 0.45, wall_height - y));
    }
    float glow = max(max(p3d_ColorScale.r, p3d_ColorScale.g), p3d_ColorScale.b);
    if (glow > 1.01) light = 1.0;      // 燈和螢幕本身會發光
    color.rgb *= light;

    float t = clamp((length(to_cam) - fog_start) / (fog_end - fog_start), 0.0, 1.0);   // 霧從 fog_start 才開始
    color.rgb = mix(color.rgb, fog_color.rgb, t * fog_color.a);
}
"""), default_input={
    "texture_scale": Vec2(1, 1),
    "texture_offset": Vec2(0, 0),
    "wall_height": 3.2,
})



# 霧和相機位置不放在每個物件身上，而是設在整個場景的根節點，所有物件一起繼承：
# 換樓層不用一個一個設霧，每一幀也只要更新一次相機位置（原本每幀要設一千多次）。
# Ursina 預設 shader（unlit_with_fog）也一樣：不要每個物件每一幀各設一次相機位置，改成從根節點繼承。
from ursina.shaders.unlit_with_fog_shader import unlit_with_fog_shader as _unlit
for _k in ("fog_color", "fog_start", "fog_end", "camera_world_position"):
    _unlit.default_input.pop(_k, None)
_unlit.continuous_input.clear()


def _roots():
    from ursina import camera, scene
    return (scene, camera.ui)


def set_fog(fog_color, start, end):
    from ursina import scene
    from panda3d.core import NodePath
    for root in _roots():
        NodePath.set_shader_input(root, "fog_color", fog_color if root is scene else color.clear)
        NodePath.set_shader_input(root, "fog_start", float(start))
        NodePath.set_shader_input(root, "fog_end", float(end))
    scene.fog.setColor(fog_color)            # 沒用自訂 shader 的東西走 Panda 內建的霧
    scene.fog.setLinearRange(start, end)
    scene._fog_color, scene._fog_density = fog_color, (start, end)


def update_camera():
    """每一幀呼叫一次：把相機位置告訴所有用光影 shader 的東西。"""
    from ursina import camera
    from panda3d.core import NodePath
    p = camera.world_position
    for root in _roots():
        NodePath.set_shader_input(root, "camera_world_position", p)



def light_scene(entities=None):
    """把還在用預設 shader 的東西換成有光影的版本（畫面上的介面不換）。
    entities 給了就只看這些（例如剛蓋好的樓層），不用把整個場景掃一遍。"""
    from ursina import Entity, camera, scene
    default = Entity.default_shader
    for e in (scene.entities if entities is None else entities):
        if not e:
            continue
        if e.is_empty() or e.shader is not default or e.model is None or e.has_ancestor(camera.ui):
            continue
        keep = {k: v for k, v in e._shader_inputs.items() if k in ("texture_scale", "texture_offset")}
        e.shader = lit_shader           # 換 shader 會把材質的重複次數洗掉，要補回去
        for k, v in keep.items():
            e.set_shader_input(k, v)


# 人物用：模型自己帶平滑的法線，看起來圓圓的，不會一格一格；另外加一點輪廓光讓人從背景跳出來。
person_shader = Shader(name="person_lit", language=Shader.GLSL, vertex=_v("""\
#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec4 p3d_Color;
out vec4 vertex_color;
out vec3 world_pos;
out vec3 world_normal;

void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    vertex_color = p3d_Color;
    world_pos = (p3d_ModelMatrix * p3d_Vertex).xyz;
    world_normal = normalize(mat3(p3d_ModelMatrix) * p3d_Normal);
}
"""), fragment=_f("""\
#version 140
uniform vec4 p3d_ColorScale;
uniform vec3 camera_world_position;
uniform vec4 fog_color;
uniform float fog_start;
uniform float fog_end;
in vec4 vertex_color;
in vec3 world_pos;
in vec3 world_normal;
out vec4 color;

void main() {
    color = p3d_ColorScale * vertex_color;
    vec3 n = normalize(world_normal);
    vec3 to_cam = camera_world_position - world_pos;
    vec3 v = normalize(to_cam);
    vec3 key = normalize(vec3(0.35, 1.0, 0.25));
    vec3 fill = normalize(vec3(-0.5, 0.3, -0.8));
    float wrap = max((dot(n, key) + 0.4) / 1.4, 0.0);           // 柔和一點的主光
    float light = 0.52 + 0.1 * n.y + 0.42 * wrap + 0.14 * max(dot(n, fill), 0.0);
    float rim = pow(1.0 - max(dot(n, v), 0.0), 3.0);
    float spec = pow(max(dot(n, normalize(key + v)), 0.0), 24.0);
    color.rgb = color.rgb * light + vec3(0.10) * rim + vec3(0.06) * spec;
    float t = clamp((length(to_cam) - fog_start) / (fog_end - fog_start), 0.0, 1.0);   // 霧從 fog_start 才開始
    color.rgb = mix(color.rgb, fog_color.rgb, t * fog_color.a);
}
"""), default_input={})
