"""Join the demo frames from web/scripts/demo-frames.mjs into docs/demo.gif.

I keep it under 12 seconds and 5 MB, so the README loads quickly.

Usage: python scripts/make_gif.py runs/demo_frames
"""

import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
WIDTH = 1000
MAX_SECONDS, MAX_MB = 12, 5


def main() -> None:
    frames_dir = Path(sys.argv[1])
    spec = json.loads((frames_dir / "frames.json").read_text(encoding="utf-8"))
    total = sum(f["ms"] for f in spec) / 1000
    if total > MAX_SECONDS:
        sys.exit(f"The demo is {total:.1f} s, over {MAX_SECONDS} s")
    images = []
    for f in spec:
        im = Image.open(frames_dir / Path(f["path"]).name).convert("RGB")
        im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
        # One shared palette per frame keeps text crisp and the file small.
        images.append(im.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=0))
    out = ROOT / "docs" / "demo.gif"
    images[0].save(out, save_all=True, append_images=images[1:],
                   duration=[f["ms"] for f in spec], loop=0, optimize=True)
    mb = out.stat().st_size / 2**20
    print(f"Wrote {out.relative_to(ROOT)}: {total:.1f} s, {mb:.2f} MB")
    if mb > MAX_MB:
        sys.exit(f"Over {MAX_MB} MB; lower WIDTH or the number of colours")


if __name__ == "__main__":
    main()
