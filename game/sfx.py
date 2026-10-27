"""用程式合成音效（日光燈嗡嗡聲、心跳、腳步、被抓到的音效），存成 wav。"""
import math
import random
import struct
import wave
from pathlib import Path

RATE = 22050
OUT = Path(__file__).parent / "_sfx"


def _write(name, samples):
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{name}.wav"
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32000)) for s in samples))
    return path


def hum():
    """日光燈的 60Hz 嗡嗡聲加一點電流雜音，2 秒剛好整數週期可無縫循環。"""
    rng = random.Random(1)
    n = RATE * 2
    out = []
    lp = 0.0
    for i in range(n):
        t = i / RATE
        lp += (rng.uniform(-1, 1) - lp) * 0.05
        out.append(0.18 * math.sin(2 * math.pi * 60 * t) + 0.1 * math.sin(2 * math.pi * 120 * t)
                   + 0.04 * math.sin(2 * math.pi * 180 * t) + 0.12 * lp)
    return out


def heartbeat():
    out = [0.0] * RATE
    for start, amp in ((0.0, 1.0), (0.22, 0.7)):
        for i in range(int(RATE * 0.18)):
            t = i / RATE
            out[int(start * RATE) + i] += amp * math.sin(2 * math.pi * 48 * t) * math.exp(-t * 22)
    return out


def step():
    rng = random.Random(3)
    out, lp = [], 0.0
    for i in range(int(RATE * 0.12)):
        t = i / RATE
        lp += (rng.uniform(-1, 1) - lp) * 0.15
        out.append((lp * 2.2 + 0.4 * math.sin(2 * math.pi * 70 * t)) * math.exp(-t * 35))
    return out


def sting():
    """被抓到：不和諧的高音加噪音。"""
    rng = random.Random(4)
    out = []
    for i in range(int(RATE * 1.4)):
        t = i / RATE
        env = min(1, t * 40) * math.exp(-t * 2.2)
        s = sum(math.sin(2 * math.pi * f * t) for f in (466, 494, 523, 740)) / 4
        out.append(env * (0.7 * s + 0.5 * rng.uniform(-1, 1)))
    return out


def page():
    """翻紙的沙沙聲。"""
    rng = random.Random(5)
    out, hp = [], 0.0
    for i in range(int(RATE * 0.35)):
        t = i / RATE
        x = rng.uniform(-1, 1)
        hp = x - hp * 0.6
        out.append(0.35 * hp * math.sin(math.pi * t / 0.35) * (0.6 + 0.4 * math.sin(t * 90)))
    return out


def rumble():
    """密集書架滑動的低沉轟隆聲。"""
    rng = random.Random(6)
    out, lp = [], 0.0
    n = int(RATE * 1.3)
    for i in range(n):
        t = i / RATE
        lp += (rng.uniform(-1, 1) - lp) * 0.02
        env = min(1, t * 6) * min(1, (1.3 - t) * 4)
        out.append(env * (lp * 3 + 0.25 * math.sin(2 * math.pi * 38 * t)))
    return out


def beep():
    """錄音帶裡的嗶聲。"""
    n = int(RATE * 0.22)
    return [0.5 * math.sin(2 * math.pi * 880 * i / RATE) * min(1, i / 200, (n - i) / 400) for i in range(n)]


def generate():
    """只在第一次執行時產生，之後直接用存好的檔案。"""
    paths = {}
    for name, fn in (("hum", hum), ("heartbeat", heartbeat), ("step", step), ("sting", sting), ("page", page), ("rumble", rumble), ("beep", beep)):
        p = OUT / f"{name}.wav"
        paths[name] = p if p.exists() else _write(name, fn())
    return paths
