"""Independent subtitle-sync check: transcribe the rendered voice with ElevenLabs speech-to-text
(word timestamps) and compare against the highlight timings in build/timing.json.

  python3 -I engine/qa_sync.py <video_dir> [--lead 0.08]

Writes <video_dir>/qa-sync.json and prints a verdict:
  PASS  median offset between -120 ms and +40 ms, ≥85% of matched words between -200 ms and +100 ms,
        and ≤5% of words more than 150 ms late (slightly early reads as "in sync"; late reads as lag)
  FIX   otherwise (lists the worst lines)
Offset = highlight start (timing + lead applied) minus the spoken word start. Positive = highlight late.

Credits: speech-to-text is called only when build/voice.wav is new. The transcript is cached in
build/stt.json with the audio's SHA-256, so re-checks after visual-only fixes, re-renders or a changed
--lead are free. Only the voice track is sent (not the music mix), which is shorter to bill and cleaner to transcribe.
"""
import difflib, hashlib, json, os, re, sys, urllib.request, uuid
from pathlib import Path
import numpy as np

API = "https://api.elevenlabs.io/v1/speech-to-text"


def key():
    k = os.environ.get("ELEVENLABS_API_KEY")
    env = Path.home() / ".config/explainer-studio/.env"
    if not k and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("ELEVENLABS_API_KEY="):
                k = line.split("=", 1)[1].strip()
    return k


def transcribe(wav):
    b = uuid.uuid4().hex
    fields = [("model_id", "scribe_v1"), ("language_code", "ind"), ("timestamps_granularity", "word"),
              ("tag_audio_events", "false")]
    body = bytearray()
    for n, v in fields:
        body += f"--{b}\r\nContent-Disposition: form-data; name=\"{n}\"\r\n\r\n{v}\r\n".encode()
    body += (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"voice.wav\"\r\n"
             f"Content-Type: audio/wav\r\n\r\n").encode() + Path(wav).read_bytes() + b"\r\n"
    body += f"--{b}--\r\n".encode()
    h = {"Content-Type": f"multipart/form-data; boundary={b}"}
    if key():
        h["xi-api-key"] = key()
    r = json.load(urllib.request.urlopen(urllib.request.Request(API, data=bytes(body), headers=h), timeout=600))
    return [w for w in r["words"] if w.get("type", "word") == "word"]


def norm(w):
    return re.sub(r"[^\w]", "", w.lower())


def main():
    vdir = Path(sys.argv[1])
    lead = float(sys.argv[sys.argv.index("--lead") + 1]) if "--lead" in sys.argv else 0.08
    timing = json.loads((vdir / "build/timing.json").read_text())
    ours = [(l["id"], w["w"], w["start"]) for l in timing["lines"] for w in l["words"]]
    wav = vdir / "build/voice.wav"
    digest = hashlib.sha256(wav.read_bytes()).hexdigest()
    cache = vdir / "build/stt.json"
    c = json.loads(cache.read_text()) if cache.exists() else {}
    if c.get("sha256") == digest:
        heard = c["words"]
        print("speech-to-text: cached (no credits used)")
    else:
        heard = transcribe(wav)
        cache.write_text(json.dumps({"sha256": digest, "words": heard}, ensure_ascii=False))
        print("speech-to-text: new transcript")
    sm = difflib.SequenceMatcher(None, [norm(o[1]) for o in ours], [norm(h["text"]) for h in heard], autojunk=False)
    pairs = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for k in range(i2 - i1):
                o, h = ours[i1 + k], heard[j1 + k]
                pairs.append({"line": o[0], "word": o[1], "offset": round(o[2] - lead - h["start"], 3)})
    if not pairs:
        print("FIX: no words matched between subtitles and transcript"); sys.exit(1)
    off = np.array([p["offset"] for p in pairs])
    med = float(np.median(off))
    within = float(np.mean((off >= -0.2) & (off <= 0.1)))
    late = float(np.mean(off > 0.15))
    per_line = {}
    for p in pairs:
        per_line.setdefault(p["line"], []).append(p["offset"])
    worst = sorted(((lid, float(np.median(v))) for lid, v in per_line.items()), key=lambda x: -abs(x[1]))[:5]
    verdict = "PASS" if -0.12 <= med <= 0.04 and within >= 0.85 and late <= 0.05 else "FIX"
    rep = {"verdict": verdict, "lead": lead, "matched_words": len(pairs), "of_words": len(ours),
           "median_offset_s": round(med, 3), "share_in_window": round(within, 3), "share_late_over_150ms": round(late, 3),
           "worst_lines": [{"line": l, "median_offset_s": round(m, 3)} for l, m in worst], "pairs": pairs}
    (vdir / "qa-sync.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    print(f"{verdict}: median {med*1000:+.0f} ms (positive = highlight late), {within:.0%} of {len(pairs)} "
          f"matched words in [-200, +100] ms, {late:.0%} >150 ms late; worst lines: " + ", ".join(f"{l} {m*1000:+.0f} ms" for l, m in worst))


if __name__ == "__main__":
    main()
