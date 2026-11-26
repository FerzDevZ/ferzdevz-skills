---
name: web-performance-core-vitals
description: Use when LCP, INP or CLS regress at p75.
version: "2026.1.0"
metadata:
  hermes:
    tags: [performance, core-web-vitals, lcp, inp, cls, rum]
    category: web-dev
---

# Fix the p75 Core Web Vital that regressed, not the lab score

Core Web Vitals are field metrics: the 75th percentile of real page visits, split by
device class. A green Lighthouse run proves the page can be fast on your laptop; it
does not prove your users get a fast page. Diagnose from attribution data, fix the
specific subpart, then confirm with 28-day field data.

## When to Use

- CrUX or PageSpeed Insights shows p75 LCP > 2.5s, INP > 200ms or CLS > 0.1 on mobile.
- Lighthouse is green while users report a slow page, or the reverse.
- A release moved a metric and you need to name the element or handler responsible.
- A performance budget must fail CI before a regression ships.
- Skip when the page has no traffic and no RUM: instrument first, optimize second.

## Compatibility & Stack Matrix (2026)

| Component | Threshold / version | Notes |
| --- | --- | --- |
| LCP | good <= 2500 ms, poor > 4000 ms | Report p75 separately for mobile and desktop |
| INP | good <= 200 ms, poor > 500 ms | Longest interaction, ignoring one per 50 interactions |
| CLS | good <= 0.1, poor > 0.25 | Largest session window, max 5 s |
| web-vitals | 6.2.x | `web-vitals/attribution` exposes LCP subparts, INP subparts, shift targets |
| CrUX | 28-day rolling window | Needs enough traffic per origin or URL; API key required |
| Lighthouse | lab only | TBT is a proxy for INP; it cannot measure real interactions |
| Own RUM | beacon endpoint | Segment by route, device and connection type |

## Production Implementation

1. Collect field data with attribution before changing code.

```ts
// app/rum.ts — imported by a client component
import { onCLS, onINP, onLCP } from 'web-vitals/attribution'

function report(metric: { name: string; value: number; id: string; attribution: unknown }) {
  const body = JSON.stringify({ ...metric, path: location.pathname })
  navigator.sendBeacon('/rum', body)
}

onLCP(report)
onINP(report)
onCLS(report)
```

2. Read the attribution field, not the total, to pick the fix.

| Metric | Attribution field | Meaning | First fix |
| --- | --- | --- | --- |
| LCP | `timeToFirstByte` | Server or CDN is slow | Cache HTML at the edge, cut server work |
| LCP | `resourceLoadDelay` | Hero discovered late | Preload it, `fetchpriority="high"`, never `loading="lazy"` |
| LCP | `resourceLoadDuration` | Image too heavy or far away | AVIF/WebP, sized `srcset`, CDN near users |
| LCP | `elementRenderDelay` | Render-blocking work after load | Remove blocking CSS/JS, stop client-only heroes |
| INP | `inputDelay` | Main thread busy before the handler | Split long tasks, defer third-party scripts |
| INP | `processingDuration` | Handler itself is slow | Shrink work, batch state updates, move to a worker |
| INP | `presentationDelay` | DOM and style recalculation | Reduce node count, avoid layout thrash |
| CLS | `largestShiftTarget` | Element injected without geometry | Reserve width/height, `aspect-ratio`, fixed ad slots |

3. Reproduce in the lab under throttling so the fix is testable.

```bash
npx lighthouse https://example.com/ --preset=desktop --only-categories=performance \
  --output=json --output-path=./lh.json --chrome-flags="--headless=new"
node -e "const r=require('./lh.json'); console.log(r.audits['largest-contentful-paint'].numericValue, r.audits['cumulative-layout-shift'].numericValue)"
```

4. Fix LCP at the document level: discover the hero early and give it geometry.

```html
<link rel="preload" as="image" href="/hero.avif" fetchpriority="high">
<img src="/hero.avif" width="1600" height="900" fetchpriority="high" alt="Workspace overview">
```

If `<img srcset>` selects a different file than the preload, the preload is wasted;
mirror it with `imagesrcset` and `imagesizes` on the link.

5. Fix INP by yielding to the browser before heavy work, and by shrinking the handler.

```ts
async function onSearch(input: string) {
  const q = input.trim()
  await new Promise<void>((resolve) => setTimeout(resolve, 0)) // let the next frame paint
  const rows = await search(q)
  render(rows)
}
```

6. Fix CLS by reserving space and matching fallback font metrics.

```css
.hero { aspect-ratio: 16 / 9; width: 100%; height: auto; }
.ad-slot { min-height: 250px; contain: layout; }

@font-face {
  font-family: "Inter Fallback";
  src: local("Arial");
  size-adjust: 107%;
  ascent-override: 90%;
}
body { font-family: Inter, "Inter Fallback", sans-serif; }
```

7. Gate lab metrics in CI and alert on field p75; they catch different failures. Save this as `lighthouserc.json`.

```json
{
  "ci": {
    "collect": { "url": ["http://localhost:3000/"], "numberOfRuns": 3 },
    "assert": {
      "assertions": {
        "largest-contentful-paint": ["error", { "maxNumericValue": 2500 }],
        "cumulative-layout-shift": ["error", { "maxNumericValue": 0.1 }],
        "total-blocking-time": ["warn", { "maxNumericValue": 200 }]
      }
    }
  }
}
```

```bash
npx @lhci/cli autorun
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Lab score 100 but field p75 LCP is 4.2s | Lab ran on fast hardware with a warm cache | Segment field data by device, reproduce with 4x CPU slowdown and cold cache |
| A page has no INP in CrUX | Users only scrolled or hovered; neither counts as an interaction | Instrument real click/tap flows with `web-vitals` on the page |
| LCP improves in the lab, not in the field | The LCP element differs per user after personalization | Group RUM samples by `attribution.target` and optimize the dominant one |
| CLS reads 0.0 while users report jumping | The shift follows a tap and is not counted by the metric | Reserve space anyway; confirm with a manual Layout Instability trace |
| INP regresses only on low-end Android | Desktop RUM averages hide main-thread cost | Segment by `deviceMemory` and `hardwareConcurrency`, test at 6x throttle |
| Preloaded hero is still slow | `srcset` selected a different file than the preload | Add `imagesrcset`/`imagesizes` to the preload link |
| Gains disappear within a week | A third-party tag adds late layout and main-thread work | Reserve fixed slots, load the tag after interaction, alert on p75 |

## Verification

- `npx @lhci/cli autorun` prints assertion results and exits 0 when LCP <= 2500 and CLS <= 0.1.
- `node -e "const r=require('./lh.json'); console.log(r.audits['largest-contentful-paint'].numericValue)"` prints a number at or below `2500`.
- `curl -s -X POST https://example.com/rum -H 'content-type: application/json' -d '{"name":"LCP","value":1800,"id":"t"}' -o /dev/null -w '%{http_code}\n'` returns `204`.
- After 28 days, CrUX p75 for the URL shows LCP <= 2500 ms, INP <= 200 ms, CLS <= 0.1, mobile segment.

## Sources (2026)

- https://web.dev/articles/vitals
- https://web.dev/articles/inp
- https://web.dev/articles/optimize-lcp
