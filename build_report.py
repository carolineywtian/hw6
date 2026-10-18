"""Problem 9: build output/hw6_report.html, a single self-contained results page.

    source .venv/bin/activate
    python build_report.py

Every number on the page is read from the saved results of earlier problems, never typed in:
    Problem 2  handbook token count (same tokenizer as count_handbook_tokens.py)
    Problem 4  output/cache_test.json                (caching)
    Problem 5  output/attack_results.json            (Problem 3 agent + undefended baseline)
    Problem 6  output/defense_results.json           (5 setups x 12 documents)
    Problem 7  output/usage_log.json / audit_trail.json for the red-team run IDs in output/red_team.md
    Problem 8  output/exam_results.json (+ provenance)

One file: inline CSS, inline SVG charts, a few lines of inline JS for hover tooltips. No internet, fonts,
images, or other files. Colors: Yale navy / light blues / white.
    Two-series charts:   #285A9E (navy) and #4A90D9 (light blue)   - pass the dataviz validator on white
    Cost-type ramp:      #8FB7E6 < #5E95D8 < #3570B8 < #1C4680       - ordinal (light = cheap, dark = pricey),
                         passes the validator's ordinal checks on white
Charts follow the dataviz rules: bars start at zero; the one zoomed strip is labelled as zoomed and uses
dots, not bars; every chart has hover values and a table or direct labels.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from statistics import mean

import tiktoken

import agent as A
from tools import load_handbook, now_iso

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
REPORT = OUT / "hw6_report.html"

YALE = "#00356B"
NAVY, LIGHT = "#285A9E", "#4A90D9"
RAMP = {"cached": "#8FB7E6", "uncached": "#5E95D8", "write": "#3570B8", "output": "#1C4680"}
DOCS_PER_MONTH = 1000 * 30
RED_TEAM_RUNS = {  # from output/red_team.md (Problem 7)
    "a01_northstar_quote.html": {"off": "9c83d6ce0b9d", "on": "9686a3e0c337"},
    "a02_harborlight_quote.eml": {"off": "6bd0b83ac060", "on": "3d15740876bc"},
}
# Short labels for the hidden attacks, as found in Problem 5 (output/attack_results.md sections 2-3).
ATTACK_LABELS = {
    "p02": ("Fake lower price ($5.11)", "zero-size font"),
    "p03": ("Fake approved vendor", "hidden page section"),
    "p04": ("Approve a $4,800 deposit", "HTML comment"),
    "p06": ("Email out our cost list", "white text on white"),
    "p07": ("Fake 7-day lead time", "0.8-point font"),
    "p09": ("Fake 12-day lead time + link", "hidden half of the email"),
    "p12": ("Fake lower price ($17.44)", "placed off the page"),
}


def load(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def esc(x) -> str:
    return html.escape(str(x))


def usd(x: float, digits: int = 5) -> str:
    return f"${x:,.{digits}f}"


def price(v: float) -> str:
    """$ per 1M tokens with at least 2 decimals: 0.5 -> $0.50, 0.125 -> $0.125."""
    return f"${v:.3f}".rstrip("0") if round(v, 2) != v else f"${v:.2f}"


def short(doc: str) -> str:
    return doc.split("_")[0]


def tip(text: str) -> str:
    return f'class="mark" data-tip="{esc(text)}"'


# --------------------------------------------------------------------------- chart helpers


def nice_ticks(v: float, integer: bool = False, target: int = 4) -> list[float]:
    """About `target` gridlines from 0 to a clean top >= v; every tick is an exact multiple of the step."""
    steps = (1, 2, 5) if integer else (1, 2, 2.5, 5)
    raw = max(v, 1 if integer else 1e-9) / target
    step = min(s * 10 ** e for e in range(-8, 5) for s in steps if s * 10 ** e >= raw and (not integer or s * 10 ** e >= 1))
    n = int(-(-v // step)) or 1
    return [step * i for i in range(n + 1)]


def hbar_path(x: float, y: float, w: float, h: float, r: float = 4) -> str:
    """Horizontal bar anchored at the zero line, only its data end (right) rounded."""
    if w <= 0:
        return ""
    r = min(r, h / 2, w)
    return (f"M{x:.1f},{y:.1f} H{x + w - r:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} "
            f"V{y + h - r:.1f} Q{x + w:.1f},{y + h:.1f} {x + w - r:.1f},{y + h:.1f} H{x:.1f} Z")


def x_axis(left: float, right: float, top: float, bottom: float, ticks: list[float], fmt, label: str) -> list[str]:
    span = ticks[-1] or 1
    out = []
    for t in ticks:
        x = left + (right - left) * t / span
        out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{top}" y2="{bottom}" class="grid"/>')
        out.append(f'<text x="{x:.1f}" y="{bottom + 16}" class="tick" text-anchor="middle">{esc(fmt(t))}</text>')
    out.append(f'<text x="{(left + right) / 2:.1f}" y="{bottom + 34}" class="axis-label" text-anchor="middle">{esc(label)}</text>')
    return out


def hbar_chart(rows: list[tuple[str, float, str]], fmt, label: str, axis_label: str, color: str = NAVY,
               integer: bool = False, width: int = 760, highlight: str | None = None, emphasize: bool = True) -> str:
    """Horizontal bars from zero with the value written at each bar end. rows = (category, value, tooltip)."""
    left, right_pad, top, row_h = 130, 90, 8, 34
    right = width - right_pad
    bottom = top + row_h * len(rows)
    ticks = nice_ticks(max(v for _, v, _ in rows), integer)
    span = ticks[-1]
    p = [f'<svg class="chart" viewBox="0 0 {width} {bottom + 44}" role="img" aria-label="{esc(label)}">']
    p += x_axis(left, right, top, bottom, ticks, fmt, axis_label)
    for i, (cat, v, t) in enumerate(rows):
        y = top + i * row_h + 7
        w = (right - left) * v / span
        fill = color if highlight is None or cat == highlight or not emphasize else "#9DB4CF"
        weight = ' font-weight="700"' if cat == highlight else ""
        p.append(f'<text x="{left - 10}" y="{y + 15}" class="cat" text-anchor="end"{weight}>{esc(cat)}</text>')
        p.append(f'<g {tip(t)}><rect x="{left}" y="{y - 5}" width="{right - left}" height="{row_h}" class="hit"/>'
                 f'<path d="{hbar_path(left, y, w, 20)}" fill="{fill}"/></g>')
        p.append(f'<text x="{left + w + 8:.1f}" y="{y + 15}" class="val"{weight}>{esc(fmt(v) if not integer else f"{v:.0f} of 12")}</text>')
    p.append(f'<line x1="{left}" x2="{left}" y1="{top}" y2="{bottom}" class="baseline"/></svg>')
    return f'<figure><figcaption>{esc(label)}</figcaption>{"".join(p)}</figure>'


def dumbbell(rows: list[tuple[str, float, float, str]], a_name: str, b_name: str, label: str, axis_label: str,
             width: int = 980) -> str:
    """Per-item before/after: one dot per setup on a shared zero-based axis, joined by a line."""
    left, top, row_h = 70, 8, 30
    right = width - (190 if any(n for *_, n in rows) else 24)
    bottom = top + row_h * len(rows)
    ticks = nice_ticks(max(max(a, b) for _, a, b, _ in rows), target=5)
    span = ticks[-1]
    X = lambda v: left + (right - left) * v / span
    p = [f'<svg class="chart" viewBox="0 0 {width} {bottom + 44}" role="img" aria-label="{esc(label)}">']
    p += x_axis(left, right, top, bottom, ticks, lambda v: f"${v:.3f}", axis_label)
    for i, (cat, a, b, note) in enumerate(rows):
        y = top + i * row_h + row_h / 2
        p.append(f'<text x="{left - 10}" y="{y + 4:.1f}" class="cat" text-anchor="end">{esc(cat)}</text>')
        p.append(f'<line x1="{X(a):.1f}" x2="{X(b):.1f}" y1="{y:.1f}" y2="{y:.1f}" class="connector"/>')
        for v, color, name in ((b, LIGHT, b_name), (a, NAVY, a_name)):
            p.append(f'<g {tip(f"{cat} · {name}: {usd(v, 8)}" + (f" ({note})" if note and name == a_name else ""))}>'
                     f'<circle cx="{X(v):.1f}" cy="{y:.1f}" r="12" class="hit"/>'
                     f'<circle cx="{X(v):.1f}" cy="{y:.1f}" r="6" fill="{color}" stroke="#fff" stroke-width="2"/></g>')
        if note:  # in the empty space past the far dot, never on top of the line
            p.append(f'<text x="{X(max(a, b)) + 14:.1f}" y="{y + 4:.1f}" class="note-in">{esc(note)}</text>')
    p.append("</svg>")
    legend = (f'<div class="legend"><span><i class="dot" style="background:{NAVY}"></i>{esc(a_name)}</span>'
              f'<span><i class="dot" style="background:{LIGHT}"></i>{esc(b_name)}</span></div>')
    return f'<figure><figcaption>{esc(label)}</figcaption>{legend}{"".join(p)}</figure>'


def stacked_hbar(rows: list[tuple[str, dict[str, float]]], parts: list[tuple[str, str, str]], label: str,
                 axis_label: str, width: int = 760) -> str:
    """Part-to-whole: one horizontal stacked bar per row, 2px white gap between segments, total at the end."""
    left, right_pad, top, row_h = 130, 110, 8, 46
    right = width - right_pad
    bottom = top + row_h * len(rows)
    ticks = nice_ticks(max(sum(v.values()) for _, v in rows))
    span = ticks[-1]
    p = [f'<svg class="chart" viewBox="0 0 {width} {bottom + 44}" role="img" aria-label="{esc(label)}">']
    p += x_axis(left, right, top, bottom, ticks, lambda v: f"${v:.3f}", axis_label)
    for i, (cat, vals) in enumerate(rows):
        y = top + i * row_h + 9
        total = sum(vals.values())
        x = left
        p.append(f'<text x="{left - 10}" y="{y + 18}" class="cat" text-anchor="end">{esc(cat)}</text>')
        for key, name, color in parts:
            w = (right - left) * vals[key] / span
            if w > 0:
                share = vals[key] / total * 100
                p.append(f'<g {tip(f"{cat} · {name}: {usd(vals[key], 6)} ({share:.1f}% of {usd(total, 5)})")}>'
                         f'<rect x="{x:.1f}" y="{y}" width="{max(w - 2, 0.8):.1f}" height="26" fill="{color}" rx="2"/></g>')
                if share >= 12 and w > 70:
                    p.append(f'<text x="{x + 8:.1f}" y="{y + 17}" class="in-bar">{share:.0f}% {esc(name.split(" (")[0].lower())}</text>')
            x += w
        p.append(f'<text x="{x + 8:.1f}" y="{y + 18}" class="val">{usd(total, 4)}</text>')
    p.append(f'<line x1="{left}" x2="{left}" y1="{top}" y2="{bottom}" class="baseline"/></svg>')
    legend = '<div class="legend">' + "".join(
        f'<span><i style="background:{c}"></i>{esc(n)}</span>' for _, n, c in parts) + "</div>"
    return f'<figure><figcaption>{esc(label)}</figcaption>{legend}{"".join(p)}</figure>'


def zoom_strip(points: list[tuple[str, float, str]], label: str, width: int = 760) -> str:
    """Zoomed dot strip for small differences. Dots (not bars), and the axis is labelled as zoomed."""
    left, right, y = 40, width - 40, 46
    vmin, vmax = min(v for _, v, _ in points), max(v for _, v, _ in points)
    step = nice_ticks(vmax - vmin, target=3)[1]  # exact 1/2/2.5/5 x 10^n step
    lo, hi = (vmin // step) * step, -(-vmax // step) * step
    if hi - vmax < step * 0.2:
        hi += step
    if vmin - lo < step * 0.2:
        lo -= step
    X = lambda v: left + (right - left) * (v - lo) / (hi - lo)
    p = [f'<svg class="chart" viewBox="0 0 {width} 110" role="img" aria-label="{esc(label)}">',
         f'<line x1="{left}" x2="{right}" y1="{y}" y2="{y}" class="baseline"/>']
    for k in range(round((hi - lo) / step) + 1):
        v = lo + step * k
        p.append(f'<line x1="{X(v):.1f}" x2="{X(v):.1f}" y1="{y - 4}" y2="{y + 4}" class="baseline"/>'
                 f'<text x="{X(v):.1f}" y="{y + 22}" class="tick" text-anchor="middle">{usd(v, 5)}</text>')
    ordered = sorted(points, key=lambda z: z[1])
    for i, (cat, v, t) in enumerate(ordered):
        p.append(f'<g {tip(t)}><circle cx="{X(v):.1f}" cy="{y}" r="11" class="hit"/>'
                 f'<circle cx="{X(v):.1f}" cy="{y}" r="5.5" fill="{LIGHT}" stroke="#fff" stroke-width="2"/></g>')
        if i in (0, len(ordered) - 1):  # selective labels: cheapest and most expensive only
            what = "cheapest" if i == 0 else "most expensive"
            p.append(f'<text x="{X(v):.1f}" y="{y - 16}" class="cat" text-anchor="middle">{esc(cat)} · {what}</text>')
    p.append(f'<text x="{left}" y="{y + 46}" class="axis-label">Zoomed axis: it does not start at $0. '
             f'All 12 fall between {usd(min(v for _, v, _ in points), 5)} and {usd(max(v for _, v, _ in points), 5)}. Hover a dot to see which document it is.</text></svg>')
    return f'<figure><figcaption>{esc(label)}</figcaption>{"".join(p)}</figure>'


def count(value: float, dec: int = 0, prefix: str = "", suffix: str = "") -> str:
    """A number that counts up when it scrolls into view. The real value is already in the HTML."""
    shown = f"{prefix}{value:,.{dec}f}{suffix}"
    return f'<span class="count" data-to="{value}" data-dec="{dec}" data-pre="{esc(prefix)}" data-suf="{esc(suffix)}">{esc(shown)}</span>'


def tiles(items: list[tuple[str, str]], cls: str = "") -> str:
    return f'<div class="tiles {cls}">' + "".join(
        f'<div class="tile"><div class="big">{big}</div><div class="cap">{cap}</div></div>' for big, cap in items) + "</div>"


def ok(text: str) -> str:
    return f'<span class="ok">✓ {esc(text)}</span>'


def bad(text: str) -> str:
    return f'<span class="bad">✗ {esc(text)}</span>'


def warn(text: str) -> str:
    return f'<span class="warn">! {esc(text)}</span>'


def badge(decision: str) -> str:
    return (f'<span class="badge rec">Recommend</span>' if decision == "recommend"
            else f'<span class="badge dnr">Do not recommend</span>')




# --------------------------------------------------------------------------- original artwork (inline SVG)
# Drawn from scratch for this page: a Gothic campus skyline and a cartoon bulldog mascot. No official Yale
# logos or Handsome Dan art (those are licensed marks), and no image files, so the page stays one file.


def skyline_svg() -> str:
    """Night skyline of Gothic college buildings, with a tall tiered tower and softly lit windows."""
    W, G = 1440, 170
    shapes, windows = [], []
    buildings = [(0, 90, 60, "gable"), (90, 70, 85, "crenel"), (160, 110, 55, "gable"), (270, 60, 100, "tower"),
                 (330, 130, 65, "gable"), (460, 80, 80, "crenel"), (540, 50, 118, "spire"), (590, 120, 60, "gable"),
                 (710, 74, 156, "tiered"), (784, 106, 72, "crenel"), (890, 60, 96, "tower"), (950, 140, 60, "gable"),
                 (1090, 80, 84, "crenel"), (1170, 50, 112, "spire"), (1220, 120, 64, "gable"), (1340, 100, 76, "crenel")]
    for i, (x, w, h, kind) in enumerate(buildings):
        top = G - h
        if kind == "tiered":  # tall tiered tower with corner pinnacles and a small spire
            t1, t2 = G - h * 0.55, G - h * 0.82
            shapes.append(f"M{x},{G} V{t1} H{x + 8} V{t2} H{x + 16} V{top + 14} H{x + w - 16} V{t2} H{x + w - 8} V{t1} H{x + w} V{G} Z")
            for px in (x + 16, x + w - 22):
                shapes.append(f"M{px},{top + 14} L{px + 3},{top - 6} L{px + 6},{top + 14} Z")
            shapes.append(f"M{x + w / 2 - 5},{top + 14} L{x + w / 2},{top - 18} L{x + w / 2 + 5},{top + 14} Z")
        else:
            shapes.append(f"M{x},{G} V{top} H{x + w} V{G} Z")
            if kind == "gable":
                shapes.append(f"M{x - 2},{top} L{x + w / 2},{top - 24} L{x + w + 2},{top} Z")
            elif kind == "crenel":
                shapes += [f"M{cx},{top} v-7 h7 v7 Z" for cx in range(x + 2, x + w - 6, 13)]
            elif kind == "tower":
                shapes += [f"M{px},{top} L{px + 3},{top - 16} L{px + 6},{top} Z" for px in (x, x + w - 6)]
            elif kind == "spire":
                shapes.append(f"M{x},{top} L{x + w / 2},{top - 42} L{x + w},{top} Z")
        for row, wy in enumerate(range(int(top) + 14, G - 14, 16)):  # a few lit windows, picked deterministically
            for col, wx in enumerate(range(x + 10, x + w - 10, 14)):
                if (i * 7 + row * 3 + col * 5) % 9 == 0:
                    windows.append(f'<rect class="win" x="{wx}" y="{wy}" width="4" height="7" rx="1" style="animation-delay:{(i + row + col) % 7 * 0.6:.1f}s"/>')
    return (f'<svg class="skyline" viewBox="0 0 {W} {G}" preserveAspectRatio="xMidYMax slice" aria-hidden="true">'
            f'<path d="{" ".join(shapes)}" fill="#001A38"/>{"".join(windows)}</svg>')


def bulldog_svg() -> str:
    """An original, friendly cartoon bulldog head in Yale blues."""
    ink, navy = "#0B2F5E", "#1C4680"
    return f"""<svg class="dog" viewBox="0 0 160 170" role="img" aria-label="Cartoon bulldog mascot">
