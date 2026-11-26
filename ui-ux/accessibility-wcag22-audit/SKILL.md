---
name: accessibility-wcag22-audit
description: Use when auditing a UI to WCAG 2.2 AA with evidence.
version: "2026.1.0"
metadata:
  hermes:
    tags: [accessibility, wcag, audit, a11y-testing]
    category: ui-ux
---

# Audit to WCAG 2.2 AA with reproducible evidence

A conformance claim is a legal and commercial statement, so the deliverable of an audit
is not a score but findings a second person can reproduce on the same build: criterion,
element, steps, expected, actual, severity. W3C is explicit that no tool alone can
determine conformance; automation sets the baseline, manual passes decide the verdict.

## When to Use

- You must state "this product meets WCAG 2.2 AA" for a launch, tender or customer security review.
- A redesign is about to ship and keyboard or screen-reader regressions are suspected.
- You need a regression gate, not a one-off report: the same rules must run in CI and drift must fail the build.
- Skip this when the ask is visual design critique; use a design review instead and keep the audit for conformance.

## Compatibility & Stack Matrix (2026)

| Component | Version | Note |
| --- | --- | --- |
| axe-core | 4.10+ | rule tags include `wcag2a`, `wcag2aa`, `wcag21aa`, `wcag22aa` |
| @axe-core/cli | 4.10.x | `axe <url> --exit` returns 1 on any failing rule |
| pa11y | 8.x | `--standard WCAG2AA`, htmlcs runner, `--reporter json` |
| Playwright + @axe-core/playwright | 1.4x | only way to scan post-interaction states (dialogs, errors) |
| NVDA 2026 / VoiceOver | Windows 11 / macOS 15 | manual pass; NVDA with Firefox or Chrome |
| Browsers in scope | Chrome, Firefox, Safari, Edge (current) | 2.4.11 and 2.5.8 differ per engine |

Pin every tool in `package.json`; a floating axe major silently changes the rule set
between audits and makes two reports incomparable.

## Production Implementation

1. Fix scope and target first, because a finding without a scope is an opinion.

```bash
mkdir -p audit/evidence audit/reports
cat > audit/scope.txt <<'EOF'
target: WCAG 2.2 Level AA
views: 12 (structured sample) + 5 random
processes: signup, checkout, password reset
assistive tech: NVDA 2026 + Firefox, VoiceOver + Safari
EOF
```

2. Build a sample set that includes complete processes, not just landing pages.
   A checkout that fails only at the payment step must be sampled at the payment step.

```bash
cat > audit/urls.txt <<'EOF'
https://app.example.com/
https://app.example.com/signup
https://app.example.com/checkout/address
https://app.example.com/checkout/payment
EOF
```

3. Run the automated baseline and keep the JSON, since the delta between runs is the useful number.

```bash
npx @axe-core/cli $(cat audit/urls.txt) \
  --tags wcag2a,wcag2aa,wcag21aa,wcag22aa --exit --save audit/axe.json
npx pa11y --standard WCAG2AA --reporter json https://app.example.com/ > audit/pa11y.json
```

4. Scan states that a crawler never reaches: open dialogs, inline errors, expanded menus.

```ts
// audit/states.spec.ts
import { test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("error and dialog states", async ({ page }) => {
  await page.goto("/checkout/payment");
  await page.getByRole("button", { name: "Pay now" }).click(); // triggers inline errors
  const { violations } = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  const blocking = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  if (blocking.length > 0) throw new Error(JSON.stringify(blocking.map((v) => v.id)));
});
```

5. Run the keyboard pass by hand and record it, because this is where automation stops.
   - Tab from the address bar through the page: order must match visual order and every control must be reachable.
   - Focus must be visible on every stop (2.4.7) and never fully covered by sticky headers or chat widgets (2.4.11).
   - A skip link must appear on first Tab and move focus past navigation (2.4.1).
   - Escape closes overlays; focus returns to the trigger, not to `<body>`.
   - Nothing traps focus: 20 Tabs must eventually leave any widget; scrolling the focused element under a sticky header must not hide it (2.4.11), even when automation is green.

