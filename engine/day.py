"""Per-day pipeline folder and hand-off checks for the agent setup.

  python3 -I engine/day.py init  <account_dir> <YYYY-MM-DD>      # create daily/<date>/ and status.json
  python3 -I engine/day.py check <sweep.json>                     # validate one researcher file
  python3 -I engine/day.py merge <account_dir> <YYYY-MM-DD>       # add new events from all sweeps to events.csv (dedup), render events.md
  python3 -I engine/day.py status <account_dir> <YYYY-MM-DD> [step=value ...]   # show / set step status

Day folder: <account_dir>/daily/<date>/
  sweep-markets.json · sweep-politics.json · sweep-business.json · sweep-national.json   (researchers)
  ideas.md · ideas-factcheck.md                                                          (writer, fact-checker)
  status.json                                                                            (coordinator)
"""
import datetime as dt, json, re, subprocess, sys
from pathlib import Path

AREAS = ["markets", "politics", "business", "national"]
CATS = {"MKT", "ECO", "BIZ", "TECH", "POL", "NEWS", "ENV", "GLB"}
STEPS = ["sweep", "merge", "ideas", "ideas_factcheck", "ideas_sent", "picked", "draft", "draft_factcheck",
         "draft_sent", "approved", "render", "video_sent", "ok_post", "posted", "knowledge"]
HERE = Path(__file__).resolve().parent


def day_dir(acct, date):
    return Path(acct) / "daily" / date


def init(acct, date):
    d = day_dir(acct, date)
    d.mkdir(parents=True, exist_ok=True)
    s = d / "status.json"
    if not s.exists():
        s.write_text(json.dumps({"date": date, "steps": {k: "todo" for k in STEPS}, "notes": []}, indent=1))
    print(d)


def check(path):
    errs = []
    try:
        j = json.loads(Path(path).read_text())
    except Exception as e:
        print(f"FAIL: not valid JSON: {e}"); sys.exit(1)
    if j.get("area") not in AREAS:
        errs.append(f"area must be one of {AREAS}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(j.get("run_date", ""))):
        errs.append("run_date must be YYYY-MM-DD")
    if not j.get("checked"):
        errs.append("checked: list every checklist item you searched")
    evs = j.get("events")
    if not isinstance(evs, list) or not evs:
        errs.append("events: must be a non-empty list")
        evs = []
    for i, e in enumerate(evs):
        p = f"events[{i}]"
        try:
            dt.date.fromisoformat(e.get("date", ""))
        except Exception:
            errs.append(f"{p}.date must be YYYY-MM-DD (use the start date for ranges)")
        if e.get("category") not in CATS:
            errs.append(f"{p}.category must be one of {sorted(CATS)}")
        if len(e.get("event", "")) < 15:
            errs.append(f"{p}.event too short")
        if e.get("status") not in ("verified", "partial", "upcoming"):
            errs.append(f"{p}.status must be verified|partial|upcoming")
        src = e.get("sources") or []
        if not src or not all(isinstance(s, dict) and str(s.get("url", "")).startswith("http") and s.get("label") for s in src):
            errs.append(f"{p}.sources must be a list of {{label, url}} with real http(s) URLs")
        sig = e.get("signals")
        keys = ("spreading", "wallet", "surprise", "visual", "fresh", "rivals")
        legacy = sig is None and isinstance(e.get("video_potential"), int) and str(j.get("run_date", "")) < "2026-10-21"
        if not legacy and (not isinstance(sig, dict) or any(sig.get(k) not in (0, 1, 2) for k in keys)):
            errs.append(f"{p}.signals must have {', '.join(keys)}, each 0, 1 or 2")
        if e.get("sensitivity", "normal") not in ("normal", "high"):
            errs.append(f"{p}.sensitivity must be normal|high")
    if errs:
        print("FAIL:\n- " + "\n- ".join(errs)); sys.exit(1)
    print(f"OK: {len(evs)} events")


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def merge(acct, date):
    sys.path.insert(0, str(HERE))
    import events as ev
    k = Path(acct) / "knowledge"
    rows = ev.load(k)
    known_urls = set(re.findall(r"<([^>]+)>", " ".join(r["sources"] for r in rows)))
    known_text = {norm(r["event"])[:80] for r in rows}
    new, skipped = [], 0
    d = day_dir(acct, date)
    for area in AREAS:
        f = d / f"sweep-{area}.json"
        if not f.exists():
            print(f"missing: {f.name}")
            continue
        for e in json.loads(f.read_text())["events"]:
            urls = [s["url"] for s in e["sources"]]
            if norm(e["event"])[:80] in known_text or (urls and all(u in known_urls for u in urls)):
                skipped += 1
                continue
            text = e["event"] + (f" (update of {e['update_of']})" if e.get("update_of") else "")
            new.append({"date": e["date"], "category": e["category"], "event": text,
                        "key_numbers": e.get("key_numbers", ""), "storyline": e.get("storyline", ""),
                        "status": e["status"], "sources": " ; ".join(f"{s['label']} <{s['url']}>" for s in e["sources"])})
            known_text.add(norm(e["event"])[:80]); known_urls.update(urls)
    tmp = d / "merge.json"
    tmp.write_text(json.dumps(new, ensure_ascii=False, indent=1))
    if new:
        ev.add(k, tmp)
    ev.render(k)
    st = d / "status.json"
    if st.exists():
        j = json.loads(st.read_text())
        j["merge_stats"] = {"new": len(new), "duplicates": skipped}
        st.write_text(json.dumps(j, indent=1, ensure_ascii=False))
    print(f"merged {len(new)} new events, skipped {skipped} duplicates")


def status(acct, date, sets):
    s = day_dir(acct, date) / "status.json"
    j = json.loads(s.read_text())
    for kv in sets:
        key, val = kv.split("=", 1)
        if key == "note":
            j["notes"].append(f"{dt.datetime.now(dt.timezone.utc):%H:%MZ} {val}")
        else:
            j["steps"][key] = val
    s.write_text(json.dumps(j, indent=1, ensure_ascii=False))
    print(" · ".join(f"{k}={v}" for k, v in j["steps"].items() if v != "todo") or "nothing done yet")


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "init":
        init(sys.argv[2], sys.argv[3])
    elif c == "check":
        check(sys.argv[2])
    elif c == "merge":
        merge(sys.argv[2], sys.argv[3])
    elif c == "status":
        status(sys.argv[2], sys.argv[3], sys.argv[4:])