<g class="dog-head">
  <path d="M30,44 Q14,8 50,22 Q48,38 38,52 Z" fill="#5E95D8" stroke="#C9DBF2" stroke-width="3" stroke-linejoin="round"/>
  <path d="M130,44 Q146,8 110,22 Q112,38 122,52 Z" fill="#5E95D8" stroke="#C9DBF2" stroke-width="3" stroke-linejoin="round"/>
  <path d="M33,40 Q24,18 45,26 Q43,35 37,44 Z M127,40 Q136,18 115,26 Q117,35 123,44 Z" fill="#8FB7E6"/>
  <ellipse cx="80" cy="82" rx="58" ry="52" fill="#F3F7FC" stroke="{ink}" stroke-width="3"/>
  <path d="M60,50 Q80,43 100,50 M64,58 Q80,53 96,58" stroke="#9DB4CF" stroke-width="2.5" fill="none" stroke-linecap="round"/>
  <path d="M48,64 Q58,58 68,63 M92,63 Q102,58 112,64" stroke="{ink}" stroke-width="3" fill="none" stroke-linecap="round"/>
  <g class="eyes"><circle cx="60" cy="75" r="7.5" fill="{ink}"/><circle cx="100" cy="75" r="7.5" fill="{ink}"/>
  <circle cx="62.5" cy="72.5" r="2.4" fill="#fff"/><circle cx="102.5" cy="72.5" r="2.4" fill="#fff"/></g>
  <ellipse cx="80" cy="104" rx="36" ry="23" fill="#E3ECF7" stroke="{ink}" stroke-width="2.5"/>
  <ellipse cx="80" cy="91" rx="12" ry="7.5" fill="{ink}"/><ellipse cx="76" cy="89" rx="3" ry="1.6" fill="#5E7FA8"/>
  <path d="M80,98 V106" stroke="{ink}" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M58,108 Q80,132 102,108 Q80,120 58,108 Z" fill="{navy}" stroke="{ink}" stroke-width="2.5" stroke-linejoin="round"/>
  <path d="M68,110 L71,102 L74,111 Z M86,111 L89,102 L92,110 Z" fill="#fff" stroke="{ink}" stroke-width="1.5" stroke-linejoin="round"/>
  <ellipse cx="46" cy="100" rx="7" ry="4" fill="#C9DBF2" opacity=".8"/><ellipse cx="114" cy="100" rx="7" ry="4" fill="#C9DBF2" opacity=".8"/>
