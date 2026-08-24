#!/usr/bin/env python3
"""Photo -> self-typing ASCII portrait SVG.

Pipeline (each stage earns its place):
  rembg cut-out   -- background forced to white = blank end of the ramp
  bilateral       -- smooths skin, keeps edges
  CLAHE clip 3.0  -- local contrast; global autocontrast flattens a face
  (v/255)^1.7     -- darkening curve; what makes brows and lips survive
  map to ramp     -- leading space clears the background to nothing

Animation is SMIL (GitHub strips scripts, runs SMIL): each row in a
clipPath whose rect wipes open, cursor block riding the edge, staggered
0.09s per row, fill=freeze -- prints once and stops.

Usage: python scripts/generate_portrait.py path/to/photo.jpg
Deps:  pip install -r scripts/requirements-portrait.txt
"""

import pathlib
import sys

import cv2
import numpy as np
from PIL import Image
from rembg import remove

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from svgkit import ROOT, THEME_CSS, char_w, font_face, svg_open

COLS = 90
FS = 12.9
CHAR_W = char_w(FS)  # 7.74 -- JetBrains Mono is exactly 600/1000
LINE_H = CHAR_W / 0.48  # monospace cell is ~2x taller than wide
RAMP = " .:-=+*#%@"
STAGGER = 0.09
ROW_DUR = 0.6


def ascii_grid(photo: pathlib.Path) -> list[str]:
    img = Image.open(photo).convert("RGB")
    cut = remove(img)  # RGBA, subject only
    white = Image.new("RGBA", cut.size, (255, 255, 255, 255))
    flat = Image.alpha_composite(white, cut).convert("L")
    g = np.array(flat)

    g = cv2.bilateralFilter(g, d=9, sigmaColor=60, sigmaSpace=60)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    g = clahe.apply(g)
    g = (np.power(g / 255.0, 1.7) * 255).astype(np.uint8)  # the fix

    h, w = g.shape
    rows = max(1, round(COLS * (h / w) * 0.48))
    small = cv2.resize(g, (COLS, rows), interpolation=cv2.INTER_AREA)

    lines = []
    for r in small:
        # bright -> blank, dark -> @
        idx = ((255 - r.astype(int)) * (len(RAMP) - 1) // 255).clip(0, len(RAMP) - 1)
        lines.append("".join(RAMP[i] for i in idx))
    return lines


def render(lines: list[str]) -> str:
    w = COLS * CHAR_W
    h = len(lines) * LINE_H + 4
    css = font_face("jbmono-ramp.woff2", "jbmr", 400) + THEME_CSS
    s = [svg_open(round(w), round(h), css)]
    s.append("<defs>")
    for i in range(len(lines)):
        beg = f"{i * STAGGER:.2f}s"
        s.append(
            f'<clipPath id="r{i}"><rect x="0" y="{i * LINE_H:.1f}" width="0" '
            f'height="{LINE_H:.1f}">'
            f'<animate attributeName="width" from="0" to="{w:.0f}" '
            f'dur="{ROW_DUR}s" begin="{beg}" fill="freeze"/></rect></clipPath>'
        )
    s.append("</defs>")
    for i, line in enumerate(lines):
        y = i * LINE_H + FS
        txt = (
            line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace(" ", "&#160;")
        )
        s.append(
            f'<g clip-path="url(#r{i})"><text x="0" y="{y:.1f}" font-size="{FS}" '
            f"style=\"font-family:'jbmr',monospace\" xml:space=\"preserve\" "
            f'textLength="{w:.1f}" class="accent">{txt}</text></g>'
        )
        # cursor riding the wipe edge, hidden when its row is done
        beg = f"{i * STAGGER:.2f}s"
        end = f"{i * STAGGER + ROW_DUR:.2f}s"
        s.append(
            f'<rect x="0" y="{i * LINE_H:.1f}" width="{CHAR_W:.2f}" '
            f'height="{LINE_H:.1f}" class="accent" fill="var(--accent)" opacity="0">'
            f'<set attributeName="opacity" to="0.8" begin="{beg}" fill="freeze"/>'
            f'<animate attributeName="x" from="0" to="{w:.0f}" dur="{ROW_DUR}s" '
            f'begin="{beg}" fill="freeze"/>'
            f'<set attributeName="opacity" to="0" begin="{end}" fill="freeze"/></rect>'
        )
    s.append("</svg>")
    return "".join(s)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: generate_portrait.py photo.jpg")
    photo = pathlib.Path(sys.argv[1])
    lines = ascii_grid(photo)
    out = ROOT / "assets" / "portrait.svg"
    out.write_text(render(lines), encoding="utf-8")
    print(f"wrote {out} ({len(lines)} rows, ~{len(lines) * STAGGER + ROW_DUR:.1f}s animation)")
    # plain-text preview so you can judge the likeness without a browser
    print("\n".join(lines))


if __name__ == "__main__":
    main()
