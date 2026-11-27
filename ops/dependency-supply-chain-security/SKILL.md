---
name: dependency-supply-chain-security
description: Use when CI merges deps with known vulns, no gate.
version: "2026.1.0"
metadata:
  hermes:
    tags: [supply-chain, sbom, dependencies, security]
    category: ops
---

# Make every dependency pin, scan and SBOM traceable

A lockfile that CI ignores is a suggestion. A vulnerability scan that exits 0 on
findings is decoration. This skill fixes the three things an auditor asks for:
reproducible installs, a gate that fails on real findings, and an SBOM you can
hand to a customer for the exact artifact you shipped.

## When to Use

- CI runs `npm install` and the lockfile changes on every build.
- `npm audit` / `pip-audit` runs but nobody has ever seen it fail a build.
- A release goes out with no SBOM, or with one nobody can map to an image digest.
- A PR adds a package whose name is one character off a popular one.
- Skip this for a throwaway script with no deployed artifact.

## Compatibility & Stack Matrix (2026)

| Component | Version/variant | Notes |
| --- | --- | --- |
| npm | 10.x / 11.x | `npm ci`, `npm audit --audit-level`, `audit signatures` |
| pip-audit | 2.10+ | `-r`, `--strict`, `-f json`, `-o`; needs Python 3.10+ |
| osv-scanner | v2 | `scan source -r`, `--format`; reads lockfiles and SBOMs |
| syft | 1.x | `-o spdx-json=`, `-o cyclonedx-json=` |
| Node | 22 LTS / 24 | `npm ci` requires lockfile in sync |
| Python | 3.10+ | `--require-hashes` needs fully pinned requirements |

## Production Implementation

1. Enforce the lockfile instead of trusting it. `npm ci` fails when
   `package.json` and the lock disagree; `npm install` silently rewrites it.

```bash
npm ci --ignore-scripts
git diff --exit-code -- package-lock.json
```

2. Gate on findings with explicit thresholds, one gate per ecosystem. `--strict`
   makes pip-audit fail when a dependency cannot be resolved, which is the case
   that otherwise passes as "no vulnerabilities found".

```bash
npm audit --audit-level=high --omit=dev
pip-audit -r requirements.txt --strict -f json -o pip-audit.json
osv-scanner scan source -r . --format table
```

3. Run the dev-dependency audit separately. `--omit=dev` is right for the shipped
   runtime but hides build tooling that executes in CI with your token.

```bash
npm audit --audit-level=high
```

4. Generate an SBOM from the built artifact, not from the source tree, so the
   component list matches the image digest you deploy.

```bash
syft "$IMAGE" -o spdx-json=app.spdx.json -o cyclonedx-json=app.cdx.json
jq '.components | length' app.cdx.json
```

5. Pin direct dependencies exactly and let the lockfile carry transitive ranges.
   Force a patched transitive version with `overrides` rather than editing the
   lockfile by hand.

```json
{
  "dependencies": { "express": "5.1.0" },
  "overrides": { "minimist": "1.2.8" }
}
```

6. Verify registry signatures and provenance for what you installed. This is the
   only check that catches a package published from a stolen token.

```bash
npm audit signatures
```

7. Set an upgrade cadence that is automatic but not immediate: weekly Renovate
   PRs with a cooldown, so a malicious release is yanked before it reaches you.

```json
{
  "minimumReleaseAge": "7 days",
  "schedule": ["before 06:00 on monday"],
  "rangeStrategy": "pin"
}
```

8. Treat a new package as guilty until inspected: publish date, repository,
   maintainer history and install scripts are the four signals that separate a
   typosquat from a real dependency.

```bash
npm view LEFT-PAD repository.url time.created maintainers --json
npm view LEFT-PAD scripts --json
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `npm ci` fails with `EUSAGE` on a clean clone | lockfile out of sync with `package.json` | run `npm install` locally, review the lock diff, commit it |
| Audit gate green while a CVE ships | `--omit=dev` skipped the vulnerable package, or threshold too high | run a second `npm audit --audit-level=high` over dev deps |
| pip-audit reports nothing on a vulnerable app | it audited the ambient environment, not the requirements file | pass `-r requirements.txt --strict`, or `--locked` for a project |
| SBOM has 0 components | scanned a source tree or a distroless image with no package DB | scan the built image by digest, after `docker pull` |
| A typo-squatted package ran code during install | lifecycle scripts execute as the CI user | install with `--ignore-scripts`, then run only known build scripts |
| Findings disappear after a rebase | cache restored an old vulnerability DB or old lockfile | key the cache on the lockfile hash; refresh osv/trivy DB per run |

## Verification

- `npm ci --ignore-scripts` exits 0 and `git status --porcelain` prints nothing.
- `npm audit --audit-level=high` prints `found 0 vulnerabilities`.
- `pip-audit -r requirements.txt --strict` exits 0 and prints `No known vulnerabilities found`.
- `osv-scanner scan source -r .` exits 0 with no packages listed under "affected".
- `jq '.components | length' app.cdx.json` prints a number greater than 0.
- `npm audit signatures` exits 0 for every package in the lockfile.

## Sources (2026)

- https://google.github.io/osv-scanner/usage/
- https://pypi.org/project/pip-audit/
- https://docs.npmjs.com/cli/v11/commands/npm-audit/
