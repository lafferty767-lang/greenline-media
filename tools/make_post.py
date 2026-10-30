"""Turn 16:9 GREENLINE gameplay clips into 1080x1920 posts for TikTok, Reels and Shorts.

Usage: python3 tools/make_post.py tools/posts.json CLIP_DIR OUT_DIR [id ...]

Each post in the JSON list has:
  id        output name, e.g. "07-rat-king" -> OUT_DIR/07-rat-king.mp4
  src       clip file in CLIP_DIR
  hook      two lines shown under the logo (white, then green)
  mode      "crop" (default): the clip fills a 1080x1100 window, cropped from the middle
            "wide": the whole width shows in a 1080x608 window (menus, UI)
  pan       optional [[start, end], ...] seconds when the window slides to the clip's
            left edge, e.g. while a boss name card is on screen
  captions  optional [[start, end, "text"], ...] burned-in captions near the bottom
            of the video window
  trim      optional [start, duration] in seconds of the clip
  cut       optional [start, end] in seconds (after trim) to remove, e.g. a slow stretch;
            pan and caption times are on the finished post's timeline

Fonts (Jersey 15, Barlow, all SIL Open Font License) are downloaded from the
Google Fonts repo on first use into ~/.cache/greenline-fonts.
"""

import json
import os
import subprocess
import sys
import tempfile
import urllib.request

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.environ.get("GREENLINE_LOGO", "/mnt/project-files/logo/greenline-logo-transparent.png")
FONT_DIR = os.path.expanduser("~/.cache/greenline-fonts")
FONTS = {
    "Jersey15-Regular.ttf": "ofl/jersey15/Jersey15-Regular.ttf",
    "Barlow-SemiBold.ttf": "ofl/barlow/Barlow-SemiBold.ttf",
}
# Video window: top edge and height for each mode.
WINDOW = {"crop": (410, 1100), "wide": (640, 608)}
WHITE, GREEN, INK = (240, 246, 255), (166, 255, 60), (6, 8, 12, 255)


def font(name, size):
    path = os.path.join(FONT_DIR, name)
    if not os.path.exists(path):
        os.makedirs(FONT_DIR, exist_ok=True)
        urllib.request.urlretrieve("https://raw.githubusercontent.com/google/fonts/main/" + FONTS[name], path)
    return ImageFont.truetype(path, size)


def text(img, y, s, name, size, fill, glow=None, max_w=W - 90, outline=4):
    """Centered text with a dark outline and optional glow, shrunk to fit max_w."""
    f = font(name, size)
    while ImageDraw.Draw(img).textlength(s, font=f) > max_w and size > 30:
        size -= 2
        f = font(name, size)
    x = (W - ImageDraw.Draw(img).textlength(s, font=f)) / 2
    if glow:
        g = Image.new("RGBA", (W, H))
        ImageDraw.Draw(g).text((x, y), s, font=f, fill=glow)
        img.alpha_composite(g.filter(ImageFilter.GaussianBlur(10)))
    o = Image.new("RGBA", (W, H))
    od = ImageDraw.Draw(o)
    for dx in (-outline, 0, outline):
        for dy in (-outline, 0, outline, outline + 3):
            od.text((x + dx, y + dy), s, font=f, fill=INK)
    img.alpha_composite(o)
    ImageDraw.Draw(img).text((x, y), s, font=f, fill=fill)


def stripes(img, y):
    st = Image.new("RGBA", (W, 12))
    sd = ImageDraw.Draw(st)
    sd.rectangle((0, 0, W, 12), fill=(20, 20, 20, 255))
    for i in range(-20, W, 40):
        sd.polygon([(i, 12), (i + 20, 12), (i + 32, 0), (i + 12, 0)], fill=(255, 200, 40, 255))
    img.alpha_composite(st, (0, y))