6. Run one screen-reader pass per template, in browse mode and forms mode.
   - Landmarks resolve (`banner`, `nav`, `main`, `contentinfo`) and the heading outline is sane.
   - Each control announces name, role and state; a field announced as "edit text" has no label.
   - Inline errors are announced when they appear and stay re-readable when focus returns (3.3.1, 4.1.3); dialogs announce their title on open.

7. Treat ARIA as a last resort, because every wrong attribute is worse than no attribute.

| Misuse | Effect | Correct move |
| --- | --- | --- |
| `<div role="button" tabindex="0">` with a click handler only | Enter and Space do nothing | use `<button>`; if forced, handle `keydown` for Enter and Space |
| `aria-label` that drops the visible words | voice control cannot say "click Add to cart" | keep visible text inside the accessible name (2.5.3 Label in Name) |
| `aria-hidden="true"` on a focusable element | focus lands on nothing | hide with `hidden`/`display:none`, or remove from tab order |
| `aria-expanded` on a control that opens nothing | screen reader reports a false state | bind it to the popup it actually controls |
| `role="alert"` on a container present at load | no announcement on update | insert the live region empty, then fill it |

8. Record every finding in one schema so the report, the ticket and the retest agree.

```json
{
  "id": "A11Y-014",
  "criterion": "2.4.11 Focus Not Obscured (Minimum)",
  "level": "AA",
  "page": "/checkout/address",
  "selector": "input[name=postalCode]",
  "steps": ["Tab from #city to #postalCode", "Element scrolls under sticky header"],
  "expected": "Focused control stays at least partially visible",
  "actual": "Sticky header covers the input completely",
  "severity": "serious",
  "evidence": "audit/evidence/A11Y-014.webm",
  "fix": "scroll-margin-top: 96px on :focus-visible"
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| axe reports 0 violations, keyboard users still get stuck | rules cover machine-detectable DOM failures; 2.4.11 and 2.1.2 have no reliable rule | run step 5 and attach a screenshot per focus stop |
| Contrast passes in the report but fails on screen | scanner measured a gradient, a hover state or a font that had not loaded | wait for `document.fonts.ready` and network idle, then measure the painted state |
| A field is announced as "edit text" with no name | only a placeholder is present; placeholder is not a label (3.3.2) | add a real `<label for>`; keep the placeholder as an example |
| Findings are rejected by the client as "opinions" | records lack steps and evidence | one JSON record per finding with selector, steps and a recording |
| Dialog opens and focus stays behind it | focus not moved into the dialog, no trap and no restore | move focus to the dialog title, trap inside, restore to the trigger on close |
| Same page passes then fails between runs | animated carousel or lazy content changed the scanned DOM | freeze animations (`prefers-reduced-motion`), scan after load settles |
| Audit blocked on 403 for third-party widgets | iframe owners forbid scanning | document the third party as an exclusion in scope, never as a pass |

## Verification

```bash
npx @axe-core/cli https://app.example.com/ --tags wcag22aa --exit; echo "exit=$?"
# expected: exit=0 and no rule rows printed
```

```bash
python3 - <<'PY'
import json
data = json.load(open("audit/axe.json"))
pages = data if isinstance(data, list) else [data]
print(f"{len(pages)} pages; {sum(len(p.get('violations', [])) for p in pages)} violations")
PY
# expected: 4 pages; 0 violations
```

Manual gate: every control reachable and visibly focused in a full Tab pass, and each
template announces name, role and state under NVDA. Both must be ticked before a
conformance statement is written.

## Sources (2026)

- https://www.w3.org/WAI/WCAG22/quickref/ (criteria text and levels, opened for this skill)
- https://www.w3.org/TR/WCAG-EM/ (scope, sample set, evaluation procedure)
- https://www.w3.org/WAI/test-evaluate/ ("no tool alone can determine if a site meets accessibility standards")
- https://github.com/dequelabs/axe-core-npm (CLI flags `--tags`, `--exit`, `--save`)
