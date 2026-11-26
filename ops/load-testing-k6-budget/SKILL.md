---
name: load-testing-k6-budget
description: Use when load tests pass but the SLO regresses.
version: "2026.1.0"
metadata:
  hermes:
    tags: [performance, k6, load-testing, slo, ci]
    category: ops
---

# Spend a load test like a budget: one SLO, three workloads, honest percentiles

Most k6 suites fail in both directions: they pass while users complain because the
threshold was set from last week's average, or they block deploys on a random p95
because the load generator, not the service, ran out of CPU. The fix is to derive
thresholds from the SLO, split the workload into ramp/steady/spike, and prove which
side of the wire is saturated after every run.

## When to Use

- You must decide whether a release is performance-safe before a traffic event.
- A test passes but p99 in production is 4x the p95 the test reports.
- CI fails intermittently on latency and nobody can say if the service or the generator moved.
- Thresholds were copied from a blog post and no SLO number exists anywhere.
- Skip for a single-endpoint latency probe; the smoke run below covers that case.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Notes |
| --- | --- | --- |
| k6 | v2.x | v2.0.0 moved the REST API off by default and removed `--no-summary`; use `--summary-mode` |
| Executors | `ramping-arrival-rate`, `constant-arrival-rate`, `ramping-vus` | arrival-rate models an open workload; VU ramps model a closed one |
| Thresholds | `p(95)`, `p(99)`, `rate`, `count` | a failed threshold exits `99`, which is what CI reads |
| Output | `--summary-export`, `--out json=`, `--out csv=` | summary JSON is enough for a per-build record |
| Grafana Cloud k6 | optional | only needed when one generator cannot produce the load |

## Production Implementation

1. Derive the threshold from the SLO, not from a previous run. A 99.9% availability SLO
   allows 43m12s of downtime in 30 days; scaled to a 30-minute test at 50 rps (90,000
   requests) that is 90 failed requests, so `http_req_failed: ['rate<0.001']`. Latency
   thresholds come from the user-facing budget: if the page must render inside 1s and the
   API is one of three calls, the API gets `p(95)<300` and `p(99)<800`, never `avg<200`.

2. Declare three scenarios in one file so the same script can be a smoke test, a baseline
   and a spike, and so each result carries its own tags.

```js
// load/scenarios.js
import http from 'k6/http';

const BASE = __ENV.BASE_URL || 'https://staging.example.test';

export const options = {
  discardResponseBodies: true, // keep RAM for VUs, not HTML
  scenarios: {
    ramp: {
      executor: 'ramping-arrival-rate',
      startRate: 5, timeUnit: '1s', preAllocatedVUs: 50, maxVUs: 400,
      stages: [
        { target: 50, duration: '5m' },  // climb to steady rate
        { target: 50, duration: '10m' }, // hold: this window is the baseline
        { target: 0, duration: '2m' },
      ],
      tags: { workload: 'ramp' },
    },
    steady: {
      executor: 'constant-arrival-rate',
      startTime: '20m', rate: 50, timeUnit: '1s', duration: '15m',
      preAllocatedVUs: 60, maxVUs: 500,
      tags: { workload: 'steady' },
    },
    spike: {
      executor: 'ramping-arrival-rate',
      startTime: '36m', startRate: 50, timeUnit: '1s', preAllocatedVUs: 50, maxVUs: 900,
      stages: [
        { target: 300, duration: '30s' }, // 6x in half a minute
        { target: 300, duration: '2m' },
        { target: 50, duration: '1m' },
      ],
      tags: { workload: 'spike' },
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.001'],
    'http_req_duration{workload:ramp}': ['p(95)<300', 'p(99)<800'],
    'http_req_duration{workload:steady}': ['p(95)<300', 'p(99)<800'],
    'http_req_duration{workload:spike}': ['p(95)<1200'], // spikes may degrade, not fail
    dropped_iterations: ['count<10'],
  },
};

export default function () {
  http.get(`${BASE}/api/catalog?page=1`, { tags: { endpoint: 'catalog' } });
  http.get(`${BASE}/api/cart`, { tags: { endpoint: 'cart' } });
}
```

