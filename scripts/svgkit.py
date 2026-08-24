"""Shared helpers for the profile's self-drawn SVGs.

Every SVG carries its own base64-subset of JetBrains Mono (600/1000 units,
so the 0.600 em advance the grids assume holds on every platform), and a
prefers-color-scheme block so the graphics follow GitHub's theme.
"""

import base64
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"

# JetBrains Mono advance is 600/1000 units: width of one char = 0.6 * font_size
def char_w(font_size: float) -> float:
    return 0.6 * font_size


def font_face(subset: str, family: str, weight: int = 400) -> str:
    data = base64.b64encode((FONTS / subset).read_bytes()).decode("ascii")
    return (
        f"@font-face{{font-family:'{family}';font-weight:{weight};"
        f"src:url(data:font/woff2;base64,{data}) format('woff2');}}"
    )


# GitHub-native palette, dark default, light via media query.
THEME_CSS = """
:root{--fg:#c9d1d9;--dim:#8b949e;--accent:#58a6ff;--rule:#30363d;--faint:#21262d}
@media (prefers-color-scheme: light){
:root{--fg:#24292f;--dim:#57606a;--accent:#0969da;--rule:#d0d7de;--faint:#eaeef2}
}
text{font-family:'jbm',monospace}
.fg{fill:var(--fg)}.dim{fill:var(--dim)}.accent{fill:var(--accent)}
.rule{stroke:var(--rule)}.faint{fill:var(--faint)}
"""


def svg_open(width: int, height: int, css: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img">'
        f"<style>{css}</style>"
    )


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
