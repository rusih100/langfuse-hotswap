"""
Renders docs/assets/demo.gif: a schematic prompt-management UI where the production label moves
from v12 to v13 and the live trace list switches from gpt-5.5 to claude-sonnet-5-5.
"""

from __future__ import annotations

import sys

from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]
W, H = 1200, 640
SCALE = 2  # render at 2x, downsample for crisp text
DURATION = 12.0
FPS = 8

BG = (244, 244, 241)
CARD = (255, 255, 255)
LINE = (228, 228, 223)
INK = (31, 31, 28)
MUTED = (107, 107, 102)
CODE = (59, 59, 55)
ACCENT = (79, 70, 229)
TINT = (243, 242, 255)
GREEN = (22, 163, 74)


def font(size: int, weight: str = "regular", mono: bool = False) -> ImageFont.FreeTypeFont:
    size *= SCALE
    if mono:
        return ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", size)
    path = "/System/Library/Fonts/HelveticaNeue.ttc"
    index = {"regular": 0, "bold": 1, "medium": 7}.get(weight, 0)
    try:
        return ImageFont.truetype(path, size, index=index)
    except OSError:
        return ImageFont.truetype(path, size)


F13 = font(13)
F14 = font(14)
F14B = font(14, "bold")
F20B = font(20, "bold")
F12 = font(12)
F12B = font(12, "bold")
F11 = font(11)
M13 = font(13, mono=True)


def s(v: float) -> int:
    return round(v * SCALE)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


def ramp(t: float, start: float, end: float) -> float:
    return 0.0 if end == start else max(0.0, min(1.0, (t - start) / (end - start)))


def text(
    d: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    txt: str,
    f: ImageFont.FreeTypeFont,
    fill: tuple[int, ...],
    anchor: str = "la",
) -> None:
    d.text((s(xy[0]), s(xy[1])), txt, font=f, fill=fill, anchor=anchor)


def rect(
    d: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    fill: tuple[int, ...] | None,
    outline: tuple[int, ...] | None = None,
    radius: float = 0,
) -> None:
    x0, y0, x1, y1 = (s(v) for v in box)
    d.rounded_rectangle((x0, y0, x1, y1), radius=s(radius), fill=fill, outline=outline, width=SCALE if outline else 0)


def blend(c: tuple[int, int, int], bg: tuple[int, int, int], a: float) -> tuple[int, int, int]:
    r, g, b = (round(bg[i] + (c[i] - bg[i]) * a) for i in range(3))
    return r, g, b


TRACES = [
    ("14:02:11", "v12", "gpt-5.5", "1.3 s", 0.04),
    ("14:02:14", "v12", "gpt-5.5", "1.0 s", 0.12),
    ("14:02:17", "v12", "gpt-5.5", "1.2 s", 0.20),
    ("14:02:20", "v12", "gpt-5.5", "1.1 s", 0.28),
    ("14:02:26", "v13", "claude-sonnet-5-5", "1.9 s", 0.53),
    ("14:02:29", "v13", "claude-sonnet-5-5", "1.5 s", 0.63),
    ("14:02:32", "v13", "claude-sonnet-5-5", "1.6 s", 0.73),
    ("14:02:35", "v13", "claude-sonnet-5-5", "1.4 s", 0.83),
]


def top_bar(d: ImageDraw.ImageDraw) -> None:
    """
    Draws the navigation bar.
    """

    rect(d, (0, 0, W, 52), CARD)
    d.line((0, s(52), s(W), s(52)), fill=LINE, width=SCALE)
    text(d, (28, 26), "Prompt management", F14B, INK, "lm")
    x = 28 + d.textlength("Prompt management", font=F14B) / SCALE + 36
    for name, active in (("Traces", False), ("Prompts", True), ("Datasets", False), ("Evaluations", False)):
        text(d, (x, 26), name, F14B if active else F14, INK if active else MUTED, "lm")
        w = d.textlength(name, font=F14B if active else F14) / SCALE
        if active:
            d.line((s(x), s(51), s(x + w), s(51)), fill=INK, width=2 * SCALE)
        x += w + 20
    d.ellipse((s(W - 56), s(12), s(W - 28), s(40)), fill=(217, 217, 210))


def versions(d: ImageDraw.ImageDraw, t: float) -> None:
    """
    Draws the prompt versions, the production label and the cursor that moves it.
    """

    lx, ly = 28, 76
    text(d, (lx, ly + 12), "support-reply", F20B, INK, "lm")
    text(d, (lx + 142, ly + 13), "chat prompt · 2 versions", F14, MUTED, "lm")
    cards = [
        ("v13", "2 min ago", "anthropic / claude-sonnet-5-5 · temperature 0.2", 112),
        ("v12", "3 days ago", "openai / gpt-5.5 · temperature 0.2", 184),
    ]
    for ver, age, cfg, y in cards:
        rect(d, (lx, y, lx + 440, y + 62), CARD, LINE, 12)
        text(d, (lx + 16, y + 20), ver, F14B, INK, "lm")
        text(d, (lx + 50, y + 20), age, F14, MUTED, "lm")
        text(d, (lx + 16, y + 44), cfg, M13, CODE, "lm")

    # Production badge: on v12 until 38%, moves to v13 by 46%
    badge_y = lerp(184 + 9, 112 + 9, ramp(t, 0.38, 0.46))
    bw = d.textlength("production", font=F12B) / SCALE + 20
    bx = lx + 440 - 16 - bw
    rect(d, (bx, badge_y, bx + bw, badge_y + 22), ACCENT, None, 11)
    text(d, (bx + bw / 2, badge_y + 11), "production", F12B, CARD, "mm")

    # Cursor: appears at 28%, reaches the badge at 34%, drags it up, fades at 50%
    if 0.28 <= t < 0.50:
        a = ramp(t, 0.28, 0.32) * (1 - ramp(t, 0.47, 0.50))
        cx = lerp(560, bx + bw / 2 + 6, ramp(t, 0.28, 0.34))
        cy = lerp(330, 184 + 12 + 10, ramp(t, 0.28, 0.34))
        if t >= 0.38:
            cy = badge_y + 10
        pts = [(2, 2), (2, 20), (7, 15), (11, 24), (14, 23), (10, 14), (17, 14)]
        poly = [(s(cx + px), s(cy + py)) for px, py in pts]
        d.polygon(poly, fill=blend(INK, BG, a), outline=blend(CARD, BG, a))

    # Caption under the versions
    cap = [
        "Drag the production label to another version.",
        "The service picks it up on the next call:",
        "no restart, no deploy.",
    ]
    for i, line in enumerate(cap):
        text(d, (lx, 300 + i * 22), line, F14, MUTED, "lm")


