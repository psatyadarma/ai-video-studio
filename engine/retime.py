"""Shorten an existing voice take without a new TTS request (no ElevenLabs credits).

Usage: python3 -I engine/retime.py <project> [--cut l4,l9] [--speed 1.18]

- --cut: drop whole lines from build/voice.wav + build/timing.json (and remove them from script.json).
- --speed: time-stretch the voice (ffmpeg atempo, pitch kept). The tagline line ("rd") is kept at 1.0x
  so the signature recording always sounds identical.
- Rewrites build/voice.wav, build/timing.json, build/timing.js. Keeps a backup in build/orig/ on first run.
Use when a voice runs long (e.g. Cahaya reads ~130 wpm vs the 150–170 target).
"""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf


def stretch(x, sr, f):
    if abs(f - 1) < 1e-6 or len(x) == 0:
        return x
    with tempfile.TemporaryDirectory() as d:
        a, b = Path(d) / "a.wav", Path(d) / "b.wav"
        sf.write(a, x, sr)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(a), "-filter:a", f"atempo={f}", str(b)], check=True)
        y, _ = sf.read(b, dtype="float32")
    return y


def main(project, cut, speed):
    p = Path(project); b = p / "build"
    orig = b / "orig"
    if not orig.exists():
        orig.mkdir()
        for n in ("voice.wav", "timing.json", "timing.js"):
            shutil.copy(b / n, orig / n)
    x, sr = sf.read(b / "voice.wav", dtype="float32")
    T = json.loads((b / "timing.json").read_text())
    L = T["lines"]

    # 1) cuts: remove [X.start-0.05, next.start-0.05]
    for cid in cut:
        i = next(k for k, l in enumerate(L) if l["id"] == cid)
        s = L[i]["start"] - 0.05
        e = (L[i + 1]["start"] - 0.05) if i + 1 < len(L) else T["duration"] - 0.9
        x = np.concatenate([x[: int(s * sr)], x[int(e * sr):]])
        d = e - s
        del L[i]
        for l in L[i:]:
            l["start"] -= d; l["end"] -= d
            for w in l["words"]:
                w["start"] -= d; w["end"] -= d
        T["duration"] -= d

    # 2) speed, piecewise: tagline kept at 1.0
    if abs(speed - 1) > 1e-6:
        rd = next((l for l in L if l["id"] == "rd"), None)
        bounds = [0.0]
        if rd:
            bounds += [rd["start"] - 0.02, rd["end"] + 0.02]
        bounds.append(len(x) / sr)
        pieces, maps, t_new = [], [], 0.0
        for k in range(len(bounds) - 1):
            a, c = bounds[k], bounds[k + 1]
            f = 1.0 if (rd and k == 1) else speed
            y = stretch(x[int(a * sr): int(c * sr)], sr, f)
            pieces.append(y)
            maps.append((a, c, t_new, f))
            t_new += len(y) / sr
        x = np.concatenate(pieces)

        def tm(t):
            for a, c, n0, f in maps:
                if t <= c or (a, c, n0, f) == maps[-1]:
                    return round(n0 + (t - a) / f, 3)
        for l in L:
            l["start"], l["end"] = tm(l["start"]), tm(l["end"])
            for w in l["words"]:
                w["start"], w["end"] = tm(w["start"]), tm(w["end"])
    for l in L:
        l["start"], l["end"] = round(l["start"], 3), round(l["end"], 3)
        for w in l["words"]:
            w["start"], w["end"] = round(w["start"], 3), round(w["end"], 3)
    T["duration"] = round(len(x) / sr, 3)
    sf.write(b / "voice.wav", x, sr)
    (b / "timing.json").write_text(json.dumps(T, ensure_ascii=False, indent=1))
    (b / "timing.js").write_text("window.TIMING = " + json.dumps(T, ensure_ascii=False) + ";\n")
    if cut:
        s = json.loads((p / "script.json").read_text())
        s["lines"] = [l for l in s["lines"] if l["id"] not in cut]
        (p / "script.json").write_text(json.dumps(s, ensure_ascii=False, indent=1))
    print(f"retimed: {T['duration']}s, {len(L)} lines (cut {cut or '-'}, speed {speed})")


if __name__ == "__main__":
    a = sys.argv[1:]
    get = lambda k, d: a[a.index(k) + 1] if k in a else d
    main(a[0], [c for c in get("--cut", "").split(",") if c], float(get("--speed", 1)))
