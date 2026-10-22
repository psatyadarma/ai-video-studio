"""Turn a photo into a sticker: background removed, white outline and soft shadow baked in, trimmed.

  python3 -I engine/cutout.py <in.jpg> <out.png> [--kind person|object] [--outline 14] [--shadow 1]

--kind person uses rembg's u2net_human_seg (people), object uses isnet-general-use (products, logos, props).
Models live in ~/.u2net (downloaded once from the rembg GitHub release, ~175 MB each):
  curl -L -o ~/.u2net/u2net_human_seg.onnx https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx
  curl -L -o ~/.u2net/isnet-general-use.onnx https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx
Only use photos whose licence allows it (assets/people/<slug>.json records the credit). Never cut out
a photo from a news agency or a random website.
"""
import sys
import numpy as np
from PIL import Image, ImageFilter


def opt(name, default):
    return type(default)(sys.argv[sys.argv.index("--" + name) + 1]) if "--" + name in sys.argv else default


def main():
    src, dst = sys.argv[1], sys.argv[2]
    kind = opt("kind", "person")
    outline = opt("outline", 14)
    shadow = opt("shadow", 1)
    from rembg import new_session, remove
    sess = new_session("u2net_human_seg" if kind == "person" else "isnet-general-use")
    im = Image.open(src).convert("RGB")
    cut = remove(im, session=sess, post_process_mask=True)  # RGBA
    a = np.array(cut.split()[-1])
    a = np.where(a > 128, 255, 0).astype(np.uint8)  # crisp edge for the sticker look
    alpha = Image.fromarray(a).filter(ImageFilter.GaussianBlur(0.8))
    cut.putalpha(alpha)
    pad = outline * 3 + 40
    W, H = cut.width + 2 * pad, cut.height + 2 * pad
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    big = Image.new("L", (W, H), 0)
    big.paste(alpha, (pad, pad))
    ring = big.filter(ImageFilter.MaxFilter(outline * 2 + 1)).filter(ImageFilter.GaussianBlur(1.2))
    if shadow:
        sh = ring.filter(ImageFilter.GaussianBlur(outline * 0.9)).point(lambda v: int(v * 0.28))
        sh_img = Image.new("RGBA", (W, H), (27, 36, 48, 0))
        sh_img.putalpha(sh)
        base.alpha_composite(sh_img, (0, int(outline * 1.1)))
    white = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    white.putalpha(ring)
    base.alpha_composite(white)
    base.alpha_composite(cut, (pad, pad))
    bbox = base.getbbox()
    base.crop(bbox).save(dst)
    print(dst, base.crop(bbox).size)


if __name__ == "__main__":
    main()