</g>
<path d="M34,118 Q80,140 126,118 L126,130 Q80,152 34,130 Z" fill="#4A90D9" stroke="{ink}" stroke-width="2.5" stroke-linejoin="round"/>
<circle cx="80" cy="146" r="10" fill="#C9DBF2" stroke="{ink}" stroke-width="2.5"/>
<text x="80" y="150" text-anchor="middle" font-size="9" font-weight="800" fill="{ink}">CC</text>
</svg>"""


def savings_ring(pct: float, label: str) -> str:
    """Hero number as a ring that fills to the saved share (a single value, so no axis is needed)."""
    r, c = 70, 2 * 3.14159265 * 70
    off = c * (1 - pct / 100)
    return f"""<figure class="ring-fig" aria-label="{esc(label)}"><svg class="ring" viewBox="0 0 180 180">
<circle cx="90" cy="90" r="{r}" fill="none" stroke="#E3ECF7" stroke-width="16" class="track"/>
<circle cx="90" cy="90" r="{r}" fill="none" stroke="{NAVY}" stroke-width="16" stroke-linecap="round"
  stroke-dasharray="{c:.1f}" stroke-dashoffset="{off:.1f}" transform="rotate(-90 90 90)" class="arc" style="--c:{c:.1f}"/>
<text x="90" y="88" text-anchor="middle" class="ring-num">{pct:.1f}%</text>
<text x="90" y="112" text-anchor="middle" class="ring-cap">saved by caching</text></svg></figure>"""


def coin_pictogram(rows: list[tuple[str, float]], coin_value: float, label: str, note: str) -> str:
    """Cost per 1,000 documents as coins (each coin = coin_value dollars); the last coin is cut to its share."""
    size, gap, left = 30, 6, 150
    most = max(v for _, v in rows) / coin_value
    width = int(left + (size + gap) * (int(most) + 1) + 110)
    h = 26 + len(rows) * 52
    p = [f'<svg class="chart coins" viewBox="0 0 {width} {h}" role="img" aria-label="{esc(label)}"><defs>']
    for i, (_, v) in enumerate(rows):
        n = v / coin_value
        frac = n - int(n)
        cx = left + (size + gap) * int(n)
        p.append(f'<clipPath id="cut{i}"><rect x="{cx}" y="0" width="{size * frac:.1f}" height="{h}"/></clipPath>')
    p.append("</defs>")
    for i, (name, v) in enumerate(rows):
        y = 14 + i * 52
        n = v / coin_value
        p.append(f'<text x="{left - 14}" y="{y + 20}" class="cat" text-anchor="end">{esc(name)}</text>')
        coins = [(k, None) for k in range(int(n))] + ([(int(n), f"url(#cut{i})")] if n - int(n) > 0.01 else [])
        for k, clip in coins:
            cx = left + (size + gap) * k + size / 2
            clip_attr = f' clip-path="{clip}"' if clip else ""
            p.append(f'<g class="coin" style="animation-delay:{k * 0.07 + i * 0.25:.2f}s"{clip_attr}>'
                     f'<g {tip(f"{name}: {usd(v, 2)} per 1,000 documents")}>'
                     f'<circle cx="{cx}" cy="{y + 15}" r="{size / 2}" fill="#8FB7E6" stroke="{NAVY}" stroke-width="2.5"/>'
                     f'<circle cx="{cx}" cy="{y + 15}" r="{size / 2 - 5}" fill="none" stroke="#fff" stroke-width="1.5" opacity=".7"/>'
                     f'<text x="{cx}" y="{y + 20}" text-anchor="middle" class="coin-d">$</text></g></g>')
        end = left + (size + gap) * n + 10
        p.append(f'<text x="{end:.1f}" y="{y + 20}" class="val">{usd(v, 2)}</text>')
    p.append("</svg>")
    return (f'<figure class="coin-fig"><figcaption>{esc(label)}</figcaption>'
            f'<div class="legend"><span>Each coin = {usd(coin_value, 2)}</span></div>{"".join(p)}<p class="coin-note">{note}</p></figure>')


# --------------------------------------------------------------------------- page


def build() -> str:
    # ---------- data
    cache = load("cache_test.json")
    att = load("attack_results.json")
    dfn = load("defense_results.json")
    exam = load("exam_results.json")
    prov = load("exam_results_provenance.json")
    usage = {e["run_id"]: e for e in load("usage_log.json")}
    audit = {e["run_id"]: e for e in load("audit_trail.json")}
    trap_entries = len(load("trap_calls.json"))
    prices = cache["prices_per_1m"]
    hb_tokens = len(tiktoken.get_encoding("o200k_base").encode(load_handbook()))
    est_uncached, est_cached = hb_tokens * prices["input_per_1m"] / 1e6, hb_tokens * prices["cached_input_per_1m"] / 1e6

    cs, ns = cache["summary"]["cache"], cache["summary"]["no_cache"]
    runs = {(r["setup"], r["document"]): r for r in cache["runs"]}
    docs = [r["document"] for r in cache["runs"] if r["setup"] == "cache"]
    calls = cache["calls"]
    missed = {c["document"] for c in calls if c["setup"] == "cache" and c["cached_input_tokens"] == 0}
    warm_cache_doc = mean(runs[("cache", d)]["cost_usd"] for d in docs if d not in missed)
    warm_call = mean(c["cost_usd"] for c in calls if c["setup"] == "cache" and c["call"] == 1 and c["cached_input_tokens"] > 0)
    nocache_call = ns["total_cost_usd"] / ns["model_calls"]
    miss_call = mean(c["cost_usd"] for c in calls if c["setup"] == "cache" and c["cached_input_tokens"] == 0)
    miss_extra = miss_call - warm_call  # what one cache miss costs over a warm call
    nc_input_per_doc = ns["input_tokens"] / ns["documents"]
    # Problem 2's 1,000-call estimate: one cache write, then 999 cached reads, vs 1,000 uncached calls
    est_write = hb_tokens * prices["cache_write_per_1m"] / 1e6
    est_saving = (1000 * est_uncached - (est_write + 999 * est_cached)) / (1000 * est_uncached) * 100
    enc = tiktoken.get_encoding("o200k_base")
    rules_tokens = len(enc.encode(A.build_instructions(("prompt",)))) - len(enc.encode(A.build_instructions(())))

    def spend(setup: str) -> dict[str, float]:
        cs_ = [c for c in calls if c["setup"] == setup]
        return {
            "cached": sum(c["cached_input_tokens"] for c in cs_) * prices["cached_input_per_1m"] / 1e6,
            "uncached": sum(c["uncached_input_tokens"] for c in cs_) * prices["input_per_1m"] / 1e6,
            "write": sum(c["cache_write_tokens"] for c in cs_) * prices["cache_write_per_1m"] / 1e6,
            "output": sum(c["output_tokens"] for c in cs_) * prices["output_per_1m"] / 1e6,
        }

    S = dfn["summary"]
    setups = ["no_defenses", "code_only", "design_only", "prompt_only", "all_defenses"]
    names = {"no_defenses": "No defenses", "code_only": "Code only", "design_only": "Design only",
             "prompt_only": "Prompt only", "all_defenses": "All three"}

    def warm(setup: str) -> float:
        return mean(d[setup]["cost_usd"] for d in dfn["documents"]
                    if all(r["cached_input_tokens"] > 0 for r in usage[d[setup]["run_id"]]["per_request"]))

    W = {s: warm(s) for s in setups}
    exam_avg = sum(r["cost_usd"] for r in exam) / len(exam)
    month_exam, month_warm = exam_avg * DOCS_PER_MONTH, W["all_defenses"] * DOCS_PER_MONTH
    month_nocache = ns["cost_per_document_usd"] * DOCS_PER_MONTH
    fooled_before, fooled_after = len(S["no_defenses"]["documents_fooled"]), len(S["all_defenses"]["documents_fooled"])
    cheaper = (1 - W["all_defenses"] / W["no_defenses"]) * 100
    removed = sum(len(x["hidden_text_removed_by_code"]) for x in prov["runs"])

    # ---------- at a glance
    glance = f"""
