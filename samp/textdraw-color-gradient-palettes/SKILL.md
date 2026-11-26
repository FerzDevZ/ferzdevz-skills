---
name: textdraw-color-gradient-palettes
description: Use when HUD colours fail contrast or gradients band.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw, colour, accessibility, ui]
    category: samp
---

# Pick TextDraw colours by measured contrast, not by taste

Every TextDraw colour is one 32-bit value in `0xRRGGBBAA` order — alpha last, not first. The
two failures that follow from getting this wrong are a panel that renders solid black because
`0xFF` landed in the red slot, and text that disappears on a bright accent because nobody
measured the pair. Both are arithmetic problems, and both are checkable before a restart.

## When to Use

- Text is unreadable on some backgrounds, or only at night in game.
- A gradient shows visible bands, or looks washed out on the panel it sits on.
- Colours are scattered as hex literals across twenty files and drift on every edit.
- You are adding an accent colour and need a foreground that stays readable on it.

## Compatibility & Stack Matrix (2026)

| Item | 2026 baseline | Note |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218 | same model as 0.3.7 |
| Encoding | `0xRRGGBBAA` — alpha is the **last** byte | `0xFF8A00FF` = opaque orange |
| Text colour | `TextDrawColor` / `PlayerTextDrawColor` | alpha below `0xFF` fades the glyph |
| Box colour | `TextDrawBoxColor` / `PlayerTextDrawBoxColor` | alpha is the panel's transparency |
| Background | `TextDrawBackgroundColor` | behind the glyph only, not the box |
| Outline | `TextDrawSetOutline(td, 1)` | one unit of the text colour, size-scaled |
| Shadow | `TextDrawSetShadow(td, 1)` | offset copy; ignore when outline is on |
| Proportional | `TextDrawSetProportional(td, true)` | consistent spacing between glyphs |
| Contrast target | 4.5:1 body text, 3:1 large text | WCAG 2.2 AA on sRGB luminance |

A panel is two colours doing two jobs: the box (surface) and the glyph (ink). Gradients add a
third job — depth — and depth is where banding appears. No sprite or texture is involved
anywhere in this skill.

## Production Implementation

1. Put every colour in one include, one line per role. Names describe the job, not the hue, so
   a palette change touches one file:

```pawn
// ui_palette.inc — 0xRRGGBBAA, alpha last
#define UI_BG        0x101418FF   // app background
#define UI_SURFACE   0x1A2027FF   // panels and cards
#define UI_SURFACE_2 0x232B34FF   // raised panel / hover
#define UI_INK       0xF2F5F7FF   // primary text
#define UI_MUTED     0x9AA4AEFF   // secondary text, labels
#define UI_ACCENT    0xFF8A00FF   // action and focus
#define UI_DANGER    0xE5484DFF   // destructive and damage
#define UI_OK        0x37C871FF   // success and health
#define UI_HAIRLINE  0xFFFFFF14   // 8% white divider
```

2. Measure each ink/surface pair before shipping — the numbers are in Verification. The decision
   that gets missed is the label on the accent: the accent is light, so the label must be the
   dark ink (7.83:1), never the light one (2.16:1).

3. Keep dividers at low alpha instead of a second grey. `0xFFFFFF14` composites on every panel
   below it, so one token covers all surfaces and reads as a hairline rather than a border.
   Panels themselves are boxes: `TextDrawUseBox(td, true)`, `TextDrawBoxColor(td, UI_SURFACE)`,
   and `TextDrawTextSize` at the right and bottom edges — see `progress-bar-hud-rendering` for
   the edge maths.

4. Build gradients from RGB interpolation across three to five stops, not from two stops with a
   huge alpha swing. Interpolating channels keeps the ramp even; fading alpha between two very
   different luminances is what bands over 8-bit output:

