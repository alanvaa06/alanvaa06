# Greeting cycle — design

**Date:** 2026-08-24 · **Status:** approved by Alan (chat)

## What

Replace the ASCII self-portrait at the top of the profile README (redundant with
the avatar photo) with a cycling multilingual greeting: eight words, each typed
in ASCII-ramp characters, holding, fading, looping forever.

Cycle (LatAm-first, non-Latin scripts closing): BIENVENIDO → WELCOME →
BEM-VINDO → BIENVENUE → WILLKOMMEN → BENVENUTO → 欢迎 → स्वागत.
8 × 2.5s = 20s loop.
Fixed caption below the cycle: `you found the lab.`

## How

**Generator** — `scripts/generate_greeting.py`, run locally, output committed
(no CI change; regenerate only when wording changes). Every word — any script —
goes through the portrait's raster pipeline: render text to pixels with a system
font, downscale, map brightness to the ramp `" .:-=+*#%@"`.

- Fonts (generation-time only, never embedded): Consolas Bold for Latin,
  Microsoft YaHei (regular weight, wider grid — bold muddied) for 欢迎,
  Nirmala for स्वागत.
- Per-word target rows: Latin 8, Devanagari 10, CJK 13; columns derived from
  the word's aspect ratio, capped at 124. Blocks centered on a shared grid.

**SVG** — `assets/greeting.svg`, viewBox ~960 wide, displayed at 560.

- Each word in a `<g opacity="0">`; a 20s `repeatCount="indefinite"` opacity
  animation (begin = i × 2.5s) sequences hold/fade via keyTimes. Base
  opacity 0 hides words before their first cycle starts.
- Typing = row-staggered clipPath wipe (0.09s/row stagger, ~1s total), plus one
  full-height cursor bar per word riding the wipe edge. All animations SMIL —
  GitHub strips scripts but runs SMIL.
- Caption fades in once (`fill="freeze"`), dim color.
- Embedded fonts: jbmono-ramp subset for grids, jbmono-latin for the caption.
  Theme-aware palette (accent blue glyphs, same tokens as the stats SVGs).

**README + cleanup** — greeting replaces the portrait `<img>`, centered,
alt "welcome, in eight languages". `assets/portrait.svg` deleted;
`generate_portrait.py` kept as a working tool. Scratch `_preview*.html` /
`_scripts_test.txt` removed.

## Verification

Local render, both color schemes; confirm the 20s loop restarts cleanly and no
word is visible before its first cycle; confirm 欢迎 legibility; push; verify
the live profile.
