---
name: ci-pipeline-gates
description: Use when CI order, caching or required checks drift.
version: "2026.1.0"
metadata:
  hermes:
    tags: [ci, github-actions, caching, release-engineering]
    category: ops
---

# Order CI so a red run fails for exactly one reason

Parallel gates report five failures for one bad import and hide which gate owns
the contract. Sequence the cheap gates first and pin what merge requires.

## When to Use

- Every PR shows a dozen red checks and nobody knows which one blocks merge.
- A cache makes CI faster but occasionally ships a build from old sources.
- A required check is green on `main` yet the PR stays "Expected — waiting".
- A matrix leg fails and the other legs are cancelled before you read them.
- Skip this for a repo with a single job and no branch protection.

## Compatibility & Stack Matrix (2026)

| Component | Version/variant | Notes |
| --- | --- | --- |
| GitHub Actions | hosted `ubuntu-24.04` | 4 vCPU, 16 GB; concurrency per repo |
| `actions/checkout` | `@v6` | shallow clone by default |
| `actions/setup-node` | `@v4` | `cache: npm` keys on the lockfile hash |
| `actions/upload-artifact` | `@v4` | required for artifact sharing; v3 retired |
| Node | 22 LTS, 24 current | matrix both only on `main` |
| `gh` CLI | 2.6x | `gh api`, `gh run view --json` |

A cache written on a feature branch is readable by that branch and its PR base.

## Production Implementation

1. Fix the order once: `lint -> typecheck -> test -> security -> build`. Each job
   declares `needs` on the one before, so the first red job names the defect.

```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

permissions:
  contents: read

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm }
      - run: npm ci && npm run lint

  typecheck:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm }
      - run: npm ci && npx tsc --noEmit

  test:
    needs: typecheck
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        node: [22, 24]
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v4
        with: { node-version: "${{ matrix.node }}", cache: npm }
      - run: npm ci
      - run: npm test

  security:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - run: npm audit --audit-level=high --omit=dev

  build:
    needs: security
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm }
      - run: npm ci && npm run build
      - uses: actions/upload-artifact@v4
        with:
          name: dist-${{ github.sha }}
          path: dist/
          retention-days: 7
          if-no-files-found: error
```

2. The `concurrency` block above cancels superseded PR runs and never a `main`
   run, because `cancel-in-progress` is an expression on the event name.

3. Cache package downloads, not `node_modules`. `setup-node` with `cache: npm`
   hashes `package-lock.json`; a hand-rolled `actions/cache@v4` key must include
   `hashFiles('**/package-lock.json')` or it restores a stale tree.

4. Decide fail-fast per job, not globally: `fail-fast: false` on the test matrix
   so one broken axis cannot hide the others; the default is fine for build.

5. Make merge depend on those job names, then read back what is enforced with
   `gh api repos/OWNER/REPO/branches/main/protection --jq '.required_status_checks.contexts'`.

6. Set `retention-days` per artifact (7 for build output, 14 for coverage). The
   repository default of 90 days is what quietly fills the storage quota.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| PR stays `Expected — waiting for status` forever | required check lives in a job a `paths:` filter skipped | drop the filter for that job or add an always-running aggregate job |
| Tests pass locally, fail on CI with stale code | cache restored `node_modules` from another branch | cache `~/.npm` only and always run `npm ci` |
| Every PR push cancels the running deploy | one `concurrency` group shared by PR and `main` | key the group on `github.ref`, gate cancellation on the event name |
| One matrix leg fails and its log is gone | `fail-fast: true` is the default | set `fail-fast: false` on test matrices |
| Deploy cannot download the build artifact | artifact name collides across runs or expired | name it with `${{ github.sha }}`, keep retention above the deploy window |

## Verification

- `gh workflow list` shows the workflow as `active`.
- `gh run view <run-id> --json jobs --jq '.jobs[] | "\(.name) \(.conclusion)"'` lists lint, typecheck, test, security, build in order with one failure at the owning stage.
- `gh api repos/OWNER/REPO/branches/main/protection --jq '.required_status_checks.contexts'` returns the same job names the workflow defines.
- `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` exits 0.
- A second push to the same PR marks the first run `cancelled`; a push to `main` never cancels.

## Sources (2026)

- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
- https://docs.github.com/en/actions/tutorials/store-and-share-data