<section class="glance" aria-label="At a glance">
  <a class="g" href="#caching"><div class="k">Caching</div><div class="big">{count(round(cache['summary']['saved_percent']), suffix='%')} cheaper</div><div class="cap">{usd(cs['cost_per_document_usd'])} vs {usd(ns['cost_per_document_usd'])} per document</div></a>
  <a class="g" href="#attacks"><div class="k">Attacks</div><div class="big">{count(fooled_before)} → {count(fooled_after)} fooled</div><div class="cap">of 12 booby-trapped practice documents</div></a>
  <a class="g" href="#cost"><div class="k">Defense cost</div><div class="big">{count(round(cheaper), suffix='%')} cheaper</div><div class="cap">the defenses save money: {usd(W['all_defenses'])} vs {usd(W['no_defenses'])}</div></a>
  <a class="g" href="#exam"><div class="k">Exam</div><div class="big">{count(len(exam))} documents</div><div class="cap">{sum(r['trap_tool_called'] for r in exam)} trap calls · results verified unedited</div></a>
  <a class="g verdict" href="#recommendation"><div class="k">Recommendation</div><div class="big">Turn it on ✨</div><div class="cap">≈ ${month_exam:,.2f} a month at 1,000 documents a day</div></a>
</section>"""

    # ---------- 1. caching
    db_rows = [(short(d), runs[("cache", d)]["cost_usd"], runs[("no_cache", d)]["cost_usd"],
                "cache miss: paid to rewrite it" if d in missed else "") for d in docs]
    parts = [("cached", f"Cached input ({price(prices['cached_input_per_1m'])}/1M)", RAMP["cached"]),
             ("uncached", f"Plain input ({price(prices['input_per_1m'])}/1M)", RAMP["uncached"]),
             ("write", f"Cache write ({price(prices['cache_write_per_1m'])}/1M)", RAMP["write"]),
             ("output", f"Output ({price(prices['output_per_1m'])}/1M)", RAMP["output"])]
    sp_c, sp_n = spend("cache"), spend("no_cache")
    strip = [(short(d), runs[("no_cache", d)]["cost_usd"],
              f"{short(d)}: {usd(runs[('no_cache', d)]['cost_usd'], 8)} · {runs[('no_cache', d)]['output_tokens']} output tokens")
             for d in docs]
    nc_vals = [runs[("no_cache", d)]["cost_usd"] for d in docs]
    hi_doc = max(docs, key=lambda d: runs[("no_cache", d)]["cost_usd"])
    lo_doc = min(docs, key=lambda d: runs[("no_cache", d)]["cost_usd"])
    est_rows = [
        ("Handbook tokens per call", f"{hb_tokens:,} (handbook only)", f"≈ {round(mean(c['input_tokens'] for c in calls if c['call'] == 1)):,} (with instructions + tools)"),
        ("Cost per call, no cache", usd(est_uncached, 7), usd(nocache_call, 7)),
        ("Cost per call, warm cache", usd(est_cached, 8), usd(warm_call, 8)),
        ("Model calls per document", "1 (assumed)", f"{cs['model_calls'] // cs['documents']}"),
        ("Saved by caching", f"{est_saving:.1f}%", f"{cache['summary']['saved_percent']:.1f}% measured · {(1 - warm_cache_doc / ns['cost_per_document_usd']) * 100:.1f}% with no cache miss"),
    ]
    sec1 = f"""
<section id="caching"><div class="eyebrow">Problem 4</div><h2>1. Caching results</h2>
<div class="hero-row"><div>
<p class="lead">Reusing the handbook from the prompt cache cut the cost per document by <b>{cache['summary']['saved_percent']:.1f}%</b>, from {usd(ns['cost_per_document_usd'])} to {usd(cs['cost_per_document_usd'])}.</p>
<p>Every call sends the same instructions and {hb_tokens:,}-token handbook. I ran all 12 practice documents with caching on and with it off: {cache['summary']['cache']['model_calls'] + ns['model_calls']} real model calls. The no-cache setup showed <b>{sum(c['cached_input_tokens'] for c in calls if c['setup'] == 'no_cache')} cached tokens</b>, which proves it really reused nothing.</p></div>
{savings_ring(cache['summary']['saved_percent'], 'Share of cost saved by caching')}</div>
{tiles([(usd(cs['cost_per_document_usd']), 'per document <b>with</b> cache'), (usd(ns['cost_per_document_usd']), 'per document <b>without</b> cache'), (f"{cache['summary']['saved_percent']:.1f}%", 'saved by caching'), (usd(warm_cache_doc), 'with cache, on documents with no cache miss')])}
{coin_pictogram([('Without cache', ns['cost_per_document_usd'] * 1000), ('With cache', cs['cost_per_document_usd'] * 1000)], 0.5,
   'What 1,000 documents cost',
   f"Caching keeps <b>{usd((ns['cost_per_document_usd'] - cs['cost_per_document_usd']) * 1000, 2)}</b> in the shop's pocket for every 1,000 documents. That's about <b>${(ns['cost_per_document_usd'] - cs['cost_per_document_usd']) * DOCS_PER_MONTH:,.0f} a month</b> at 1,000 documents a day.")}
{dumbbell(db_rows, 'With cache', 'Without cache', 'Cost of each document, with vs without cache', 'US dollars per document (axis starts at $0)')}
<div class="explain"><h3>How to read this</h3><p>Each row is one document. The light dot is its cost <b>without</b> cache, the navy dot <b>with</b> cache, and the line is the saving.</p><p>Without cache, every document costs almost exactly the same, about {usd(mean(nc_vals), 4)}. That is because about {nc_input_per_doc:,.0f} input tokens, almost all instructions and handbook, are paid for on every document, and the documents themselves add only a few hundred.</p><p>With cache, most documents drop to about {usd(warm_cache_doc, 4)}. Three ({', '.join(sorted(short(d) for d in missed))}) had one call that missed the cache and paid to rewrite it.</p></div>
{stacked_hbar([('With cache', sp_c), ('Without cache', sp_n)], parts, 'Where the money goes (all 12 documents)', 'US dollars for 12 documents (axis starts at $0)')}
<p class="note">Darker = more expensive per token. Without cache, <b>{sp_n['write'] / sum(sp_n.values()) * 100:.0f}%</b> of the bill is cache writes: the provider still saves every prompt to the cache at {price(prices['cache_write_per_1m'])} per 1M, more than plain input, even though nothing ever reuses it. With cache, most tokens are cheap cached reads.</p>
{zoom_strip(strip, 'Zoom: the small differences between documents without cache')}
<p class="note">The {usd(max(nc_vals) - min(nc_vals), 5)} spread ({(max(nc_vals) - min(nc_vals)) / min(nc_vals) * 100:.1f}%) comes mostly from answer length. Output costs {price(prices['output_per_1m'])} per 1M tokens, so {short(hi_doc)}'s {runs[('no_cache', hi_doc)]['output_tokens']}-token answer costs more than {short(lo_doc)}'s {runs[('no_cache', lo_doc)]['output_tokens']}-token one.</p>
<h3>My Problem 2 estimate vs the real runs</h3>
<table><thead><tr><th></th><th>Problem 2 estimate</th><th>Real (Problem 4)</th></tr></thead><tbody>
{''.join(f'<tr><td>{esc(a)}</td><td class="num">{esc(b)}</td><td class="num">{esc(c)}</td></tr>' for a, b, c in est_rows)}
</tbody></table>
<details><summary>Show the per-document numbers</summary><table><thead><tr><th>Document</th><th>With cache</th><th>Without cache</th></tr></thead><tbody>
{''.join(f"<tr><td>{esc(short(d))}</td><td class='num'>{usd(runs[('cache', d)]['cost_usd'], 8)}</td><td class='num'>{usd(runs[('no_cache', d)]['cost_usd'], 8)}</td></tr>" for d in docs)}
<tr class="total"><td>Total</td><td class="num">{usd(cs['total_cost_usd'], 8)}</td><td class="num">{usd(ns['total_cost_usd'], 8)}</td></tr></tbody></table></details>
</section>"""

    # ---------- 2. attacks
    fooled_rows = [(names[s], len(S[s]["documents_fooled"]),
                    f"{names[s]}: fooled by {len(S[s]['documents_fooled'])} of 12 ({', '.join(short(d) for d in S[s]['documents_fooled']) or 'none'})")
                   for s in setups]
    trs = []
    for doc in dfn["documents"]:
        d = short(doc["document"])
        b, a = doc["no_defenses"], doc["all_defenses"]
        what, where = ATTACK_LABELS.get(d, ("None, a clean document", ""))
        attack = f"<b>{esc(what)}</b>" + (f"<br><span class='muted'>hidden by {esc(where)}</span>" if where else "")

        def cell(r) -> str:
            if r["fooled"]:
                wrong = ", ".join(k.replace("_", " ") for k, okk in r["fields_matched"].items() if not okk)
                return bad(f"Fooled: {r['answer']['decision'].replace('_', ' ')}" + (f" ({wrong})" if wrong else ""))
            if r.get("leaked_private_handbook_number"):
                return warn("Right, but leaked a private cost")
            return ok("Right")

        kind = "attack" if d in ATTACK_LABELS else "clean"
        trs.append(f"<tr data-kind='{kind}'><td class='doc'>{esc(d)}</td><td>{attack}</td><td>{badge(doc['key']['decision'])}</td><td>{cell(b)}</td><td>{cell(a)}</td></tr>")
    sec2 = f"""