def frame_overlay(path, hook, mode):
    """Logo, hook lines, hazard stripes around the video window, and the signup call to action."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    logo = Image.open(LOGO).convert("RGBA")
    lh = 150
    logo = logo.resize((int(logo.width * lh / logo.height), lh), Image.LANCZOS)
    img.alpha_composite(logo, ((W - logo.width) // 2, 28))
    top, height = WINDOW[mode]
    y = 196 if mode == "crop" else top - 230
    for i, line in enumerate(hook):
        text(img, y, line, "Jersey15-Regular.ttf", 78, WHITE if i == 0 else GREEN, None if i == 0 else (120, 255, 90, 200))
        y += 78
    stripes(img, top - 12)
    stripes(img, top + height)
    cta = 1538 if mode == "crop" else 1480
    text(img, cta, "BETA SIGNUPS OPEN", "Jersey15-Regular.ttf", 84, GREEN, (110, 255, 90, 220))
    text(img, cta + 92, "link in bio  ·  @playgreenline", "Barlow-SemiBold.ttf", 44, (230, 236, 246))
    img.save(path)


def caption_png(path, s, mode):
    """One burned-in caption: Jersey 15 on a dark rounded plate near the bottom of the window
    ("wide" posts put it just under the window so menus stay clear). A "DISPATCH:" prefix
    becomes a small green radio label above the line, like the in-game boss card."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    f = font("Jersey15-Regular.ttf", 62)
    d = ImageDraw.Draw(img)
    label = None
    if s.startswith("DISPATCH:"):
        label, s = "DISPATCH", s[len("DISPATCH:"):].strip()
    lines = [s]
    if d.textlength(s, font=f) > W - 160:  # two balanced lines
        words = s.split()
        splits = [(" ".join(words[:i]), " ".join(words[i:])) for i in range(1, len(words))]
        lines = list(min(splits, key=lambda p: max(d.textlength(p[0], font=f), d.textlength(p[1], font=f))))
    lh, label_h = 66, (44 if label else 0)
    top, height = WINDOW[mode]
    block = label_h + lh * len(lines)
    y0 = top + height - 60 - block if mode == "crop" else top + height + 26
    wmax = max([d.textlength(line, font=f) for line in lines] + [220 if label else 0])
    plate = Image.new("RGBA", (W, H))
    ImageDraw.Draw(plate).rounded_rectangle(((W - wmax) / 2 - 28, y0 - 14, (W + wmax) / 2 + 28, y0 + block + 14), radius=18, fill=(6, 10, 14, 190))
    img.alpha_composite(plate)
    if label:
        text(img, y0 - 2, "·  " + label + "  ·", "Barlow-SemiBold.ttf", 34, GREEN, outline=2)
    for i, line in enumerate(lines):
        text(img, y0 + label_h + i * lh, line, "Jersey15-Regular.ttf", 62, WHITE, max_w=W - 120, outline=3)
    img.save(path)


def pan_expr(pan, x0):
    """Crop x that eases from the middle (x0) to the left edge during each pan window."""
    if not pan:
        return str(x0)
    ramp = 0.35
    ks = [f"clip((t-({a}-{ramp}))/{ramp},0,1)*clip((({b}+{ramp})-t)/{ramp},0,1)" for a, b in pan]
    k = ks[0]
    for other in ks[1:]:
        k = f"max({k},{other})"
    return f"{x0}*(1-(({k})*({k})*(3-2*({k}))))"


def render(post, clip_dir, out_dir):
    mode = post.get("mode", "crop")
    top, height = WINDOW[mode]
    src = os.path.join(clip_dir, post["src"])
    out = os.path.join(out_dir, post["id"] + ".mp4")
    with tempfile.TemporaryDirectory() as tmp:
        ov = os.path.join(tmp, "overlay.png")
        frame_overlay(ov, post["hook"], mode)
        inputs = ["-i", ov]
        caps = post.get("captions", [])
        for i, (a, b, s) in enumerate(caps):
            p = os.path.join(tmp, f"cap{i}.png")
            caption_png(p, s, mode)
            inputs += ["-i", p]

        # 16:9 source scaled so the window height fits ("wide" shows the full width).
        if mode == "crop":
            sw = round(1920 * height / 1080 / 2) * 2
            fg = f"[b]scale={sw}:{height},crop={W}:{height}:x='{pan_expr(post.get('pan'), (sw - W) // 2)}':y=0[fg]"
        else:
            fg = f"[b]scale={W}:{height}[fg]"
        src_v, cut_a = "[0:v]", ""
        if post.get("cut"):
            a, b = post["cut"]
            src_v = f"[0:v]select='not(between(t,{a},{b}))',setpts=N/FRAME_RATE/TB[src];[src]"
            cut_a = f"aselect='not(between(t,{a},{b}))',asetpts=N/SR/TB,"
        dim = -0.22 if mode == "crop" else -0.5
        chain = [
            f"{src_v}split[a][b]",
            # "wide" blurs only the top of the frame, so bright menu buttons don't glow through
            f"[a]{'' if mode == 'crop' else 'crop=iw:ih*0.5:0:0,'}scale=-2:1920,crop=1080:1920,boxblur=28:2,eq=brightness={dim}:saturation=1.2[bg]",
            fg,
            f"[bg][fg]overlay=0:{top}[v0]",
            "[v0][1:v]overlay=0:0[v1]",
        ]
        last = "v1"
        for i, (a, b, s) in enumerate(caps):
            chain.append(f"[{last}][{i + 2}:v]overlay=0:0:enable='between(t,{a},{b})'[c{i}]")
            last = f"c{i}"
        chain.append(f"[{last}]fps=30,format=yuv420p[v]")

        trim = []
        if post.get("trim"):
            trim = ["-ss", str(post["trim"][0]), "-t", str(post["trim"][1])]
        cmd = ["ffmpeg", "-loglevel", "error", "-y", *trim, "-i", src, *inputs,
               "-filter_complex", ";".join(chain), "-map", "[v]", "-map", "0:a?",
               "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
               "-af", cut_a + "loudnorm=I=-16:TP=-1.5", "-movflags", "+faststart", out]
        subprocess.run(cmd, check=True)
    return out


def main():
    spec, clip_dir, out_dir, *only = sys.argv[1:]
    os.makedirs(out_dir, exist_ok=True)
    for post in json.load(open(spec)):
        if only and post["id"] not in only:
            continue
        print("made", render(post, clip_dir, out_dir), flush=True)


if __name__ == "__main__":
    main()
