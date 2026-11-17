"""場景用的簡單光影 shader：讓方塊的每一面有不同亮度，牆角和地板交界暗一點，看起來比較立體。

Ursina 預設的 shader 不算光，所有面都一樣亮，東西看起來像貼紙。這個 shader：
· 用螢幕上的偏微分算出每個面的法線（不用模型自己帶法線，合併過的 mesh 也能用）
· 一盞從天花板斜照下來的主光、一盞補光，再加一點環境光
· 牆面靠近地板和天花板的地方壓暗一點，假裝有陰影（假的環境光遮蔽）
· 跟原本的一樣有霧
會發光的東西（顏色調得比 1 還亮的燈、螢幕）不算光，保持亮。
"""
from ursina import Vec2, Vec3, color
from ursina.shader import Shader

lit_shader = Shader(name="library_lit", language=Shader.GLSL, vertex="""\
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
""", fragment="""\
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

    if (abs(n.y) < 0.5) {      // 牆、書架側面：靠地板和天花板的地方暗一點
        float y = world_pos.y;
        light *= mix(0.72, 1.0, smoothstep(0.0, 0.55, y));
        light *= mix(0.85, 1.0, smoothstep(0.0, 0.45, wall_height - y));
    }
    float glow = max(max(p3d_ColorScale.r, p3d_ColorScale.g), p3d_ColorScale.b);
    if (glow > 1.01) light = 1.0;      // 燈和螢幕本身會發光
    color.rgb *= light;

    float t = clamp(length(to_cam) / (fog_end - fog_start), 0.0, 1.0);
    color.rgb = mix(color.rgb, fog_color.rgb, t * fog_color.a);
}
""", default_input={
    "texture_scale": Vec2(1, 1),
    "texture_offset": Vec2(0, 0),
    "fog_color": color.clear,
    "fog_start": 10,
    "fog_end": 100,
    "camera_world_position": Vec3.zero,
    "wall_height": 3.2,
})


def _camera_position():
    from ursina import camera
    return camera.world_position


lit_shader.continuous_input["camera_world_position"] = _camera_position


def light_scene():
    """把場景裡還在用預設 shader 的東西換成有光影的版本（畫面上的介面不換）。"""
    from ursina import Entity, camera, scene
    default = Entity.default_shader
    for e in scene.entities:
        if e.is_empty() or e.shader is not default or e.model is None or e.has_ancestor(camera.ui):
            continue
        keep = {k: v for k, v in e._shader_inputs.items() if k in ("texture_scale", "texture_offset")}
        e.shader = lit_shader           # 換 shader 會把材質的重複次數洗掉，要補回去
        for k, v in keep.items():
            e.set_shader_input(k, v)
