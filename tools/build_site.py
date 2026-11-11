#!/usr/bin/env python3
"""Build GREENLINE's one-page website (static, no trackers, no outside requests).

Usage: python3 tools/build_site.py OUT_DIR

Pictures, the hero loop and the fonts are made once from the gameplay clips in
GREENLINE_CLIPS (default /mnt/project-files) and kept in OUT_DIR/a/. If they are
already there the clips are not needed, so the page text and the "New videos"
row (the three newest videos that have posted) can be rebuilt anywhere.

The page loads nothing from other sites: fonts, pictures and video all sit next
to it. Most players are kids, so there are no cookies, analytics or embeds.
"""

import html
import json
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from shorts import BOSSES, ROOT as CLIPS, Clip  # noqa: E402

FORM = "https://docs.google.com/forms/d/e/1FAIpQLSd51AuoKTMDFyrlNFWwah8pnWpVvALnqrFCke5LK_ycoza8qA/viewform"
SOCIAL = [("TikTok", "https://www.tiktok.com/@playgreenline"),
          ("Instagram", "https://www.instagram.com/playgreenline2026/"),
          ("YouTube", "https://www.youtube.com/@playgreenline")]
FONT_CACHE = os.path.expanduser("~/.cache/greenline-fonts")
FONTS = [("Bungee", "Bungee-Regular.ttf", "400"), ("Rubik", "Rubik.ttf", "300 900"), ("Barlow", "Barlow-SemiBold.ttf", "600")]
V4 = "greenline_v4_16x9_{}.mp4"

# name, clip, second, what the picture shows (alt text)
SHOTS = [
    ("squad", "coop_chaos", 1.1, "Four players stand side by side in a train yard at dusk, facing one small zombie"),
    ("boss", "coop_chaos", 7.8, "Three players run toward the camera with the Foreman, a zombie in a yellow hard hat, chasing them"),
    ("blast", "ability_demolitionist", 5.85, "A player's blast throws a group of zombies into the air in a burst of green Glo"),
    ("ring", "last_save", 1.8, "A Medic stands in the middle of a tight ring of zombies"),
    ("lurker", "lurker", 3.75, "The Lurker, a zombie in a camouflage hat, pops up right in front of the camera in a green sewer"),
    ("rescue", "secret", 5.0, "A player opens a blue shipping container and a hidden survivor steps out"),
]
DO = [  # picture, heading, sentence
    ("squad", "Squad up", "Up to four players in one run. Jump in with friends and hold the yard together."),
    ("boss", "Take down the bosses", "Ten Greenline sites, ten bosses, from the train yard to the tower. Every one of them used to work there."),
    ("blast", "Pick a class", "Blow up the horde as the Demolitionist, pull your squad out of trouble as the Medic, or trick zombies as the Jester."),
]
PARENTS = [
    "Made for players about 9 to 15. It is spooky, not gory: zombies burst into green Glo, and the blood setting is off unless a player turns it on.",
    "There is no open chat. Players can't type messages to each other, names are filtered, and any name can be reported.",
    "The shop has no loot boxes. Players always see what they get before they get it.",
    "Players 12 and under join the beta through a parent's email. We never ask a child for contact details.",
    "This page uses no cookies, no trackers and nothing loaded from other sites.",
]
FACTS = [("Game", "GREENLINE"), ("Studio", "Tufufal Studios, a small student-run studio"), ("Kind of game", "Co-op cube zombie shooter"),
         ("Players", "1 to 4, online co-op"), ("Phones", "iPhone and Android"), ("Stage", "In development. Beta signups are open"),
         ("Release date", "Not announced yet"), ("Contact", "Message @playgreenline2026 on Instagram")]


