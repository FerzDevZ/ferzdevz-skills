---
name: analytics-event-taxonomy
description: Use when event names and properties drift per team.
version: "2026.1.0"
metadata:
  hermes:
    tags: [analytics, events, tracking-plan, schema, pii]
    category: web-dev
---

# Put the event taxonomy in the repo, not in a spreadsheet

Analytics rot is silent: `signup`, `user_registered` and `account_created` all fire with
different shapes, and six months later no dashboard matches the billing table. The fix is
a schema that ships with the code and rejects unknown events at the call site.

## When to Use

- Two teams emit different names or shapes for the same user action.
- A dashboard number cannot be reconciled with the database and nobody knows which events are inflated.
- You are adding a warehouse or CDP and need one definition of "active user" and "purchase".
- Free-text properties are being sent, and something in there looks like an email address.
- Skip for a single throwaway page-view counter with no downstream reporting.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Notes |
| --- | --- | --- |
| Segment Spec | `identify` / `track` / `page` / `screen` / `group` / `alias` | Six semantic calls with shared common fields; destinations map from these |
| GA4 events | automatic, enhanced, recommended, custom | `purchase`, `sign_up`, `login` are recommended and unlock prebuilt reports |
| GA4 naming | `snake_case`, starts with a letter, letters/digits/underscores | Case sensitive; `page_view`, `session_start`, `click`, `scroll` are reserved |
| GA4 parameters | `user_id`, `session_id`, `ga_*` reserved | Prefixing your own keys with `ga_` is rejected |
| Zod | 3.x / 4.x | Runtime validation in dev, drop-and-log in production |

## Production Implementation

1. Name events `object_action`, past tense, no UI vocabulary: `checkout_completed`, not
   `clickedBuyButton`; `subscription_cancelled`, not `cancel`. No spaces, no camelCase, no
   `_v2` suffix — a changed definition gets a new *property*, never a new event name.

2. Write the registry as code. It is the only source of truth for names, required
   properties and ownership.

```ts
// analytics/events.ts
import { z } from 'zod';

export const events = {
  checkout_completed: {
    owner: 'payments',
    props: z.object({
      order_id: z.string().uuid(),
      value_minor: z.number().int().nonnegative(),
      currency: z.string().length(3),
      payment_method: z.enum(['card', 'va', 'qris', 'ewallet']),
    }),
  },
  search_performed: {
    props: z.object({ query_length: z.number().int().nonnegative(), result_count: z.number().int() }),
  },
} as const;

export type EventName = keyof typeof events;
```

3. Send everything through one wrapper, so an unknown name is a type error.

```ts
// analytics/track.ts
export function track<N extends EventName>(
  name: N,
  props: z.input<(typeof events)[N]['props']>,
  ctx: { anonymousId: string; sessionId: string },
) {
  const parsed = events[name].props.safeParse(props);
  if (!parsed.success) {
    if (process.env.NODE_ENV !== 'production') throw new Error(`${name}: ${parsed.error.message}`);
    return void deadLetter({ name, issues: parsed.error.issues, at: Date.now() });
  }
  window.analytics?.track(name, { ...parsed.data, event_id: crypto.randomUUID(), session_id: ctx.sessionId });
}
```

It is the only place touching the vendor SDK, so swapping providers is a one-file change.

4. Separate identity from session, and set each once.

- `identify(userId, traits)` on login, signup and account switch — not on every page.
- `anonymousId` lives in a first-party cookie and rides the identify call, so pre-login history stitches to the user.
- `sessionId` belongs to the SDK or a 30-minute idle timer; a new id per event shreds every funnel.

5. Dedupe on both sides: a SPA mounts twice in development and effects re-fire on route
   change, so key each send by the logical action and let the server drop repeats.

```ts
const fired = new Set<string>();
export const once = (key: string, send: () => void) => { if (!fired.has(key)) { fired.add(key); send(); } };
```

Store `(event_id, name)` with a unique constraint for 24 hours; that also absorbs browser
retries and `sendBeacon` replays.

6. Minimise PII with an allowlist. The registry already does it: `z.object` strips
   unknown keys, so a property that is not declared cannot leave the client.

| Never send | Send instead |
| --- | --- |
| Email, phone, full name | `user_id`, `plan`, `account_age_days` |
| Card, bank account, address | `payment_method`, `bank_code` |

If a hashed identifier must travel, hash it server-side with a pepper and send only the
digest: an unhashed email in an analytics property is a breach with a retention policy.

7. QA the instrumentation like a feature.

```ts
// tests/analytics.test.ts
const reserved = new Set(['page_view', 'session_start', 'click', 'scroll', 'purchase']);

it('uses valid, non-reserved names', () => {
  for (const n of Object.keys(events)) expect(n).toMatch(/^[a-z][a-z0-9]*(_[a-z0-9]+)+$/);
  for (const n of Object.keys(events)) expect(reserved.has(n)).toBe(false);
});

it('rejects a missing required property', () => {
  expect(() => track('checkout_completed', { order_id: 'x' } as never, { anonymousId: 'a', sessionId: 's' })).toThrow(/order_id/);
});
```

8. Reconcile weekly against the billing table — `count(distinct order_id)` for
   `checkout_completed` versus `count(*)` of paid orders. A gap over ~2% is an
   instrumentation bug, not an insight.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Two names for one action in the dashboard | Naming left to each team's habit | Registry in code plus a rule: no `track()` call outside the wrapper |
| Event count roughly doubles | Effect fires on mount and on every route re-entry | `once()` keyed by logical action id, plus server-side dedupe on `event_id` |
| Property missing on one code path only | Optional at the call site | Zod schema per event; the type error fails the build first |
| GA4 shows the event under an unexpected name | Reserved name collision, or someone renamed it in the UI | Lint names against the reserved list; treat the property's event list as read-only |
| Every user looks new | `identify` never called, `anonymousId` regenerated on reload | Persist `anonymous_id` in a first-party cookie; call `identify` on login |
| Email addresses in event properties | A free-form object passed straight through | Allowlist properties in the schema; `z.object` strips the rest |
| Warehouse and vendor totals differ by 30% | Ad blockers drop client events and nothing mirrors them | Mirror critical events server-side and reconcile against the billing table |

## Verification

- `npx vitest run tests/analytics.test.ts` passes, and renaming an event in `events.ts` without updating the call site fails `npx tsc --noEmit`.
- List what the app actually emits and compare it with the registry:

```bash
grep -rhoE "track\('[a-z0-9_]+'" src | sort | uniq -c | sort -rn
```

Expected: every printed name also exists in `analytics/events.ts`, and no name appears
twice from two modules.

- In the vendor debugger (Segment or GA4 DebugView) one `checkout_completed` event shows
  `event_id`, `session_id` and only the declared properties — no email or phone anywhere.

## Sources (2026)

- https://segment.com/docs/connections/spec/
- https://support.google.com/analytics/answer/13316687
- https://developers.google.com/analytics/devguides/collection/ga4/events
