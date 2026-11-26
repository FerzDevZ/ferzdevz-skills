---
name: color-system-accessible-palette
description: Use when a palette must pass contrast and survive dark mode
version: "2026.1.0"
metadata:
  hermes:
    tags: [color, oklch, wcag, apca, dark-mode, accessibility]
    category: web-design
---

# Pick colour steps by measured contrast, not by index

Most palettes are eleven hexes chosen by eye and a "500" that happens to look right.
The two failures that follow are predictable: the primary button fails 4.5:1 at the
step designers liked, and dark mode is a second palette that drifts on the next edit.
Build the ramp in OKLCH so lightness is a number you control, then gate every pair.

## When to Use

- A brand colour needs a 50–950 ramp and buttons need a defensible step choice.
- Grey text passes a checker but is unreadable on a laptop in daylight.
- Dark mode currently means a duplicated stylesheet with hand-picked hexes.
- Success/warning/danger badges exist but nobody measured their text contrast.
- Skip this if you ship one accent colour on white and never theme it.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Notes |
| --- | --- | --- |
| `oklch()` in CSS | Baseline since May 2023 | L is 0–1; C 100% = 0.4, not 1 |
| Relative colour syntax | `oklch(from var(--x) ...)` | Newer than plain `oklch()`; feature-detect |
| WCAG 2.2 | W3C Recommendation, Dec 2024 | SC 1.4.3 text, SC 1.4.11 non-text |
| APCA | `apca-w3` 0.1.9 (constants 0.0.98G-4g) | Polarity-aware; sign flips for light-on-dark |
| culori | 4.x | Gamut test + OKLCH→sRGB conversion |
| Browsers | Chrome/Edge 111+, Safari 15.4+, Firefox 113+ | Below that, ship sRGB fallbacks |

WCAG 2.2 remains the legal bar; APCA is the readability model to design against. Run both.

## Production Implementation

1. Generate the ramp by fixing hue and binary-searching chroma until each step is
   inside sRGB. Hand-picked chroma is why ramps look muddy at the light end.

```js
import { converter, formatHex, inGamut } from "culori";

const HUE = 262;
const STEPS = [0.985, 0.95, 0.90, 0.82, 0.72, 0.62, 0.52, 0.44, 0.37, 0.30, 0.24];

const maxChroma = (l, h) => {
  let lo = 0, hi = 0.37;
  for (let i = 0; i < 28; i++) {
    const mid = (lo + hi) / 2;
    inGamut("rgb")({ mode: "oklch", l, c: mid, h }) ? (lo = mid) : (hi = mid);
  }
  return lo;
};

const ramp = STEPS.map((l) => {
  const c = maxChroma(l, HUE) * 0.92;
  return { l, c: +c.toFixed(3), hex: formatHex({ mode: "oklch", l, c, h: HUE }) };
});
```

2. Measure the ramp instead of trusting it. Contrast against white decides where the
   solid-button step starts; this table is the output of that measurement for hue 262.

| Step | L | C | Hex | vs white |
| --- | --- | --- | --- | --- |
| 50 | 0.985 | 0.001 | `#fafafb` | 1.04:1 |
| 100 | 0.95 | 0.022 | `#e7effe` | 1.16:1 |
| 400 | 0.72 | 0.134 | `#76a3f8` | 2.51:1 |
| 500 | 0.62 | 0.188 | `#437ff6` | 3.75:1 |
| 600 | 0.52 | 0.221 | `#125ae5` | 5.80:1 |
| 700 | 0.44 | 0.187 | `#0c46b7` | 8.15:1 |

`500` is the trap: it looks like a primary and fails white text at 3.75:1. `600` is the
first step that clears 4.5:1, so `--color-action-bg` aliases 600 and `500` is hover-only
fills, never a text background.

3. Write semantic roles, never palette names, into components: `action-bg`,
   `action-fg`, `surface`, `surface-raised`, `text-muted`, `border-strong`, plus one
   triplet per state. Each state gets a foreground chosen and measured separately.

| Role | fg | bg | WCAG | APCA \|Lc\| |
| --- | --- | --- | --- | --- |
| danger | `#ffffff` | `#b91c1c` | 6.47:1 | Lc 85 |
| success | `#ffffff` | `#15803d` | 5.02:1 | Lc 80 |
| warning | `#1a1a1a` | `#fde68a` | 13.98:1 | Lc 90 |

