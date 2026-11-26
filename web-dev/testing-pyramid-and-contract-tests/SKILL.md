---
name: testing-pyramid-and-contract-tests
description: Use when e2e grows and unit tests disappear.
version: "2026.1.0"
metadata:
  hermes:
    tags: [testing, contract-tests, pact, playwright, flake]
    category: web-dev
---

# Buy signal per test second: unit budget, contracts, thin e2e

A suite rots in one direction: every bug becomes a browser test because that is the only
place nobody argues. Two years later the PR gate takes 40 minutes, half the team reruns
jobs instead of reading them, and the failure sits in a layer that cannot name the broken
function. The fix is arithmetic plus one contract layer.

## When to Use

- The e2e suite is the only place a regression is caught and it runs longer than 15 minutes.
- Two services deploy independently and break each other on field renames or status codes.
- Unit tests need a database, a queue or a browser, so nobody runs them locally.
- A flaky test has been retried to green for more than a week.
- Skip when the product is one deployable with no second consumer; contracts buy nothing there.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Notes |
| --- | --- | --- |
| Vitest | 3.x | one `--config` per layer keeps the include globs apart |
| Playwright | 1.x | `--shard`, `--repeat-each`, `--last-failed`, `--grep-invert` |
| Pact JS | current (`PactV3`, `Verifier`) | consumer builder and provider verifier in one package |
| Pact Broker CLI | `pact-broker` | `publish`, `can-i-deploy`, `record-deployment` |

## Production Implementation

1. Write the budget before the tests; publish it in the README and let CI enforce the
   runtime column, not the counts.

| Layer | How many | Wall clock | Runs on |
| --- | --- | --- | --- |
| unit | 150-300 | under 20s | every save |
| integration | 20-40 | under 3 min | every push |
| contract | 1 per consumer-provider pair | under 1 min | every push |
| e2e | 5-15 journeys | under 10 min | merge queue, sharded |

2. Split layers by config file, not by naming discipline. A unit test that reaches the
   app bootstrap via a barrel import opens a pool and takes 400ms; separate configs make
   that merge impossible. The integration config mirrors the glob with `pool: 'forks'`
   and `fileParallelism: false` — one database cannot reset a schema concurrently.

```ts
// vitest.config.unit.ts
import { defineConfig } from 'vitest/config';

export default defineConfig({ test: {
  include: ['src/**/*.test.ts'],
  exclude: ['src/**/*.int.test.ts', 'e2e/**'],
  environment: 'node', testTimeout: 5_000,
} });
```

3. Contract-test the seam, not the system. The consumer records only the fields it
   reads, which is the difference between a contract and an OpenAPI file describing
   every field nobody uses.

```ts
// src/orders/orders.client.contract.test.ts
import { PactV3, MatchersV3 } from '@pact-foundation/pact';
import { OrdersClient } from './orders.client';

const provider = new PactV3({ dir: 'pacts', consumer: 'orders-web', provider: 'orders-api' });
const { like, eachLike } = MatchersV3;

it('GET /orders returns what the table renders', () => {
  provider
    .given('two orders exist for customer 42')
    .uponReceiving('a request for the order list')
    .withRequest({ method: 'GET', path: '/orders', query: { customer: '42' } })
    .willRespondWith({ status: 200, headers: { 'Content-Type': 'application/json' },
      body: eachLike({ id: like('o_1'), total: like(1299), currency: like('EUR') }) });

  return provider.executeTest(async (mock) => {
    const orders = await new OrdersClient(mock.url).list('42');
    expect(orders[0].currency).toBe('EUR');
  });
});
```

4. Publish on every consumer build — a contract nobody verifies is a JSON file that
   lies — then verify from the provider and publish that result too.

```bash
npx pact-broker publish ./pacts --consumer-app-version="$(git rev-parse --short HEAD)" \
  --branch="$(git rev-parse --abbrev-ref HEAD)" \
  --broker-base-url="$PACT_BROKER_BASE_URL" --broker-token="$PACT_BROKER_TOKEN"
```

