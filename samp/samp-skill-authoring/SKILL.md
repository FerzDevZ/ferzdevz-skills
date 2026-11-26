---
name: samp-skill-authoring
description: Use when a samp skill must pass the pack gates.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, meta, skills, process]
    category: samp
---

# Authoring a library skill

A skill in this pack is a contract, not a document: fixed frontmatter, fixed section order,
a failure table that is not empty, a runnable verification block, and sources that were
opened. `bin/audit.py` enforces the contract; the older `scripts/` gates still enforce API
truth and compilation. Know which gate owns which defect before rewriting anything.

## When to Use

- You are adding a folder under `samp/`.
- An existing skill failed a gate and you need to know which one is authoritative.
- A stub passed the gates and still answers nothing (form is not depth).

## Compatibility & Stack Matrix (2026)

| Gate | Command | Blocks on |
| --- | --- | --- |
| Contract | `python3 bin/audit.py --root . --only samp --names <name>` | frontmatter, section order, depth, empty failure table, source count |
| Sources live | same command plus `--net` | 404, 410, DNS/timeout |
| Structure (legacy) | `python3 samp/samp-dev-router/scripts/validate_library.py` | pre-contract header names; see failures |
| API truth | `python3 samp/samp-dev-router/scripts/check_natives.py` | identifier outside `assets/*natives.txt` |
| Includes | `python3 samp/samp-dev-router/scripts/compile_snippets.py` | fatal error 100 only |
| Patterns | `python3 samp/samp-dev-router/assets/harness/compile_harness.py` | any pawn error or warning |
| Catalog | `python3 bin/catalog.py --check` | stale `CATALOG.md` |
| Whole pack | `python3 samp/samp-dev-router/scripts/run_gates.py` | any gate that exits non-zero |

`bin/audit.py` is the contract gate and the only one the pack's CI calls. The `scripts/`
gates predate the contract and are scoped to the install path they sit in; both are useful,
they are not interchangeable.

## Production Implementation

1. Create the folder in the repo you are editing. `new_skill.py` writes to
   `~/.hermes/skills/samp/<name>`, not to the checkout, so use it only when the installed
   library is the thing you are extending:

```bash
mkdir -p samp/samp-my-topic
test -d samp/samp-my-topic && echo created
```

2. Write the body to the contract. Order is fixed and no section may be skipped, and no
   heading may appear at column zero anywhere except its own section start — a heading
   inside a fenced block truncates the section parser:

```text
# title
When to Use                              (3 bullets)
Compatibility & Stack Matrix (2026)      (markdown table)
Production Implementation                (numbered, commands that run)
Failure Modes & Fixes                    (table, >= 3 data rows)
Verification                             (command + expected output)
Sources (2026)                           (2-3 URLs you opened)
```

3. Frontmatter that passes: `name` equals the folder, `version` is `"2026.1.0"`,
   `metadata.hermes.category` is `samp`, and `description` is a 60-character sentence that
   opens with `Use when` and names the failure, not the topic. Body length stays between 100
   and 160 lines — past 160 the reader is paying for prose, not procedure.

4. Audit the one file, not the category, while drafting:

```bash
python3 bin/audit.py --root . --only samp --names samp-my-topic
```

`--names` takes a comma list, `--min-body`/`--min-sources` raise the floors, `--json`
gives machine output, `--strict` turns thin-but-passing skills into a warning.

5. Add the network check before you commit. Offline audit cannot tell a real URL from a
   plausible one:

```bash
python3 bin/audit.py --root . --only samp --names samp-my-topic --net
```

6. Run the remaining gates and read the result as advisory where the tooling is stale:

```bash
python3 samp/samp-dev-router/scripts/check_natives.py
python3 samp/samp-dev-router/scripts/compile_snippets.py
python3 samp/samp-dev-router/assets/harness/compile_harness.py
python3 bin/catalog.py --check
```

7. Register the skill in `samp-dev-router`: one row in the routing table under the task it
   serves, and the topic owner if it claims one.

8. Re-run the contract gate over the category so the batch is checked as a whole:

```bash
python3 bin/audit.py --root . --only samp
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `description is 61 chars (max 60)` | trigger written as a sentence | cut to the discriminating words; keep the verb |
| `code fence without language tag` | fence opened with no info string | tag every fence: `bash`, `pawn`, `text`, `json` |
| `Failure Modes table needs >= 3 data rows` | section is bullets | three real symptom/cause/fix rows |
| `Sources: 1 URL(s), need >= 2` | one link reused per skill | open two more pages and cite the specific function |
| `validate_library.py` lists two missing sections | it checks the pre-contract headers (`## 2026 Compatibility & Architecture Matrix`, `## Deprecated Traps & Edge Cases (2026)`) | leave the contract headers; `bin/audit.py` decides. Do not revert to satisfy a stale script |
| `duplicate pair` with ratio above 0.86 | two skills share a trigger | rewrite the newer trigger around its distinguishing failure |
| `--net` reports `status 404` | guessed doc path | fetch the sitemap or the function page and copy the real URL |
| `--net` reports `blocked(403/429)` | host rate-limits bots | replace it; the gate tolerates it but a reader cannot open it |
| Gate green, skill useless | sections filled with truisms | delete the sentence that would be true of any server |
| `needs a markdown table` on a section that has one | a fenced block repeats `## Section` text at column zero and truncates the parser | keep section headings out of fences entirely |

## Verification

Contract gate on the skill you just wrote, exit code 0 on success:

```bash
python3 bin/audit.py --root . --only samp --names memory-leak-timer-audit; echo "exit=$?"
```

```text
skills: 1  categories: 1  lines: 160  avg: 160
per category: samp=1

OK    all skills pass structure and depth gates
exit=0
```

Catalog freshness and source reachability. The catalog stores body line counts, so it is
stale the moment you edit a skill — regenerate it in the same commit rather than shipping
the mismatch:

```bash
python3 bin/catalog.py --check; echo "catalog_exit=$?"
python3 bin/audit.py --root . --only samp --names memory-leak-timer-audit --net | tail -2
```

```text
CATALOG.md is stale; run bin/catalog.py
catalog_exit=1

net: checked 3 unique source URL(s)
```

## Sources (2026)

- https://agentskills.io/specification
- https://open.mp/docs/changelog
- https://github.com/openmultiplayer/omp-stdlib

For pack-wide tooling (auditor design, install, CI wiring) rather than one SA-MP skill, the
`skill-pack-engineering` skill owns it.
