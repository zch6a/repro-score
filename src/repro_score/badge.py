"""A badge for the README: an SVG in the flat style of shields.io, made here (nothing is fetched)."""

from __future__ import annotations

from xml.sax.saxutils import escape

# widths of Verdana 11px characters (as shields.io measures text), the common ones; others take the average
WIDTHS = {" ": 3.9, "-": 4.8, "/": 4.8, "0": 7.0, "1": 7.0, "2": 7.0, "3": 7.0, "4": 7.0, "5": 7.0, "6": 7.0, "7": 7.0, "8": 7.0, "9": 7.0,
          "a": 6.7, "b": 6.9, "c": 5.8, "d": 6.9, "e": 6.7, "f": 3.9, "g": 6.9, "i": 3.0, "l": 3.0, "m": 10.7, "n": 7.0, "o": 6.7, "p": 6.9,
          "r": 4.7, "s": 5.8, "t": 4.3, "u": 7.0, "x": 6.5}  # fmt: skip


def colour(score: int) -> str:
    """shields.io's colours for a score out of 100."""
    return "#4c1" if score >= 80 else "#97ca00" if score >= 65 else "#dfb317" if score >= 50 else "#fe7d37" if score >= 35 else "#e05d44"


def _width(text: str) -> float:
    return sum(WIDTHS.get(c, 6.8) for c in text)


def badge(score: int, label: str = "repro-score") -> str:
    """The badge's SVG text.

    >>> 'repro-score' in badge(72) and '72/100' in badge(72) and '#97ca00' in badge(72)
    True
    """
    value = f"{score}/100"
    lw, vw = round(_width(label) + 10), round(_width(value) + 10)
    w = lw + vw
    lx, vx = lw * 5, (lw + vw / 2) * 10
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="{escape(label)}: {value}">'
        f"<title>{escape(label)}: {value}</title>"
        '<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>'
        f'<clipPath id="r"><rect width="{w}" height="20" rx="3" fill="#fff"/></clipPath>'
        f'<g clip-path="url(#r)"><rect width="{lw}" height="20" fill="#555"/><rect x="{lw}" width="{vw}" height="20" fill="{colour(score)}"/>'
        f'<rect width="{w}" height="20" fill="url(#s)"/></g>'
        '<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="110">'
        f'<text x="{lx}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)">{escape(label)}</text>'
        f'<text x="{lx}" y="140" transform="scale(.1)">{escape(label)}</text>'
        f'<text x="{vx:.0f}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)">{value}</text>'
        f'<text x="{vx:.0f}" y="140" transform="scale(.1)">{value}</text></g></svg>\n'
    )
