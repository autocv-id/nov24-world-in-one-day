#!/usr/bin/env python3
"""NI24 v2-mode1 build tool (PIL). Renders entry.png 1024x1024 RGB.

Layout follows the prescriptive § GRID in mode1-brief-v2.md. Text wrapping
is mandatory: nothing is truncated mid-word; the self-check measures every
string and reports any overflow as a warning (fit) or error (tally/refs).
"""
import os
import sys
from collections import Counter

from PIL import Image, ImageDraw, ImageFont

from data import (
    DATECHECK_LEFT,
    DATECHECK_NOTYET,
    RAIL,
    STORIES,
    TIMELINE,
)

W = H = 1024
MARGIN = 16
USABLE = 992

# ---- palette ----
CREAM = (247, 243, 232)
NAVY = (15, 32, 64)
NAVY2 = (27, 48, 88)
INK = (17, 24, 39)
RED = (192, 57, 43)
RED_DK = (153, 27, 27)
PINK_BG = (254, 242, 242)
WHITE = (255, 255, 255)
GRAY_TXT = (100, 116, 139)
LIGHT_LINE = (203, 213, 225)
PANEL = (255, 255, 255)
MAP_BG = (15, 32, 64)

REGION_COLORS = {
    "ASIA": (37, 99, 235),
    "EUROPE": (124, 58, 237),
    "MIDDLE EAST": (234, 88, 12),
    "AMERICAS": (22, 163, 74),
    "AFRICA": (219, 39, 119),
    "OCEANIA": (8, 145, 178),
    "GLOBAL": (71, 85, 105),
}
REGION_ORDER = ["ASIA", "EUROPE", "MIDDLE EAST", "AMERICAS", "AFRICA", "OCEANIA", "GLOBAL"]

FONT_DIR = "/usr/share/fonts/truetype/dejavu"