3. Get think time right or every number you read is fiction. In a closed model
   (`ramping-vus`, `constant-vus`) add `sleep(<measured gap>)` at the end of the iteration,
   because the VU would otherwise hammer the service as fast as it answers. In an
   arrival-rate executor the `rate` already paces iterations — k6's own docs say not to add
   `sleep` at the end — so model the pause by lowering `rate`. Take the gap from real
   session data (median between page views), never from a guess.

4. Keep the generator out of the bottleneck. Watch `dropped_iterations` (the generator
   could not start iterations on time), `vus_max` (it ran out of pre-allocated VUs) and
   `http_req_blocked`/`http_req_connecting` (connection queueing, not service time).

```bash
k6 run --summary-export=run.json load/scenarios.js
jq '.metrics.dropped_iterations.count, .metrics.http_req_blocked["p(95)"]' run.json
```

If `dropped_iterations` is non-zero the result describes your laptop, not the service:
raise `preAllocatedVUs`/`maxVUs`, stop fetching bodies you never parse, or run the load
from several machines. If `http_req_blocked` p95 grows while `http_req_waiting` stays
flat, the client is queueing connections — a generator or egress problem.

5. Split CI: smoke on every PR, the full workload nightly. A smoke run answers "does the
   script still work and is the service alive", nothing else, and finishes in a minute.

```bash
# PR gate: one iteration of the steady scenario; --vus/--iterations are ignored here
k6 run --scenario steady --once --quiet --summary-mode=compact load/scenarios.js

# nightly: full run against a dedicated environment, record the evidence
k6 run --summary-export="artifacts/k6-$(date -u +%F).json" load/scenarios.js
```

6. Read percentiles as distributions, never as averages of averages. `p(95)` and `p(99)`
   are computed from the raw samples of the whole run, so a per-minute average of p95 tells
   you nothing. Compare the same scenario, same data, same environment — two runs of
   different shapes are not comparable — and treat a p99 that moves while p95 stays flat as
   a queue or GC signal rather than noise. `http_req_failed` counts only non-2xx/3xx
   responses by default, so add a `check()` for payload correctness if a 200 can be wrong.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Test passes, users report slow checkout | Thresholds on `avg`, or on the whole run instead of the endpoint | Tag per endpoint and threshold `p(95)`/`p(99)` on the tag |
| `dropped_iterations` above zero, latency looks great | The generator ran out of VUs or CPU | Raise `preAllocatedVUs`/`maxVUs`, drop response bodies, split across generators |
| p95 stable, p99 doubles after each release | Connection pool or GC, not raw throughput | Compare `http_req_waiting` vs `http_req_blocked`; look at pool saturation under the same rate |
| Nightly run flaps between pass and fail | Shared staging with other jobs, or a different dataset each run | Dedicated environment, seeded data, compare only identical runs |
| Spike scenario reports 500s that never happen in prod | Ramp is faster than any real surge, or autoscaling is disabled in staging | Match the surge to a real event (a campaign, a cron fan-out) and enable the same autoscaling |
| Threshold passes at 5 rps and fails at 50 | Load is too low to reach the queue | Pick the rate from production traffic percentiles, not from what the runner survives |

## Verification

```bash
k6 inspect load/scenarios.js | jq '.scenarios | keys'
k6 run --scenario steady --once --quiet load/scenarios.js; echo "exit=$?"
k6 run -e BASE_URL=https://staging.example.test load/scenarios.js; echo "exit=$?"
```

Expected: `k6 inspect` prints `["ramp","spike","steady"]`, which proves the options
parsed before any load is sent; the `--once` run prints `exit=0`; the full run prints a
`█ THRESHOLDS` block with `✓` per threshold and `exit=0`. A `✗` line there is a real
finding and the process exits `99`, which is the code CI must treat as failure — verify
the pipeline fails on it rather than swallowing the status.

## Sources (2026)

- https://grafana.com/docs/k6/latest/using-k6/k6-options/reference/
- https://grafana.com/docs/k6/latest/using-k6/thresholds/
- https://grafana.com/docs/k6/latest/using-k6/scenarios/executors/constant-arrival-rate/
- https://grafana.com/docs/k6/latest/testing-guides/automated-performance-testing/
- https://grafana.com/docs/learning-paths/automate-k6-cicd/handle-exit-code/