def run(*cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def make_assets(a):
    """Everything in a/ that comes from the gameplay clips, the logo and the fonts. Skips what is already there."""
    os.makedirs(a, exist_ok=True)
    src = lambda name: os.path.join(CLIPS, name)  # noqa: E731
    hero = os.path.join(a, "hero.mp4")
    if not os.path.exists(hero):
        run("ffmpeg", "-loglevel", "error", "-y", "-ss", "4.5", "-t", "5.4", "-i", src(V4.format("coop_chaos")), "-an",
            "-vf", "scale=1280:720:flags=lanczos,fps=30", "-c:v", "libx264", "-preset", "slow", "-crf", "27",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", hero)
        run("ffmpeg", "-loglevel", "error", "-y", "-ss", "7.8", "-i", src(V4.format("coop_chaos")), "-frames:v", "1",
            "-vf", "scale=1280:720:flags=lanczos", "-q:v", "4", os.path.join(a, "hero.jpg"))
    for name, clip, t, _ in SHOTS:
        for w, tag in ((960, ""), (1920, "-full")):
            out = os.path.join(a, f"shot-{name}{tag}.jpg")
            if not os.path.exists(out):
                run("ffmpeg", "-loglevel", "error", "-y", "-ss", str(t), "-i", src(V4.format(clip)), "-frames:v", "1",
                    "-vf", f"scale={w}:-2:flags=lanczos", "-q:v", "3" if tag else "4", out)
    # boss badge photos, all brought to the same brightness
    if not all(os.path.exists(os.path.join(a, f"boss-{k}.jpg")) for k in BOSSES):
        pics = {}
        for k, b in BOSSES.items():
            im = Clip(b["src"], b["card"] + 0.1, b["card"] + 0.4, (b["cx"] - 420, 120, 840, 840), (420, 420)).at(0)
            pics[k] = np.asarray(im.convert("RGB"), np.float32)
        target = float(np.mean([p.mean() for p in pics.values()])) * 1.3
        for k, p in pics.items():
            g = min(1.8, max(0.9, target / p.mean()))
            Image.fromarray(np.clip(p * g, 0, 255).astype(np.uint8)).save(os.path.join(a, f"boss-{k}.jpg"), quality=86)
    logo = os.path.join(a, "logo.png")
    if not os.path.exists(logo):
        im = Image.open(os.path.join(CLIPS, "logo", "greenline-logo-transparent.png")).convert("RGBA")
        im = im.crop(im.getbbox())
        im.save(os.path.join(a, "greenline-logo.png"))  # full size, for the press kit
        im.resize((900, round(900 * im.height / im.width)), Image.LANCZOS).save(logo)
        icon = Image.open(os.path.join(CLIPS, "logo", "greenline-app-icon-1024.png")).convert("RGB")
        icon.save(os.path.join(a, "greenline-icon.png"))
        icon.resize((180, 180), Image.LANCZOS).save(os.path.join(a, "icon-180.png"))
    for family, ttf, _ in FONTS:
        out = os.path.join(a, ttf.replace(".ttf", ".woff2"))
        if not os.path.exists(out):
            from fontTools.ttLib import TTFont
            f = TTFont(os.path.join(FONT_CACHE, ttf))
            f.flavor = "woff2"
            f.save(out)


def newest_videos(a, count=3):
    """The newest videos that have really posted, shrunk for the page. Returns [(file, poster, title)]."""
    posted = json.load(open(os.path.join(REPO, "schedule", "buffer-posted.json")))
    schedule = {e["video"]: e for e in json.load(open(os.path.join(REPO, "schedule", "buffer.json")))}
    seen, out = set(), []
    for r in sorted((r for r in posted if r.get("status") == "sent"), key=lambda r: r["posted_on"], reverse=True):
        v = r["video"]
        if v in seen or not os.path.exists(os.path.join(REPO, v)) or v.startswith("videos/youtube/"):
            continue
        seen.add(v)
        base = os.path.splitext(os.path.basename(v))[0]
        mp4, jpg = os.path.join(a, f"v-{base}.mp4"), os.path.join(a, f"v-{base}.jpg")
        if not os.path.exists(mp4):
            run("ffmpeg", "-loglevel", "error", "-y", "-i", os.path.join(REPO, v), "-vf", "scale=540:960:flags=lanczos",
                "-c:v", "libx264", "-preset", "slow", "-crf", "28", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
                "-movflags", "+faststart", mp4)
            run("ffmpeg", "-loglevel", "error", "-y", "-ss", "1.5", "-i", os.path.join(REPO, v), "-frames:v", "1",
                "-vf", "scale=540:960:flags=lanczos", "-q:v", "5", jpg)
        entry = schedule.get(v, {})
        title = (entry.get("youtube") or {}).get("title") or base
        title = "".join(ch for ch in title.split("#")[0] if ord(ch) < 0x2190).strip()  # no emoji in captions
        out.append((os.path.basename(mp4), os.path.basename(jpg), title))
        if len(out) == count:
            break
    keep = {n for v in out for n in v[:2]}
    for f in os.listdir(a):  # drop videos that fell off the row
        if f.startswith("v-") and f not in keep:
            os.remove(os.path.join(a, f))
    return out


CSS = """
@font-face{font-family:Bungee;src:url(a/Bungee-Regular.woff2) format("woff2");font-display:swap}
@font-face{font-family:Rubik;src:url(a/Rubik.woff2) format("woff2");font-weight:300 900;font-display:swap}
@font-face{font-family:Barlow;src:url(a/Barlow-SemiBold.woff2) format("woff2");font-weight:600;font-display:swap}
:root{--dusk:#141a4a;--indigo:#1f2670;--asphalt:#333ca0;--glo:#a6ff3c;--amber:#ffb84a;--paper:#f4f8ff;--ink:#080a14;
  --step:6px;--wrap:1120px}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--dusk);color:var(--paper);font:400 1.125rem/1.55 Rubik,system-ui,sans-serif;-webkit-font-smoothing:antialiased}
img,video{display:block;max-width:100%;height:auto}
a{color:var(--glo)}
a:focus-visible,button:focus-visible,video:focus-visible{outline:3px solid var(--amber);outline-offset:3px}
h1,h2,h3{font-family:Bungee,Impact,sans-serif;font-weight:400;line-height:1.08;margin:0;letter-spacing:.01em}
h2{font-size:clamp(1.7rem,4.2vw,2.75rem);margin-bottom:.5em}
h3{font-size:1.2rem;margin:1rem 0 .35rem}
p{margin:0 0 1em;max-width:62ch}
.wrap{width:min(var(--wrap),100% - 2.5rem);margin-inline:auto}
section{padding:clamp(3rem,8vw,5.5rem) 0}
/* stepped pixel corners, the way the game's cubes are cut */
.px{clip-path:polygon(0 var(--step),var(--step) var(--step),var(--step) 0,calc(100% - var(--step)) 0,calc(100% - var(--step)) var(--step),100% var(--step),100% calc(100% - var(--step)),calc(100% - var(--step)) calc(100% - var(--step)),calc(100% - var(--step)) 100%,var(--step) 100%,var(--step) calc(100% - var(--step)),0 calc(100% - var(--step)))}
.lift{filter:drop-shadow(6px 6px 0 var(--ink))}

.hero{position:relative;min-height:min(92vh,860px);display:flex;align-items:flex-end;padding:0;overflow:hidden;background:var(--ink)}
.hero video,.hero .still{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:50% 40%}
.hero::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(20,26,74,.05) 30%,rgba(20,26,74,.72) 68%,var(--dusk) 100%)}
.hero .wrap{position:relative;z-index:1;padding:0 0 clamp(2rem,6vw,4rem)}
.hero h1 img{width:min(560px,82vw);height:auto;filter:drop-shadow(0 6px 0 var(--ink))}
.hero p.lead{font-size:clamp(1.15rem,2.4vw,1.5rem);font-weight:500;max-width:34ch;margin:.9rem 0 1.4rem;text-shadow:0 2px 0 var(--ink)}
.go{display:inline-block}
.go a{display:block;background:var(--glo);color:var(--ink);font:400 clamp(1.05rem,2.6vw,1.35rem)/1 Bungee,sans-serif;text-decoration:none;padding:1.05em 1.5em}
.go a:hover{background:#c6ff7a}
.small{font-size:.95rem;max-width:46ch;margin:1.1rem 0 0;color:#dfe6ff}
.pause{position:absolute;z-index:2;right:1rem;top:1rem;background:rgba(8,10,20,.72);color:var(--paper);border:2px solid var(--paper);font:600 .95rem Barlow,sans-serif;padding:.35em .8em;cursor:pointer}
.tape{height:18px;background:repeating-linear-gradient(-45deg,var(--amber) 0 22px,var(--ink) 22px 44px)}

.do{display:grid;grid-template-columns:repeat(3,1fr);gap:clamp(1.25rem,3vw,2.25rem)}
.do img{border:3px solid var(--ink);width:100%;aspect-ratio:16/9;object-fit:cover}
.do p{font-size:1.05rem;margin:0}

.staff{background:var(--indigo)}
.badges{display:grid;grid-template-columns:repeat(4,1fr);gap:1.75rem 1.5rem;margin-top:2rem;list-style:none;padding:0}
.badge{background:var(--paper);color:var(--ink);padding:0 0 .9rem;--step:8px}
.badges li:nth-child(4n+1){rotate:-1.6deg}.badges li:nth-child(4n+2){rotate:1.2deg}.badges li:nth-child(4n+3){rotate:-.7deg}.badges li:nth-child(4n){rotate:1.8deg}
.badge .strip{background:var(--glo);font:600 .95rem/1 Barlow,sans-serif;padding:.7rem .9rem .55rem;display:flex;justify-content:space-between;align-items:center}
.badge .strip i{display:block;width:44px;height:9px;background:var(--ink);border-radius:5px}
.badge img{width:100%;aspect-ratio:1;object-fit:cover}
.badge b{display:block;font:400 1.02rem/1.1 Bungee,sans-serif;padding:.75rem .9rem .15rem}
.badge span{display:block;font:600 1rem/1.2 Barlow,sans-serif;padding:0 .9rem;color:#3a3f5c}

.clips{display:grid;grid-template-columns:repeat(3,minmax(0,300px));gap:clamp(1rem,3vw,2rem);margin-top:1.75rem}
.clips figure{margin:0}
.clips video{width:100%;aspect-ratio:9/16;background:var(--ink);border:8px solid var(--ink);border-radius:26px}
.clips figcaption{font:600 1.05rem/1.25 Barlow,sans-serif;margin-top:.6rem}

.two{display:grid;grid-template-columns:1fr 1fr;gap:clamp(2rem,6vw,5rem)}
.plain{background:var(--indigo)}
.points{padding-left:1.15rem;margin:0}
.points li{margin-bottom:.7em;max-width:56ch}
.points li::marker{color:var(--glo)}
dl{display:grid;grid-template-columns:max-content 1fr;gap:.45rem 1.25rem;margin:0 0 1.5rem;font-size:1.02rem}
dt{font:600 1.02rem/1.5 Barlow,sans-serif;color:var(--amber)}
dd{margin:0}
.files{display:flex;flex-wrap:wrap;gap:.6rem;list-style:none;padding:0;margin:0}
.files a{display:block;border:2px solid var(--glo);padding:.4em .8em;text-decoration:none;font:600 1rem Barlow,sans-serif}
.files a:hover{background:var(--glo);color:var(--ink)}

.end{text-align:left;padding:clamp(3rem,8vw,5rem) 0}
.end h2{max-width:16ch}
footer{background:var(--ink);padding:1.75rem 0 2.25rem;font-size:.98rem}
footer .wrap{display:flex;flex-wrap:wrap;gap:.5rem 1.75rem;align-items:baseline}
footer p{margin:0}
@media (max-width:860px){
  .do{grid-template-columns:1fr}.two{grid-template-columns:1fr}
  .badges{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;gap:1.1rem;padding:.75rem 1.25rem 1.5rem;margin-inline:-1.25rem}
  .badges li{flex:0 0 62vw;max-width:260px;scroll-snap-align:center}
  .clips{grid-template-columns:repeat(3,62vw);overflow-x:auto;padding-bottom:1rem;margin-inline:-1.25rem;padding-inline:1.25rem}
  .hero{min-height:88vh}
}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}.hero video{display:none}}
"""

JS = """
(function(){var v=document.querySelector('.hero video'),b=document.querySelector('.pause');if(!v||!b)return;
if(matchMedia('(prefers-reduced-motion: reduce)').matches){b.hidden=true;return}
b.addEventListener('click',function(){if(v.paused){v.play();b.textContent='Pause video'}else{v.pause();b.textContent='Play video'}});
document.querySelectorAll('.clips video').forEach(function(c){c.addEventListener('play',function(){
document.querySelectorAll('.clips video').forEach(function(o){if(o!==c)o.pause()})})})})();
"""


def page(videos):
    e = html.escape
    do = "".join(f'<div><img class="lift" src="a/shot-{p}.jpg" width="960" height="540" loading="lazy" alt="{e(alt)}"><h3>{e(h)}</h3><p>{e(t)}</p></div>'
                 for p, h, t in DO for n, _, _, alt in SHOTS if n == p)
    badges = "".join(f'<li class="lift"><div class="badge px"><div class="strip"><span style="padding:0;color:inherit">Greenline staff</span><i></i></div>'
                     f'<img src="a/boss-{k}.jpg" width="420" height="420" loading="lazy" alt="{e(b["name"].title())}, a cube zombie boss">'
                     f'<b>{e(b["name"])}</b><span>{e(b["job"])}</span></div></li>' for k, b in BOSSES.items())
    clips = "".join(f'<figure><video controls playsinline preload="none" poster="a/{j}" src="a/{m}"></video><figcaption>{e(t)}</figcaption></figure>'
                    for m, j, t in videos)
    parents = "".join(f"<li>{e(t)}</li>" for t in PARENTS)
    facts = "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in FACTS)
    files = [("Logo (PNG)", "a/greenline-logo.png"), ("App icon (PNG)", "a/greenline-icon.png")]
    files += [(f"Screenshot {i + 1} (JPG)", f"a/shot-{n}-full.jpg") for i, (n, *_) in enumerate(SHOTS)]
    files += [(f"Clip {i + 1} (MP4)", f"a/{m}") for i, (m, _, _) in enumerate(videos)]
    files = "".join(f'<li><a href="{h}" download>{e(t)}</a></li>' for t, h in files)
    social = ", ".join(f'<a href="{h}" rel="noopener">{e(n)}</a>' for n, h in SOCIAL[:-1]) + f' and <a href="{SOCIAL[-1][1]}" rel="noopener">{SOCIAL[-1][0]}</a>'
    desc = "GREENLINE is a co-op cube zombie shooter for iPhone and Android. Up to four players, ten bosses, beta signups open."
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GREENLINE, a co-op cube zombie shooter for phones</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="GREENLINE, a co-op cube zombie shooter for phones">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="website">
<meta property="og:image" content="a/hero.jpg">
<meta name="theme-color" content="#141a4a">
<link rel="icon" href="a/icon-180.png">
<link rel="apple-touch-icon" href="a/icon-180.png">
<link rel="preload" href="a/Bungee-Regular.woff2" as="font" type="font/woff2" crossorigin>
<style>{CSS}</style>
</head>
<body>
<header class="hero">
  <img class="still" src="a/hero.jpg" alt="" width="1280" height="720">
  <video autoplay muted loop playsinline poster="a/hero.jpg" aria-hidden="true" tabindex="-1"><source src="a/hero.mp4" type="video/mp4"></video>
  <button class="pause" type="button">Pause video</button>
  <div class="wrap">
    <h1><img src="a/logo.png" alt="GREENLINE" width="900" height="506"></h1>
    <p class="lead">A co-op cube zombie shooter for iPhone and Android. Grab up to three friends and clean up the Greenline leak.</p>
    <div class="go lift"><a class="px" href="{FORM}" rel="noopener">Sign up for the beta</a></div>
    <p class="small">Beta testers get a free Legendary skin. If you are 12 or younger, a parent signs you up.</p>
  </div>
</header>
<div class="tape" role="presentation"></div>
<main>
<section>
  <div class="wrap">
    <h2>What you do in Greenline</h2>
    <p>Something leaked at the Greenline fuel company, and now the whole town glows. You and your squad go site by site and take it back.</p>
    <div class="do" style="margin-top:2rem">{do}</div>
  </div>
</section>
<section class="staff">
  <div class="wrap">
    <h2>Meet the staff</h2>
    <p>Every boss used to work at Greenline. Here are eight of their old ID badges.</p>
    <ul class="badges">{badges}</ul>
  </div>
</section>
<section>
  <div class="wrap">
    <h2>New videos</h2>
    <p>A new one goes up every day on {social}.</p>
    <div class="clips">{clips}</div>
  </div>
</section>
<section class="plain">
  <div class="wrap two">
    <div>
      <h2>For parents</h2>
      <ul class="points">{parents}</ul>
    </div>
    <div>
      <h2>Press kit</h2>
      <dl>{facts}</dl>
      <ul class="files">{files}</ul>
    </div>
  </div>
</section>
<section class="end">
  <div class="wrap">
    <h2>Be one of the first to play</h2>
    <p>Sign up now. Every beta tester gets the Legendary beta skin, and it will never be sold in the shop.</p>
    <div class="go lift"><a class="px" href="{FORM}" rel="noopener">Sign up for the beta</a></div>
  </div>
</section>
</main>
<div class="tape" role="presentation"></div>
<footer>
  <div class="wrap">
    <p>GREENLINE is made by Tufufal Studios.</p>
    <p>{social}</p>
    <p>No cookies. No trackers.</p>
  </div>
</footer>
<script>{JS}</script>
</body>
</html>
"""


def main():
    out = sys.argv[1]
    a = os.path.join(out, "a")
    make_assets(a)
    videos = newest_videos(a)
    with open(os.path.join(out, "index.html"), "w") as f:
        f.write(page(videos))
    open(os.path.join(out, ".nojekyll"), "w").close()  # GitHub Pages: serve the files as they are
    size = sum(os.path.getsize(os.path.join(a, f)) for f in os.listdir(a))
    print(f"built {out}: {len(os.listdir(a))} files in a/, {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
