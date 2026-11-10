#!/usr/bin/env python3
"""Trend-format GREENLINE shorts (1080x1920, 30 fps) cut from gameplay clips.

Usage: python3 tools/shorts.py OUT_DIR [name ...]
       GREENLINE_CLIPS (default /mnt/project-files) is the folder the clip paths start from.

Formats (SHORTS at the bottom lists the videos):
  guess_boss    a pixelated boss that sharpens on every beat, 3-2-1, then the reveal and a fight
  this_or_that  two bosses stacked top and bottom: who would you fight?
  tier_list     each boss's intro card, then its badge photo drops into an S to D tier board
  satisfying    an explosion combo cut to the beat, with slow motion on the last one
  montage       vertical clips back to back with a hook plate (dance party, race, bug + question)
  screenshot_boss  the 8 bosses flick past in a small frame: screenshot to get yours
  secret_room   the rooftop hatch opens and the hideout is the reveal

Every video loops: the last frames lead back into the first one. Music and sound
effects come from tools/sound.py (made from scratch, no samples). There is no signup
banner: the caption carries the call to action, and YouTube's kids feed recommends
videos that look like ads less.
"""

import os
import subprocess
import sys
import tempfile
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sound  # noqa: E402

W, H, FPS = 1080, 1920, 30
BEAT = 0.5  # 120 BPM
ROOT = os.environ.get("GREENLINE_CLIPS", "/mnt/project-files")
LOGO = os.environ.get("GREENLINE_LOGO", "/mnt/project-files/logo/greenline-logo-transparent.png")
FONT_DIR = os.path.expanduser("~/.cache/greenline-fonts")
FONTS = {"Bungee-Regular.ttf": "ofl/bungee/Bungee-Regular.ttf", "Rubik.ttf": "ofl/rubik/Rubik%5Bwght%5D.ttf"}
WHITE, GREEN, RED, INK = (244, 248, 255, 255), (166, 255, 60, 255), (255, 74, 61, 255), (8, 10, 14, 255)
GLOW_G, GLOW_R = (120, 255, 90, 200), (255, 90, 60, 170)

# The bosses as they appear in the clips. Times are seconds in the clip.
#   card   when the boss name card slides in (the camera then frames the boss around x=cx)
#   fight  when a good stretch of the fight starts (boss near the middle of the frame)
BOSSES = {
    "foreman": dict(name="THE FOREMAN", job="Boss of the Yard", hint="He ran the train yard",
                    src="2_foreman_intro_fight.mp4", card=5.2, cx=1290, fight=13.6),
    "glo-bro": dict(name="GLO-BRO", job="Boss of Glo-Land", hint="Strongest guy at the carnival",
                    src="3_globro_intro.mp4", card=3.7, cx=1290, fight=6.8),
    "rat-king": dict(name="THE RAT KING", job="Boss of the Sewers", hint="He lives under the city",
                     src="social/clips/07_sewers_ratking.mp4", card=5.6, cx=1290, fight=9.6),
    "coach": dict(name="THE COACH", job="Boss of Greenline High", hint="He never misses a game",
                  src="social/clips/08_highschool_coach.mp4", card=5.6, cx=1290, fight=9.4),
    "mall-cop": dict(name="THE MALL COP", job="Boss of the Mega Mall", hint="The mall is closed",
                     src="social/clips/09_mall_mallcop.mp4", card=7.0, cx=1290, fight=10.4),
    "ice-cream-man": dict(name="THE ICE CREAM MAN", job="Boss of the Suburbs", hint="Hear that jingle?",
                          src="social/clips/10_suburbs_icecream.mp4", card=5.6, cx=1270, fight=9.4),
    "dr-verde": dict(name="DR. VERDE", job="Boss of the Research Lab", hint="She made the Glo",
                     src="social/clips/11_lab_verde_bubble.mp4", card=4.6, cx=1290, fight=11.4),
    "scrap-titan": dict(name="THE SCRAP TITAN", job="Boss of the Glo Reactor", hint="The reactor built him",
                        src="social/clips/12_reactor_titan.mp4", card=5.0, cx=1290, fight=7.6),
}


# ---------------------------------------------------------------- basics

_fonts = {}


def font(name, size, weight=None):
    key = (name, size, weight)
    if key not in _fonts:
        path = os.path.join(FONT_DIR, name)
        if not os.path.exists(path):
            os.makedirs(FONT_DIR, exist_ok=True)
            urllib.request.urlretrieve("https://raw.githubusercontent.com/google/fonts/main/" + FONTS[name], path)
        f = ImageFont.truetype(path, size)
        if weight:
            f.set_variation_by_name(weight)
        _fonts[key] = f
    return _fonts[key]


def label(s, size, fill=WHITE, name="Bungee-Regular.ttf", weight=None, glow=None, max_w=W - 100):
    """Text sprite: dark outline, soft drop shadow, optional glow. Shrinks to fit max_w."""
    f = font(name, size, weight)
    while f.getlength(s) > max_w and size > 24:
        size -= 4
        f = font(name, size, weight)
    stroke = max(3, size // 11)
    l, t, r, b = f.getbbox(s, stroke_width=stroke)
    pad = 34
    img = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad + 10))
    org = (pad - l, pad - t)
    sh = Image.new("RGBA", img.size)
    ImageDraw.Draw(sh).text((org[0], org[1] + 8), s, font=f, fill=(0, 0, 0, 170), stroke_width=stroke, stroke_fill=(0, 0, 0, 170))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(5)))
    if glow:
        g = Image.new("RGBA", img.size)
        ImageDraw.Draw(g).text(org, s, font=f, fill=glow, stroke_width=stroke, stroke_fill=glow)
        img.alpha_composite(g.filter(ImageFilter.GaussianBlur(14)))
    ImageDraw.Draw(img).text(org, s, font=f, fill=fill, stroke_width=stroke, stroke_fill=INK)
    return img


