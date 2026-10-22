"""Pre-flight health check for the daily run: warn BEFORE something runs out mid-pipeline.

  python3 -I engine/health.py accounts/rangkumindong        # prints OK / WARN lines, exit 0 always

Checks (never prints key values):
  - keys file present (~/.config/explainer-studio/.env with both keys)
  - ElevenLabs character credit left vs what ~3 videos need (voice + STT checks), and the reset date
  - Upload-Post: the account's profile exists and its connected platforms match brand.json posting.platforms
  - metrics gaps: posted videos whose Instagram 24 h / 72 h row is missing (computer/Chrome may be off)
  - free disk space in the working directory
The coordinator puts every WARN line at the top of the morning message.
"""
import csv, datetime as dt, json, os, shutil, sys, urllib.request
from pathlib import Path

ENV = Path.home() / ".config/explainer-studio/.env"
PER_VIDEO_CHARS = 3500          # ~1.6k voice (incl. one retake) + STT sync checks, with margin
WARN_VIDEOS = 3


def keys():
    out = {}
    if ENV.exists():
        for line in ENV.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1); out[k.strip()] = v.strip()
    for k in ("ELEVENLABS_API_KEY", "UPLOAD_POST_API_KEY"):
        out.setdefault(k, os.environ.get(k, ""))
    return out


def get(url, headers):
    req = urllib.request.Request(url, headers={"User-Agent": "explainer-studio-health", **headers})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def main():
    acct = Path(sys.argv[1]); brand = json.loads((acct / "brand.json").read_text())
    k = keys(); lines = []
    ok = lambda m: lines.append("OK   " + m)
    warn = lambda m: lines.append("WARN " + m)

    missing = [n for n in ("ELEVENLABS_API_KEY", "UPLOAD_POST_API_KEY") if not k.get(n)]
    warn(f"missing keys: {', '.join(missing)} (re-read the project doc 'keys')") if missing else ok("keys present")

    if k.get("ELEVENLABS_API_KEY"):
        try:
            s = get("https://api.elevenlabs.io/v1/user/subscription", {"xi-api-key": k["ELEVENLABS_API_KEY"]})
            left = s.get("character_limit", 0) - s.get("character_count", 0)
            reset = s.get("next_character_count_reset_unix")
            rs = dt.datetime.fromtimestamp(reset).strftime("%d %b") if reset else "?"
            n = left // PER_VIDEO_CHARS
            msg = f"ElevenLabs: {left:,} characters left (~{n} videos), resets {rs}"
            warn(msg + " — top up or expect voice to fail soon") if n < WARN_VIDEOS else ok(msg)
        except Exception as e:
            warn(f"ElevenLabs check failed: {type(e).__name__} {getattr(e, 'code', '')}")

    if k.get("UPLOAD_POST_API_KEY"):
        try:
            u = get("https://api.upload-post.com/api/uploadposts/users", {"Authorization": "Apikey " + k["UPLOAD_POST_API_KEY"]})
            prof = brand.get("posting", {}).get("profile") or brand.get("posting", {}).get("user") or "Rangkumindong"
            profiles = u.get("profiles") or u.get("users") or []
            p = next((x for x in profiles if str(x.get("username", "")).lower() == prof.lower()), None)
            if not p:
                warn(f"Upload-Post: profile '{prof}' not found")
            else:
                conn = {name for name, v in (p.get("social_accounts") or {}).items() if v}
                want = set(brand.get("posting", {}).get("platforms", []))
                gap = want - conn
                warn(f"Upload-Post: {', '.join(sorted(gap))} not connected on '{prof}'") if gap else ok(f"Upload-Post: {', '.join(sorted(want))} connected")
        except Exception as e:
            warn(f"Upload-Post check failed: {type(e).__name__} {getattr(e, 'code', '')}")

    # metrics gaps (evening Instagram task needs the user's computer + Chrome)
    kn = acct / "knowledge"
    try:
        have = {(r["folder"], r["platform"], r["hours"]) for r in csv.DictReader(open(kn / "metrics.csv"))} if (kn / "metrics.csv").exists() else set()
        now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
        gaps = []
        for r in csv.DictReader(open(kn / "covered.csv")):
            if r["kind"] != "video" or r["status"] != "posted":
                continue
            age = (now.date() - dt.date.fromisoformat(r["date"])).days
            for h in (24, 72):
                if age >= h // 24 + 1 and (r["folder"], "instagram", str(h)) not in have:
                    gaps.append(f"{r['date']} {h}h")
        warn(f"Instagram metrics missing for {', '.join(gaps)} — the computer/Chrome may have been off or signed out") if gaps else ok("Instagram metrics up to date")
    except Exception as e:
        warn(f"metrics check failed: {e}")

    free = shutil.disk_usage(".").free / 1e9
    warn(f"disk: only {free:.1f} GB free") if free < 2 else ok(f"disk: {free:.1f} GB free")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
