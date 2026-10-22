"""What we've already covered (videos) and already offered (ideas), so nothing gets repeated by accident.

  python3 -I engine/covered.py add   <knowledge_dir> <json-file>      # append rows (list of dicts)
  python3 -I engine/covered.py check <knowledge_dir> "<idea text>"     # similar past videos/ideas, best first
  python3 -I engine/covered.py set   <knowledge_dir> <folder-or-title> status=posted links="..."   # update a row
  python3 -I engine/covered.py list  <knowledge_dir> [days]

File: <knowledge_dir>/covered.csv (source of truth; mirrored in the video log).
Columns: date, kind (video|idea), title, angle, key_numbers, storyline, part, events (E-ids), folder, status
(offered|picked|drafted|posted|rejected), links.
"""
import csv, datetime as dt, json, re, sys
from pathlib import Path

FIELDS = ["date", "kind", "title", "angle", "key_numbers", "storyline", "part", "events", "folder", "status", "links"]
STOP = set("dan yang di ke dari ini itu jadi dengan untuk atau juga ada akan sudah baru the a of to in on and for is".split())


def path(k):
    return Path(k) / "covered.csv"


def load(k):
    p = path(k)
    if not p.exists():
        return []
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def save(k, rows):
    with open(path(k), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({x: r.get(x, "") for x in FIELDS})


def toks(s):
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in STOP and len(t) > 2}


def check(k, text):
    q = toks(text)
    scored = []
    for r in load(k):
        t = toks(" ".join([r["title"], r["angle"], r["key_numbers"], r["storyline"].replace("-", " ")]))
        if not q or not t:
            continue
        s = len(q & t) / min(len(q), len(t))  # share of the idea's words already used before
        if r["storyline"] and r["storyline"] in text:
            s += 0.3
        scored.append((s, r))
    scored.sort(key=lambda x: -x[0])
    hits = [(s, r) for s, r in scored if s >= 0.25][:5]
    if not hits:
        print("NEW: nothing similar covered or offered before"); return
    for s, r in hits:
        print(f"{s:.2f} · {r['date']} · {r['kind']}/{r['status']} · {r['title']} · storyline={r['storyline'] or '-'}"
              f"{' PART ' + r['part'] if r['part'] else ''} · {r['folder'] or ''}")


def add(k, f):
    rows = load(k)
    new = json.loads(Path(f).read_text())
    for r in new:
        r.setdefault("date", dt.date.today().isoformat())
    save(k, rows + new)
    print(f"covered.csv: +{len(new)} rows, {len(rows) + len(new)} total")


def set_(k, key, kvs):
    rows = load(k)
    n = 0
    for r in rows:
        if key in (r["folder"], r["title"]):
            for kv in kvs:
                a, b = kv.split("=", 1)
                r[a] = b
            n += 1
    save(k, rows)
    print(f"updated {n} row(s)")


def list_(k, days=60):
    cut = dt.date.today() - dt.timedelta(days=int(days))
    for r in load(k):
        if dt.date.fromisoformat(r["date"]) >= cut:
            print(f"{r['date']} {r['kind']:5} {r['status']:8} {r['title']} [{r['storyline']}{' P' + r['part'] if r['part'] else ''}]")


if __name__ == "__main__":
    c, k = sys.argv[1], sys.argv[2]
    {"add": lambda: add(k, sys.argv[3]), "check": lambda: check(k, sys.argv[3]),
     "set": lambda: set_(k, sys.argv[3], sys.argv[4:]),
     "list": lambda: list_(k, *(sys.argv[3:4]))}[c]()
