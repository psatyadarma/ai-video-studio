"""Find and download freely licensed photos from Wikimedia Commons, with credit info.

  python3 -I engine/commons.py search "<query>" [n=8]            # list candidates: title, licence, size, author
  python3 -I engine/commons.py get "<File:Title.jpg>" <out_dir> <slug> [width=1200]
        → <out_dir>/<slug>.jpg + <slug>.json (page URL, author, licence, licence URL, credit line)

Only public domain, CC0, CC BY and CC BY-SA files are accepted. Always eyeball the photo before using it
(right person, front-facing, not a crowd shot).
"""
import json, re, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "RangkuminDongBot/0.1 (https://github.com/psatyadarma/ai-video-studio; news explainer videos) python-urllib"}
OK = re.compile(r"^(public domain|pd|cc0|cc by(-sa)? ?\d|cc-by(-sa)?-\d)", re.I)


def fetch(url, tries=4):
    import time
    for k in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or k == tries - 1:
                raise
            time.sleep(5 * (k + 1))  # Commons rate limit: back off


def api(**p):
    p.update(format="json")
    return json.loads(fetch(API + "?" + urllib.parse.urlencode(p)))


def strip(h):
    return re.sub(r"<[^>]+>", "", h or "").strip()


def info(titles, width=1200):
    r = api(action="query", titles="|".join(titles), prop="imageinfo", iiprop="url|extmetadata|size", iiurlwidth=width)
    out = []
    for p in r["query"]["pages"].values():
        if "imageinfo" not in p:
            continue
        ii = p["imageinfo"][0]
        m = ii.get("extmetadata", {})
        lic = strip(m.get("LicenseShortName", {}).get("value"))
        out.append({"title": p["title"], "page": ii.get("descriptionurl"), "url": ii.get("thumburl") or ii["url"],
                    "w": ii.get("width"), "h": ii.get("height"), "license": lic,
                    "license_url": strip(m.get("LicenseUrl", {}).get("value")),
                    "author": strip(m.get("Artist", {}).get("value")) or "unknown",
                    "ok": bool(OK.match(lic))})
    return out


def search(q, n=8):
    r = api(action="query", list="search", srsearch=q + " filetype:bitmap", srnamespace=6, srlimit=n)
    titles = [x["title"] for x in r["query"]["search"]]
    for i in info(titles) if titles else []:
        print(f"{'OK ' if i['ok'] else 'NO '} {i['title']} | {i['license']} | {i['w']}x{i['h']} | {i['author'][:60]}")


def get(title, out_dir, slug, width=1200):
    i = info([title], width)[0]
    if not i["ok"]:
        sys.exit(f"licence not allowed: {i['license']}")
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    # thumb.wikimedia.org may be blocked; upload.wikimedia.org serves the same thumbnail path
    data = fetch(i["url"].replace("://thumb.wikimedia.org/", "://upload.wikimedia.org/"))
    (out / f"{slug}.jpg").write_bytes(data)
    i["credit"] = f"Foto: {i['author']}, {i['license']}, via Wikimedia Commons"
    (out / f"{slug}.json").write_text(json.dumps(i, ensure_ascii=False, indent=1))
    print(out / f"{slug}.jpg", i["credit"])


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "search":
        search(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 8)
    elif c == "get":
        get(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]) if len(sys.argv) > 5 else 1200)