def put(canvas, spr, cx, cy, scale=1.0, alpha=1.0):
    """Paste a sprite centered at (cx, cy), scaled and faded, clipped to the canvas."""
    if scale <= 0.02 or alpha <= 0.02:
        return
    if scale != 1:
        spr = spr.resize((max(1, round(spr.width * scale)), max(1, round(spr.height * scale))), Image.BILINEAR)
    if alpha < 1:
        spr = spr.copy()
        spr.putalpha(spr.getchannel("A").point(lambda v: int(v * alpha)))
    x, y = round(cx - spr.width / 2), round(cy - spr.height / 2)
    sx, sy = max(0, -x), max(0, -y)
    x2, y2 = min(canvas.width, x + spr.width), min(canvas.height, y + spr.height)
    if x2 > x + sx and y2 > y + sy:
        canvas.alpha_composite(spr.crop((sx, sy, x2 - x, y2 - y)), (x + sx, y + sy))


def clamp01(x):
    return max(0.0, min(1.0, x))


def smooth(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def back(x):
    x = clamp01(x)
    return 1 + 2.70158 * (x - 1) ** 3 + 1.70158 * (x - 1) ** 2


def pop(t, t0, d=0.22):
    return 0.0 if t < t0 else back((t - t0) / d)


def decay(t, t0, d):
    """1 at t0, easing to 0 after d seconds (0 before t0)."""
    return 0.0 if t < t0 else 1 - smooth((t - t0) / d)


def pixelate(img, block):
    if block <= 1:
        return img
    w, h = img.size
    return img.resize((max(1, w // block), max(1, h // block)), Image.BILINEAR).resize((w, h), Image.NEAREST)


def punch(img, k):
    if k <= 1.001:
        return img
    w, h = img.size
    cw, ch = w / k, h / k
    return img.resize((w, h), Image.BICUBIC, box=((w - cw) / 2, (h - ch) / 2, (w + cw) / 2, (h + ch) / 2))


def flash(img, a):
    return img if a <= 0.01 else Image.blend(img, Image.new("RGBA", img.size, (255, 255, 255, 255)), min(1, a))


def backdrop(img, dark=0.42):
    """Full-screen blurred, darkened copy of a frame (behind windows and split screens)."""
    w, h = img.size
    k = max(W / w, H / h)
    small = img.convert("RGB").resize((max(1, round(w * k / 24)), max(1, round(h * k / 24))), Image.BILINEAR)
    small = small.filter(ImageFilter.GaussianBlur(1.5))
    big = small.resize((round(w * k), round(h * k)), Image.BILINEAR)
    big = big.crop(((big.width - W) // 2, (big.height - H) // 2, (big.width - W) // 2 + W, (big.height - H) // 2 + H))
    return Image.eval(big, lambda v: int(v * dark)).convert("RGBA")


def frame_box(canvas, x, y, w, h):
    d = ImageDraw.Draw(canvas)
    d.rectangle((x - 6, y - 6, x + w + 5, y + h + 5), outline=INK, width=6)
    d.rectangle((x - 2, y - 2, x + w + 1, y + h + 1), outline=(120, 255, 90, 255), width=2)


_logo = None


def logo(height=64):
    global _logo
    if _logo is None or _logo.height != height:
        im = Image.open(LOGO).convert("RGBA")
        _logo = im.resize((round(im.width * height / im.height), height), Image.LANCZOS)
    return _logo


def fps_of(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                        "-of", "csv=p=0", path], capture_output=True, text=True, check=True).stdout.strip()
    a, b = r.split("/")
    return float(a) / float(b)


class Clip:
    """Frames of a clip between t0 and t1 (clip seconds), cropped to box=(x, y, w, h) and scaled to size."""

    def __init__(self, src, t0, t1, box, size, fps=None):
        path = os.path.join(ROOT, src)
        self.fps = fps or fps_of(path)
        x, y, w, h = box
        vf = f"crop={w}:{h}:{x}:{y},scale={size[0]}:{size[1]}:flags=lanczos" + (f",fps={fps}" if fps else "")
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", path,
                              "-vf", vf, "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True, check=True).stdout
        n = len(raw) // (size[0] * size[1] * 3)
        if n == 0:
            raise RuntimeError(f"no frames from {src} at {t0}-{t1}")
        self.frames = np.frombuffer(raw, np.uint8)[: n * size[0] * size[1] * 3].reshape(n, size[1], size[0], 3)

    def at(self, s):
        i = min(len(self.frames) - 1, max(0, int(s * self.fps + 0.5)))
        return Image.fromarray(self.frames[i]).convert("RGBA")


def clip_audio(src, t0, dur, speed=1.0):
    """Stereo game audio for dur output seconds; speed < 1 is slow motion (pitch drops with it)."""
    path = os.path.join(ROOT, src)
    af = f"aresample={sound.SR}"
    if speed != 1:
        af += f",asetrate={int(sound.SR * speed)},aresample={sound.SR}"
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t0:.3f}", "-t", f"{dur * speed:.3f}", "-i", path,
                          "-vn", "-af", af, "-ac", "2", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2)


_sfx = {}


def sfx(name):
    if name not in _sfx:
        _sfx[name] = sound.sfx(name)
    return _sfx[name]


def render(out, seconds, draw, audio):
    n = round(seconds * FPS)
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "a.wav")
        peak = float(np.abs(audio).max())
        sound.write_wav(wav, audio / max(1.0, peak / 0.9))
        p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                              "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                              "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-af", "loudnorm=I=-14:TP=-1.5,aresample=48000,alimiter=limit=0.8:attack=2:release=60:level=false", "-ar", "48000",
                              "-shortest", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
        for i in range(n):
            p.stdin.write(draw(i / FPS).convert("RGB").tobytes())
        p.stdin.close()
        if p.wait():
            raise RuntimeError("ffmpeg failed for " + out)
    return out


# ---------------------------------------------------------------- formats

WIN, WIN_Y = 1080, 360  # square video window for guess_boss


def guess_boss(key, out):
    """0-4 s: pixelated boss, sharper on every beat, 3-2-1. 4 s: flash reveal + name. 5.5 s: the fight."""
    b = BOSSES[key]
    T, R = 8.0, 4.0
    t_still = b["card"] + 0.1
    reveal = Clip(b["src"], t_still, t_still + 1.6, (b["cx"] - 420, 120, 840, 840), (WIN, WIN))
    fight = Clip(b["src"], b["fight"], b["fight"] + 2.7, (420, 0, 1080, 1080), (WIN, WIN))
    still = reveal.at(0)
    title = label("GUESS THE BOSS", 112, WHITE, glow=GLOW_G)
    name = label(b["name"], 104, RED, glow=GLOW_R)
    hint = label("HINT: " + b["hint"], 60, WHITE, name="Rubik.ttf", weight="Black")
    job = label(b["job"], 64, GREEN, name="Rubik.ttf", weight="Black")
    digits = {k: label(str(k), 330, WHITE, glow=GLOW_G) for k in (1, 2, 3)}
    qmark = label("?", 460, WHITE, glow=GLOW_G)
    blocks = [96, 80, 64, 48, 36, 26, 18, 12]
    cy = WIN_Y + WIN / 2

    def draw(t):
        if t < R:
            k = int(t / BEAT)
            win = punch(pixelate(still, blocks[min(k, 7)]), 1 + 0.06 * t / R + 0.03 * decay(t, k * BEAT, 0.14))
        elif t < R + 1.5:
            win = punch(reveal.at(t - R), 1 + 0.16 * decay(t, R, 0.3))
        else:
            win = fight.at(t - R - 1.5)
            if t > T - 0.4:  # melt back into pixels so the loop restarts cleanly
                win = pixelate(win, int(12 + 84 * smooth((t - (T - 0.4)) / 0.4)))
        c = backdrop(win)
        c.alpha_composite(win, (0, WIN_Y))
        frame_box(c, 0, WIN_Y, WIN, WIN)
        c.alpha_composite(logo(76), (24, WIN_Y + 22))
        if t < R:
            if t < 2.5:
                put(c, qmark, W / 2, cy, 1 + 0.06 * decay(t, int(t / BEAT) * BEAT, 0.2), 0.8)
            else:
                k = 3 - int((t - 2.5) / BEAT)
                put(c, digits[k], W / 2, cy, pop(t, 2.5 + (3 - k) * BEAT, 0.18))
            bar = int(W * (1 - t / R))
            ImageDraw.Draw(c).rectangle((0, WIN_Y + WIN + 8, bar, WIN_Y + WIN + 26), fill=GREEN)
            put(c, title, W / 2, 232, pop(t, 0, 0.18) if t > 0 else 0.86)
            put(c, hint, W / 2, WIN_Y + WIN + 96, pop(t, 1.0))
        else:
            c = flash(c, 1.0 * decay(t, R, 0.35))
            if t > T - 0.4:
                put(c, title, W / 2, 232, pop(t, T - 0.4, 0.18))
            else:
                put(c, name, W / 2, 232, pop(t, R, 0.25))
                put(c, job, W / 2, WIN_Y + WIN + 96, pop(t, R + 0.25))
        return c

    parts = [(0, sound.beat(T, drop=R, style="quiz"), 0.9)]
    parts += [(k * BEAT, sfx("tick"), 0.3 if k < 5 else 0.6) for k in range(8)]
    parts += [(R - 1.0, sfx("riser"), 0.45), (R, sfx("impact"), 0.9), (R, sfx("reveal"), 0.55),
              (R, clip_audio(b["src"], t_still, 1.5), 0.45), (R + 1.5, clip_audio(b["src"], b["fight"], T - R - 1.5), 0.5),
              (T - 0.4, sfx("whoosh"), 0.35), (1.0, sfx("pop"), 0.4)]
    return render(out, T, draw, sound.mix(T, parts))


def this_or_that(key_a, key_b, out):
    """Two bosses, top and bottom: intro, name card, fight. 'Who would you fight?'"""
    HW, HH = W, 960
    halves = []
    for key in (key_a, key_b):
        b = BOSSES[key]
        intro = Clip(b["src"], b["card"] - 1.0, b["card"], (960 - 450, 140, 900, 800), (HW, HH))
        card = Clip(b["src"], b["card"], b["card"] + 1.5, (b["cx"] - 420, 140, 900, 800), (HW, HH))
        f0 = b["card"] + 1.7
        fight = Clip(b["src"], f0, f0 + 7.0, (960 - 607, 0, 1215, 1080), (HW, HH))
        halves.append((b, intro, card, fight, len(fight.frames) / fight.fps))
    T = min(8.5, int((2.5 + min(h[4] for h in halves)) / BEAT) * BEAT)
    hook = label("WHO WOULD YOU FIGHT?", 92, WHITE, glow=GLOW_G)
    names = [label(h[0]["name"], 74, RED, glow=GLOW_R, max_w=W - 220) for h in halves]
    nums = [label(n, 96, GREEN, glow=GLOW_G) for n in ("1", "2")]
    vs = label("VS", 110, WHITE, glow=GLOW_R)
    pick = label("1 OR 2?", 88, GREEN, glow=GLOW_G)

    def half(h, t):
        _, intro, card, fight, _ = h
        if t < 1.0:
            return intro.at(t)
        if t < 2.5:
            return punch(card.at(t - 1.0), 1 + 0.08 * decay(t, 1.0, 0.25))
        return fight.at(t - 2.5)

    def draw(t):
        top, bot = half(halves[0], t), half(halves[1], t)
        z = 1 + 0.1 * decay(t, 0, 0.3)
        c = Image.new("RGBA", (W, H), INK)
        c.alpha_composite(punch(top, z), (0, 0))
        c.alpha_composite(punch(bot, z), (0, HH))
        d = ImageDraw.Draw(c)
        d.rectangle((0, HH - 6, W, HH + 6), fill=INK)
        d.rectangle((0, HH - 2, W, HH + 2), fill=(120, 255, 90, 255))
        c = flash(c, 0.7 * decay(t, 1.0, 0.25))
        put(c, hook, W / 2, 230, pop(t, 0, 0.18) if t > 0 else 0.86)
        put(c, nums[0], 80, HH - 140, pop(t, 0.25))
        put(c, names[0], W / 2 + 40, HH - 140, pop(t, 0.25))
        put(c, nums[1], 80, HH + 150, pop(t, 0.5))
        put(c, names[1], W / 2 + 40, HH + 150, pop(t, 0.5))
        if t < T - 2.5:
            d = ImageDraw.Draw(c)
            s = 1 + 0.08 * decay(t, int(t / BEAT) * BEAT, 0.2)
            r = 84 * s * pop(t, 0.1)
            d.ellipse((W / 2 - r, HH - r, W / 2 + r, HH + r), fill=(20, 22, 28, 255), outline=(255, 74, 61, 255), width=6)
            put(c, vs, W / 2, HH, s * pop(t, 0.1))
        else:
            put(c, pick, W / 2, HH, pop(t, T - 2.5) * (1 + 0.06 * decay(t, int(t / BEAT) * BEAT, 0.2)))
        return c

    parts = [(0, sound.beat(T, style="disco"), 0.8), (0, sfx("whoosh"), 0.5), (0.1, sfx("impact"), 0.5),
             (0.25, sfx("pop"), 0.5), (0.5, sfx("pop"), 0.5), (1.0, sfx("impact"), 0.45), (T - 2.5, sfx("reveal"), 0.4)]
    for h in halves:
        b = h[0]
        parts += [(1.0, clip_audio(b["src"], b["card"], 1.5), 0.25), (2.5, clip_audio(b["src"], b["card"] + 1.7, T - 2.5), 0.22)]
    return render(out, T, draw, sound.mix(T, parts))


BADGE = (102, 195, 143, 163)  # badge photo on the boss name card, source pixels (x, y, w, h)
TIERS = [("S", (255, 92, 92)), ("A", (255, 170, 77)), ("B", (255, 216, 77)), ("C", (143, 227, 107)), ("D", (107, 199, 255))]


def tier_list(order, out, end_key="scrap-titan"):
    """order: [(boss key, tier letter), ...]. One boss per second, then 'DO YOU AGREE?'."""
    VW, VH, VY = W, 472, 350  # 1920x840 card shots (no letterbox bars) shown full width
    BY, ROW, LW = 900, 116, 116  # tier board top, row height, label width
    PS = 96  # badge photo width
    cards, faces = [], []
    for key, _ in order:
        b = BOSSES[key]
        cards.append(Clip(b["src"], b["card"] + 0.1, b["card"] + 1.2, (0, 120, 1920, 840), (VW, VH)))
        # the badge photo on the boss's name card (same place on every card)
        f = Clip(b["src"], b["card"] + 0.8, b["card"] + 0.9, BADGE, (PS, round(PS * BADGE[3] / BADGE[2]))).at(0)
        ImageDraw.Draw(f).rectangle((0, 0, f.width - 1, f.height - 1), outline=INK, width=4)
        faces.append(f)
    eb = BOSSES[end_key]
    ending = Clip(eb["src"], eb["fight"], eb["fight"] + 2.0, (0, 120, 1920, 840), (VW, VH))
    T0, STEP = 0.5, 1.0
    T = T0 + STEP * len(order) + 1.5
    rows = {letter: i for i, (letter, _) in enumerate(TIERS)}
    slots, count = [], {letter: 0 for letter, _ in TIERS}
    for key, letter in order:
        slots.append((LW + 30 + count[letter] * (PS + 12) + PS / 2, BY + rows[letter] * ROW + ROW / 2))
        count[letter] += 1
    hook = label("BOSS TIER LIST", 118, WHITE, glow=GLOW_G)
    sub = label("Who hits the hardest?", 54, GREEN, name="Rubik.ttf", weight="Black")
    names = [label(BOSSES[k]["name"], 64, RED, glow=GLOW_R) for k, _ in order]
    agree = label("DO YOU AGREE?", 92, GREEN, glow=GLOW_G)
    board = Image.new("RGBA", (W, ROW * len(TIERS)), (0, 0, 0, 0))
    bd = ImageDraw.Draw(board)
    for i, (letter, col) in enumerate(TIERS):
        y = i * ROW
        bd.rectangle((24, y + 3, W - 24, y + ROW - 3), fill=(18, 22, 30, 235))
        bd.rectangle((24, y + 3, 24 + LW, y + ROW - 3), fill=col + (255,))
    lf = font("Bungee-Regular.ttf", 72)
    for i, (letter, _) in enumerate(TIERS):
        bd.text((24 + LW / 2, i * ROW + ROW / 2), letter, font=lf, fill=(14, 16, 20, 255), anchor="mm")

    def landed(i, t):
        return t >= T0 + i * STEP + 0.5 + 0.22

    def draw(t):
        i = min(len(order) - 1, int(max(0, t - T0) / STEP))
        if t < T0:
            win = cards[0].at(0)
        elif t < T0 + STEP * len(order):
            win = punch(cards[i].at(t - T0 - i * STEP), 1 + 0.07 * decay(t, T0 + i * STEP, 0.25))
        else:
            win = ending.at(t - T0 - STEP * len(order))
        c = backdrop(win, 0.3)
        c.alpha_composite(win, (0, VY))
        frame_box(c, 0, VY, VW, VH)
        put(c, hook, W / 2, 175, pop(t, 0, 0.18) if t > 0 else 0.86)
        put(c, sub, W / 2, 272, pop(t, 0.15))
        bshake = 0
        for j in range(len(order)):
            tl = T0 + j * STEP + 0.5 + 0.22
            if t >= tl:
                bshake += 6 * decay(t, tl, 0.18)
        c.alpha_composite(board, (0, BY + round(bshake)))
        for j in range(len(order)):
            ts = T0 + j * STEP + 0.5
            if t < ts:
                break
            sx, sy = slots[j]
            k = smooth((t - ts) / 0.22)
            x0, y0 = W / 2, VY + VH / 2
            x, y = x0 + (sx - x0) * k, y0 + (sy - y0) * k - 160 * np.sin(np.pi * k)
            put(c, faces[j], x, y + (bshake if landed(j, t) else 0), 2.2 - 1.2 * k)
            if landed(j, t):  # row flash on landing
                a = decay(t, ts + 0.22, 0.25)
                if a > 0:
                    rr = BY + rows[order[j][1]] * ROW
                    ov = Image.new("RGBA", (W - 48, ROW - 6), (255, 255, 255, int(90 * a)))
                    c.alpha_composite(ov, (24, rr + 3))
        if t < T0 + STEP * len(order):
            if t >= T0:
                put(c, names[i], W / 2, VY + VH + 52, pop(t, T0 + i * STEP, 0.18))
        else:
            put(c, agree, W / 2, VY + VH + 52, pop(t, T0 + STEP * len(order)))
        return c

    parts = [(0, sound.beat(T, style="disco"), 0.8)]
    for j, (key, _) in enumerate(order):
        b = BOSSES[key]
        ts = T0 + j * STEP
        parts += [(ts, sfx("whoosh"), 0.3), (ts + 0.5 + 0.22, sfx("thunk"), 0.7), (ts, clip_audio(b["src"], b["card"] + 0.1, 1.0), 0.3)]
    te = T0 + STEP * len(order)
    parts += [(te, sfx("reveal"), 0.45), (te, clip_audio(eb["src"], eb["fight"], 1.5), 0.45)]
    return render(out, T, draw, sound.mix(T, parts))


def satisfying(segments, out, hook=("WAIT FOR", "THE LAST ONE")):
    """segments: [(clip, clip start, length, speed, boom at (output s from segment start, or None), crop center x)].
    Full-screen vertical crop; flash + punch + shake on each boom; combo counter; loops."""
    clips, t, booms = [], 0.0, []
    for src, s0, length, speed, boom, cx in segments:
        clips.append((t, length, speed, Clip(src, s0, s0 + length * speed + 0.1, (cx - 280, 84, 560, 996), (W, H)), src, s0))
        if boom is not None:
            booms.append(t + boom)
        t += length
    T = t
    hooks = [label(hook[0], 104, WHITE, glow=GLOW_G), label(hook[1], 104, GREEN, glow=GLOW_G)]
    combos = [label(f"x{n + 1}", 200 if n < len(booms) - 1 else 300, WHITE if n < len(booms) - 1 else GREEN, glow=GLOW_G)
              for n in range(len(booms))]
    boom_word = label("COMBO!", 120, RED, glow=GLOW_R)
    rng = np.random.default_rng(3)
    jit = rng.uniform(-1, 1, (int(T * FPS) + 2, 2))

    def draw(t):
        for t0, length, speed, clip, _, _ in clips:
            if t < t0 + length or clip is clips[-1][3]:
                img = clip.at((t - t0) * speed)
                break
        z, sh, fl = 1.0, 0.0, 0.0
        last = None
        for n, tb in enumerate(booms):
            if t >= tb:
                big = 1.6 if n == len(booms) - 1 else 1.0
                z += 0.12 * big * decay(t, tb, 0.35)
                sh += 26 * big * decay(t, tb, 0.4)
                fl = max(fl, 0.75 * decay(t, tb, 0.18))
                last = n
        img = punch(img, z)
        if sh > 0.5:
            j = jit[min(len(jit) - 1, int(t * FPS))]
            img = img.transform(img.size, Image.AFFINE, (1, 0, j[0] * sh, 0, 1, j[1] * sh), Image.BILINEAR)
        c = flash(img, fl)
        put(c, hooks[0], W / 2, 250, pop(t, 0, 0.18) if t > 0 else 0.86)
        put(c, hooks[1], W / 2, 360, pop(t, 0, 0.18) if t > 0 else 0.86)
        if last is not None:
            tb = booms[last]
            put(c, combos[last], W / 2, 700, pop(t, tb, 0.2) * (1.0 if t - tb < 0.6 or last == len(booms) - 1 else max(0, 1 - (t - tb - 0.6) * 4)))
            if last == len(booms) - 1:
                put(c, boom_word, W / 2, 900, pop(t, tb + 0.15, 0.25))
        return c

    parts = [(0, sound.beat(T, style="hype"), 0.55)]
    for t0, length, speed, _, src, s0 in clips:
        parts.append((t0, clip_audio(src, s0, length, speed), 1.0))
    for n, tb in enumerate(booms):
        parts.append((tb, sfx("impact"), 0.5 if n < len(booms) - 1 else 0.95))
    parts.append((booms[-1] - 1.0, sfx("riser"), 0.4))
    return render(out, T, draw, sound.mix(T, parts))


def music_audio(path, t0, dur):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", os.path.join(ROOT, path),
                          "-af", f"aresample={sound.SR}", "-ac", "2", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2)


def faded(x, ms=12):
    n = min(len(x) // 2, int(sound.SR * ms / 1000))
    if n:
        x = x.copy()
        ramp = np.linspace(0, 1, n, dtype=np.float32)[:, None]
        x[:n] *= ramp
        x[-n:] *= ramp[::-1]
    return x


def montage(out, segs, hook=(), hook_y=1400, music=None, clip_gain=1.0, ask=None, beat=None):
    """Vertical 1080x1920 clips played back to back (the Mac's v3 clips).

    segs: [dict(src, s0, length, punch=False, flash=False, badge=None)], each played from clip time s0.
    hook: text lines shown on a dark plate centred at hook_y for the whole video.
    music: (wav path, start s) played under everything; clip_gain sets the clips' own sound.
    beat: (style, gain) adds a beat from tools/sound.py instead of a music file.
    ask: text that pops over the hook for the last 2 s (e.g. "COMMENT 1-8")."""
    T = sum(sg["length"] for sg in segs)
    starts = np.cumsum([0] + [sg["length"] for sg in segs])[:-1]
    lines = [label(txt, size, col, glow=GLOW_G if col == GREEN else None) for txt, size, col in hook]
    ask_spr = label(ask, 76, GREEN, glow=GLOW_G) if ask else None
    badges = {i: label(sg["badge"], 120, WHITE, glow=GLOW_G) for i, sg in enumerate(segs) if sg.get("badge")}
    cache = {}

    def frames_for(i):
        if i not in cache:
            cache.clear()  # keep one segment in memory
            sg = segs[i]
            cache[i] = Clip(sg["src"], sg["s0"], sg["s0"] + sg["length"] + 0.1, (0, 0, 1080, 1920), (W, H), fps=FPS)
        return cache[i]

    hook_h = sum(sp.height - 60 for sp in lines)

    def draw(t):
        i = int(np.searchsorted(starts, t, side="right") - 1)
        sg, t0 = segs[i], starts[i]
        img = frames_for(i).at(t - t0)
        if sg.get("punch"):
            img = punch(img, 1 + 0.08 * decay(t, t0, 0.3))
        c = flash(img, 0.8 * decay(t, t0, 0.2)) if sg.get("flash") else img
        if lines:
            y = hook_y - hook_h / 2
            plate = Image.new("RGBA", (W, H))
            ImageDraw.Draw(plate).rounded_rectangle((60, y - 26, W - 60, y + hook_h + 26), radius=26, fill=(6, 10, 14, 175))
            c.alpha_composite(plate)
            for k, sp in enumerate(lines):
                h = sp.height - 60
                put(c, sp, W / 2, y + h / 2, pop(t, 0.05 * k, 0.18) if t > 0 else 0.9)
                y += h
        if i in badges:
            put(c, badges[i], 120, 470, pop(t, t0, 0.2) if t > 0 else 1.0)
        if ask_spr is not None and t > T - 2.0:
            put(c, ask_spr, W / 2, hook_y - hook_h / 2 - 90, pop(t, T - 2.0))
        return c

    parts = []
    if music:
        parts.append((0, music_audio(music[0], music[1], T), 1.0))
    if beat:
        parts.append((0, sound.beat(T, style=beat[0]), beat[1]))
    if clip_gain:
        for sg, t0 in zip(segs, starts):
            parts.append((t0, faded(clip_audio(sg["src"], sg["s0"], sg["length"])), clip_gain))
    for sg, t0 in zip(segs, starts):
        if sg.get("flash"):
            parts.append((t0, sfx("whoosh"), 0.35))
    audio = sound.mix(T, parts)
    return render(out, T, draw, audio)


V3 = "greenline_v3_9x16_{}.mp4"
DISCO = "greenline_music_disco_125_a.wav"  # 125 BPM, first beat at 0.02 s; the disco clips start in sync with it
BAR = 4 * 60 / 125


def dance_off(out):
    """All 8 bosses, one bar each. Each boss's clip time is chosen so its dance stays on the beat of the music."""
    segs = []
    for k in range(8):
        base = 4.0 * (k % 4)
        t_out = k * BAR
        x = (t_out - base) % (BAR / 4)
        x = x + BAR / 4 if x < 0.3 else x  # skip the name card's first frames
        segs.append(dict(src=V3.format("disco_bossoff_" + "ab"[k // 4]), s0=base + x, length=BAR, punch=True, badge=str(k + 1)))
    return montage(out, segs, hook=[("WHO DANCES BEST?", 84, WHITE)], music=(DISCO, 0.0), clip_gain=0, ask="PICK 1 TO 8")


def screenshot_boss(out):
    """The 8 bosses flick past in a small frame: screenshot to see which one you get.

    Only the small frame changes and every boss picture is set to the same brightness,
    so the fast flicking never flashes the whole screen."""
    T, HOLD, SIZE, TOP = 8.0, 4, 660, 690
    keys = list(BOSSES)
    pics = []
    for k in keys:
        b = BOSSES[k]
        im = Clip(b["src"], b["card"] + 0.1, b["card"] + 0.4, (b["cx"] - 420, 120, 840, 840), (SIZE, SIZE)).at(0)
        pics.append(np.asarray(im.convert("RGB"), np.float32))
    target = float(np.mean([p.mean() for p in pics]))
    gains = [min(1.3, max(0.8, target / p.mean())) for p in pics]
    pics = [Image.fromarray(np.clip(p * g, 0, 255).astype(np.uint8)).convert("RGBA") for p, g in zip(pics, gains)]
    names = [label(BOSSES[k]["name"], 76, RED, glow=GLOW_R, max_w=W - 160) for k in keys]
    rng = np.random.default_rng(3)
    order = []
    while len(order) < round(T * FPS) // HOLD:
        perm = [int(v) for v in rng.permutation(len(keys))]
        if order and perm[0] == order[-1]:
            perm.reverse()
        order += perm
    bg = backdrop(pics[-1], 0.3)
    title = label("SCREENSHOT", 124, WHITE, glow=GLOW_G)
    sub = label("TO GET YOUR BOSS", 84, GREEN, glow=GLOW_G)
    ask = label("WHO DID YOU GET?", 72, WHITE, name="Rubik.ttf", weight="Black")
    x0 = (W - SIZE) // 2

    def draw(t):
        k = order[min(len(order) - 1, int(t * FPS + 0.5) // HOLD)]
        c = bg.copy()
        c.alpha_composite(pics[k], (x0, TOP))
        frame_box(c, x0, TOP, SIZE, SIZE)
        put(c, title, W / 2, 400, pop(t, 0, 0.18) if t > 0 else 0.9)
        put(c, sub, W / 2, 540, pop(t, 0.08, 0.18) if t > 0 else 0.9)
        put(c, names[k], W / 2, TOP + SIZE + 100)
        put(c, ask, W / 2, TOP + SIZE + 250, 1 + 0.05 * decay(t, int(t / BEAT) * BEAT, 0.2))
        c.alpha_composite(logo(84), (W // 2 - logo(84).width // 2, 190))
        return c

    return render(out, T, draw, sound.mix(T, [(0, sound.beat(T, style="hype"), 0.9)]))


def secret_room(out):
    """The rooftop hatch: it opens, the survivor climbs down, and the hideout is the reveal."""
    src = "social/clips/15_hatch_climb.mp4"
    sq = (420, 0, 1080, 1080)
    cuts = [(2.4, 3.0, sq), (7.0, 0.6, sq), (8.6, 0.6, sq), (9.55, 2.3, (545, 110, 830, 830))]
    clips = [Clip(src, s0, s0 + d + 0.1, box, (WIN, WIN), fps=FPS) for s0, d, box in cuts]
    starts = [float(v) for v in np.cumsum([0] + [d for _, d, _ in cuts])[:-1]]
    T, R = sum(d for _, d, _ in cuts), starts[-1]
    line1 = label("THERE'S A SECRET ROOM", 78, WHITE, glow=GLOW_G)
    line2 = label("UNDER THIS HATCH", 78, GREEN, glow=GLOW_G)
    ask = label("What's down there?", 64, WHITE, name="Rubik.ttf", weight="Black")
    name = label("THE HIDEOUT", 110, GREEN, glow=GLOW_G)
    job = label("Your base between missions", 60, WHITE, name="Rubik.ttf", weight="Black")

    def draw(t):
        i = max(k for k, s0 in enumerate(starts) if t >= s0 - 1e-6)
        win = clips[i].at(t - starts[i])
        if i:
            win = punch(win, 1 + (0.14 if i == len(cuts) - 1 else 0.06) * decay(t, starts[i], 0.3))
        c = backdrop(win)
        c.alpha_composite(win, (0, WIN_Y))
        frame_box(c, 0, WIN_Y, WIN, WIN)
        c.alpha_composite(logo(76), (24, WIN_Y + 22))
        if t < R:
            put(c, line1, W / 2, 170, pop(t, 0, 0.18) if t > 0 else 0.9)
            put(c, line2, W / 2, 278, pop(t, 0.08, 0.18) if t > 0 else 0.9)
            put(c, ask, W / 2, WIN_Y + WIN + 96, pop(t, 0.8))
            bar = int(W * (1 - t / R))
            ImageDraw.Draw(c).rectangle((0, WIN_Y + WIN + 8, bar, WIN_Y + WIN + 26), fill=GREEN)
        else:
            c = flash(c, 1.0 * decay(t, R, 0.35))
            put(c, name, W / 2, 232, pop(t, R, 0.25))
            put(c, job, W / 2, WIN_Y + WIN + 96, pop(t, R + 0.25))
        return c

    parts = [(0, sound.beat(T, drop=R, style="quiz"), 0.9), (R - 1.0, sfx("riser"), 0.45), (R, sfx("impact"), 0.9),
             (R, sfx("reveal"), 0.55), (1.3, sfx("thunk"), 0.6)]
    parts += [(s0, faded(clip_audio(src, c0, d)), 0.5) for s0, (c0, d, _) in zip(starts, cuts)]
    parts += [(s0, sfx("whoosh"), 0.3) for s0 in starts[1:-1]]
    return render(out, T, draw, sound.mix(T, parts))


# ---------------------------------------------------------------- the videos

SHORTS = {
    "18-guess-rat-king": lambda o: guess_boss("rat-king", o),
    "19-ice-cream-or-mall-cop": lambda o: this_or_that("ice-cream-man", "mall-cop", o),
    "20-boss-tier-list": lambda o: tier_list([("foreman", "D"), ("ice-cream-man", "C"), ("glo-bro", "B"), ("coach", "C"),
                                              ("mall-cop", "B"), ("rat-king", "A"), ("dr-verde", "A"), ("scrap-titan", "S")], o),
    "21-wait-for-the-last-one": lambda o: satisfying([
        ("social/clips/13_overload_shockwave.mp4", 3.0, 1.5, 1.0, 1.0, 900),
        ("1_yard_horde.mp4", 2.7, 1.0, 1.0, 0.5, 900),
        ("social/clips/13_overload_shockwave.mp4", 8.1, 1.0, 1.0, 0.5, 900),
        ("social/clips/14_demolitionist_grenade.mp4", 3.0, 1.5, 1.0, 1.0, 900),
        ("5_bomber_multikill.mp4", 7.3, 0.5, 1.0, None, 900),
        ("5_bomber_multikill.mp4", 7.8, 2.5, 0.4, 1.0, 900),
    ], o),
    "22-guess-scrap-titan": lambda o: guess_boss("scrap-titan", o),
    "23-rat-king-or-dr-verde": lambda o: this_or_that("rat-king", "dr-verde", o),
    "24-guess-mall-cop": lambda o: guess_boss("mall-cop", o),
    # from the Mac's v3 clips (drafts until Logan approves them)
    "25-glo-disco": lambda o: montage(o, [
        dict(src=V3.format("disco_close_1"), s0=0.0, length=BAR),
        dict(src=V3.format("disco_close_2"), s0=BAR, length=BAR / 2, punch=True),
        dict(src=V3.format("disco_close_3"), s0=1.5 * BAR, length=BAR / 2, punch=True),
        dict(src=V3.format("disco_party"), s0=2 * BAR, length=BAR),
        dict(src=V3.format("disco_party"), s0=3 * BAR, length=BAR, punch=True),
        dict(src=V3.format("disco_party"), s0=4 * BAR, length=BAR),
    ], hook=[("WHEN THE ZOMBIES", 84, WHITE), ("FIND THE DISCO", 84, GREEN)], hook_y=330, music=(DISCO, 0.0), clip_gain=0),
    "26-boss-dance-off": dance_off,
    "27-noob-pro-hacker": lambda o: montage(o, [
        dict(src=V3.format("noob_pro_hacker"), s0=0.2, length=1.0),
        dict(src=V3.format("noob_pro_hacker"), s0=4.4, length=2.0),
        dict(src=V3.format("noob_pro_hacker"), s0=7.2, length=3.2, flash=True),
        dict(src=V3.format("noob_pro_hacker"), s0=13.6, length=4.8, flash=True),
    ], hook=[("WHICH ONE ARE YOU?", 80, WHITE)]),
    "28-bloopers": lambda o: montage(o, [
        dict(src=V3.format("bloopers"), s0=0.4, length=2.4),
        dict(src=V3.format("bloopers"), s0=5.0, length=2.4, flash=True),
        dict(src=V3.format("bloopers"), s0=8.6, length=2.4, flash=True),
        dict(src=V3.format("bloopers"), s0=13.0, length=2.6, flash=True),
        dict(src=V3.format("bloopers"), s0=16.2, length=1.8, flash=True),
    ], hook=[("BUGS WE FOUND", 80, WHITE), ("MAKING OUR GAME", 80, GREEN)]),
    "29-before-now": lambda o: montage(o, [
        dict(src=V3.format("before_now"), s0=0.0, length=1.6),
        dict(src=V3.format("before_now"), s0=5.0, length=5.4, flash=True, punch=True),
    ], hook=[("OUR GAME,", 80, WHITE), ("ONE MONTH APART", 80, GREEN)]),
    # Nov 10: formats that the research and our own numbers point to (race, bug + question, screenshot game, secret)
    "30-level-1-vs-max": lambda o: montage(o, [
        dict(src="level1_vs_max_9x16_v4.mp4", s0=0.0, length=8.0),
    ], hook=[("WHO CLEARS 13 ZOMBIES FIRST?", 56, WHITE)], hook_y=925, beat=("hype", 0.55), clip_gain=0.8),
    "31-keep-this-bug": lambda o: montage(o, [
        dict(src=V3.format("bloopers"), s0=8.0, length=2.8),
        dict(src=V3.format("bloopers"), s0=8.0, length=2.8, flash=True),
    ], hook=[("SHOULD WE KEEP", 84, WHITE), ("THIS BUG?", 84, GREEN)], ask="YES OR NO?", beat=("hype", 0.6)),
    "32-screenshot-your-boss": screenshot_boss,
    "33-secret-room": secret_room,
}


def main():
    out_dir, *only = sys.argv[1:]
    os.makedirs(out_dir, exist_ok=True)
    for name, make in SHORTS.items():
        if only and name not in only:
            continue
        print("made", make(os.path.join(out_dir, name + ".mp4")), flush=True)


if __name__ == "__main__":
    main()
