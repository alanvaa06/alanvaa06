#!/usr/bin/env python3
"""Cycling multilingual greeting -> assets/greeting.svg.

Every word, whatever the script, goes through the portrait's raster
pipeline: draw the text with a system font, downscale, map brightness to
the ramp. That is what lets one SVG greet in Latin, Hanzi and Devanagari
while embedding only the 10-character ramp subset of JetBrains Mono.

Run locally (needs Windows system fonts); output is committed. Regenerate
only when the wording changes.

Usage: python scripts/generate_greeting.py
"""

import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from svgkit import ROOT, THEME_CSS, char_w, font_face, svg_open

RAMP = " .:-=+*#%@"
FS = 12.9
CHAR_W = char_w(FS)  # 7.74
LINE_H = CHAR_W / 0.48
MAX_COLS = 124

STEP = 2.5  # seconds each word owns
ROW_STAGGER = 0.09
TYPE_DUR = 0.8  # per-row wipe duration

FONTS = {
    "latin": (r"C:\Windows\Fonts\consolab.ttf", 8),
    "cjk": (r"C:\Windows\Fonts\msyh.ttc", 13),
    "deva": (r"C:\Windows\Fonts\Nirmala.ttc", 10),
}

WORDS = [
    ("BIENVENIDO", "latin"),
    ("WELCOME", "latin"),
    ("BEM-VINDO", "latin"),
    ("BIENVENUE", "latin"),
    ("WILLKOMMEN", "latin"),
    ("BENVENUTO", "latin"),
    ("\u6b22\u8fce", "cjk"),
    ("\u0938\u094d\u0935\u093e\u0917\u0924", "deva"),
]

CAPTION = "to my lab."


def word_to_ascii(text: str, kind: str) -> list[str]:
    fontpath, target_rows = FONTS[kind]
    f = ImageFont.truetype(fontpath, 160, index=0)
    bbox = f.getbbox(text)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    img = Image.new("L", (w + 24, h + 24), 255)
    ImageDraw.Draw(img).text((12 - bbox[0], 12 - bbox[1]), text, font=f, fill=0)

    cols = round(target_rows / 0.48 * (img.width / img.height))
    if cols > MAX_COLS:
        cols = MAX_COLS
    rows = max(1, round(cols * (img.height / img.width) * 0.48))
    small = np.array(img.resize((cols, rows), Image.LANCZOS)).astype(int)

    lines = []
    for r in small:
        idx = ((255 - r) * (len(RAMP) - 1) // 255).clip(0, len(RAMP) - 1)
        lines.append("".join(RAMP[i] for i in idx))
    return lines


def esc_row(line: str) -> str:
    return (
        line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace(" ", "&#160;")
    )


def main():
    grids = [word_to_ascii(t, k) for t, k in WORDS]
    max_rows = max(len(g) for g in grids)
    n = len(WORDS)
    cycle = n * STEP

    W = round(MAX_COLS * CHAR_W)
    grid_h = max_rows * LINE_H
    H = round(grid_h + 42)

    css = (
        font_face("jbmono-ramp.woff2", "jbmr", 400)
        + font_face("jbmono-latin.woff2", "jbm", 400)
        + THEME_CSS
    )
    s = [svg_open(W, H, css)]
    s.append("<defs>")
    for i, g in enumerate(grids):
        gw = len(g[0]) * CHAR_W
        x0 = (W - gw) / 2
        y0 = (grid_h - len(g) * LINE_H) / 2
        beg = i * STEP
        for r in range(len(g)):
            # keyTimes sequence the wipe inside each word's 20s period;
            # base width 0 hides rows before the first cycle starts
            t0 = (r * ROW_STAGGER) / cycle
            t1 = (r * ROW_STAGGER + TYPE_DUR) / cycle
            s.append(
                f'<clipPath id="w{i}r{r}"><rect x="{x0:.1f}" '
                f'y="{y0 + r * LINE_H:.1f}" width="0" height="{LINE_H:.1f}">'
                f'<animate attributeName="width" values="0;0;{gw:.0f};{gw:.0f}" '
                f'keyTimes="0;{t0:.4f};{t1:.4f};1" dur="{cycle}s" '
                f'begin="{beg}s" repeatCount="indefinite"/></rect></clipPath>'
            )
    s.append("</defs>")

    hold_end = (STEP) / cycle          # word owns [0, STEP) of its period
    fade_end = (STEP + 0.3) / cycle
    for i, g in enumerate(grids):
        gw = len(g[0]) * CHAR_W
        x0 = (W - gw) / 2
        y0 = (grid_h - len(g) * LINE_H) / 2
        beg = i * STEP
        s.append(
            f'<g opacity="0"><animate attributeName="opacity" '
            f'values="1;1;0;0" keyTimes="0;{hold_end:.4f};{fade_end:.4f};1" '
            f'dur="{cycle}s" begin="{beg}s" repeatCount="indefinite"/>'
        )
        for r, line in enumerate(g):
            y = y0 + r * LINE_H + FS
            s.append(
                f'<g clip-path="url(#w{i}r{r})"><text x="{x0:.1f}" y="{y:.1f}" '
                f'font-size="{FS}" style="font-family:\'jbmr\',monospace" '
                f'xml:space="preserve" textLength="{gw:.1f}" '
                f'class="accent">{esc_row(line)}</text></g>'
            )
        # one full-height cursor bar riding the wipe, gone once typing ends
        type_total = (len(g) - 1) * ROW_STAGGER + TYPE_DUR
        tc = type_total / cycle
        s.append(
            f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{CHAR_W:.2f}" '
            f'height="{len(g) * LINE_H:.1f}" fill="var(--accent)" opacity="0">'
            f'<animate attributeName="opacity" values="0.7;0.7;0;0" '
            f'keyTimes="0;{tc:.4f};{min(tc + 0.005, 1):.4f};1" dur="{cycle}s" '
            f'begin="{beg}s" repeatCount="indefinite"/>'
            f'<animate attributeName="x" values="{x0:.1f};{x0 + gw:.1f};{x0 + gw:.1f}" '
            f'keyTimes="0;{tc:.4f};1" dur="{cycle}s" begin="{beg}s" '
            f'repeatCount="indefinite"/></rect>'
        )
        s.append("</g>")

    cy = H - 12
    s.append(
        f'<text x="{W / 2:.0f}" y="{cy}" font-size="13" text-anchor="middle" '
        f'class="dim" opacity="0">{CAPTION}'
        f'<animate attributeName="opacity" from="0" to="1" dur="0.5s" '
        f'begin="1s" fill="freeze"/></text>'
    )
    s.append("</svg>")

    out = ROOT / "assets" / "greeting.svg"
    out.write_text("".join(s), encoding="utf-8")
    kb = out.stat().st_size / 1024
    print(f"wrote {out} ({kb:.0f} KB, {n} words, {cycle:.0f}s cycle)")
    for (t, _), g in zip(WORDS, grids):
        # ascii-only console output: Windows terminals default to cp1252
        label = t.encode("ascii", "backslashreplace").decode("ascii")
        print(f"  {label}: {len(g[0])}x{len(g)}")


if __name__ == "__main__":
    main()
