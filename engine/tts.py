"""Voice-over with timings.

Reads <project>/script.json:
  {"lines": [{"id": "hook", "text": "...", "pause": 0.25}, ...]}
Writes <project>/build/voice.wav and <project>/build/timing.json:
  {"duration": s, "lines": [{"id", "text", "start", "end", "words": [{"w", "start", "end"}]}]}

Engine "piper" (free, offline, default) generates one clip per line, so line timings are exact;
word timings inside a line are estimated from syllable-ish length.
Engine "elevenlabs" (when ELEVENLABS_API_KEY is set and the host is reachable) will use the
/with-timestamps endpoint for exact word timings. (Not implemented until the key is available.)
"""
import json, re, sys
from pathlib import Path
import numpy as np
import soundfile as sf

MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "vits-piper-id_ID-news_tts-medium"


def piper():
    import sherpa_onnx
    d = MODEL_DIR
    cfg = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
        vits=sherpa_onnx.OfflineTtsVitsModelConfig(
            model=str(d / "id_ID-news_tts-medium.onnx"), tokens=str(d / "tokens.txt"),
            data_dir=str(d / "espeak-ng-data")), num_threads=4))
    return sherpa_onnx.OfflineTts(cfg)


def trim(x, sr, thresh=0.01):
    idx = np.where(np.abs(x) > thresh)[0]
    if len(idx) == 0:
        return x
    a, b = max(0, idx[0] - int(0.02 * sr)), min(len(x), idx[-1] + int(0.04 * sr))
    return x[a:b]


def weight(word):
    # rough spoken length: vowel groups + digits count extra
    v = len(re.findall(r"[aiueoAIUEO]+", word))
    return max(1, v) + 0.3


def main(project, speed=1.0):
    project = Path(project)
    script = json.loads((project / "script.json").read_text())
    tts = piper()
    sr = None
    chunks, lines, t = [], [], 0.0
    lead = 0.3
    for ln in script["lines"]:
        text = ln.get("say", ln["text"])  # "say" = pronunciation override, "text" = subtitle
        a = tts.generate(text, sid=0, speed=speed)
        sr = a.sample_rate
        x = trim(np.array(a.samples, dtype=np.float32), sr)
        if not chunks:
            chunks.append(np.zeros(int(lead * sr), np.float32)); t = lead
        start, dur = t, len(x) / sr
        words = ln["text"].split()
        ws = [weight(w) for w in words]
        tot, acc, wl = sum(ws), 0.0, []
        for w, k in zip(words, ws):
            ws0 = start + dur * acc / tot
            acc += k
            wl.append({"w": w, "start": round(ws0, 3), "end": round(start + dur * acc / tot, 3)})
        lines.append({"id": ln["id"], "text": ln["text"], "start": round(start, 3),
                      "end": round(start + dur, 3), "words": wl})
        pause = ln.get("pause", 0.25)
        chunks += [x, np.zeros(int(pause * sr), np.float32)]
        t = start + dur + pause
    tail = script.get("tail", 1.2)
    chunks.append(np.zeros(int(tail * sr), np.float32))
    voice = np.concatenate(chunks)
    out = project / "build"
    out.mkdir(exist_ok=True)
    sf.write(out / "voice.wav", voice, sr)
    timing = {"duration": round(len(voice) / sr, 3), "lines": lines}
    (out / "timing.json").write_text(json.dumps(timing, ensure_ascii=False, indent=1))
    (out / "timing.js").write_text("window.TIMING = " + json.dumps(timing, ensure_ascii=False) + ";\n")
    print(f"voice {timing['duration']}s, {len(lines)} lines")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 1.0)
