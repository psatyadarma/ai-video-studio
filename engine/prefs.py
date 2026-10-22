"""Learn the user's topic preferences from what they pick, and keep them in knowledge/preferences.md.

  python3 -I engine/prefs.py <account_dir>          # recompute the "What the picks show" section

preferences.md has two parts:
  - "What the user told us": explicit feedback, appended by the coordinator whenever the user says something
    about topics or angles (one dated line each). Never rewritten by this script.
  - "What the picks show": recomputed from covered.csv (ideas offered vs picked per day) + each day's ideas.md
    (rank, score line, sensitivity). Patterns only count once there are 5+ picks.
The writer reads the whole file and uses it as a tiebreaker (+1 for a strong fit), never to override
fact-checking, sensitivity rules or a clearly higher virality score.
"""
import csv, json, re, sys
from collections import Counter
from pathlib import Path

MARK = "## What the picks show"


def idea_meta(acct, date):
    f = Path(acct) / "daily" / date / "ideas.md"
    out = {}
    if not f.exists():
        return out
    for m in re.finditer(r"^## (\d+)\.\s*(.+?)\n(.*?)(?=^## |\Z)", f.read_text(), re.M | re.S):
        body = m.group(3)
        sc = re.search(r"(\d+)/12", body)
        se = re.search(r"\*\*Sensitivity:\*\*\s*([A-Za-z]+)", body)
        out[int(m.group(1))] = {"title": m.group(2).replace("⭐", "").strip(), "rec": "⭐" in m.group(2),
                                "score": int(sc.group(1)) if sc else None, "sens": se.group(1).lower() if se else ""}
    return out


def main():
    acct = Path(sys.argv[1]); k = acct / "knowledge"
    rows = [r for r in csv.DictReader(open(k / "covered.csv")) if r["kind"] == "idea"]
    days = sorted({r["date"] for r in rows})
    picks, ranks, rec_hits, story_off, story_pick, sens_pick = [], [], 0, Counter(), Counter(), Counter()
    lines = []
    for d in days:
        offered = [r for r in rows if r["date"] == d]
        picked = [r for r in offered if r["status"] in ("picked", "drafted", "posted")]
        st = Path(acct) / "daily" / d / "status.json"
        if st.exists() and json.loads(st.read_text()).get("steps", {}).get("default_pick") == "done":
            picked = []      # auto-picked on timeout: not the user's choice
            lines.append(f"- {d}: no pick by the deadline (default #1 used; not counted)")
        meta = idea_meta(acct, d)
        for r in offered:
            story_off[r["storyline"] or "-"] += 1
        for p in picked:
            picks.append(p); story_pick[p["storyline"] or "-"] += 1
            rank = next((n for n, m in meta.items() if m["title"][:25].lower() in p["title"].lower() or p["title"][:25].lower() in m["title"].lower()), None)
            m = meta.get(rank, {})
            ranks.append(rank); rec_hits += bool(m.get("rec")); sens_pick[m.get("sens") or "?"] += 1
            lines.append(f"- {d}: picked #{rank or '?'} {'(recommended)' if m.get('rec') else ''} \"{p['title']}\"" +
                         (f", score {m['score']}/12" if m.get("score") else "") + f", storyline {p['storyline'] or '-'}")
    n = len(picks)
    summary = [MARK, "", f"_Recomputed by engine/prefs.py from {len(days)} days of offers, {n} picks._", ""]
    summary += lines or ["- no picks yet"]
    summary.append("")
    if n >= 5:
        known = [r for r in ranks if r]
        summary.append(f"- Picks the recommended idea {rec_hits}/{n} times; average pick rank {sum(known)/len(known):.1f}." if known else "")
        liked = [s for s, c in story_pick.items() if c / max(1, story_off[s]) >= 0.5 and c >= 2]
        skipped = [s for s, c in story_off.items() if c >= 3 and story_pick[s] == 0]
        if liked: summary.append(f"- Storylines picked often when offered: {', '.join(liked)}.")
        if skipped: summary.append(f"- Offered 3+ times, never picked: {', '.join(skipped)} (lower priority unless big news).")
        summary.append(f"- Sensitivity of picks: {dict(sens_pick)}.")
    else:
        summary.append(f"- Not enough picks yet for patterns ({n}/5). Rely on the explicit notes above.")
    p = k / "preferences.md"
    head = p.read_text().split(MARK)[0].rstrip() if p.exists() else "# Topic preferences — learned\n\n## What the user told us\n"
    p.write_text(head + "\n\n" + "\n".join(summary).strip() + "\n")
    print(p.read_text())


if __name__ == "__main__":
    main()
