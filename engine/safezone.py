"""Draw the platforms' UI zones and the profile-grid crop over 1080×1920 stills, for QA.

  python3 -I engine/safezone.py <out.png> <still1.png> [still2.png ...]

Shaded = covered on a phone (approximate, TikTok / Reels / Shorts combined):
  top 0–200 (status bar, tabs) · right 930–1080 between y 640 and 1640 (like/comment/share buttons)
  · bottom 1500–1920 (caption, username, music, progress).
Dashed box = what the 3:4 profile grid shows (y 240–1680).
Anything important (headline, numbers, chart labels, subtitles) should sit in the clear area.
"""
import sys
from PIL import Image, ImageDraw

ZONES = [(0, 0, 1080, 200), (930, 640, 1080, 1640), (0, 1500, 1080, 1920)]
GRID = (0, 240, 1080, 1680)


def overlay(path):
    im = Image.open(path).convert("RGBA").resize((1080, 1920))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(sh)
    for z in ZONES:
        d.rectangle(z, fill=(220, 40, 40, 70))
    x0, y0, x1, y1 = GRID
    for x in range(x0, x1, 40):
        d.line([(x, y0), (x + 20, y0)], fill=(30, 90, 220, 255), width=6)
        d.line([(x, y1), (x + 20, y1)], fill=(30, 90, 220, 255), width=6)
    return Image.alpha_composite(im, sh).convert("RGB")


def main():
    out, stills = sys.argv[1], sys.argv[2:]
    tiles = [overlay(p).resize((360, 640)) for p in stills]
    cols = min(6, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 360 + (cols - 1) * 8, rows * 640 + (rows - 1) * 8), "white")
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * 368, (i // cols) * 648))
    sheet.save(out)
    print(out)


if __name__ == "__main__":
    main()