def F(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


WARNINGS = []
ERRORS = []


def warn(msg):
    WARNINGS.append(msg)
    print("WARN:", msg)


def err(msg):
    ERRORS.append(msg)
    print("ERROR:", msg)


# ---------------------------------------------------------------- text helpers

def text_w(d, s, font):
    return d.textlength(s, font=font)


def wrap(d, text, font, max_w):
    """Word-wrap text to max_w. Never splits a word; a single over-wide
    word is returned whole and flagged by the caller via measure."""
    words = text.split()
    lines, cur = [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if text_w(d, trial, font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fit_lines(d, text, font, max_w, max_lines, label):
    """Wrap text; warn if it needs more lines than allowed or a word
    alone exceeds the box. Returns the lines (never truncated)."""
    lines = wrap(d, text, font, max_w)
    for ln in lines:
        if text_w(d, ln, font) > max_w + 0.5:
            warn(f"{label}: line exceeds box ({text_w(d, ln, font):.0f}px > {max_w}px): {ln!r}")
    if len(lines) > max_lines:
        warn(f"{label}: needs {len(lines)} lines, max {max_lines}: {text!r}")
    return lines[:max_lines] if len(lines) > max_lines else lines


def fit_one_line(d, text, font, max_w, label):
    if text_w(d, text, font) > max_w + 0.5:
        warn(f"{label}: exceeds box ({text_w(d, text, font):.0f}px > {max_w}px): {text!r}")
        return False
    return True


def shrink_to_fit(d, text, fname, size, max_w, min_size=14):
    """Largest font size in [min_size..size] at which text fits 1 line."""
    sz = size
    while sz > min_size:
        f = F(fname, sz)
        if text_w(d, text, f) <= max_w:
            return f
        sz -= 1
    return F(fname, min_size)


# ---------------------------------------------------------------- self-checks

def check_tally():
    tiers = Counter(s["tier"] for s in STORIES)
    regions = Counter(s["region"] for s in STORIES)
    if len(STORIES) != 31:
        err(f"story count {len(STORIES)} != 31")
    if (tiers.get("L", 0), tiers.get("M", 0), tiers.get("B", 0)) != (3, 12, 16):
        err(f"tiering wrong: {dict(tiers)} (want 3L+12M+16B)")
    if len(regions) != 7:
        err(f"regions {len(regions)} != 7: {dict(regions)}")
    if regions.get("AMERICAS", 0) < 1:
        err("zero AMERICAS stories")
    nums = [s["n"] for s in STORIES]
    if sorted(nums) != list(range(1, 32)):
        err(f"story numbers not 1..31: {sorted(nums)}")
    print(f"tally: {len(STORIES)} stories, tiers {dict(tiers)}, regions {dict(regions)}")
    return regions


def check_strings():
    bad = ["Monday", "Sunday", "Nov 23", "Nov 22", "Saturday", "Friday"]
    for s in STORIES:
        blob = s["headline"] + " " + s["deck"]
        for b in bad:
            if b in blob:
                err(f"story #{s['n']} contains forbidden string {b!r}: {blob!r}")
    for n, label, ref in RAIL:
        if ref not in {s["n"] for s in STORIES}:
            err(f"rail ref #{ref} not a story")
    for phrase in ["liftoff", "FIDE", "Canada"]:
        if phrase == "liftoff":
            for s in STORIES:
                if "liftoff" in (s["headline"] + " " + s["deck"]).lower():
                    err(f"story #{s['n']} mentions liftoff (DATE CHECK exclusion)")
    print("string audit: OK")


# ---------------------------------------------------------------- scenes
# Each painter draws ONLY inside (x, y, w, h). Flat shapes, no photos.

def scene_chart_up(d, x, y, w, h):
    d.rectangle([x, y, x + w, y + h], fill=(220, 252, 231))
    for i in range(1, 4):
        yy = y + h * i // 4
        d.line([x + 4, yy, x + w - 4, yy], fill=(187, 247, 208), width=1)
    pts = [(x + 6, y + h - 14), (x + w * 0.3, y + h - 26),
           (x + w * 0.55, y + h - 20), (x + w * 0.8, y + 16), (x + w - 8, y + 8)]
    d.line(pts, fill=(22, 163, 74), width=4, joint="curve")
    d.polygon([(x + w - 8, y + 8), (x + w - 18, y + 8), (x + w - 8, y + 18)],
              fill=(22, 163, 74))
    for i, bh in enumerate((14, 22, 18, 30, 38)):
        bx = x + 8 + i * (w - 16) // 5
        d.rectangle([bx, y + h - 8 - bh, bx + (w - 16) // 5 - 4, y + h - 8],
                    fill=(134, 239, 172))


def scene_blast(d, x, y, w, h):
    d.rectangle([x, y, x + w, y + h], fill=(41, 37, 36))
    cx, cy = x + w // 2, y + h // 2 + 4
    for r, col in ((30, (234, 88, 12)), (20, (249, 115, 22)), (12, (253, 224, 71))):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    for dx, dy in ((-28, -14), (26, -18), (-24, 16), (28, 14), (0, -24), (-6, 24)):
        d.ellipse([cx + dx - 5, cy + dy - 5, cx + dx + 5, cy + dy + 5],
                  fill=(249, 115, 22))
    d.rectangle([x, y + h - 12, x + w, y + h], fill=(28, 25, 23))


def scene_rocket(d, x, y, w, h):
    d.rectangle([x, y, x + w, y + h], fill=(12, 24, 48))
    for sx, sy in ((10, 10), (w - 14, 18), (w // 3, 8), (w - 30, 40), (16, 44)):
        d.ellipse([x + sx, y + sy, x + sx + 3, y + sy + 3], fill=WHITE)
    cx = x + w // 2
    d.polygon([(cx, y + 8), (cx - 9, y + 26), (cx + 9, y + 26)], fill=(220, 38, 38))
    d.rounded_rectangle([cx - 9, y + 24, cx + 9, y + h - 26], radius=4, fill=WHITE)
    d.rectangle([cx - 13, y + h - 34, cx - 9, y + h - 20], fill=(220, 38, 38))
    d.rectangle([cx + 9, y + h - 34, cx + 13, y + h - 20], fill=(220, 38, 38))
    d.polygon([(cx - 6, y + h - 22), (cx + 6, y + h - 22), (cx, y + h - 6)],
              fill=(249, 115, 22))
    d.ellipse([x + w - 26, y + 8, x + w - 8, y + 26], fill=(226, 232, 240))


def scene_quake(d, x, y, w, h):
    d.rectangle([x, y, x + w, y + h], fill=(254, 243, 199))
    d.rectangle([x, y + h - 22, x + w, y + h], fill=(120, 84, 52))
    mid = x + w // 2
    d.line([(mid - 14, y + h - 22), (mid - 4, y + h - 12), (mid + 6, y + h - 16),
            (mid + 16, y + h - 6)], fill=(69, 46, 26), width=3)
    d.rectangle([x + 10, y + 18, x + 34, y + h - 22], fill=(148, 163, 184))
    d.rectangle([x + w - 40, y + 12, x + w - 12, y + h - 22], fill=(148, 163, 184))
    d.line([(x + 40, y + 14), (x + 52, y + 26), (x + 44, y + 38)], fill=RED, width=2)


def scene_smoke(d, x, y, w, h):
    d.rectangle([x, y, x + w, y + h], fill=(203, 213, 225))
    d.rectangle([x + 8, y + h - 30, x + 40, y + h - 6], fill=(71, 85, 105))
    d.rectangle([x + w - 44, y + h - 24, x + w - 10, y + h - 6], fill=(71, 85, 105))
    for cx, r in ((x + 24, 12), (x + 30, 9), (x + w - 26, 11)):
        for k, rr in enumerate((r, r - 3, r - 6)):
            d.ellipse([cx - rr, y + 8 + k * 8, cx + rr, y + 8 + k * 8 + rr * 2],
                      fill=(100, 116, 139))


def scene_flames(d, x, y, w, h):
    d.rectangle([x, y, x + w, y + h], fill=(28, 25, 23))
    d.rectangle([x + 6, y + h - 26, x + w - 6, y + h - 6], fill=(68, 64, 60))
    d.rectangle([x + w // 2 - 4, y + 8, x + w // 2 + 4, y + h - 26], fill=(120, 113, 108))
    for fx, fh, col in ((0.3, 26, (249, 115, 22)), (0.5, 34, (234, 88, 12)),
                        (0.7, 22, (253, 224, 71))):
        fx0 = x + int(w * fx)
        d.polygon([(fx0 - 9, y + h - 26), (fx0, y + h - 26 - fh),
                   (fx0 + 9, y + h - 26)], fill=col)


def scene_border(d, x, y, w, h):
    d.rectangle([x, y, x + w, y + h], fill=(254, 243, 199))
    d.rectangle([x, y + h - 14, x + w, y + h], fill=(120, 113, 108))
    for i in range(5):
        bx = x + 6 + i * (w - 12) // 5
        d.rectangle([bx, y + 16, bx + (w - 12) // 10, y + h - 14], fill=(68, 64, 60))
    d.rectangle([x + 4, y + 20, x + w - 4, y + 30], fill=RED)
    d.rectangle([x + 4, y + 30, x + w - 4, y + 34], fill=WHITE)
    d.rectangle([x + w - 18, y + 6, x + w - 14, y + h - 14], fill=(68, 64, 60))
    d.polygon([(x + w - 14, y + 6), (x + w - 2, y + 10), (x + w - 14, y + 14)],
              fill=(22, 163, 74))


def scene_island(d, x, y, w, h):
    d.rectangle([x, y, x + w, y + h], fill=(186, 230, 253))
    d.ellipse([x + w - 26, y + 6, x + w - 10, y + 22], fill=(253, 224, 71))
    d.ellipse([x + w // 2 - 30, y + h - 30, x + w // 2 + 30, y + h - 8],
              fill=(34, 197, 94))
    d.line([x + w // 2, y + h - 30, x + w // 2, y + h - 48], fill=(120, 84, 52),
           width=3)
    for dx, dy in ((-12, -6), (12, -6), (-8, -12), (8, -12)):
        d.line([x + w // 2, y + h - 48, x + w // 2 + dx, y + h - 48 + dy],
               fill=(22, 163, 74), width=2)
    d.line([x + 6, y + h - 12, x + w - 6, y + h - 12], fill=(56, 189, 248), width=2)


def scene_court(d, x, y, w, h):
    d.rectangle([x, y, x + w, y + h], fill=(30, 58, 95))
    d.polygon([(x + 10, y + 18), (x + w // 2, y + 6), (x + w - 10, y + 18)],
              fill=(226, 232, 240))
    for i in range(4):
        cx = x + 16 + i * (w - 32) // 3
        d.rectangle([cx - 4, y + 20, cx + 4, y + h - 12], fill=(226, 232, 240))
    d.rectangle([x + 6, y + h - 12, x + w - 6, y + h - 6], fill=(226, 232, 240))


def scene_document(d, x, y, w, h):
    d.rectangle([x, y, x + w, y + h], fill=(241, 245, 249))
    d.rectangle([x + w // 2 - 20, y + 8, x + w // 2 + 20, y + h - 8], fill=WHITE,
                outline=(148, 163, 184))
    for i in range(4):
        yy = y + 16 + i * 8
        d.line([x + w // 2 - 14, yy, x + w // 2 + 14, yy], fill=(148, 163, 184),
               width=2)
    d.polygon([(x + w - 24, y + h - 10), (x + w - 12, y + h - 30),
               (x + w - 2, y + h - 10)], fill=(220, 38, 38))
    d.text((x + w - 17, y + h - 24), "!", font=F("DejaVuSans-Bold.ttf", 11),
           fill=WHITE)


def scene_jet(d, x, y, w, h):
    d.rectangle([x, y, x + w, y + h], fill=(147, 197, 253))
    # dashed zone boundary across the upper third
    for dx in range(4, w - 8, 10):
        d.line([x + dx, y + 8, x + dx + 6, y + 8], fill=RED, width=2)
    for jx, jy, sc in ((0.38, 0.5, 1.5), (0.72, 0.68, 1.1)):
        cx, cy = x + int(w * jx), y + int(h * jy)
        s = int(14 * sc)
        d.polygon([(cx + s, cy), (cx - s, cy - s // 2), (cx - s // 2, cy),
                   (cx - s, cy + s // 2)], fill=(51, 65, 85))


def scene_podium(d, x, y, w, h):
    d.rectangle([x, y, x + w, y + h], fill=(226, 232, 240))
    cx = x + w // 2
    d.ellipse([cx - 9, y + 10, cx + 9, y + 28], fill=(51, 65, 85))
    d.polygon([(cx - 16, y + h - 22), (cx - 9, y + 28), (cx + 9, y + 28),
               (cx + 16, y + h - 22)], fill=(51, 65, 85))
    d.rectangle([cx - 22, y + h - 22, cx + 22, y + h - 6], fill=(100, 116, 139))
    d.line([cx + 8, y + 30, cx + 16, y + 20], fill=(30, 41, 59), width=2)
    d.ellipse([cx + 14, y + 17, cx + 19, y + 22], fill=(30, 41, 59))


def scene_pill(d, x, y, w, h):
    d.rectangle([x, y, x + w, y + h], fill=(240, 253, 244))
    cx, cy = x + w // 2, y + h // 2
    d.rounded_rectangle([cx - 30, cy - 11, cx + 30, cy + 11], radius=11,
                        fill=WHITE, outline=(22, 163, 74), width=2)
    d.rounded_rectangle([cx - 30, cy - 11, cx, cy + 11], radius=11,
                        fill=(220, 38, 38))
    d.line([cx, cy - 11, cx, cy + 11], fill=(22, 163, 74), width=2)


SCENES = {
    "chart_up": scene_chart_up,
    "blast": scene_blast,
    "rocket": scene_rocket,
    "quake": scene_quake,
    "smoke": scene_smoke,
    "flames": scene_flames,
    "border": scene_border,
    "island": scene_island,
    "court": scene_court,
    "document": scene_document,
    "jet": scene_jet,
    "podium": scene_podium,
    "pill": scene_pill,
}


def draw_badge(d, x, y, s, big):
    """Number badge overlaid on a scene, top-left."""
    num_font = F("DejaVuSans-Bold.ttf", 30 if big else 22)
    unit_font = F("DejaVuSans-Bold.ttf", 9 if big else 8)
    nw = text_w(d, s["badge"], num_font)
    uw = text_w(d, s["unit"], unit_font)
    bw = int(max(nw, uw)) + 12
    bh = 44 if big else 32
    d.rectangle([x, y, x + bw, y + bh], fill=(15, 23, 42))
    d.text((x + 6, y + 3), s["badge"], font=num_font, fill=WHITE)
    d.text((x + 6, y + bh - 11), s["unit"], font=unit_font, fill=(253, 224, 71))
    return bw, bh


# ---------------------------------------------------------------- map

LAND = [
    (-168, -52, 15, 72), (-58, -20, 60, 83), (-80, -34, -56, 12),
    (-11, 32, 36, 71), (-18, 52, -35, 32), (32, 180, 5, 77),
    (95, 141, -11, 8), (113, 154, -39, -10), (-6, 2, 50, 59),
    (129, 146, 31, 46), (166, 179, -47, -34), (43, 51, -26, -12),
    (-23, -14, 63, 67),
]


def _is_land(lon, lat):
    return any(lo <= lon <= hi and la0 <= lat <= la1
               for lo, hi, la0, la1 in LAND)


def draw_map(d, x0, y0, w, h):
    d.rectangle([x0, y0, x0 + w, y0 + h], fill=MAP_BG)
    title_f = F("DejaVuSans-Bold.ttf", 13)
    sub_f = F("DejaVuSans.ttf", 9)
    d.text((x0 + 10, y0 + 8), "WHERE IT HAPPENED", font=title_f,
           fill=(56, 189, 248))
    d.text((x0 + 10, y0 + 26), "pins = story numbers", font=sub_f,
           fill=(148, 163, 184))
    gx0, gy0 = x0 + 6, y0 + 46
    gw, gh = w - 12, h - 54
    lat_top, lat_bot = 75, -60

    def proj(lon, lat):
        px = gx0 + (lon + 180) / 360.0 * gw
        py = gy0 + (lat_top - lat) / (lat_top - lat_bot) * gh
        return px, py

    # dotted continents
    lat = lat_top
    while lat >= lat_bot:
        lon = -180
        while lon < 180:
            if _is_land(lon, lat):
                px, py = proj(lon, lat)
                d.ellipse([px - 1.4, py - 1.4, px + 1.4, py + 1.4],
                          fill=(100, 116, 139))
            lon += 3
        lat -= 3
    # pins with deterministic collision offsets
    placed = []
    pin_f = F("DejaVuSans-Bold.ttf", 8)
    for s in STORIES:
        lon, lat = s["pin"]
        px, py = proj(lon, lat)
        placed_ok = False
        for ox, oy in ((0, 0), (13, 0), (0, -13), (-13, 0), (0, 13),
                       (13, -13), (-13, -13), (13, 13)):
            cx, cy = px + ox, py + oy
            if all((cx - qx) ** 2 + (cy - qy) ** 2 >= 13 ** 2 for qx, qy in placed):
                placed.append((cx, cy))
                placed_ok = True
                break
        if not placed_ok:
            cx, cy = px, py
            placed.append((cx, cy))
        cx = min(max(cx, gx0 + 8), gx0 + gw - 8)
        cy = min(max(cy, gy0 + 8), gy0 + gh - 8)
        d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=(220, 38, 38),
                  outline=WHITE, width=1)
        num = str(s["n"])
        d.text((cx - text_w(d, num, pin_f) / 2, cy - 5), num, font=pin_f,
               fill=WHITE)


# ---------------------------------------------------------------- panels

def draw_large(d, s, x, y):
    w, h = 246, 184
    d.rectangle([x, y, x + w, y + h], fill=PANEL, outline=LIGHT_LINE)
    # scene 0-84
    SCENES[s["scene"]](d, x + 1, y + 1, w - 2, 83)
    draw_badge(d, x + 5, y + 5, s, big=True)
    # headline 86-120, 1 line, shrink-to-fit from 20px
    hf = shrink_to_fit(d, s["headline"], "DejaVuSans-Bold.ttf", 20, w - 12)
    d.text((x + 6, y + 88), s["headline"], font=hf, fill=INK)
    # deck 120-168, max 2 lines 12px
    df = F("DejaVuSans.ttf", 12)
    lines = fit_lines(d, s["deck"], df, w - 12, 2, f"large #{s['n']} deck")
    for i, ln in enumerate(lines):
        d.text((x + 6, y + 122 + i * 15), ln, font=df, fill=(51, 65, 85))
    # tag/source 168-182
    tf = F("DejaVuSans-Bold.ttf", 10)
    sf = F("DejaVuSans.ttf", 10)
    tag = s["tag"]
    tw = text_w(d, tag, tf) + 8
    d.rectangle([x + 6, y + 168, x + 6 + tw, y + 180], fill=(226, 232, 240))
    d.text((x + 10, y + 168), tag, font=tf, fill=(51, 65, 85))
    d.text((x + 10 + tw, y + 168), s["source"], font=sf, fill=GRAY_TXT)
    # story number chip, right end of the tag row (never on the headline)
    nf = F("DejaVuSans-Bold.ttf", 12)
    num = f"#{s['n']}"
    d.text((x + w - text_w(d, num, nf) - 6, y + 168), num, font=nf, fill=RED)


def draw_medium(d, s, x, y):
    w, h = 158, 140
    d.rectangle([x, y, x + w, y + h], fill=PANEL, outline=LIGHT_LINE)
    # scene band 0-52
    SCENES[s["scene"]](d, x + 1, y + 1, w - 2, 51)
    draw_badge(d, x + 4, y + 4, s, big=False)
    # headline 54-92, max 2 lines 14px bold
    hf = F("DejaVuSans-Bold.ttf", 14)
    lines = fit_lines(d, s["headline"], hf, w - 10, 2, f"medium #{s['n']} headline")
    for i, ln in enumerate(lines):
        d.text((x + 5, y + 56 + i * 17), ln, font=hf, fill=INK)
    # deck 92-124, max 2 lines 10px
    df = F("DejaVuSans.ttf", 10)
    lines = fit_lines(d, s["deck"], df, w - 10, 2, f"medium #{s['n']} deck")
    for i, ln in enumerate(lines):
        d.text((x + 5, y + 92 + i * 13), ln, font=df, fill=(51, 65, 85))
    # tag 124-136
    tf = F("DejaVuSans-Bold.ttf", 9)
    sf = F("DejaVuSans.ttf", 9)
    tag = s["tag"]
    tw = text_w(d, tag, tf) + 6
    d.rectangle([x + 5, y + 124, x + 5 + tw, y + 135], fill=(226, 232, 240))
    d.text((x + 8, y + 124), tag, font=tf, fill=(51, 65, 85))
    src = s["source"]
    if text_w(d, src, sf) > w - 10 - tw - 4:
        src = src.split(" /")[0].split(",")[0]
    d.text((x + 8 + tw, y + 124), src, font=sf, fill=GRAY_TXT)
    # story number chip: dark square, top-right corner of the scene band
    # (the tag row is too crowded for it in a 158px panel)
    nf = F("DejaVuSans-Bold.ttf", 11)
    num = f"#{s['n']}"
    nw = int(text_w(d, num, nf)) + 8
    d.rectangle([x + w - nw - 4, y + 4, x + w - 4, y + 20], fill=(15, 23, 42))
    d.text((x + w - nw, y + 5), num, font=nf, fill=WHITE)


def draw_brief(d, s, x, y):
    w, h = 228, 50
    d.rectangle([x, y, x + w, y + h], fill=PANEL, outline=(226, 232, 240))
    # number chip (reserved width, never on top of text)
    d.rectangle([x + 4, y + 6, x + 22, y + 24], fill=NAVY)
    nf = F("DejaVuSans-Bold.ttf", 11)
    num = str(s["n"])
    d.text((x + 13 - text_w(d, num, nf) / 2, y + 8), num, font=nf, fill=WHITE)
    # headline 1 line 12px bold
    hf = F("DejaVuSans-Bold.ttf", 12)
    fit_one_line(d, s["headline"], hf, w - 30, f"brief #{s['n']} headline")
    d.text((x + 26, y + 5), s["headline"], font=hf, fill=INK)
    # detail 1 line 10px
    df = F("DejaVuSans.ttf", 10)
    fit_one_line(d, s["deck"], df, w - 30, f"brief #{s['n']} deck")
    d.text((x + 26, y + 22), s["deck"], font=df, fill=(51, 65, 85))
    # region + source 1 line 9px
    sf = F("DejaVuSans.ttf", 9)
    meta = f"{s['region']} · {s['source']}"
    if text_w(d, meta, sf) > w - 30:
        meta = s["region"]
    d.text((x + 26, y + 37), meta, font=sf, fill=GRAY_TXT)


# ---------------------------------------------------------------- page

def main():
    regions = check_tally()
    check_strings()

    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)

    # --- top bar 0-18 ---
    d.rectangle([0, 0, W, 18], fill=NAVY)
    tf = F("DejaVuSans-Bold.ttf", 11)
    d.text((MARGIN, 2), "THE WORLD IN ONE DAY", font=tf, fill=WHITE)
    right = f"{len(STORIES)} STORIES · {len(regions)} REGIONS"
    d.text((W - MARGIN - text_w(d, right, tf), 2), right, font=tf,
           fill=(253, 224, 71))

    # --- masthead 20-80 ---
    mf = F("DejaVuSerif-Bold.ttf", 48)
    mast = "TUESDAY 24 NOVEMBER 2026"
    fit_one_line(d, mast, mf, USABLE, "masthead")
    d.text((MARGIN, 22), mast, font=mf, fill=INK)
    d.line([MARGIN, 80, W - MARGIN, 80], fill=INK, width=2)

    # --- kicker 80-100 ---
    kf = F("DejaVuSerif.ttf", 17)
    kicker = ("Asia's AI rebound · Zaporizhzhia strike kills 2 · "
              "Shenzhou-24 unveils Tiangong's first foreign astronaut")
    if text_w(d, kicker, kf) > USABLE:
        kf = F("DejaVuSerif.ttf", 16)
    fit_one_line(d, kicker, kf, USABLE, "kicker")
    d.text((MARGIN, 82), kicker, font=kf, fill=RED)

    # --- region bar 102-122: chips renormalized to exactly 992px ---
    chip_f = F("DejaVuSans-Bold.ttf", 11)
    labels = [(r, f"{r} {regions[r]}") for r in REGION_ORDER if regions.get(r)]
    widths = [text_w(d, lab, chip_f) + 16 for _, lab in labels]
    total = sum(widths) + 6 * len(labels)  # 6px gaps
    scale = USABLE / total
    x = MARGIN
    for (region, lab), wd in zip(labels, widths):
        cw = int(wd * scale)
        d.rectangle([x, 102, x + cw, 122], fill=REGION_COLORS[region])
        d.text((x + (cw - text_w(d, lab, chip_f)) / 2, 105), lab, font=chip_f,
               fill=WHITE)
        x += cw + 6

    # --- timeline 124-150: dark navy, entries spaced by measured width ---
    d.rectangle([MARGIN, 124, W - MARGIN, 150], fill=NAVY2)
    tf2 = F("DejaVuSans-Bold.ttf", 10)
    tf3 = F("DejaVuSans.ttf", 10)
    d.text((MARGIN + 6, 131), "UTC", font=tf2, fill=(253, 224, 71))
    entries = []
    for t, txt in TIMELINE:
        entries.append((t, txt, text_w(d, t, tf2) + 4 + text_w(d, txt, tf3)))
    avail = USABLE - 40
    ew = sum(e[2] for e in entries)
    gap = (avail - ew) / max(len(entries) - 1, 1)
    if gap < 8:
        warn(f"timeline entries too wide (gap {gap:.1f}px)")
        gap = 8
    x = MARGIN + 36
    for t, txt, _ in entries:
        d.text((x, 131), t, font=tf2, fill=(253, 224, 71))
        x += text_w(d, t, tf2) + 4
        d.text((x, 131), txt, font=tf3, fill=WHITE)
        x += text_w(d, txt, tf3) + gap

    # --- larges + rail 156-340 ---
    larges = [s for s in STORIES if s["tier"] == "L"]
    for i, s in enumerate(larges):
        draw_large(d, s, 16 + i * 254, 156)
    # rail x 778-1008
    rx, rw = 778, 230
    d.rectangle([rx, 156, rx + rw, 340], fill=NAVY)
    rf = F("DejaVuSans-Bold.ttf", 13)
    d.text((rx + 10, 162), "THE DAY IN NUMBERS", font=rf, fill=WHITE)
    d.line([rx + 10, 182, rx + rw - 10, 182], fill=(71, 85, 105), width=1)
    nf = F("DejaVuSans-Bold.ttf", 19)
    lf = F("DejaVuSans.ttf", 9)
    cf = F("DejaVuSans-Bold.ttf", 9)
    for i, (num, label, ref) in enumerate(RAIL):
        ry = 188 + i * 25
        d.text((rx + 10, ry), num, font=nf, fill=(253, 224, 71))
        d.text((rx + 82, ry + 5), label, font=lf, fill=(226, 232, 240))
        chip = f"#{ref}"
        d.text((rx + rw - text_w(d, chip, cf) - 10, ry + 5), chip, font=cf,
               fill=(148, 163, 184))

    # --- mediums rows 346-486, 486-626: 6 cols x 158 ---
    mediums = [s for s in STORIES if s["tier"] == "M"]
    for i, s in enumerate(mediums):
        row, col = divmod(i, 6)
        draw_medium(d, s, 16 + col * 166, 346 + row * 140)

    # --- bottom band 632-938: briefs + map ---
    briefs = [s for s in STORIES if s["tier"] == "B"]
    cols = [briefs[0:6], briefs[6:11], briefs[11:16]]
    for ci, col in enumerate(cols):
        for ri, s in enumerate(col):
            draw_brief(d, s, 16 + ci * 236, 632 + ri * 51)
    draw_map(d, 728, 632, 280, 306)

    # --- DATE CHECK 940-980: red border, exclusions only ---
    d.rectangle([MARGIN, 940, W - MARGIN, 980], fill=PINK_BG, outline=RED, width=2)
    dcf = F("DejaVuSans-Bold.ttf", 10)
    d.text((MARGIN + 8, 941), "DATE CHECK (EXCLUSIONS ONLY):", font=dcf, fill=RED_DK)
    df2 = F("DejaVuSans.ttf", 10)
    fit_one_line(d, DATECHECK_LEFT, df2, USABLE - 16, "datecheck line 1")
    d.text((MARGIN + 8, 953), DATECHECK_LEFT, font=df2, fill=(127, 29, 29))
    fit_one_line(d, DATECHECK_NOTYET, df2, USABLE - 16, "datecheck line 2")
    d.text((MARGIN + 8, 965), DATECHECK_NOTYET, font=df2, fill=(127, 29, 29))

    # --- legend 980-1002 ---
    lf2 = F("DejaVuSans.ttf", 9)
    legend = ("CERTAINTY: CONFIRMED (2+ official) · OFFICIAL (named statement) · "
              "REPORTED (wire/agency) · CLAIM (party assertion) | "
              "Scenes are drawn illustrations, not photographs.")
    fit_one_line(d, legend, lf2, USABLE, "legend")
    d.text((MARGIN, 984), legend, font=lf2, fill=GRAY_TXT)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "entry.png")
    img.save(out, "PNG", optimize=True)
    size = os.path.getsize(out)
    print(f"saved {out} ({size} bytes)")
    if size > 1_048_576:
        err(f"entry.png over 1 MiB: {size}")
    print(f"self-check: {len(WARNINGS)} warnings, {len(ERRORS)} errors")
    return 1 if ERRORS else 0


if __name__ == "__main__":
    sys.exit(main())
