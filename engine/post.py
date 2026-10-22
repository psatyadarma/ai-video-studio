"""Publish a finished video to TikTok, Instagram Reels and YouTube Shorts via Upload-Post.

Usage:
  python3 -I engine/post.py <video_dir> <account_dir> [--when "2026-10-20T12:30"] [--trial] [--dry-run]

--trial: Instagram only, as a Trial Reel shown to non-followers first (share_mode
TRIAL_REELS_DONT_SHARE_TO_FOLLOWERS). Used for the opening B version (<folder>-b, made by engine/variant.py).

Reads <video_dir>/post.json:
  {"caption": "...", "youtube_title": "... #Shorts", "youtube_description": "...", "tags": ["..."],
   "platforms": ["tiktok", "instagram", "youtube"]}
and posts <video_dir>/out/video.mp4 for the Upload-Post profile named in <account_dir>/brand.json ("upload_post_user").

Only run this after the user has explicitly said to post this video.
Key: UPLOAD_POST_API_KEY from env or ~/.config/explainer-studio/.env (never in the repo).
Writes the API response to <video_dir>/posted.json.
"""
import json, mimetypes, os, sys, uuid, urllib.request
from pathlib import Path

API = "https://api.upload-post.com/api/upload"


def key():
    # Key from env or ~/.config/explainer-studio/.env; if absent, the cloud environment's network secret
    # (Authorization: Apikey ... on api.upload-post.com) is attached by the proxy.
    k = os.environ.get("UPLOAD_POST_API_KEY")
    env = Path.home() / ".config/explainer-studio/.env"
    if not k and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("UPLOAD_POST_API_KEY="):
                k = line.split("=", 1)[1].strip()
    return k


def multipart(fields, files):
    b = uuid.uuid4().hex
    out = bytearray()
    for name, val in fields:
        out += f"--{b}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{val}\r\n".encode()
    for name, path in files:
        ct = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        out += (f"--{b}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{Path(path).name}\"\r\n"
                f"Content-Type: {ct}\r\n\r\n").encode() + Path(path).read_bytes() + b"\r\n"
    out += f"--{b}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={b}"


def main():
    args = sys.argv[1:]
    vdir, adir = Path(args[0]), Path(args[1])
    when = args[args.index("--when") + 1] if "--when" in args else None
    dry = "--dry-run" in args
    trial = "--trial" in args
    brand = json.loads((adir / "brand.json").read_text())
    post = json.loads((vdir / "post.json").read_text())
    video = vdir / "out" / "video.mp4"
    req_id = f"{brand.get('upload_post_user', 'acct')}-{vdir.name}"
    fields = [("user", brand["upload_post_user"]), ("title", post["caption"][:2200]),
              ("request_id", req_id), ("async_upload", "true")]
    for p in (["instagram"] if trial else post.get("platforms", ["tiktok", "instagram", "youtube"])):
        fields.append(("platform[]", p))
    # YouTube
    fields += [("youtube_title", post["youtube_title"][:100]),
               ("youtube_description", post.get("youtube_description", post["caption"])),
               ("privacyStatus", "public"), ("selfDeclaredMadeForKids", "false")]
    for t in post.get("tags", []):
        fields.append(("tags[]", t))
    # Instagram Reels (caption = instagram_title, falls back to title)
    fields += [("media_type", "REELS"), ("share_to_feed", "true"), ("instagram_title", post["caption"][:2200])]
    if trial:
        fields += [("share_mode", "TRIAL_REELS_DONT_SHARE_TO_FOLLOWERS")]
    # Sources as an automatic first comment on every platform
    if post.get("pinned_comment"):
        fields.append(("first_comment", post["pinned_comment"]))
    # TikTok: keep account default privacy; direct post
    fields += [("post_mode", "DIRECT_POST")]
    if when:
        fields += [("scheduled_date", when), ("timezone", "Asia/Makassar")]
    if dry:
        print(json.dumps({"fields": fields, "video": str(video)}, indent=1, ensure_ascii=False)); return
    body, ctype = multipart(fields, [("video", video)])
    req = urllib.request.Request(API, data=body, headers={**({"Authorization": f"Apikey {key()}"} if key() else {}), "Content-Type": ctype,
                                                          "Idempotency-Key": req_id})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=600))
    except urllib.error.HTTPError as e:
        r = {"http_error": e.code, "body": e.read().decode(errors="replace")[:2000]}
    (vdir / ("posted-trial.json" if trial else "posted.json")).write_text(json.dumps(r, indent=1, ensure_ascii=False))
    print(json.dumps(r, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