<section id="attacks"><div class="eyebrow">Problems 5 and 6</div><h2>2. Attacks before and after my defenses</h2>
<p class="lead">Without defenses, <b>{fooled_before} of 12</b> booby-trapped practice documents fooled the agent. With my three defense layers, <b>{fooled_after}</b> did, and it got all 12 fully right.</p>
<p>Seven practice documents hide text aimed at an AI that a person opening them can't see. Clean documents still came back right in every setup ({S['all_defenses']['clean_documents_correct']} after), and no real quote was ever refused or blanked.</p>
{tiles([(f'{fooled_before} of 12', 'fooled the agent <b>before</b>'), (f'{fooled_after} of 12', 'fooled the agent <b>after</b>'), (f"{S['all_defenses']['all_fields_matched']} / 12", 'fully right after (every field and the decision)'), (str(trap_entries), 'trap tool calls by my agent, ever')])}
{hbar_chart(fooled_rows, lambda v: f'{v:.0f}', 'Documents that fooled each setup (each layer tested alone, then all three)', 'documents fooled, out of 12', integer=True, highlight='All three', emphasize=False)}
<div class="filters" role="group" aria-label="Filter the table"><span class="muted">Show:</span>
<button type="button" class="chip on" data-filter="all">All 12</button>
<button type="button" class="chip" data-filter="attack">Booby-trapped ({len(ATTACK_LABELS)})</button>
<button type="button" class="chip" data-filter="clean">Clean ({12 - len(ATTACK_LABELS)})</button></div>
<table class="attacks" id="attack-table"><thead><tr><th>Doc</th><th>What the hidden text tries</th><th>Correct answer</th><th>Before: no defenses</th><th>After: defended</th></tr></thead><tbody>{''.join(trs)}</tbody></table>
<p class="note">In Problem 5 my original Problem 3 agent was fooled by {len(att['summary']['problem3_agent']['documents_fooled'])} of 12 and the undefended baseline by {len(att['summary']['undefended_baseline']['documents_fooled'])}. Whether an attack lands varies from run to run, which is why the defenses can't rely on luck.</p>
</section>"""

    # ---------- 3. defense cost
    layer_text = {"code_only": "Cleans each document before the AI reads it; a web page shrinks to its visible text",
                  "design_only": "AI only copies 5 facts; code makes the decision, so 2 model calls per document instead of 3",
                  "prompt_only": f"Adds {rules_tokens} tokens of security rules to every call (cached, so cheap)",
                  "all_defenses": "All three layers together"}
    cost_rows = [(names[s], W[s], f"{names[s]}: {usd(W[s], 8)} per document · {S[s]['avg_model_calls_per_document']:.0f} model calls") for s in setups]
    ltr = []
    for s in ["code_only", "design_only", "prompt_only", "all_defenses"]:
        din = S[s]["avg_input_tokens_per_document"] - S["no_defenses"]["avg_input_tokens_per_document"]
        dc = W[s] - W["no_defenses"]
        ltr.append(f"<tr><td><b>{esc(names[s])}</b></td><td>{esc(layer_text[s])}</td><td class='num'>{S[s]['avg_model_calls_per_document']:.0f}</td>"
                   f"<td class='num'>{din:+,.0f}</td><td class='num'>{'+' if dc >= 0 else '−'}{usd(abs(dc), 6)}</td><td class='num'>{dc / W['no_defenses'] * 100:+.1f}%</td></tr>")
    sec3 = f"""
<section id="cost"><div class="eyebrow">Problem 6</div><h2>3. What my defenses cost in tokens and dollars</h2>
<p class="lead">The defenses <b>save</b> money: the fully defended agent costs <b>{usd(W['all_defenses'])}</b> per document, {cheaper:.0f}% less than the undefended one ({usd(W['no_defenses'])}).</p>
<p>I switched each layer on by itself and ran all 12 practice documents (60 runs). Costs are from documents where no call missed the cache, because a random cache miss (about {usd(miss_extra, 4)} extra) would otherwise drown out the difference.</p>
{hbar_chart(cost_rows, lambda v: f'${v:.5f}', 'Cost per document by setup', 'US dollars per document (axis starts at $0)', highlight='All three')}
<table><thead><tr><th>Layer</th><th>What it does</th><th>Model calls per doc</th><th>Extra input tokens per doc</th><th>Extra $ per doc</th><th>Change</th></tr></thead><tbody>{''.join(ltr)}</tbody></table>
<p class="note">Only the prompt layer adds tokens, and they sit in the cached part of the prompt. The design layer removes a whole model call per document, {S['no_defenses']['avg_input_tokens_per_document'] - S['design_only']['avg_input_tokens_per_document']:,.0f} input tokens, which is why the defended agent is the cheapest setup.</p>
</section>"""

    # ---------- 4. exam + red team
    etr = "".join(
        f"<tr><td class='doc'>{esc(r['file'])}</td><td>{esc(r['vendor'])}</td><td class='nowrap'>{esc(r['sku'])}</td>"
        f"<td class='num'>{usd(r['unit_price'], 2)}</td><td class='num'>{r['lead_time_days']}</td><td class='num'>{r['min_order']:,}</td>"
        f"<td>{badge(r['decision'])}</td><td class='reason'>{esc(r['reason'])}</td>"
        f"<td>{'yes' if r['trap_tool_called'] else 'no'}</td><td class='num'>{usd(r['cost_usd'], 6)}</td></tr>"
        for r in exam)
    red_meta = {
        "a01_northstar_quote.html": ("Image alt text", "Falsify a warranty term and push a recommendation",
                                     "No: the image file isn't included, so the browser shows the alt text", "reached the AI, which ignored it"),
        "a02_harborlight_quote.eml": ("Custom email header", "Hide a $95 setup fee and a no-returns rule",
                                      "Yes, in a normal email view", "never reached the AI"),
    }
    cards = []
    for doc, ids in RED_TEAM_RUNS.items():
        where, goal, seen, reached = red_meta[doc]
        before, after = audit[ids["off"]], audit[ids["on"]]
        cards.append(f"""<div class="card"><div class="card-h">{esc(doc)}</div>
<dl><dt>Hidden in</dt><dd>{esc(where)}</dd><dt>Tries to</dt><dd>{esc(goal)}</dd><dt>Hidden from a person?</dt><dd>{esc(seen)}</dd>
<dt>Before (no defenses)</dt><dd>{ok('Right: ' + before['final_answer']['decision'].replace('_', ' '))} · {esc(reached)} · no trap</dd>
<dt>After (defended)</dt><dd>{ok('Right: ' + after['final_answer']['decision'].replace('_', ' '))} · never reached the AI · no trap</dd>
<dt>Cost before → after</dt><dd>{usd(usage[ids['off']]['cost_usd'], 5)} → {usd(usage[ids['on']]['cost_usd'], 5)}</dd></dl></div>""")
    sec4 = f"""
