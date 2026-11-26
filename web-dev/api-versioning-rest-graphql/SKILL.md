---
name: api-versioning-rest-graphql
description: Use when an API change must not break old clients.
version: "2026.1.0"
metadata:
  hermes:
    tags: [api, rest, graphql, versioning, deprecation]
    category: web-dev
---

# Version only what breaks, and prove it with a diff

Most `v2` APIs exist because a field was renamed in a hurry. A version is a promise
about old clients and costs a second code path, a second test suite and a migration
guide — pay that only when a change breaks a correct client, and let CI prove it.

## When to Use

- You are changing a field's type, meaning or nullability while old clients still call it.
- Mobile builds stay pinned for months, so a deploy cannot be the migration mechanism.
- A GraphQL field needs to retire without freezing the whole schema at `v1`.
- You need a deprecation window with a date instead of an announcement in Slack.
- Skip for services deployed together on one release train — the deploy *is* the cutover.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Notes |
| --- | --- | --- |
| Path versioning | `/v1/orders` | Cheapest to route and cache; the version is part of the URL contract |
| Dated header versioning | `Stripe-Version: 2026-11-18.endive` | Stripe ships monthly releases with no breaking change, plus a major twice a year |
| GraphQL | one evolving schema, `@deprecated` | Spec §3.13.3; introspection exposes `isDeprecated` and `deprecationReason` |
| `Sunset` header | RFC 8594 | Informational RFC; the `sunset` link relation points at the migration notice |
| graphql-js | current `graphql` package | `findBreakingChanges(oldSchema, newSchema)` is the gate, no service needed |

## Production Implementation

1. Classify the change. Additive means no version: a new endpoint, a new response
   field, a new optional request field, a new documented error code, a new enum value
   for clients that have a default branch. Everything else breaks someone — removing or
   renaming a field, making an optional field required, changing a unit (`cents` to
   `decimal`), removing an enum value, or changing a status code for one condition.

2. Share one handler, mount it twice, and let an adapter map the shape.

```ts
// routes/orders.ts
export function ordersRouter(version: 'v1' | 'v2') {
  const r = Router();
  r.get('/orders/:id', async (req, res) => {
    const order = await getOrder(req.params.id); // one query for both versions
    if (!order) return res.status(404).json({ error: 'order_not_found' });
    res.json(version === 'v1'
      ? { id: order.id, amount: order.amountMinor / 100 }
      : { id: order.id, amount_minor: order.amountMinor });
  });
  return r;
}

app.use('/v1', ordersRouter('v1'));
app.use('/v2', ordersRouter('v2'));
```

The moment the `v1` branch gets its own query, the versions start returning different
data and the deprecation date becomes fiction.

3. If you version by header, pin it per request and vary caches on it.

```ts
// middleware/api-version.ts
const SUPPORTED = new Set(['2025-06-30.basil', '2026-11-18.endive']);

export function apiVersion(req, res, next) {
  const raw = req.header('api-version') ?? req.account.defaultApiVersion;
  if (!SUPPORTED.has(raw)) return res.status(400).json({ error: 'unsupported_api_version' });
  req.apiVersion = raw;
  res.setHeader('Vary', 'Api-Version'); // else one version is served to the other's clients
  next();
}
```

Pin the version on webhook endpoints too: Stripe events use the endpoint's version, not
the account default, so an upgraded API and an un-upgraded handler disagree about the
payload shape.

4. Announce deprecation in the response, not only in the changelog.

```ts
// middleware/deprecation.ts
export const deprecation = (sunsetISO: string, docs: string) => (req, res, next) => {
  const sunset = new Date(sunsetISO).toUTCString();
  res.setHeader('Sunset', sunset);                                  // RFC 8594, HTTP-date
  res.setHeader('Link', `<${docs}>; rel="sunset"; type="text/html"`);
  next();
};

app.use('/v1', deprecation('2027-03-31T00:00:00Z', 'https://docs.example.com/v2'));
```

5. Retire on usage, not on the calendar.

```sql
SELECT api_version, route, count(*) AS calls, max(created_at) AS last_seen
FROM api_request_log
WHERE created_at > now() - interval '30 days'
GROUP BY 1, 2 ORDER BY calls DESC;
```

Retire when `calls` is zero for the whole window, or the remainder is named accounts you
have contacted directly.

6. For GraphQL, deprecate in place — a second schema doubles every resolver.

```graphql
type Order {
  amountMinor: Int! @deprecated(reason: "Use total.minor. Removed after 2027-03-31.")
  total: Money!
}
```

Introspection reports the flag and the reason, so generated clients surface it. Fields
and enum values only appear when the query passes `includeDeprecated: true`; a diff that
forgets that flag sees a schema where nothing was ever removed.

7. Gate CI on a real diff, not on review attention.

```ts
// scripts/schema-diff.ts
import { readFileSync } from 'node:fs';
import { buildSchema, findBreakingChanges } from 'graphql';

const before = buildSchema(readFileSync(process.argv[2], 'utf8'));
const after = buildSchema(readFileSync(process.argv[3], 'utf8'));
const breaking = findBreakingChanges(before, after);

for (const c of breaking) console.error(`- [${c.type}] ${c.description}`);
console.log(breaking.length ? `breaking changes: ${breaking.length}` : 'no breaking changes');
process.exit(breaking.length ? 1 : 0);
```

Run `npx tsx scripts/print-schema.ts > schema/current.graphql` on every merge to main,
then diff that file against the committed previous dump. For REST the same gate
validates recorded fixtures against the OpenAPI document with `ajv`, so a removed
response property fails the job too.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| v1 and v2 slowly return different data | Each version got its own copy of the query | Keep one core function; the version should change serialisation only |
| A cache serves a `v2` payload to a `v1` client | Version lives in a header the cache ignores | Add `Vary: Api-Version` and key the CDN on it, or move the version into the path |
| Clients break the day a new enum value appears | `switch` without a default branch | Document enums as open, require a fallback branch, never rename an existing value |
| Webhook handler throws on a payload the API just returned | Endpoint pinned to an older version than the client | Set the version explicitly at endpoint creation; treat payloads as version-pinned fixtures |
| The sunset date passes and callers still arrive | No usage measurement, so the date was aspirational | Query request logs per version for 30 days; retire on zero |
| GraphQL gate reports nothing while a field was deleted | Introspection diff ran without `includeDeprecated: true` | Compare SDL dumps, or set the flag, so deprecated members are diffed |

## Verification

- `npx tsx scripts/schema-diff.ts schema/previous.graphql schema/current.graphql` prints `no breaking changes` and exits `0`; deleting a field from `current.graphql` must exit `1` and name it.
- `curl -sI https://api.example.com/v1/orders/42 | grep -iE '^(sunset|link|vary):'` prints a `Sunset` HTTP-date and a `Link` with `rel="sunset"`.
- `curl -s https://api.example.com/v1/orders/42 | jq 'has("amount")'` prints `true`; `/v2` prints `false`, while `has("amount_minor")` prints `true`.
- `curl -s $API/graphql -H 'content-type: application/json' -d '{"query":"{ __type(name:\"Order\"){ fields(includeDeprecated:true){ name isDeprecated } } }"}' | jq '[.data.__type.fields[] | select(.isDeprecated)] | length'` prints a number greater than `0` while the window is open.

## Sources (2026)

- https://docs.stripe.com/api/versioning
- https://spec.graphql.org/draft/
- https://www.rfc-editor.org/rfc/rfc8594.html
