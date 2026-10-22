"""Mix voice + synthesized music bed + SFX, master to -14 LUFS.

Reads <project>/build/voice.wav, build/timing.json and optional <project>/sfx.json:
  [{"at": "lineId" | seconds, "offset": 0.0, "type": "pop|whoosh|tick|thump|ding"}]
Writes <project>/build/mix.wav (48 kHz stereo).
Optional --deess: light de-esser on the voice only (band above 5 kHz, threshold -18 dBFS, 2:1, max -6 dB),
for hot /s/ sibilants that push AAC true peak up (QA note 21 Oct). build/voice.wav itself is not changed.
All sound is generated in code: free to use commercially, no licensing.
"""
import json, subprocess, sys
from pathlib import Path
import numpy as np
import soundfile as sf

SR = 48000
rng = np.random.default_rng(7)


def env(n, a=0.005, r=0.1):
    t = np.arange(n) / SR
    return np.minimum(1, t / a) * np.exp(-t / r)


def sfx(kind):
    n = int(SR * {"pop": .18, "whoosh": .45, "tick": .05, "thump": .5, "ding": .9}[kind])
    t = np.arange(n) / SR
    if kind == "pop":
        return np.sin(2 * np.pi * (500 + 1400 * t) * t) * env(n, .002, .05) * .5
    if kind == "tick":
        return np.sin(2 * np.pi * 2200 * t) * env(n, .001, .012) * .35
    if kind == "thump":
        return np.sin(2 * np.pi * (110 - 70 * t) * t) * env(n, .003, .15) * .9
    if kind == "ding":
        return (np.sin(2 * np.pi * 1318 * t) + .5 * np.sin(2 * np.pi * 1976 * t)) * env(n, .002, .25) * .3
    w = rng.standard_normal(n)  # whoosh: band-swept noise
    w = np.convolve(w, np.ones(24) / 24, "same")
    return w * np.sin(np.pi * t / t[-1]) ** 2 * .35


def bed(dur, bpm=100):
    """Soft, unobtrusive pulse: muted pluck chords on a 4-chord loop + light hats."""
    n = int(dur * SR)
    out = np.zeros(n)
    beat = 60 / bpm
    chords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]  # Am F C G
    b = 0
    while b * beat < dur:
        ch = chords[(b // 4) % 4]
        s = int(b * beat * SR)
        m = int(beat * SR)
        t = np.arange(m) / SR
        tone = sum(np.sin(2 * np.pi * 440 * 2 ** ((k - 69) / 12) * t) for k in ch) / 3
        seg = tone * np.exp(-t / .35) * .12
        if b % 2 == 1:  # off-beat hat
            seg[:int(.03 * SR)] += rng.standard_normal(int(.03 * SR)) * np.exp(-np.arange(int(.03 * SR)) / 300) * .04
        e = min(n, s + m)
        out[s:e] += seg[:e - s]
        b += 1
    fade = int(1.0 * SR)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out


def deess(v, sr=SR, f0=5000, thr=-18.0, ratio=2.0, max_cut=6.0):
    """Split at f0 with a zero-phase filter (low + high == input exactly), turn down only the high band
    where its 5 ms rms is above thr (attack 2 ms, release 40 ms)."""
    from scipy.signal import butter, sosfiltfilt
    hi = sosfiltfilt(butter(4, f0, "highpass", fs=sr, output="sos"), v)
    lo = v - hi
    w = int(0.005 * sr)
    n = int(np.ceil(len(v) / w))
    pad = np.pad(hi, (0, n * w - len(v)))
    lev = 20 * np.log10(np.sqrt(np.mean(pad.reshape(n, w) ** 2, 1)) + 1e-9)
    cut = np.clip((lev - thr) * (1 - 1 / ratio), 0, max_cut)
    g = 10 ** (-np.repeat(cut, w)[:len(v)] / 20)
    a, r = np.exp(-1 / (0.002 * sr)), np.exp(-1 / (0.040 * sr))
    sm = np.empty_like(g); y = 1.0
    for i in range(0, len(g), 32):  # block-wise smoothing is enough at 32 samples
        x = g[i]
        y = a * y + (1 - a) * x if x < y else r * y + (1 - r) * x
        sm[i:i + 32] = y
    print(f"de-ess: {np.mean(cut > 0) * 100:.1f}% of 5 ms frames reduced, max {cut.max():.1f} dB")
    return lo + hi * sm


def main(project, de_ess=False):
    project = Path(project)
    b = project / "build"
    timing = json.loads((b / "timing.json").read_text())
    v, vsr = sf.read(b / "voice.wav")
    if vsr != SR:
        idx = np.arange(int(len(v) * SR / vsr)) * vsr / SR
        v = np.interp(idx, np.arange(len(v)), v)
    if de_ess:
        v = deess(v)
    dur = len(v) / SR
    b0 = bed(dur)
    b0 = np.pad(b0, (0, max(0, len(v) - len(b0))))[:len(v)]
    mix = v * 1.0 + b0
    starts = {l["id"]: l["start"] for l in timing["lines"]}
    cues = json.loads((project / "sfx.json").read_text()) if (project / "sfx.json").exists() else []
    for c in cues:
        at = starts[c["at"]] if isinstance(c["at"], str) else c["at"]
        s = int((at + c.get("offset", 0)) * SR)
        x = sfx(c["type"])
        e = min(len(mix), s + len(x))
        if s < len(mix):
            mix[s:e] += x[:e - s]
    stereo = np.stack([mix, mix], 1).astype(np.float32)
    raw = b / "mix.raw.wav"
    sf.write(raw, stereo, SR)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af",
                    "loudnorm=I=-14:TP=-2.0:LRA=11", "-ar", str(SR), str(b / "mix.wav")], check=True)
    raw.unlink()
    print("mix ->", b / "mix.wav")


if __name__ == "__main__":
    main(sys.argv[1], "--deess" in sys.argv[2:])
