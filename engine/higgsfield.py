"""Generate an AI clip or image with the Higgsfield API, wait for it, download it.

  python3 -I engine/higgsfield.py <model_path> <out_file> '<json body>'
  e.g. python3 -I engine/higgsfield.py kling-video/v2.6/pro/text-to-video build/ai/hook.mp4 \
         '{"prompt": "...", "duration": 5, "aspect_ratio": "9:16", "sound": "off"}'

Key: HIGGSFIELD_API_KEY=<id>:<secret> in ~/.config/explainer-studio/.env (never in the repo, never printed).
Writes <out_file> and <out_file>.json (request id, model, body, status, cost note) for credits/licence records.
Rules (playbook → AI footage): mood shots and illustrations of places only, labelled "ilustrasi AI";
never real people, never footage that looks like a real event happening.
"""
import json, os, sys, time, urllib.request, uuid
from pathlib import Path

API = "https://api.higgsfield.ai/"


def key():
    k = os.environ.get("HIGGSFIELD_API_KEY")
    env = Path.home() / ".config/explainer-studio/.env"
    if not k and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("HIGGSFIELD_API_KEY="):
                k = line.split("=", 1)[1].strip()
    if not k:
        sys.exit("higgsfield: HIGGSFIELD_API_KEY missing")
    return k


def call(url, body=None, method=None):
    h = {"Authorization": "Key " + key(), "Content-Type": "application/json", "User-Agent": "explainer-studio"}
    if body is not None:
        h["Idempotency-Key"] = str(uuid.uuid4())
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"higgsfield: HTTP {e.code} {e.read().decode(errors='replace')[:400]}")


def main(model, out, body):
    out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    body = json.loads(body)
    r = call(API + model.strip("/"), body)
    rid, surl = r.get("request_id"), r.get("status_url")
    print(f"higgsfield: queued {rid}")
    t0 = time.time()
    while True:
        s = call(surl)
        st = s.get("status")
        if st in ("completed", "failed", "nsfw", "canceled"):
            break
        if time.time() - t0 > 900:
            sys.exit(f"higgsfield: timeout, last status {st}")
        time.sleep(6)
    meta = {"request_id": rid, "model": model, "body": body, "status": st, "seconds": round(time.time() - t0)}
    if st != "completed":
        out.with_suffix(out.suffix + ".json").write_text(json.dumps({**meta, "response": s}, indent=1))
        sys.exit(f"higgsfield: {st} {json.dumps(s.get('error', ''))[:300]}")
    url = (s.get("video") or {}).get("url") or ((s.get("images") or [{}])[0]).get("url")
    meta["url_host"] = url.split("/")[2] if url else None
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "explainer-studio"}), timeout=300) as r:
        out.write_bytes(r.read())
    out.with_suffix(out.suffix + ".json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    print(f"higgsfield: {out} ({out.stat().st_size // 1024} KB, {meta['seconds']} s)")


if __name__ == "__main__":
    main(*sys.argv[1:4])
