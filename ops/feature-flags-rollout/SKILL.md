---
name: feature-flags-rollout
description: Use when flags gate releases or never get deleted.
version: "2026.1.0"
metadata:
  hermes:
    tags: [feature-flags, rollout, kill-switch, openfeature]
    category: ops
---

# A flag is a decision with an owner, a default and an expiry date

Flags fail two ways: one gates authorization in the browser, another outlives its
release until nobody knows which branch is real. Both are fixed at creation time.

## When to Use

- The same flag is evaluated in the browser for rendering and again in the API.
- A "5% rollout" flips individual users on and off on every page refresh.
- A provider outage silently disables checkout because the default was `true`.
- Nobody can name the owner of the flags still in the config store.
- A kill switch exists in the runbook but has never been fired under load.
- Skip this when the value is permanent config — that is a setting, not a flag.

## Compatibility & Stack Matrix (2026)

| Component | Version/variant | Notes |
| --- | --- | --- |
| OpenFeature specification | flag evaluation (stable sections) | vendor-neutral API; provider owns targeting |
| OpenFeature Java SDK | 1.14.2 | `OpenFeatureAPI.getInstance()`, `getBooleanValue` |
| OpenFeature JS server SDK | 1.x | `@openfeature/server-sdk`, evaluator on the server |
| Providers | flagd, Unleash, LaunchDarkly, in-memory | swap the provider, keep call sites |
| Flag store | git-backed YAML/JSON | reviewable diff, one source of truth |

Any evaluation error returns the caller's default value, so the default is a
production setting, not a formality.

## Production Implementation

1. Classify the flag before creating it; the class sets the lifetime and the
   review path. Most flag debt is a release flag that was never given an end date.

| Type | Lifetime | Must carry |
| --- | --- | --- |
| release | days | owner, removal ticket, expiry date |
| experiment | weeks | metric, sample size, decision owner |
| ops / kill switch | permanent | owning on-call, tested fallback |
| permission | quarters | entitlement source of truth, audit log |

2. Evaluate anything that guards a write on the server. A client-side flag is a
   rendering hint; it is not an access control, because the client is attacker
   controlled.

```ts
import { OpenFeature } from "@openfeature/server-sdk";

const client = OpenFeature.getClient("checkout");
const ctx = { targetingKey: user.id, plan: user.plan, region: user.region };
const v2 = await client.getBooleanValue("checkout.v2", false, ctx);
```

   `targetingKey` is the reserved context field every provider buckets on. Pass
   the same key from every service or the same user gets two different answers.

3. Bucket percentage rollouts deterministically. `random()` per request is the
   most common cause of "it works, refresh and it doesn't".

```ts
import { createHash } from "node:crypto";

export function inRollout(flagKey: string, targetingKey: string, bps: number): boolean {
  const h = createHash("sha256").update(`${flagKey}:${targetingKey}`).digest("hex");
  return (parseInt(h.slice(0, 8), 16) % 10_000) < bps;   // bps = 500 -> 5%
}
```

   Include the flag key in the hash so two rollouts do not hit the same cohort,
   and keep the key stable when traffic moves between services.

4. Make the default the safe path and log every evaluation error. During a
   provider outage the SDK returns the default without throwing.

```ts
const detail = await client.getBooleanDetails("checkout.v2", false, ctx);
if (detail.errorCode) {
  log.warn({ flag: "checkout.v2", errorCode: detail.errorCode, variant: detail.variant });
}
```

   New code defaults to `false`; a kill switch defaults to `true` for the old
   path. Both defaults must be the behaviour you want with the provider dead.

5. Ship the kill switch separately from the release flag. One flag that means
   "new checkout" and also "turn checkout off" cannot express both states.

```yaml
# flags/ops.yaml — loaded as a local fallback snapshot at boot
flags:
  - key: checkout.enabled
    type: ops
    default: true
    owner: payments-oncall
    expires: never
  - key: checkout.v2
    type: release
    default: false
    owner: checkout-team
    expires: 2026-09-30
```

6. Test both paths, always. A flag shipped with only the ON path tested is a
   production experiment on your users.

```java
Map<String, Flag<?>> off = Map.of("checkout.v2", Flag.builder()
    .variant("on", true).variant("off", false).defaultVariant("off").build());
OpenFeatureAPI api = OpenFeatureAPI.getInstance();
api.setProviderAndWait(new InMemoryProvider(off));
Client client = api.getClient();
assertFalse(client.getBooleanValue("checkout.v2", true));   // default path

api.setProviderAndWait(new InMemoryProvider(Map.of("checkout.v2", Flag.builder()
    .variant("on", true).variant("off", false).defaultVariant("on").build())));
assertTrue(client.getBooleanValue("checkout.v2", false));   // new path
```

   Run the same assertions against the real provider's test environment once per
   release; in-memory providers prove the branch, not the targeting rule.

7. Bill the debt in CI: every key in code must exist in the registry, and no
   registry row may be past `expires`.

```bash
comm -23 \
  <(grep -rhoE 'get(Boolean|String|Number)Value\("[^"]+"' src | sed 's/.*("//' | sort -u) \
  <(grep -oE 'key: [a-z0-9.]+' flags/*.yaml | awk '{print $2}' | sort -u)
```

   Empty output means code and registry agree. Once a release flag has sat at 100%
   for a full cycle, delete the flag and the dead branch in one PR.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Users flip variants on refresh | bucketing with `Math.random()` | hash `flagKey:targetingKey`, fixed bucket count |
| Feature disappears during provider outage | default was treated as "enabled" | fail-safe default; alert on `errorCode` volume |
| Paid feature unlocked by editing the bundle | flag evaluated only in the client | re-evaluate server-side before any write |
| Registry says 12 flags, code has 40 | no ownership or expiry | CI job in step 7, one removal ticket per release flag |
| Kill switch takes 60s to apply | SDK poll interval with no invalidation | local snapshot plus push invalidation; test the outage path |
| Experiment result inconclusive | same flag does rollout and measurement | one decision per flag; separate keys per experiment |
| Two services disagree on a variant | different `targetingKey` or context per service | one key, one context schema, documented in the registry |

## Verification

- `npx jest test/flags --ci` prints `Tests: 6 passed` (ON path, OFF path, error
  path, bucketing determinism, kill switch, registry).
- The `comm -23` command in step 7 prints nothing; any key it prints is a flag
  used in code but missing from the registry.
- `grep -rn "getBooleanValue" src | wc -l` gives the call-site count you expect
  to find in the registry, so a new flag cannot land unreviewed.
- Manual: stop the provider, hit the page, confirm the safe path renders and the
  log contains one `errorCode` warning per evaluation.

## Sources (2026)

- https://openfeature.dev/docs/reference/intro/
- https://openfeature.dev/docs/reference/concepts/evaluation-api/
- https://martinfowler.com/articles/feature-toggles.html