4. Gate every pair in CI with one script. WCAG answers "is this legal", APCA answers
   "can this be read"; a pair must pass both, at the size it is actually used.

```js
import { APCAcontrast, sRGBtoY } from "apca-w3";
import { converter } from "culori";

const rgb = converter("rgb");
const lin = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const lum = (hex) => { const { r, g, b } = rgb(hex); return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b); };
const wcag = (a, b) => { const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x); return (hi + 0.05) / (lo + 0.05); };
const lc = (fg, bg) => {
  const f = rgb(fg), b = rgb(bg);
  return APCAcontrast(sRGBtoY([f.r * 255, f.g * 255, f.b * 255]),
                      sRGBtoY([b.r * 255, b.g * 255, b.b * 255]));
};
```

5. Set the thresholds from the use, not from one global number. APCA's own guidance is
   Lc 90 preferred and Lc 75 minimum for body text, Lc 60 for 24px or bold text; WCAG
   asks 4.5:1 for normal text, 3:1 for large text and 3:1 for UI borders and icons.

```js
const large = size >= 24 || (size >= 19 && weight >= 700);
const need = large ? 60 : 75;
const ok = Math.abs(lc(fg, bg)) >= need && wcag(fg, bg) >= (large ? 3 : 4.5);
```

6. Build dark mode by re-picking lightness at the same hue, one semantic set at a time.
   Surfaces land around L 0.18–0.24, body text around L 0.92, and chroma drops ~40%
   because saturated colour on a dark surface vibrates. Ten variables change; the
   primitives do not.

```css
:root { color-scheme: light; --ds-color-surface: #ffffff; --ds-color-text: #1a1a1a; }
[data-theme="dark"] { color-scheme: dark; --ds-color-surface: #0b1220; --ds-color-text: #e6edf7; }
```

7. Derive interaction states from one base where the engine supports it, and check the
   derived pair too: a 0.06 lightness drop can push a border under 3:1.

```css
@supports (color: oklch(from red l c h)) {
  .btn { --btn-hover: oklch(from var(--ds-color-action-bg) calc(l - 0.06) c h); }
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Grey `#767676` on white "passes" but reads badly | WCAG 4.54:1 passes while APCA Lc 72 misses the 75 body minimum | Raise to Lc ≥ 75 (about `#6b6b6b`) and keep WCAG ≥ 4.5:1 |
| Primary button fails contrast after a rebrand | Step picked by index, not measurement | Measure white-on-step and alias the first step ≥ 4.5:1 |
| Ramp has a muddy light end and a harsh dark end | Fixed chroma across all lightness steps | Gamut-search chroma per L, then scale to ~0.92 of maximum |
| Dark mode looks neon | Saturated hue reused unchanged on a dark surface | Drop chroma ~40% and re-pick L; keep hue fixed |
| Text on a warning banner is unreadable | One foreground reused for all states | Give each state its own fg/bg pair and measure the pair |
| `oklch(0.6 40 262)` renders a clipped, electric blue | Chroma tops out near 0.4, so `40` is ~100× the sRGB gamut | Write `0.16`, or `40%`, for a mid-chroma blue |

## Verification

- `node check-contrast.mjs` — the checker from steps 4–5 plus a loop over `pairs.json`
  — prints one line per pair; expect `FAIL` only where you intend it:

```text
PASS body/light   wcag 17.40:1  Lc 104  (need 4.5:1 / Lc 75)
FAIL muted/light  wcag 4.54:1  Lc 72  (need 4.5:1 / Lc 75)
PASS cta          wcag 5.80:1  Lc -83  (need 4.5:1 / Lc 75)
```

- `grep -rnE '#[0-9a-fA-F]{3,8}' src/components | grep -v tokens` → no output for colour
  literals; every colour arrives as `var(--ds-color-*)`.
- `node -e "console.log(CSS.supports('color','oklch(from red l c h)'))"` in a browser
  console → `true` on current engines, `false` where the hover derivation needs a fallback.

## Sources (2026)

- https://git.apcacontrast.com/documentation/APCAeasyIntro
- https://www.w3.org/TR/WCAG22/
- https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/color_value/oklch
