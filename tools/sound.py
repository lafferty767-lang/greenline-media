"""Original chiptune beats and sound effects for GREENLINE shorts, made from scratch with numpy.

Nothing here is sampled or copied, so the audio is free to post anywhere.

    beat(seconds, bpm=120, drop=None, style="disco")  -> stereo float32 array at SR
    sfx(name)                                         -> stereo float32 array
    mix(length_s, [(start_s, sound, gain), ...])      -> stereo float32 array

styles:
  "disco"  four-on-the-floor kick, offbeat hats, octave bass, arpeggio lead (spooky A minor)
  "quiz"   ticking hats and a bass pedal until `drop` seconds, then the full disco groove
  "hype"   like disco with a busier kick and a brighter lead
"""

import numpy as np

SR = 44100
rng = np.random.default_rng(7)

# A harmonic minor feel: Am | F | Dm | E  (the E major chord gives the spooky lift)
CHORDS = [(57, [0, 3, 7]), (53, [0, 4, 7]), (50, [0, 3, 7]), (52, [0, 4, 7])]


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def env(n, attack=0.002, decay=0.15, sustain=0.0, release=0.02):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(attack, 1e-4)) * (sustain + (1 - sustain) * np.exp(-t / max(decay, 1e-4)))
    r = int(release * SR)
    if r and n > r:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def pulse(f, n, duty=0.5, max_h=40):
    """Band-limited pulse wave (sum of harmonics), so high notes don't alias."""
    t = np.arange(n) / SR
    out = np.zeros(n)
    k = 1
    while k <= max_h and k * f < SR / 2.2:
        out += (np.sin(np.pi * k * duty) / k) * np.cos(2 * np.pi * k * f * t - np.pi * k * duty)
        k += 1
    return out * 1.2


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def highpass(x, cutoff):
    return x - lowpass(x, cutoff)


def kick(n=None):
    n = n or int(0.32 * SR)
    t = np.arange(n) / SR
    f = 48 + 110 * np.exp(-t / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.16)
    click = rng.standard_normal(n) * np.exp(-t / 0.004) * 0.25
    return np.tanh(1.6 * (body + click))


def clap(n=None):
    n = n or int(0.2 * SR)
    t = np.arange(n) / SR
    noise = highpass(rng.standard_normal(n), 900)
    e = np.exp(-t / 0.06)
    for d in (0.0, 0.011, 0.022):  # three quick hand hits
        e += 0.6 * np.exp(-np.maximum(t - d, 0) / 0.008) * (t >= d)
    return noise * e * 0.45


def hat(n=None, open_=False):
    n = n or int((0.16 if open_ else 0.05) * SR)
    t = np.arange(n) / SR
    noise = highpass(highpass(rng.standard_normal(n), 6000), 6000)
    return noise * np.exp(-t / (0.06 if open_ else 0.012)) * 0.35


def place(buf, sound, at):
    i = int(at * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sound))
    buf[i:j] += sound[: j - i]


