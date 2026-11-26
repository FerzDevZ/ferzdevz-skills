---
name: skill-library-auditor
description: Use when a skill pack drifts into stubs. Audit it.
version: "2026.1.0"
metadata:
  hermes:
    tags: [meta, skills, quality, audit]
    category: meta
---

# Audit a skill pack before it rots into stubs

A skill library fails quietly: every file still has frontmatter, every file still
"looks" fine, and after six months nobody notices that 60% of them are 35-line
stubs whose code blocks are comments. This audit makes that visible in one run
and turns it into a CI gate.

## When to Use

- You are adding a new skill pack or a batch of skills to one.
- An agent keeps loading a skill and still guessing (thin skill symptom).
- A reviewer asks "is this library any good?" and you need numbers, not vibes.
- Before publishing a pack to git, or before installing it into a profile.

## Compatibility & Stack Matrix (2026)

| Komponen | Versi | Catatan |
| --- | --- | --- |
| Python | 3.9+ | stdlib only; no pip install needed |
| Agent Skills spec | 2026 (agentskills.io) | SKILL.md + optional scripts/, references/, assets/ |
| Hermes | any | reads `name` + `description` at discovery time |
| Network checks | `--net` | GET with 8s timeout; 403/429 are reported, not fatal |

Skip the network pass when the machine is air-gapped; every other gate is offline.

## Production Implementation

1. Read the shape, never trust the count.

```bash
find . -name SKILL.md | wc -l
find . -name SKILL.md -exec wc -l {} + | sort -n | head -20
```

2. Run the structural gate.

```bash
python3 bin/audit.py --root .
```

3. Add the two gates that catch rot, not typos.

```bash
python3 bin/audit.py --root . --min-body 80   # depth
python3 bin/audit.py --root . --net           # dead sources
```

4. Read the output as four signals, in this order:

| Signal | Meaning | Action |
| --- | --- | --- |
| `FAIL n skill(s) with problems` | missing section, short body, no failure table | fix before anything else |
| duplicate pairs | two skills teach the same decision | merge into one, keep the shorter name |
| dead URLs | sources were invented or rotted | re-open the page, replace or delete the claim |
| `per category` imbalance | one category has 40 skills, another 2 | the pack mirrors habits, not needs |

5. Wire it into CI so it cannot be skipped.

```yaml
- run: python3 bin/audit.py --root .
- run: python3 bin/audit.py --root . --net
- run: python3 bin/catalog.py --check
```

6. When a skill fails depth, do not pad it. Load `skill-depth-upgrade` and add a
   third failure row that comes from a real incident, plus the command that detects it.
   Depth that is not evidence is noise.

7. Read the pack as a portfolio, once per wave, not per file. Four numbers decide the
   next move:

```bash
python3 bin/audit.py --root . --json | python3 -c "import json,sys,collections; \
d=json.load(sys.stdin); b=collections.Counter('under100' if s['lines']<100 else 'ok' for s in d['skills']); print(b)"
python3 bin/route_audit.py --json | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d['collisions']),'collisions')"
python3 bin/check_claims.py --json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['fail'],'failed claims')"
python3 bin/doctor.py | tail -1
```

| Signal | Healthy | Next move |
| --- | --- | --- |
| skills under 100 lines | 0-2 | rewrite the worst one, do not add a new skill |
| description collisions | 0 | fix the narrower description, never delete a skill to silence it |
| failed claims | 0 | update the number or write the check command instead |
| doctor | OK | if it is not OK, stop adding skills until it is |

8. Snapshot the verdict so the next session does not re-derive it:

```bash
python3 bin/audit.py --root . > /tmp/audit.txt 2>&1; tail -5 /tmp/audit.txt
```

## Failure Modes & Fixes

| Gejala | Sebab | Perbaikan |
| --- | --- | --- |
| Audit says `0 unknown identifiers` but skills feel useless | code blocks hold 2-6 lines, so the sample is too small to prove anything | require a runnable command in `## Verification` and count it |
| All skills pass, library still worthless | gates check form, not decisions | add `skill-selection-evals`: run 5 real prompts with and without the skill |
| Duplicate pairs spike after a batch | skills written from a template with three words changed | merge, or delete the weaker one; similarity > 0.86 is the threshold |
| `--net` marks many 403 | bot walls on vendor blogs | keep one primary source per skill (official docs) and cite blogs second |
| Descriptions get clipped in the index | description > 60 chars | rewrite as trigger: "Use when X. Do Y." |
| Install copies stale skills | `bin/install.sh` without a prior audit | the script audits first and aborts; never bypass it |

## Verification

- `python3 bin/audit.py --root .` exits 0 and prints `OK all skills pass`.
- `python3 bin/audit.py --root . --net` prints `net: checked N unique source URL(s)` with zero dead.
- `python3 bin/catalog.py --check` prints `catalog up to date`.
- Spot check: open the three longest skills and confirm each has >= 3 rows in
  Failure Modes and at least one command in Verification.

## Sources (2026)

- https://agentskills.io/home
- https://learn.microsoft.com/en-us/agent-framework/agents/skills