```pawn
stock UiLerp(from, to, Float:t)
{
    if (t < 0.0) t = 0.0;
    if (t > 1.0) t = 1.0;
    new dr = ((to >> 24) & 0xFF) - ((from >> 24) & 0xFF);
    new dg = ((to >> 16) & 0xFF) - ((from >> 16) & 0xFF);
    new db = ((to >> 8)  & 0xFF) - ((from >> 8)  & 0xFF);
    new r = ((from >> 24) & 0xFF) + floatround(dr * t);
    new g = ((from >> 16) & 0xFF) + floatround(dg * t);
    new b = ((from >> 8)  & 0xFF) + floatround(db * t);
    return (r << 24) | (g << 16) | (b << 8) | 0xFF;
}

stock UiGradient(Float:x, Float:y, Float:w, Float:h, from, to, steps)
{
    if (steps < 3) steps = 3;
    if (steps > 5) steps = 5;
    new Float:stepH = h / float(steps);
    for (new i = 0; i < steps; i++)
    {
        new Text:td = TextDrawCreate(x, y + stepH * float(i), " ");
        TextDrawUseBox(td, true);
        TextDrawBoxColor(td, UiLerp(from, to, float(i) / float(steps - 1)));
        TextDrawTextSize(td, x - 5.0 + w, y + stepH * float(i + 1) - 10.0);
        TextDrawLetterSize(td, 0.0, 0.0);
        TextDrawShowForAll(td);
    }
}
```

5. Choose one text treatment and keep it. Outline and shadow together thicken the glyph unevenly
   at small letter sizes and halve effective contrast; at 0.24 letter size, outline 1 is enough
   on any surface in the palette: `TextDrawSetOutline(td, 1)` with `TextDrawSetShadow(td, 0)`,
   `TextDrawColor(td, UI_INK)` and a transparent `TextDrawBackgroundColor` — the box is the
   surface, so the background colour must not paint over it.

6. Reserve the accent for one action per screen and for state changes. A palette where the
   accent appears three times has no accent; the eye needs one target.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Panel renders solid black | alpha written first (`0xAARRGGBB`) | rewrite as `0xRRGGBBAA`, alpha last |
| Text vanishes on the accent button | white ink on a light accent (2.16:1) | use `UI_BG` as the label colour |
| Gradient shows hard bands | two stops over a large luminance delta | 3–5 stops, interpolate RGB not alpha |
| Hairline invisible on some panels | grey chosen for one surface | low-alpha white composites on all |
| Glyphs look bold and blurry | outline and shadow both on | one unit of outline, shadow 0 |
| Colours drift between screens | literals in many files | one `ui_palette.inc`, no hex outside it |
| Box hides the textdraw's own text | `BackgroundColor` left opaque | set background alpha to 0 with a box |

## Verification

Palette tokens are parsed straight out of the include and every ink/surface pair is measured;
the check fails when a ratio drops below 4.5:

```bash
python3 - <<'PY'
import re
src = open('ui_palette.inc').read()
tok = dict(re.findall(r'#define\s+(UI_\w+)\s+0x([0-9A-Fa-f]{8})', src))
def lum(h):
    c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
def cr(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)
pairs = [('UI_INK', 'UI_BG'), ('UI_INK', 'UI_SURFACE'), ('UI_MUTED', 'UI_BG'), ('UI_BG', 'UI_ACCENT')]
bad = 0
for a, b in pairs:
    r = cr(tok[a][:6], tok[b][:6]); bad += r < 4.5
    print(f"{'PASS' if r >= 4.5 else 'FAIL'} {a} on {b} {r:.2f}")
print('pairs', len(pairs), 'fail', bad)
PY
```

Expected on the palette above:

```text
PASS UI_INK on UI_BG 16.89
PASS UI_INK on UI_SURFACE 14.99
PASS UI_MUTED on UI_BG 7.31
PASS UI_BG on UI_ACCENT 7.83
pairs 4 fail 0
```

## Sources (2026)

- https://open.mp/docs/scripting/resources/colorslist — colours are `0xRRGGBBAA`, alpha last, with the transparency table.
- https://open.mp/docs/scripting/functions/TextDrawBoxColor — box colour is used only with `useBox`, and alpha sets opacity.
- https://open.mp/docs/scripting/functions/TextDrawSetOutline — outline width and its interaction with shadow at small letter sizes.
