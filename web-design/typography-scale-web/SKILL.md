---
name: typography-scale-web
description: Use when type sizes are ad hoc or shift on font load
version: "2026.1.0"
metadata:
  hermes:
    tags: [typography, fluid-type, variable-fonts, cls, clamp]
    category: web-design
---

# A type scale you can compute, and a fallback that does not move

Two typography bugs cost real money: headings sized one-off per page, and a font swap
that shoves the layout down 40px. Both are arithmetic. Fix the ratio, express sizes in
`rem` plus a `clamp()` slope, and give the fallback face the metrics of the web font so
the first paint and the final paint occupy the same box.

## When to Use

- Headings are `font-size: 32px` here and `2.1rem` there with no shared ratio.
- Lighthouse reports CLS on text, or the page jumps once the webfont lands.
- A fluid heading is either unreadably small on mobile or absurd on 4K.
- You are shipping a variable font and faux-bold appears at some weights.
- Skip this for a single-paragraph page with system fonts only.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Notes |
| --- | --- | --- |
| `clamp()` | Baseline since Jul 2020 | Needs `rem` in the preferred term for zoom |
| `size-adjust` | Baseline since Sep 2023 | Scales all metrics of the declared face |
| `ascent/descent/line-gap-override` | Baseline since Sep 2023 | Percentages of the font size |
| Variable fonts `wght` | Chrome 62+, Safari 11+, Firefox 62+ | Set with `font-weight`, not variation settings |
| `@capsizecss/core` | 4.1.x + `@capsizecss/metrics` 4.5.x | Generates the override block |
| `text-wrap: balance` | Chrome 114+, Safari 17.5+, Firefox 121+ | Falls back to normal wrapping |

## Production Implementation

1. Fix the ratio before touching sizes. 1.2 for dense app UI, 1.25 for marketing,
   1.333 for editorial. A 1.25 scale on a 16px base gives the only sizes you may use:

```text
12.80  16.00  20.00  25.00  31.25  39.06    (px, 1.25 ratio)
```

2. Compute the fluid pair instead of guessing a `vw` value. Min and max are real pixel
   targets at real viewport widths; the slope falls out of them.

```js
const fluid = (minPx, maxPx, minVw = 360, maxVw = 1280, base = 16) => {
  const slope = ((maxPx - minPx) / (maxVw - minVw)) * 100;
  const intercept = (minPx - (slope * minVw) / 100) / base;
  return `clamp(${minPx / base}rem, ${intercept.toFixed(4)}rem + ${slope.toFixed(3)}vw, ${maxPx / base}rem)`;
};

fluid(16, 44); // clamp(1rem, 0.3152rem + 3.043vw, 2.75rem)
```

3. Apply it with a rule that survives zoom: the maximum must be at least twice the
   minimum, and the preferred term keeps a `rem` component so a user's larger default
   font size still scales the text.

```css
:root {
  --step-0: 1rem;                                        /* body never shrinks below 16px */
  --step-4: clamp(1rem, 0.3152rem + 3.043vw, 2.75rem);   /* 2.75 = 2.75× the minimum */
}
h1 { font-size: var(--step-4); line-height: 1.1; letter-spacing: -0.02em; text-wrap: balance; }
p  { font-size: var(--step-0); line-height: 1.55; max-width: 65ch; }
```

4. Load one variable file per family and drive weight through `font-weight`. A
   `font-variation-settings` declaration wins over the cascade and breaks hover weights.

```css
@font-face {
  font-family: "Inter var";
  src: url("/fonts/InterVariable.woff2") format("woff2");
  font-weight: 100 900;
  font-display: swap;
  unicode-range: U+0000-00FF, U+0131, U+2000-206F;
}
body { font-family: "Inter var", system-ui, sans-serif; font-optical-sizing: auto; font-synthesis: none; }
```

5. Give the fallback the web font's metrics. These values are the output of
   `createFontStack([inter, arial])`, not estimates — regenerate them for your pair.

```css
@font-face {
  font-family: "Inter Fallback";
  src: local("Arial"), local("ArialMT");
  ascent-override: 90.4365%;
  descent-override: 22.518%;
  line-gap-override: 0%;
  size-adjust: 107.1194%;
}
body { font-family: "Inter var", "Inter Fallback", Arial, sans-serif; }
```

6. Regenerate those numbers whenever the font or the fallback changes; they are tied to
   both faces and go stale silently.

```js
import { createFontStack } from "@capsizecss/core";
import inter from "@capsizecss/metrics/inter";
import arial from "@capsizecss/metrics/arial";

const { fontFamily, fontFaces } = createFontStack([inter, arial]);
console.log(fontFamily); // Inter, "Inter Fallback", Arial
console.log(fontFaces);  // the @font-face block above
```

7. Verify text spacing before shipping. WCAG 1.4.12 requires no clipped or overlapping
   text when line height is 1.5×, paragraph spacing 2em, letter spacing 0.12em and word
   spacing 0.16em. Fixed `height` on a text container is the usual culprit. Paste this
   into DevTools as a temporary sheet, not into the codebase.

```css
* { line-height: 1.5 !important; letter-spacing: 0.12em !important; word-spacing: 0.16em !important; }
p { margin-bottom: 2em !important; }
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| CLS 0.05–0.15 exactly at font swap | Fallback face has different ascent/x-width | Add `size-adjust` + the three overrides from `createFontStack` |
| Text stops growing at 200% browser zoom | `clamp()` maximum in `px`, or below 2× the minimum | Keep the max in `rem`; `clamp(1rem, 0.3152rem + 3.043vw, 2.75rem)` renders 88px at 200% |
| Fluid heading ignores the user's font-size setting | Preferred value is `vw` only | Keep a `rem` term in the middle value |
| Bold looks smeared at 600 | Browser synthesises bold because the file lacks the weight | Ship the variable range `100 900` and set `font-synthesis: none` |
| Hover weight change does nothing | `font-variation-settings` set inline overrides the rule | Use `font-weight: 650` and delete the variation setting |
| Lines run 120+ characters on desktop | No measure cap on the paragraph | `max-width: 65ch`; body text stays 45–75ch |

## Verification

- `node -e 'const f=(a,b,v1=360,v2=1280,base=16)=>{const s=(b-a)/(v2-v1)*100,i=(a-s*v1/100)/base;return [a/base,+i.toFixed(4),+s.toFixed(3),b/base]}; console.log(f(16,44))'`
  → `[ 1, 0.3152, 3.043, 2.75 ]`, the four numbers in the `clamp()`. Sweep the
  viewport (or the formula) and confirm a monotonic series that clamps at both ends:

```text
360px  -> 16.0px (1.000rem)
768px  -> 28.4px (1.776rem)
1024px -> 36.2px (2.263rem)
1280px -> 44.0px (2.750rem)
1600px -> 44.0px (2.750rem)
```

- `grep -rnE 'font-size: *[0-9]+px' src/` → no output; every size is `rem` or a token.
- `node -e "import('fontkit').then(k=>{const f=k.openSync('public/fonts/InterVariable.woff2');console.log(Boolean(f.variationAxes?.wght))})"`
  → `true`, proving the shipped file actually carries a `wght` axis.
- `npx lighthouse http://localhost:3000 --only-categories=performance --preset=desktop`
  → CLS ≤ 0.02 after the fallback overrides are in place.
- Manual: DevTools → Network → Slow 4G + disable cache, reload, watch the Performance
  panel; text must not reflow by more than a line at the swap.

## Sources (2026)

- https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/clamp
- https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@font-face/size-adjust
- https://www.w3.org/TR/WCAG22/
