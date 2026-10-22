"""Make the opening B version of a finished video for the daily hook A/B test (Instagram Trial Reel).

  python3 -I engine/variant.py <video_dir> <account_dir> [male|female]
  # then: python3 -I engine/mix.py <video_dir>-b && node engine/render.mjs <video_dir>-b

<video_dir>/script.json must carry:
  "hook_b": {"style": "myth", "replace": ["h1", "h2"],
             "lines": [{"id": "h1", "tag": "[...]", "text": "...", "say": "..."}, ...]}
Only the opening changes: the B lines are voiced (one short ElevenLabs call, ~100–200 characters) and spliced
onto A's existing voice track from the first kept line on, so the body is byte-for-byte A's take.
The page sees `window.TIMING.variant === "b"` and `TIMING.hook_style`; index.html draws the B opening when set.
Writes <video_dir>-b/ (a copy of the folder without out/ and stt cache) with build/voice.wav + timing.json/js.
"""
import json, shutil, sys
from pathlib import Path
import numpy as np
import soundfile as sf
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tts_eleven as T

GAP = 0.15


def main(vdir, adir, gender="male"):
    vdir, adir = Path(vdir), Path(adir)
    script = json.loads((vdir / "script.json").read_text())
    hb = script["hook_b"]
    brand = json.loads((adir / "brand.json").read_text())
    voice = brand["voices"][gender]
    tim = json.loads((vdir / "build/timing.json").read_text())
    if tim.get("voice") and tim["voice"] != voice["name"]:
        sys.exit(f"variant: A was voiced by {tim['voice']}, not {voice['name']}; pass the matching gender")
    a, sr = sf.read(vdir / "build/voice.wav", dtype="float32")
    if a.ndim > 1:
        a = a.mean(1)
    kept = [l for l in tim["lines"] if l["id"] not in hb["replace"]]
    cut_t = max(0.0, kept[0]["start"] - 0.05)
    body = a[int(cut_t * sr):]

    direction = script.get("direction", "[engaging, conversational news explainer, clear]")[:60]
    audio, tl = T.segment(hb["lines"], voice, direction)
    nz = np.where(np.abs(audio) > 0.01)[0]
    cut = max(0, (nz[0] if len(nz) else 0) - int(0.03 * T.SR))
    audio = audio[cut:]
    if T.SR != sr:
        sys.exit("variant: sample-rate mismatch")
    lead = 0.08
    shift_b = lead - cut / sr
    for l in tl:
        l["start"] = round(l["start"] + shift_b, 3); l["end"] = round(l["end"] + shift_b, 3)
        for w in l["words"]:
            w["start"] = round(max(0, w["start"] + shift_b), 3); w["end"] = round(w["end"] + shift_b, 3)
    body_t0 = lead + len(audio) / sr + GAP
    delta = body_t0 - cut_t
    for l in kept:
        l["start"] = round(l["start"] + delta, 3); l["end"] = round(l["end"] + delta, 3)
        for w in l["words"]:
            w["start"] = round(w["start"] + delta, 3); w["end"] = round(w["end"] + delta, 3)
    track = np.concatenate([np.zeros(int(lead * sr), np.float32), audio, np.zeros(int(GAP * sr), np.float32), body])

    out = vdir.parent / (vdir.name + "-b")
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(vdir, out, ignore=shutil.ignore_patterns("out", "stt.json", "posted*.json", "qa*.md", "qa-sync.json"))
    sf.write(out / "build/voice.wav", track, sr)
    data = {"duration": round(len(track) / sr, 3), "voice": voice["name"], "variant": "b",
            "hook_style": hb.get("style", ""), "lines": sorted(tl + kept, key=lambda l: l["start"])}
    (out / "build/timing.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    (out / "build/timing.js").write_text("window.TIMING = " + json.dumps(data, ensure_ascii=False) + ";\n")
    print(f"variant b: {out} · {data['duration']}s (A {tim['duration']}s) · hook {hb.get('style', '')}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