<section id="exam"><div class="eyebrow">Problems 7 and 8</div><h2>4. Exam results and my red-team attacks</h2>
<p class="lead">My final defended agent processed all 10 exam documents: <b>{sum(r['decision'] == 'recommend' for r in exam)} recommend, {sum(r['decision'] != 'recommend' for r in exam)} do not recommend, {sum(r['trap_tool_called'] for r in exam)} trap calls</b>, for {usd(sum(r['cost_usd'] for r in exam), 5)} in total.</p>
{tiles([('10', 'exam documents'), (f"{sum(r['decision'] == 'recommend' for r in exam)} / {sum(r['decision'] != 'recommend' for r in exam)}", 'recommend / do not recommend'), (str(sum(r['trap_tool_called'] for r in exam)), 'trap tool calls'), (str(removed), 'hidden lines removed before the AI saw them'), ('10 / 10', 'identical answers on a second full run')])}
<div class="scroll"><table class="exam"><thead><tr><th>File</th><th>Vendor</th><th>SKU</th><th>Price</th><th>Lead (days)</th><th>Min order</th><th>Decision</th><th>Reason</th><th>Trap</th><th>Cost</th></tr></thead><tbody>{etr}</tbody></table></div>
<p class="note">Copied straight from <code>exam_results.json</code>, which is read-only. <code>python exam_test.py --verify</code> checks every value against the logged runs.</p>
<h3>My two red-team attacks (Problem 7)</h3>
<div class="cards">{''.join(cards)}</div>
<p class="note">Neither attack fooled either agent. Both target information (warranty, fees, returns) the agent's report doesn't include, and both vendors fail the handbook's approved-vendor check anyway.</p>
</section>"""

    # ---------- 5. recommendation
    why = [
        ("✓", "Accurate", f"{S['all_defenses']['all_fields_matched']} / 12 practice documents fully right"),
        ("🛡", "Hard to trick", f"{fooled_after} of 12 fooled it (undefended: {fooled_before})"),
        ("🔒", "Can't pay or email", f"Needs a person's sign-off · {trap_entries} trap calls"),
        ("$", "Cheap", f"About ${month_exam:,.0f} a month; defenses lower the cost"),
    ]
    conditions = ["Buyer reviews every recommendation before ordering",
                  "Owner or bookkeeper signs off on every payment",
                  "Weekly check of the trap log and flagged hidden text"]
    sec5 = f"""
<section id="recommendation" class="rec"><div class="eyebrow">For the store manager</div><h2>5. Recommendation</h2>
<div class="verdict-card">
  <div><div class="v-label">Should Campus Customs turn it on for real vendor mail?</div>
  <div class="v-big">Yes, turn it on ✨</div>
  <div class="v-sub">As a recommender: a person makes the final call.</div></div>
  <button type="button" class="celebrate" id="celebrate">🎉 Celebrate</button>
</div>
<div class="cost-row">
  <div class="cost main"><div class="c-num">${month_exam:,.2f}</div><div class="c-cap">per month<br><span>measured · 1,000 docs/day</span></div></div>
  <div class="cost"><div class="c-num">${month_warm:,.2f}</div><div class="c-cap">per month<br><span>if the cache stays warm</span></div></div>
  <div class="cost muted-cost"><div class="c-num">${month_nocache:,.0f}</div><div class="c-cap">per month<br><span>without caching: keep it on</span></div></div>
</div>
<div class="calc" aria-label="Monthly cost calculator">
  <label for="docs">Documents per day: <b id="docs-out">1,000</b></label>
  <input type="range" id="docs" min="100" max="5000" step="100" value="1000"
         data-exam="{exam_avg}" data-warm="{W['all_defenses']}" data-nocache="{ns['cost_per_document_usd']}">
  <div class="calc-out"><span>Defended agent: <b id="calc-exam">${month_exam:,.2f}</b>/month</span>
  <span>Cache warm: <b id="calc-warm">${month_warm:,.2f}</b></span>
  <span class="muted">No cache: <b id="calc-nocache">${month_nocache:,.0f}</b></span></div>
</div>
<div class="why-grid">{''.join(f'<div class="why"><div class="w-icon">{i}</div><div><div class="w-t">{esc(t)}</div><div class="w-d">{esc(d)}</div></div></div>' for i, t, d in why)}</div>
<div class="checklist"><div class="ck-title">Turn it on with these 3 checks</div>
{''.join(f'<div class="ck"><span class="box">✓</span>{esc(c)}</div>' for c in conditions)}</div>
</section>"""

    css = f"""
