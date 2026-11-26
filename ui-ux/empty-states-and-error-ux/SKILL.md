---
name: empty-states-and-error-ux
description: Use when a UI needs empty, loading or error states.
version: "2026.1.0"
metadata:
  hermes:
    tags: [ux, empty-states, error-handling, loading]
    category: ui-ux
---

# Design empty, loading and error as states, not as absences

A data surface has at least six states and most teams design one. The blank panel is
not neutral: users read it as "broken", "still loading" or "I did something wrong",
and every one of those readings costs a support ticket. Treat each state as a screen
with its own copy, action and announcement, and build them before the happy path.

## When to Use

- A list, table, dashboard or inbox can be empty on first run, empty after filtering, or fail to load.
- Users report "nothing happened" after an action, or retry by refreshing the page.
- Analytics show a drop-off on a screen that is often empty for new accounts.
- Do not use for optimistic UI rollback design; that is a data-layer decision, not a state screen.

## Compatibility & Stack Matrix (2026)

| Component | Version | Note |
| --- | --- | --- |
| React | 19.x | `useTransition` keeps the shell interactive while a section reloads |
| TanStack Query | 5.x | `isPending` / `isError` / `refetch` map to the state union below |
| Playwright | 1.4x | `page.route()` forces empty, slow and 500 responses in CI |
| axe-core | 4.10+ | catches missing `role="status"` targets and heading-order breaks |
| Chrome DevTools | current | Network throttling to see the skeleton and the delayed spinner |

## Production Implementation

1. Inventory the states before styling any of them. One component per cause, because
   "no data" and "request failed" need different words and different actions.

| State | Trigger | User sees | Required action |
| --- | --- | --- | --- |
| First run | account has zero records and never had any | what this space is for | primary create action |
| No results | query matched nothing | the query, spelled back | clear or widen the search |
| Filtered to zero | active filters exclude everything | the active filters as chips | remove one filter |
| Loading | request in flight | skeleton matching final layout | none |
| Partial | one section failed, others loaded | content plus a scoped error | retry that section only |
| Error | request failed | what failed, in user terms | retry and an escape hatch |

2. Give the first-run state a heading, a reason and exactly one primary action.

```html
<section aria-labelledby="invoices-empty-title">
  <h2 id="invoices-empty-title">No invoices yet</h2>
  <p>Invoices you send appear here with their payment status.</p>
  <a class="button" href="/invoices/new">Create your first invoice</a>
  <p class="hint">Or <a href="/invoices/sample">open a sample invoice</a> to see the layout.</p>
</section>
```

3. Match the skeleton to the real row height so the page does not jump when data lands.
   Show a spinner only after 300 ms, otherwise fast responses flash a loader.

```css
.skeleton-row { height: 44px; border-radius: 6px; background: linear-gradient(90deg, #eee, #f5f5f5, #eee); animation: shimmer 1.2s infinite; }
@media (prefers-reduced-motion: reduce) { .skeleton-row { animation: none; } }
```

4. Keep the error state visually and semantically distinct from empty. An error gets an
   icon, a heading, a consequence and a retry; empty gets a heading and a create action.
   Never reuse the same component, because "no invoices" shown after a 500 teaches the
   user their data is gone.

5. Order the copy: what happened, what it means, what to do, then a reference code.
   "We could not load your invoices. Nothing was lost. Retry, or download last month's
   export. Reference: INV-7f3a" beats "Error 500" on every measure.

6. Retry with one manual trigger plus capped backoff, and keep the operation idempotent
   so a double retry cannot create two records.

```ts
export async function requestWithRetry<T>(url: string, init: RequestInit = {}) {
  const idempotencyKey = crypto.randomUUID(); // one key per logical operation
  for (let attempt = 0; attempt < 3; attempt++) {
    const res = await fetch(url, {
      ...init,
      headers: { ...init.headers, "idempotency-key": idempotencyKey },
    });
    if (res.ok) return (await res.json()) as T;
    if (res.status < 500 && res.status !== 429) throw new Error(`fatal:${res.status}`);
    await new Promise((r) => setTimeout(r, 2 ** attempt * 400 + Math.random() * 200));
  }
  throw new Error("retry-exhausted");
}
```

7. Model the surface as a union so a state cannot be forgotten at the render site.

```tsx
import { useInvoices } from "./useInvoices";

export function Invoices() {
  const { data, error, isPending, refetch } = useInvoices();

  if (isPending) return <SkeletonRows rows={5} />;
  if (error) {
    return (
      <ErrorState
        title="We could not load your invoices"
        detail="Nothing was lost. Retry, or export last month from Settings."
        onRetry={() => refetch()}
      />
    );
  }
  if (data.length === 0) return <FirstRunEmpty />; // create action lives here, not in a tooltip
  return <InvoiceTable items={data} />;
}
```

8. Announce state changes without stealing focus (4.1.3 Status Messages): render an empty
   `role="status"` region once, then write "Loaded 12 invoices" or "Retry failed" into it.
   Do not put `role="alert"` on a container that exists at load.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Blank panel after the request finishes | component returns `null` for an empty array | render the first-run state with one primary action |
| Users call a slow list "broken" | spinner only, no layout, no expectation set | skeleton rows at final row height; spinner after 300 ms |
| Same screen for "no results" and "no data" | one empty component for every cause | branch on cause; no-results keeps the query visible and offers a clear action |
| Error screen reads `500 Internal Server Error` | the raw exception reached the UI | lead with the consequence, keep the code as a copyable reference |
| Retry loop hammers the API | retry button wired to an immediate refetch in a loop | single manual retry plus capped exponential backoff with jitter |
| Retry wipes a half-typed comment | refetch replaces local form state | keep a draft, retry only the request |
| Screen reader silent after a successful retry | no live region, or it was added after the update | mount the empty live region first, update its text after |

## Verification

```bash
npx playwright test tests/states.spec.ts --reporter=line
# expected: 5 passed (empty, slow, 500, retry-success, retry-exhausted)
```

```bash
npx @axe-core/cli http://localhost:3000/invoices --tags wcag22aa --exit; echo "exit=$?"
# expected: exit=0 in the empty state, i.e. heading order and live region still valid
```

Manual check with Slow 3G: skeleton appears, content replaces it without a layout jump,
and a forced offline retry leaves the typed draft intact.

## Sources (2026)

- https://www.nngroup.com/articles/empty-state-interface-design/ (status, learnability, direct pathways)
- https://carbondesignsystem.com/patterns/empty-states-pattern/ (state variants and actions)
- https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html (4.1.3, Level AA)
