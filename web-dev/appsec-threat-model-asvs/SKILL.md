---
name: appsec-threat-model-asvs
description: Use when a feature ships with no threat model.
version: "2026.1.0"
metadata:
  hermes:
    tags: [security, asvs, threat-model, authz, ssrf, secrets]
    category: web-dev
---

# Threat-model one feature, then prove it with numbered ASVS rows

A threat model that lives in a wiki nobody opens changes no code. The version that works
is small enough to fit in a pull request: one feature, one page of trust boundaries, STRIDE
prompts turned into concrete abuses, and every mitigation tied to a verification row with
an ID you can cite in review.

## When to Use

- A feature touches money, identity, tenancy or file upload and no threat model exists.
- An audit or customer questionnaire asks for OWASP ASVS level and nobody can name the rows already met.
- Authorization is checked in the UI, or in some route handlers but not all.
- A service fetches a user-supplied URL, shells out, or builds SQL by concatenation.
- Skip for a static marketing page: no assets, no entry points, no model to write.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Notes |
| --- | --- | --- |
| OWASP ASVS | 5.0.0 (published 30 May 2025) | row id is `<chapter>.<section>.<requirement>`; cite as `v5.0.0-8.2.2` |
| ASVS levels | L1 / L2 / L3 per feature | the chosen level ships inside the threat-model file |
| STRIDE | 6 categories (Microsoft) | prompts for abuse, not a scoring system |

## Production Implementation

1. Scope exactly one feature and draw it as five boxes: browser, edge, API, worker,
   datastore. Mark every trust boundary — the lines an attacker crosses — then list assets
   (session token, card data, tenant rows) and entry points (route, webhook, upload, topic).

2. Run STRIDE as six prompts against those crossings and keep only abuses reachable with the current code — one row per abuse, no mitigations yet.

| Prompt | Abuse that actually happens | ASVS chapter that answers it |
| --- | --- | --- |
| Spoofing | Session cookie replayed from another device after logout | V6 Authentication, V7 Session Management |
| Tampering | Client posts `total` and `tenantId` with the cart | V2 Validation and Business Logic |
| Repudiation | Refund issued with no actor recorded | V16 Security Logging and Error Handling |
| Information disclosure | Order id from another tenant returns 200 | V8 Authorization, V14 Data Protection |
| Denial of service | 2 GB upload pins the worker | V5 File Handling, V13 Configuration |
| Elevation of privilege | `role` claim edited in a self-contained token | V8 Authorization, V9 Self-contained Tokens |

3. Pick the level per feature — L1 for a public read, L2 for anything with accounts or
   money, L3 only where regulation demands it — and record claimed rows in a file the PR
   can diff. The id must match a real chapter; evidence must point at code, not policy.

```yaml
# security/asvs/checkout.yaml
feature: checkout
level: L2
rows:
  - id: v5.0.0-8.2.2   # data-specific access (IDOR/BOLA): scoped in the query, not after fetch
    claim: order reads are filtered by tenant_id in SQL
    evidence: src/server/orders/repository.ts#findForTenant
    status: verified
  - id: v5.0.0-1.2.4   # parameterized queries
    claim: no SQL string concatenation on the checkout path
    evidence: src/server/orders/repository.ts
    status: verified
  - id: v5.0.0-16.3.2  # failed authorization attempts are logged
    claim: 403s log actor, route and resource id, never the payload
    evidence: src/server/authz.ts#requirePolicy
    status: open
```

4. Enforce authorization at one choke point, then prove every route uses it. A policy
   registry plus a test that walks the route directory is what stops the fortieth endpoint
   from being the one without a check.

```ts
// src/server/authz.ts
type Ctx = { userId: string; tenantId: string; roles: string[] };
type Res = { tenantId: string; ownerId?: string };
type Policy = (c: Ctx, r?: Res) => boolean;

export const policies = {
  'orders:read': (c, r) => !!r && r.tenantId === c.tenantId,
  'orders:refund': (c, r) => !!r && r.tenantId === c.tenantId && c.roles.includes('finance'),
} satisfies Record<string, Policy>;

export function requirePolicy(name: keyof typeof policies) {
  return (c: Ctx, r?: Res) => {
    if (!policies[name](c, r)) throw Object.assign(new Error('forbidden'), { status: 403 });
  };
}
```