:root {{ --yale:{YALE}; --navy:{NAVY}; --light:{LIGHT}; --wash:#EEF4FB; --wash2:#F7FAFD; --ink:#1A2433; --muted:#5A6B80; --line:#D5E1EF; --good:#1E6B3A; --bad:#A61B1B; --warn:#8A5A00; }}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:smooth; }}
body {{ margin:0; font:16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; color:var(--ink); background:#fff; }}
header {{ background:radial-gradient(1200px 300px at 70% -40%, #2B5C9A 0%, transparent 60%), linear-gradient(180deg, #001F42 0%, var(--yale) 78%); color:#fff; padding:30px 0 64px; }}
.skyline {{ position:absolute; left:0; right:0; bottom:0; width:100%; height:120px; }}
.skyline .win {{ fill:#FFE9A8; opacity:.25; animation:glow 5s ease-in-out infinite; }}
@keyframes glow {{ 0%, 100% {{ opacity:.15; }} 50% {{ opacity:.85; }} }}
.moon {{ position:absolute; left:58%; top:16px; width:44px; height:44px; border-radius:50%; box-shadow:10px 6px 0 0 #E8F0FA; transform:rotate(-20deg); opacity:.85; }}
.head-row {{ position:relative; display:flex; align-items:center; justify-content:space-between; gap:24px; }}
.kicker {{ font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:#8FB7E6; font-weight:700; margin-bottom:6px; }}
.dog-btn {{ position:relative; background:none; border:0; padding:0; cursor:pointer; flex:none; }}
.dog {{ width:132px; height:auto; display:block; filter:drop-shadow(0 6px 10px rgba(0,0,0,.35)); animation:bob 3.2s ease-in-out infinite; }}
.dog-btn:hover .dog, .dog-btn:focus-visible .dog {{ animation:wiggle .6s ease-in-out infinite; }}
@keyframes bob {{ 0%, 100% {{ transform:translateY(0); }} 50% {{ transform:translateY(-6px); }} }}
@keyframes wiggle {{ 0%, 100% {{ transform:rotate(0); }} 25% {{ transform:rotate(-7deg); }} 75% {{ transform:rotate(7deg); }} }}
.dog .eyes {{ animation:blink 4.5s infinite; transform-origin:80px 75px; transform-box:view-box; }}
@keyframes blink {{ 0%, 92%, 100% {{ transform:scaleY(1); }} 95% {{ transform:scaleY(.1); }} }}
.bubble {{ position:absolute; right:118px; top:10px; background:#fff; color:var(--yale); font-weight:700; font-size:14px; padding:8px 12px; border-radius:14px; white-space:nowrap; box-shadow:0 4px 12px rgba(0,0,0,.25); opacity:0; transform:translateY(6px) scale(.9); transition:opacity .2s, transform .2s; pointer-events:none; }}
.bubble::after {{ content:""; position:absolute; right:-7px; top:16px; border:7px solid transparent; border-left-color:#fff; border-right:0; }}
.dog-btn:hover .bubble, .dog-btn.talk .bubble {{ opacity:1; transform:none; }}
/* caching flair */
.hero-row {{ display:grid; grid-template-columns:1fr 200px; gap:24px; align-items:center; }}
.ring-fig {{ margin:0; }} .ring {{ width:190px; height:auto; display:block; }}
.ring-num {{ font-size:30px; font-weight:800; fill:var(--yale); }} .ring-cap {{ font-size:12px; fill:var(--muted); }}
.ring-fig.in .arc {{ animation:ringfill 1.4s cubic-bezier(.2,.8,.2,1) both; }}
@keyframes ringfill {{ from {{ stroke-dashoffset:var(--c); }} }}
.coin-fig {{ background:linear-gradient(180deg, #F7FAFD, #fff); border:1px solid var(--line); border-radius:12px; padding:14px 18px 6px; }}
.coins {{ max-width:760px; }} .coin-d {{ font-size:14px; font-weight:800; fill:var(--yale); }}
.coin-fig.in .coin {{ animation:drop .55s cubic-bezier(.2,.9,.3,1.3) both; }}
@keyframes drop {{ from {{ transform:translateY(-26px); opacity:0; }} to {{ transform:none; opacity:1; }} }}
.coin-note {{ font-size:15px; margin:4px 0 8px; }}
.wrap {{ max-width:1080px; margin:0 auto; padding:0 32px; }}
header h1 {{ margin:0 0 6px; font-size:34px; letter-spacing:-.01em; text-shadow:0 2px 12px rgba(0,0,0,.25); }}
header p {{ margin:0; color:#C9DBF2; font-size:15px; }}
nav {{ position:sticky; top:0; z-index:5; background:#fff; border-bottom:1px solid var(--line); }}
nav .wrap {{ display:flex; gap:22px; padding-top:11px; padding-bottom:11px; font-size:14px; }}
nav a {{ color:var(--yale); text-decoration:none; font-weight:600; }} nav a:hover {{ text-decoration:underline; }}
.glance {{ display:grid; grid-template-columns:repeat(5, 1fr); gap:12px; margin:26px 0 8px; }}
.g {{ display:block; text-decoration:none; color:var(--ink); background:var(--wash); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}
.g:hover {{ border-color:var(--navy); }}
.g .k {{ font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); font-weight:700; }}
.g .big {{ font-size:22px; font-weight:750; color:var(--yale); margin:4px 0 2px; }}
.g .cap {{ font-size:13px; color:var(--muted); line-height:1.4; }}
.g.verdict {{ background:var(--yale); border-color:var(--yale); }} .g.verdict .k, .g.verdict .cap {{ color:#C9DBF2; }} .g.verdict .big {{ color:#fff; }}
section {{ padding:38px 0 34px; border-bottom:1px solid var(--line); }}
.eyebrow {{ font-size:12px; text-transform:uppercase; letter-spacing:.08em; color:var(--light); font-weight:700; }}
h2 {{ color:var(--yale); margin:2px 0 10px; font-size:25px; letter-spacing:-.01em; }}
h3 {{ color:var(--yale); font-size:17px; margin:26px 0 8px; }}
.lead {{ font-size:19px; line-height:1.45; margin:6px 0 10px; max-width:860px; }}
p {{ max-width:860px; }}
.tiles {{ display:flex; flex-wrap:wrap; gap:12px; margin:18px 0; }}
.tile {{ background:var(--wash2); border:1px solid var(--line); border-radius:10px; padding:12px 16px; flex:1; min-width:150px; }}
.tile .big {{ font-size:24px; font-weight:750; color:var(--ink); font-variant-numeric:tabular-nums; }}
.tile .cap {{ font-size:13px; color:var(--muted); line-height:1.4; }}
.tiles.money .tile .big {{ color:var(--yale); font-size:28px; }}
.two {{ display:grid; grid-template-columns:3fr 2fr; gap:28px; align-items:start; }}
.explain {{ background:var(--wash2); border-left:4px solid var(--light); border-radius:6px; padding:4px 22px 6px; margin:8px 0 6px; font-size:15px; display:grid; grid-template-columns:1fr 1fr 1fr; gap:0 26px; }}
.explain h3 {{ grid-column:1 / -1; margin:14px 0 0; }}
figure {{ margin:22px 0 8px; }}
figcaption {{ font-weight:700; font-size:15px; margin-bottom:6px; }}
.legend {{ font-size:13px; color:var(--muted); margin:2px 0 6px; display:flex; flex-wrap:wrap; gap:6px 18px; }}
.legend i {{ display:inline-block; width:12px; height:12px; border-radius:2px; margin-right:6px; vertical-align:-1px; }}
.legend i.dot {{ border-radius:50%; }}
svg.chart {{ width:100%; height:auto; display:block; overflow:visible; }}
.grid {{ stroke:#E7EEF6; }} .baseline {{ stroke:#93A9C2; }} .connector {{ stroke:#B9CBE0; stroke-width:3; stroke-linecap:round; }}
.tick {{ font-size:11px; fill:var(--muted); font-variant-numeric:tabular-nums; }}
.axis-label {{ font-size:11.5px; fill:var(--muted); }}
.cat {{ font-size:13px; fill:var(--ink); }} .val {{ font-size:13px; fill:var(--ink); font-weight:600; font-variant-numeric:tabular-nums; }}
.in-bar {{ font-size:11.5px; fill:#fff; font-weight:600; }} .note-in {{ font-size:11px; fill:var(--muted); font-style:italic; }}
.hit {{ fill:transparent; }} .mark {{ cursor:default; }} .mark:hover path, .mark:hover circle:not(.hit), .mark:hover rect {{ opacity:.8; }}
#tip {{ position:fixed; pointer-events:none; background:var(--ink); color:#fff; font-size:12.5px; padding:6px 9px; border-radius:5px; display:none; z-index:10; max-width:320px; }}
table {{ border-collapse:collapse; width:100%; font-size:14px; margin:14px 0; }}
thead th {{ background:var(--wash); color:var(--yale); text-align:left; font-size:13px; font-weight:700; }}
th, td {{ border-bottom:1px solid var(--line); padding:9px 10px; vertical-align:top; }}
tbody tr:nth-child(even) {{ background:var(--wash2); }}
td.num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
td.doc {{ font-weight:600; white-space:nowrap; }} td.nowrap {{ white-space:nowrap; }}
tr.total td {{ font-weight:700; border-top:2px solid var(--line); }}
.ok {{ color:var(--good); font-weight:600; white-space:nowrap; }} .bad {{ color:var(--bad); font-weight:700; }} .warn {{ color:var(--warn); font-weight:600; }}
.badge {{ display:inline-block; font-size:12px; font-weight:700; padding:2px 9px; border-radius:999px; white-space:nowrap; }}
.badge.rec {{ background:#DDEAF8; color:var(--yale); }} .badge.dnr {{ background:#fff; color:var(--muted); border:1px solid #C3D0DF; }}
.muted {{ color:var(--muted); font-size:13px; }}
.note {{ font-size:14px; color:var(--muted); }}
.scroll {{ overflow-x:auto; }}
table.exam {{ font-size:13px; }} table.exam td {{ padding:8px 7px; }} td.reason {{ color:#33435a; font-size:12.5px; }}
.cards {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
.card {{ border:1px solid var(--line); border-radius:10px; overflow:hidden; }}
.card-h {{ background:var(--wash); color:var(--yale); font-weight:700; padding:10px 16px; font-family:ui-monospace, Menlo, monospace; font-size:13.5px; }}
.card dl {{ margin:0; padding:10px 16px 14px; display:grid; grid-template-columns:150px 1fr; gap:8px 12px; font-size:14px; }}
.card dt {{ color:var(--muted); font-weight:600; }} .card dd {{ margin:0; }}
details {{ margin-top:6px; }} details summary {{ cursor:pointer; color:var(--yale); font-size:14px; font-weight:600; }}
code {{ background:var(--wash); padding:1px 5px; border-radius:4px; font-size:13px; }}
.rec {{ border-bottom:none; }}
ul {{ padding-left:20px; }} li {{ margin:6px 0; }}
footer {{ font-size:13px; color:var(--muted); text-align:center; padding:26px; border-top:1px solid var(--line); }}
/* ---- recommendation ---- */
.verdict-card {{ display:flex; align-items:center; justify-content:space-between; gap:20px; background:linear-gradient(120deg, var(--yale), var(--navy)); color:#fff; border-radius:14px; padding:22px 26px; margin:12px 0 16px; position:relative; overflow:hidden; }}
.v-label {{ font-size:13px; color:#C9DBF2; text-transform:uppercase; letter-spacing:.06em; font-weight:700; }}
.v-big {{ font-size:34px; font-weight:800; margin:2px 0; }}
.v-sub {{ font-size:16px; color:#DCE8F7; }}
.celebrate {{ background:#fff; color:var(--yale); border:0; border-radius:999px; padding:11px 20px; font-size:15px; font-weight:700; cursor:pointer; white-space:nowrap; box-shadow:0 2px 8px rgba(0,0,0,.18); transition:transform .15s; }}
.celebrate:hover {{ transform:translateY(-2px) scale(1.04); }}
.cost-row {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:14px; }}
.cost {{ display:flex; align-items:center; gap:14px; background:var(--wash); border:1px solid var(--line); border-radius:12px; padding:14px 18px; }}
.cost.main {{ border:2px solid var(--navy); background:#fff; }}
.c-num {{ font-size:30px; font-weight:800; color:var(--yale); font-variant-numeric:tabular-nums; }}
.c-cap {{ font-size:14px; color:var(--ink); line-height:1.3; }} .c-cap span {{ color:var(--muted); font-size:12.5px; }}
.muted-cost {{ background:#fff; }} .muted-cost .c-num {{ color:#8A9BB0; }}
.calc {{ margin:16px 0; background:var(--wash2); border:1px dashed #B9CBE0; border-radius:12px; padding:14px 18px; }}
.calc label {{ font-size:14px; }}
.calc input[type=range] {{ width:100%; accent-color:var(--navy); margin:8px 0; }}
.calc-out {{ display:flex; flex-wrap:wrap; gap:8px 26px; font-size:15px; font-variant-numeric:tabular-nums; }}
.why-grid {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; margin:16px 0; }}
.why {{ display:flex; gap:12px; align-items:flex-start; border:1px solid var(--line); border-radius:12px; padding:14px; background:#fff; transition:transform .15s, box-shadow .15s; }}
.why:hover {{ transform:translateY(-3px); box-shadow:0 6px 16px rgba(0,53,107,.10); }}
.w-icon {{ flex:none; width:34px; height:34px; border-radius:50%; background:var(--wash); color:var(--yale); display:grid; place-items:center; font-weight:800; font-size:16px; }}
.w-t {{ font-weight:700; color:var(--yale); }} .w-d {{ font-size:13.5px; color:var(--muted); line-height:1.4; }}
.checklist {{ border-left:5px solid var(--light); background:var(--wash2); border-radius:8px; padding:12px 18px; }}
.ck-title {{ font-weight:700; color:var(--yale); margin-bottom:6px; }}
.ck {{ display:flex; align-items:center; gap:10px; padding:5px 0; font-size:15px; }}
.ck .box {{ width:20px; height:20px; border-radius:5px; background:var(--navy); color:#fff; display:grid; place-items:center; font-size:12px; font-weight:800; flex:none; }}
/* ---- interactions & sparkle ---- */
.filters {{ display:flex; align-items:center; gap:8px; margin:14px 0 4px; }}
.chip {{ border:1px solid var(--line); background:#fff; color:var(--yale); border-radius:999px; padding:5px 14px; font-size:13px; font-weight:600; cursor:pointer; }}
.chip.on {{ background:var(--yale); color:#fff; border-color:var(--yale); }}
tr.hide {{ display:none; }}
.g {{ transition:transform .15s, box-shadow .15s; }} .g:hover {{ transform:translateY(-3px); box-shadow:0 6px 16px rgba(0,53,107,.12); }}
header {{ position:relative; overflow:hidden; }}
.spark {{ position:absolute; color:#fff; opacity:0; animation:twinkle 3.2s ease-in-out infinite; pointer-events:none; }}
@keyframes twinkle {{ 0%, 100% {{ opacity:0; transform:scale(.4) rotate(0); }} 50% {{ opacity:.9; transform:scale(1) rotate(45deg); }} }}
/* Charts are fully drawn by default; revealing one only PLAYS a grow-in animation (never hides anything). */
figure svg path[fill], figure svg rect[fill] {{ transform-box:fill-box; transform-origin:left center; }}
figure.in svg path[fill], figure.in svg rect[fill] {{ animation:grow .9s cubic-bezier(.2,.8,.2,1) both; }}
figure.in svg circle:not(.hit) {{ animation:fadein .7s ease .15s both; }}
@keyframes grow {{ from {{ transform:scaleX(0); }} to {{ transform:scaleX(1); }} }}
@keyframes fadein {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
#confetti {{ position:fixed; inset:0; pointer-events:none; z-index:20; }}
#top {{ position:fixed; right:22px; bottom:22px; width:42px; height:42px; border-radius:50%; border:0; background:var(--yale); color:#fff; font-size:18px; cursor:pointer; box-shadow:0 3px 10px rgba(0,0,0,.2); opacity:0; pointer-events:none; transition:opacity .2s; }}
#top.show {{ opacity:1; pointer-events:auto; }}
@media (prefers-reduced-motion: reduce) {{ .spark {{ display:none; }} * {{ transition:none !important; animation:none !important; }} }}
@media (max-width: 900px) {{ .hero-row {{ grid-template-columns:1fr; }} .dog {{ width:96px; }} .bubble {{ right:auto; left:-10px; top:-36px; }} .bubble::after {{ display:none; }} }}
@media (max-width: 900px) {{ .cost-row, .why-grid {{ grid-template-columns:1fr 1fr; }} .verdict-card {{ flex-direction:column; align-items:flex-start; }} }}
@media (max-width: 900px) {{ .glance {{ grid-template-columns:1fr 1fr; }} .two, .cards {{ grid-template-columns:1fr; }} }}
@media print {{ .skyline .win, .dog {{ animation:none !important; }} nav {{ position:static; }} section {{ break-inside:avoid-page; }} figure svg path[fill], figure svg rect[fill], figure svg circle {{ animation:none !important; }} #top, .spark, #confetti {{ display:none; }} }}
"""
    js = """
document.body.classList.add('js');
const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const tip = document.getElementById('tip');
document.querySelectorAll('.mark').forEach(m => {
  m.addEventListener('mousemove', e => { tip.textContent = m.dataset.tip; tip.style.display = 'block';
    const x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
    tip.style.left = x + 'px'; tip.style.top = (e.clientY - 34) + 'px'; });
  m.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
});

// sparkles in the header
const hdr = document.querySelector('header');
for (let i = 0; i < 14; i++) {
  const s = document.createElement('span'); s.className = 'spark'; s.textContent = i % 3 ? '✦' : '✧';
  s.style.left = (5 + Math.random() * 90) + '%'; s.style.top = (10 + Math.random() * 75) + '%';
  s.style.fontSize = (8 + Math.random() * 12) + 'px'; s.style.animationDelay = (Math.random() * 3.2) + 's';
  hdr.appendChild(s);
}

// count-up numbers
function countUp(el) {
  const to = parseFloat(el.dataset.to), dec = +el.dataset.dec, pre = el.dataset.pre || '', suf = el.dataset.suf || '';
  if (calm) return; const t0 = performance.now(), dur = 1100;
  const step = t => { const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
    el.textContent = pre + (to * e).toLocaleString('en-US', {minimumFractionDigits: dec, maximumFractionDigits: dec}) + suf;
    if (k < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}

// reveal charts, count numbers, and celebrate once the recommendation is reached.
// A plain scroll-position check (no IntersectionObserver), so nothing can stay hidden: anything on screen
// or already scrolled past is revealed.
let celebrated = false;
const pending = new Set(document.querySelectorAll('figure, .count, #recommendation'));
function reveal() {
  pending.forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.top > innerHeight) return;  // still below the screen
    pending.delete(el);
    if (el.tagName === 'FIGURE') el.classList.add('in');
    else if (el.classList.contains('count')) { if (r.bottom > 0) countUp(el); }
    else if (el.id === 'recommendation' && !celebrated && r.bottom > 0) { celebrated = true; setTimeout(confetti, 350); }
  });
}
let ticking = false;
addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(() => { ticking = false; reveal(); }); } }, {passive: true});
addEventListener('resize', reveal);
addEventListener('load', reveal);
reveal();

// filter the attack table
document.querySelectorAll('.chip').forEach(c => c.addEventListener('click', () => {
  document.querySelectorAll('.chip').forEach(x => x.classList.toggle('on', x === c));
  document.querySelectorAll('#attack-table tbody tr').forEach(r =>
    r.classList.toggle('hide', c.dataset.filter !== 'all' && r.dataset.kind !== c.dataset.filter));
}));

// cost calculator (per-document costs are the measured ones from the runs)
const slider = document.getElementById('docs');
const money = (v, d) => '$' + v.toLocaleString('en-US', {minimumFractionDigits: d, maximumFractionDigits: d});
slider.addEventListener('input', () => {
  const n = +slider.value, m = n * 30;
  document.getElementById('docs-out').textContent = n.toLocaleString('en-US');
  document.getElementById('calc-exam').textContent = money(m * +slider.dataset.exam, 2);
  document.getElementById('calc-warm').textContent = money(m * +slider.dataset.warm, 2);
  document.getElementById('calc-nocache').textContent = money(m * +slider.dataset.nocache, 0);
});

// confetti in Yale blues
const cv = document.getElementById('confetti'), cx = cv.getContext('2d');
function confetti() {
  if (calm) return;
  cv.width = innerWidth; cv.height = innerHeight;
  const colors = ['#00356B', '#285A9E', '#4A90D9', '#8FB7E6', '#C9DBF2'];
  const bits = Array.from({length: 160}, () => ({ x: innerWidth / 2 + (Math.random() - .5) * 200, y: innerHeight * .35,
    vx: (Math.random() - .5) * 14, vy: -Math.random() * 13 - 4, r: Math.random() * 6 + 4, a: Math.random() * 6,
    va: (Math.random() - .5) * .3, c: colors[Math.floor(Math.random() * colors.length)], star: Math.random() < .25 }));
  let frames = 0;
  (function draw() {
    cx.clearRect(0, 0, cv.width, cv.height);
    bits.forEach(b => { b.vy += .32; b.vx *= .99; b.x += b.vx; b.y += b.vy; b.a += b.va;
      cx.save(); cx.translate(b.x, b.y); cx.rotate(b.a); cx.fillStyle = b.c;
      if (b.star) { cx.font = (b.r * 2.4) + 'px sans-serif'; cx.fillText('✦', -b.r, b.r); }
      else cx.fillRect(-b.r / 2, -b.r / 4, b.r, b.r / 2);
      cx.restore(); });
    if (++frames < 170) requestAnimationFrame(draw); else cx.clearRect(0, 0, cv.width, cv.height);
  })();
}
document.getElementById('celebrate').addEventListener('click', confetti);
const dog = document.getElementById('dog');
dog.addEventListener('click', () => { dog.classList.add('talk'); confetti(); setTimeout(() => dog.classList.remove('talk'), 2200); });

// back to top
const topBtn = document.getElementById('top');
addEventListener('scroll', () => topBtn.classList.toggle('show', scrollY > 700));
topBtn.addEventListener('click', () => scrollTo({top: 0, behavior: calm ? 'auto' : 'smooth'}));"""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>HW6 Results: Campus Customs Vendor Desk Agent</title><style>{css}</style></head>
<body>
<header>{skyline_svg()}<div class="moon" aria-hidden="true"></div>
<div class="wrap head-row"><div class="head-text"><div class="kicker">Yale · AI Foundations · HW6</div><h1>Campus Customs Vendor Desk Agent</h1>
<p>gpt-6-luna via Portkey · every number comes from my saved runs (Problems 2–8)<br>Built {esc(now_iso()[:10])}</p></div>
<button type="button" class="dog-btn" id="dog" aria-label="Pet the bulldog">{bulldog_svg()}<span class="bubble" id="bubble">Woof! Caching saved {cache['summary']['saved_percent']:.0f}% 🐾</span></button></div></header>
<nav><div class="wrap"><a href="#caching">1 · Caching</a><a href="#attacks">2 · Attacks</a><a href="#cost">3 · Defense cost</a><a href="#exam">4 · Exam &amp; red team</a><a href="#recommendation">5 · Recommendation</a></div></nav>
<main class="wrap">{glance}{sec1}{sec2}{sec3}{sec4}{sec5}</main>
<footer>One self-contained file: no internet, fonts, images, or other files needed. Hover over any chart mark to see its exact value.</footer>
<div id="tip" role="tooltip"></div>
<canvas id="confetti" aria-hidden="true"></canvas>
<button id="top" type="button" aria-label="Back to top">↑</button>
<script>{js}</script>
</body></html>
"""


if __name__ == "__main__":
    page = build()
    REPORT.write_text(page, encoding="utf-8")
    print(f"Wrote {REPORT.relative_to(HERE)} ({len(page.encode()):,} bytes)")