def beat(seconds, bpm=120, drop=None, style="disco"):
    n = int(seconds * SR) + SR
    drums, bass, lead = np.zeros(n), np.zeros(n), np.zeros(n)
    b = 60 / bpm
    steps = int(seconds / (b / 4)) + 4
    sixteenth = b / 4
    for s in range(steps):
        at = s * sixteenth
        bar = int(at // (4 * b))
        root, tones = CHORDS[bar % 4]
        full = drop is None or at >= drop - 1e-6
        beat_i, sub = divmod(s, 4)
        if style == "quiz" and not full:
            # tension: soft kick every beat, ticking 16th hats, pulsing bass pedal on A
            if sub == 0:
                place(drums, kick() * 0.55, at)
            place(drums, hat() * (0.9 if sub == 0 else 0.5), at)
            if sub in (0, 2):
                nb = int(sixteenth * 1.8 * SR)
                place(bass, pulse(hz(45), nb, 0.5) * env(nb, decay=0.09) * 0.5, at)
            continue
        if sub == 0:
            place(drums, kick(), at)
        if style == "hype" and sub == 3 and beat_i % 4 == 3:
            place(drums, kick() * 0.7, at)
        if sub == 0 and beat_i % 2 == 1:
            place(drums, clap(), at)
        if sub == 2:
            place(drums, hat(open_=True) * 0.8, at)
        elif sub in (1, 3):
            place(drums, hat() * 0.5, at)
        # disco octave bass on 8ths
        if sub in (0, 2):
            nb = int(sixteenth * 1.7 * SR)
            note = root - 12 + (12 if sub == 2 else 0)
            place(bass, pulse(hz(note), nb, 0.5) * env(nb, decay=0.12, sustain=0.3), at)
        # arpeggio lead on 16ths
        nl = int(sixteenth * 0.95 * SR)
        arp = [0, 1, 2, 1] if style == "disco" else [0, 1, 2, 3]
        idx = arp[sub]
        note = root + 12 + (tones + [12])[idx]
        lead_note = pulse(hz(note), nl, 0.25) * env(nl, decay=0.07)
        place(lead, lead_note * (0.32 if style == "disco" else 0.4), at)
    bass = lowpass(bass, 900) * 0.55
    lead = lowpass(lead, 5200)
    # sidechain pump: duck bass and lead right after each kick
    t = np.arange(n) / SR
    phase = (t % b) / b
    pump = 1 - 0.45 * np.exp(-phase * 9)
    if drop is not None and style == "quiz":
        pump = np.where(t >= drop, pump, 1.0)
    music = drums * 0.9 + (bass + lead) * pump
    # a little stereo width: lead slightly delayed on the right
    d = int(0.012 * SR)
    left = music
    right = drums * 0.9 + (bass + np.concatenate([np.zeros(d), lead[:-d]])) * pump
    out = np.stack([left, right], 1)[: int(seconds * SR)]
    return np.tanh(out * 0.9).astype(np.float32) * 0.8


def sfx(name):
    if name == "tick":
        n = int(0.05 * SR)
        s = np.sin(2 * np.pi * 1900 * np.arange(n) / SR) * env(n, decay=0.012)
    elif name == "pop":
        n = int(0.12 * SR)
        t = np.arange(n) / SR
        s = np.sin(2 * np.pi * np.cumsum(500 + 1400 * t / t[-1]) / SR) * env(n, decay=0.05) * 0.7
    elif name == "whoosh":
        n = int(0.45 * SR)
        t = np.arange(n) / SR
        noise = rng.standard_normal(n)
        cut = 300 + 5000 * np.sin(np.pi * t / t[-1]) ** 2
        y, acc = np.empty(n), 0.0
        for i in range(n):
            a = np.exp(-2 * np.pi * cut[i] / SR)
            acc = (1 - a) * noise[i] + a * acc
            y[i] = acc
        s = y * np.sin(np.pi * t / t[-1]) ** 1.5 * 1.6
    elif name == "impact":
        n = int(0.9 * SR)
        t = np.arange(n) / SR
        boom = np.sin(2 * np.pi * np.cumsum(38 + 90 * np.exp(-t / 0.06)) / SR) * np.exp(-t / 0.35)
        crack = lowpass(rng.standard_normal(n), 2500) * np.exp(-t / 0.05) * 1.5
        s = np.tanh(2.2 * (boom + crack)) * 0.9
    elif name == "reveal":  # bright bell chord
        n = int(1.4 * SR)
        t = np.arange(n) / SR
        s = np.zeros(n)
        for m, g in ((81, 1.0), (85, 0.7), (88, 0.6), (93, 0.35)):
            for k, kg in ((1, 1), (2.76, 0.3), (5.4, 0.12)):
                s += g * kg * np.sin(2 * np.pi * hz(m) * k * t) * np.exp(-t * (1.5 + k))
        s *= 0.22
    elif name == "thunk":
        n = int(0.25 * SR)
        t = np.arange(n) / SR
        s = np.sin(2 * np.pi * np.cumsum(80 + 160 * np.exp(-t / 0.02)) / SR) * np.exp(-t / 0.07)
        s += lowpass(rng.standard_normal(n), 1800) * np.exp(-t / 0.015) * 0.5
        s = np.tanh(1.5 * s) * 0.8
    elif name == "riser":
        n = int(1.0 * SR)
        t = np.arange(n) / SR
        f = 200 * 2 ** (3 * t / t[-1])
        s = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.25 * (t / t[-1]) ** 2
        s += highpass(rng.standard_normal(n), 2000) * 0.25 * (t / t[-1]) ** 3
    else:
        raise ValueError(name)
    s = s / (np.abs(s).max() + 1e-9) * 0.8
    return np.stack([s, s], 1).astype(np.float32)


def mix(length_s, parts):
    out = np.zeros((int(length_s * SR), 2), np.float32)
    for at, sound, gain in parts:
        i = int(at * SR)
        if i >= len(out):
            continue
        j = min(len(out), i + len(sound))
        out[i:j] += sound[: j - i] * gain
    return out


def write_wav(path, x):
    import wave
    x = np.clip(x, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())