def traces(d: ImageDraw.ImageDraw, t: float) -> None:
    """
    Draws the trace list; rows appear at their own time and switch model after the label move.
    """

    ly = 76
    rx = 28 + 440 + 24
    rw = W - 28 - rx
    text(d, (rx, ly + 12), "Traces", F20B, INK, "lm")
    text(d, (rx + 74, ly + 13), "support-service · live", F14, MUTED, "lm")
    th = 40 + 8 * 42
    rect(d, (rx, 112, rx + rw, 112 + th), CARD, LINE, 12)
    cols = (rx + 16, rx + 118, rx + rw - 16 - 90 - 12 - 170, rx + rw - 16)
    hy = 112 + 20
    for label, cx_, anchor in (
        ("Time", cols[0], "lm"),
        ("Name · prompt version", cols[1], "lm"),
        ("Model", cols[2], "lm"),
        ("Latency", cols[3], "rm"),
    ):
        text(d, (cx_, hy), label, F12, MUTED, anchor)
    d.line((s(rx), s(152), s(rx + rw), s(152)), fill=(237, 237, 232), width=SCALE)

    visible = [tr for tr in TRACES if t >= tr[4]]
    visible.sort(key=lambda tr: tr[4], reverse=True)
    for i, (time_, ver, model, lat, at) in enumerate(visible):
        a = ramp(t, at, at + 0.02)
        y0 = 152 + i * 42
        dy = (1 - a) * 8
        if ver == "v13":
            rect(d, (rx + 1, y0 + 1, rx + rw - 1, y0 + 42), blend(TINT, CARD, a))
        d.line((s(rx), s(y0 + 42), s(rx + rw), s(y0 + 42)), fill=(237, 237, 232), width=SCALE)
        yy = y0 + 21 + dy
        text(d, (cols[0], yy), time_, F14, blend(MUTED, CARD, a), "lm")
        text(d, (cols[1], yy), "support-reply", F14, blend(INK, CARD, a), "lm")
        nw = d.textlength("support-reply", font=F14) / SCALE
        text(d, (cols[1] + nw + 6, yy), f"· {ver}", F14, blend(MUTED, CARD, a), "lm")
        text(d, (cols[2], yy), model, M13, blend(INK, CARD, a), "lm")
        text(d, (cols[3], yy), lat, F14, blend(MUTED, CARD, a), "rm")


def service(d: ImageDraw.ImageDraw, t: float) -> None:
    """
    Draws the service strip with the model it is serving.
    """

    by = H - 64
    d.line((s(28), s(by), s(W - 28), s(by)), fill=LINE, width=SCALE)
    text(d, (28, by + 32), "support-service", M13, MUTED, "lm")
    text(d, (168, by + 32), 'chain = factory.create("support-reply")  ·  chain.invoke(question)', M13, CODE, "lm")
    switched = ramp(t, 0.50, 0.53)
    status = "serving · anthropic / claude-sonnet-5-5" if switched >= 0.5 else "serving · openai / gpt-5.5"
    sw = d.textlength(status, font=M13) / SCALE
    d.ellipse((s(W - 28 - sw - 16), s(by + 28), s(W - 28 - sw - 8), s(by + 36)), fill=GREEN)
    text(d, (W - 28, by + 32), status, M13, CODE, "rm")
    ra = ramp(t, 0.50, 0.53) * (1 - ramp(t, 0.70, 0.74))
    if ra > 0:
        text(d, (W - 28, by + 10), "prompt changed: chain rebuilt once", F11, blend(ACCENT, BG, ra), "rm")


def frame(t: float) -> Image.Image:
    """
    Renders the frame at ``t``, a position in the loop from 0 to 1.
    """

    img = Image.new("RGB", (W * SCALE, H * SCALE), BG)
    d = ImageDraw.Draw(img)
    top_bar(d)
    versions(d, t)
    traces(d, t)
    service(d, t)
    return img.resize((W, H), Image.Resampling.LANCZOS)


frames = [frame(i / (DURATION * FPS)) for i in range(int(DURATION * FPS))]
frames[0].save(
    OUT,
    save_all=True,
    append_images=frames[1:],
    duration=int(1000 / FPS),
    loop=0,
    optimize=True,
)
