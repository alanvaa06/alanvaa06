#!/usr/bin/env python3
"""Static heading SVGs: lowercase mono label, hairline rule to the right edge.

The only way to put our own typeface on a heading -- README text is locked
to GitHub's fonts. Run once; output is committed.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from svgkit import ROOT, THEME_CSS, char_w, esc, font_face, svg_open

W, H, FS = 840, 30, 15
HEADINGS = [
    "what i'm building",
    "contributions",
    "selected work",
    "claude code tooling",
    "stack",
    "elsewhere",
]


def main():
    css = font_face("jbmono-headings.woff2", "jbm", 400) + THEME_CSS
    out = ROOT / "assets"
    for label in HEADINGS:
        text_w = len(label) * char_w(FS)
        slug = label.replace("'", "").replace(" ", "-")
        s = [svg_open(W, H, css)]
        s.append(
            f'<text x="0" y="21" font-size="{FS}" letter-spacing="1" class="dim">{esc(label)}</text>'
        )
        rule_x = text_w + len(label) + 18  # letter-spacing adds ~1px per char
        s.append(
            f'<line x1="{rule_x:.0f}" y1="15" x2="{W}" y2="15" class="rule" stroke-width="1"/>'
        )
        s.append("</svg>")
        (out / f"h-{slug}.svg").write_text("".join(s), encoding="utf-8")
        print(f"h-{slug}.svg")


if __name__ == "__main__":
    main()