```ts
import { Verifier } from '@pact-foundation/pact';

await new Verifier({
  providerBaseUrl: 'http://127.0.0.1:3001',
  pactBrokerUrl: process.env.PACT_BROKER_BASE_URL,
  pactBrokerToken: process.env.PACT_BROKER_TOKEN,
  provider: 'orders-api', providerVersion: process.env.GIT_SHA,
  publishVerificationResult: true,
}).verifyProvider();
```

5. Gate the deploy on `can-i-deploy` (see Verification): it exits non-zero when a
   verification for that version is missing or failed, so it belongs in the deploy job.

6. With no broker (third-party API, monolith split), commit a JSON Schema snapshot taken
   from the provider build and assert the live response against it with Ajv in an
   integration test: `new Ajv({ allErrors: true }).compile(schema)` then
   `expect(validate(body)).toBe(true)`. Regenerate it from the provider, never from the
   consumer, or the diff stops meaning anything.

7. Make production unreachable from fixtures with one guard at the base-URL factory, so a
   test that forgets to read it still cannot point at prod.

```ts
// test/fixtures/base-url.ts
const ALLOWED = /(^|\.)(test|localhost|127\.0\.0\.1|internal)$/;
export function baseUrl(): string {
  const url = new URL(process.env.BASE_URL ?? 'http://127.0.0.1:3000');
  if (!ALLOWED.test(url.hostname)) throw new Error(`refusing to run against ${url.hostname}`);
  return url.origin;
}
```

Call it from `playwright.config.ts` (`use: { baseURL: baseUrl() }`) and from the
integration `beforeAll`; seed through a test-only endpoint with the same guard, because a
seeder pointed at a shared URL is how test rows reach a real tenant.

8. Keep the flake policy in writing: quarantine same day (`test.skip` or a `@quarantine`
   tag excluded with `--grep-invert`), fix or delete within five working days, re-admit
   only after twenty consecutive passes. Retries stay at one, in CI only, because
   `retries: 3` turns a race condition into a green suite.

9. Do not test at e2e: field validation, error copy, permission matrices, pricing,
   pagination, third-party sandboxes, email. It earns its place only when a journey
   crosses a process boundary and the failure costs money.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| PR gate takes 40 minutes and people rerun it blindly | Every bug became a browser test | Move validation, permission and calculation cases down a layer; keep one happy path and one money path per journey |
| Provider renames a field, consumer breaks in prod | Consumer tests ran against a mock; nothing verified the provider | Publish on consumer builds and run `can-i-deploy` in the deploy job |
| One test fails 1 in 8 runs and is retried to green | A real race (animation, shared tenant, clock) hidden by retries | Reproduce with `--repeat-each=20`, quarantine, fix the wait or fixture; retries max 1 |
| Unit suite needs Postgres to start | The test imports the app bootstrap via a barrel file | Import the unit under test directly; keep a separate integration config |
| e2e passes locally, fails only in CI | Tests share one seeded account and run in parallel | Unique tenant per worker, seed in `globalSetup`, one account per file |
| Contract file drifts silently | Snapshot regenerated by the consumer from its own output | Generate the snapshot from the provider build and review the diff like code |

## Verification

```bash
npx vitest run --config vitest.config.unit.ts 2>&1 | tail -3
npx playwright test --list | tail -2
npx playwright test e2e/checkout.spec.ts --repeat-each=20 --workers=4
npx pact-broker can-i-deploy --pacticipant orders-web \
  --version "$(git rev-parse --short HEAD)" --to-environment production
```

Expected: the Vitest summary prints `Tests  <n> passed (<n>)` in under 20s; the
Playwright listing ends with `Total: <n> tests in <m> files`; the repeat run prints
`20 passed`; `can-i-deploy` ends with `Computer says yes`. A `no` means a provider
verification is missing for that version, which is itself the finding.

## Sources (2026)

- https://martinfowler.com/articles/practical-test-pyramid.html
- https://docs.pact.io/
- https://github.com/pact-foundation/pact_broker-client
- https://playwright.dev/docs/test-sharding
- https://vitest.dev/config/