```ts
// src/server/authz.test.ts
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

it('every route declares an authorization policy', () => {
  const routes = readdirSync('src/app/api', { recursive: true, encoding: 'utf8' })
    .filter((f) => f.endsWith('route.ts')).map((f) => join('src/app/api', f));
  const missing = routes.filter((f) => !/requirePolicy\(/.test(readFileSync(f, 'utf8')));
  expect(missing).toEqual([]); // the diff names the unguarded route
});
```

5. Close the hot spots by construction: values are bound
   (`db.query('select … where tenant_id = $1 and id = $2', [tenant, id])`), outbound URLs
   pass one allowlist, and secrets never enter the repo.

```ts
// SSRF: parse, allowlist, and never follow a redirect to another host
const ALLOWED_HOSTS = new Set(['api.stripe.com', 'api.sendgrid.com']);
export function assertOutbound(raw: string): URL {
  const url = new URL(raw);
  if (url.protocol !== 'https:' || url.username || url.password) throw new Error('bad url');
  if (!ALLOWED_HOSTS.has(url.hostname)) throw new Error('host not allowed');
  return url; // caller passes redirect: 'error' to fetch
}
```

```bash
# secrets: run before every push; a hit means rotation, not a regex tweak
grep -rInE 'sk_live_[0-9a-zA-Z]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA|EC|OPENSSH) PRIVATE KEY' \
  --exclude-dir={node_modules,.git,dist} .
```

6. Record accepted risk with an owner and an expiry — a register without a date is a decision nobody revisits — and fail CI when one expires.

```yaml
# security/risk-register.yaml
- id: RISK-2026-014
  feature: checkout
  threat: 'refunds have no actor log yet (v5.0.0-16.3.2)'
  decision: accept
  control: 'finance role required; DB audit trigger captures the actor'
  owner: payments-team
  expires: 2026-09-30
```

```bash
grep -o 'expires: [0-9-]*' security/risk-register.yaml \
  | awk -v today="$(date -u +%F)" '$2 < today {print "EXPIRED:", $2}'
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Model lists 40 threats, none fixed | Whole product modelled at once | One feature, one page, abuses limited to code paths that exist today |
| Route returns another tenant's row | Ownership checked after a fetch by id | Scope in the query, assert in the policy, keep the route-walk test |
| Secrets found in a build artifact | `.env` copied in by a broad `COPY .` | Read from the secret manager at boot; run the grep in CI and pre-push |
| SSRF allowlist bypassed | Redirect followed, or DNS re-resolved after the check | `redirect: 'error'`, pin the resolved IP, reject link-local ranges |
| Register shows accepted risks past their date | No CI read of the file | The `expires` check fails the build; extend only with a new decision |
| "We are L2 compliant" with no evidence | Rows copied from a spreadsheet | Every row names a file and symbol; untested claims stay `status: open` |

## Verification

```bash
grep -c 'id: v5.0.0-' security/asvs/checkout.yaml
grep -c 'status: open' security/asvs/checkout.yaml
npx vitest run src/server/authz.test.ts
grep -o 'expires: [0-9-]*' security/risk-register.yaml | awk -v t="$(date -u +%F)" '$2 < t'
```

Expected: the first command prints the row count (an L2 feature usually lands between 12
and 25; zero means nothing was claimed); the second prints `0` once every claimed row has
evidence — the sample above still has one open row; Vitest prints `1 passed` and names any
unguarded route; the last prints nothing. A row pasted from an older ASVS version fails the
count check because its id matches no chapter.

## Sources (2026)

- https://asvs.owasp.org/
- https://github.com/OWASP/ASVS
- https://cheatsheetseries.owasp.org/cheatsheets/Threat_Modeling_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
