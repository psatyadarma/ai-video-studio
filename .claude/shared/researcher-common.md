# Shared rules for every news researcher (read this first)

You are one of the parallel news researchers for **Rangkumin Dong**, a Bahasa Indonesia short-video account that explains Indonesian business, market, tech and political news. Your only output is one JSON file. The coordinator merges the four files into the events database and builds the day's video ideas from them.

## Inputs
- Known events: run `python3 -I engine/events.py window accounts/rangkumindong/knowledge 14` (one line per event). Don't read events.csv in full. Don't re-report a known event unless there is a **new development** (then report it as a new event with `"update_of": "<id>"`).
- Active storylines: `accounts/rangkumindong/knowledge/storylines/*.md` in your categories (read the summary and latest-developments parts only).
- Your area brief (the file that told you to read this one).

## How to search (headlines first, from 21 Oct)
Window: the last 48 hours before the run date (Asia/Makassar time), plus anything scheduled in the next 14 days (`"status": "upcoming"`).
0. **Fetch only URLs you were handed by a tool (22 Oct lesson).** In scheduled sessions WebFetch refuses URLs typed from this file. So for each section page: run one WebSearch like "cnbcindonesia market terbaru" or "detik finance hari ini", then WebFetch the section page URL **as returned in the results** (or a link on a page you already fetched). Never retry a refused URL; move to the next outlet.
1. **Read the section pages** listed in your brief with WebFetch (reached as in step 0): each shows 30+ of the latest headlines, so one fetch covers many institutions at once. Search engines lag 1–3 days on Indonesian news, so this comes first. If a page fails or is stale (check article dates), use the next one. Known (19–20 Oct): detik, cnbcindonesia, bisnis, katadata, cnnindonesia, antaranews work; kompas.com and idx.co.id often can't be read; kontan.co.id may be a stale cache.
2. **Use your "watch list" to read the headlines.** It lists topics to look out for, not searches to run. **Only when a watch-list topic appears in the headlines** do you dig into it (search for follow-up coverage, open the articles, get the numbers). If it isn't in the headlines, don't search for it. Record in `checked` the pages you scanned and the watch-list topics you found.
3. **One search per active storyline** in your categories (e.g. "gibran ijazah MK terbaru"), to catch developments that aren't on the front pages.
4. **Open full articles only where needed:** for stories you'd score high on the rubric, or to get exact numbers. Never take numbers from a headline or search snippet alone.
5. No second sweep: if something looks thin, note it in `gaps` instead of searching more.
- Prefer primary sources (BI, OJK, BEI/IDX, BPS, ministries, court rulings, company filings) and major outlets (Kompas, Detik, CNN Indonesia, Tempo, Antara, CNBC Indonesia, Kontan, Bisnis, Katadata, Reuters, Bloomberg).
- `status`: `verified` = 2+ independent sources agree, or one primary source; `partial` = one secondary source, or details unclear; `upcoming` = scheduled future event.

## Output — write exactly this file
Path: `accounts/rangkumindong/daily/<RUN_DATE>/sweep-<AREA>.json` (the coordinator gives you RUN_DATE and AREA). JSON, UTF-8:

```json
{
  "area": "<AREA>",
  "run_date": "YYYY-MM-DD",
  "checked": ["every checklist item you searched, e.g. \"MK\", \"KPK\", \"Kompas terpopuler\""],
  "events": [
    {
      "date": "YYYY-MM-DD",
      "category": "MKT|ECO|BIZ|TECH|POL|NEWS|ENV|GLB",
      "event": "One neutral English sentence: who did what. Indonesian names/terms kept as-is.",
      "key_numbers": "All the numbers that matter, with units and dates, separated by ' · '",
      "storyline": "existing storyline slug, a proposed new slug, or empty",
      "update_of": "E00xx or empty",
      "status": "verified|partial|upcoming",
      "sources": [{"label": "Outlet", "url": "https://..."}],
      "why_it_matters": "One line for a general Indonesian audience",
      "signals": {"spreading": 0, "wallet": 0, "surprise": 0, "visual": 0, "fresh": 0, "rivals": 0},
      "spreading_evidence": "where you saw it trending, e.g. \"CNBC terpopuler #2\", or empty",
      "sensitivity": "normal|high"
    }
  ],
  "gaps": ["things you saw mentioned but could not verify"]
}
```
- `signals`, each 0, 1 or 2 (the virality rubric; see playbook → Topic selection):
  - `spreading`: 2 = on an outlet's most-read list or reported trending on X/TikTok today; 1 = widely covered by several outlets; 0 = niche.
  - `wallet`: 2 = changes what many ordinary people pay, earn or can do; 1 = affects a group (investors, sellers, a region); 0 = no direct effect.
  - `surprise`: 2 = a shock number, a reversal, a conflict, or something people believe wrongly; 1 = notable; 0 = expected.
  - `visual`: 2 = one clear number, map or chart that lands in 3 seconds; 1 = needs some setup; 0 = abstract.
  - `fresh`: 2 = happened today/yesterday or has a date in the next 3 days; 1 = this week; 0 = older.
  - `rivals`: 2 = few explainer accounts have covered it; 1 = some; 0 = everyone has. 
  Score the angle that would make the best video, not the dullest reading of the story.
- `sensitivity: high` for allegations, ongoing court cases, elections, SARA, named private individuals.
- Aim for 5–15 events. Quality over quantity: no duplicates, no opinion pieces as events.
- Validate before finishing: `python3 -I engine/day.py check accounts/rangkumindong/daily/<RUN_DATE>/sweep-<AREA>.json`. Fix until it prints OK.

## Final reply to the coordinator
Three lines max: number of events, the single strongest video candidate, and any gap worth a second look. Do not paste the JSON.
