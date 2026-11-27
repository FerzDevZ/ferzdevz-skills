---
name: skill-depth-upgrade
description: Use when a skill is a 35-line stub. Rebuild it on evidence.
version: "2026.1.0"
metadata:
  hermes:
    tags: [meta, skills, authoring, audit]
    category: meta
---

# Turn a stub into a skill that changes behaviour

A stub is not a short skill. It is a skill with no evidence in it: no command that
discriminates, no failure that actually happened, no output anyone verified. Padding
it to 120 lines with definitions makes it longer and still useless. This procedure
replaces adjectives with artefacts until the depth gates pass on merit.

## When to Use

- `bin/audit.py` passes but an agent loads the skill and still guesses.
- The body is under 60 lines, or every code block is 2-4 lines of pseudo-code.
- You are about to write a third failure row and can only invent one.
- A skill was synthesized from vendor docs and repeats what the model already knows.
- Not for a brand-new skill with no usage yet: write its evals first (see
  `skill-selection-evals`), then upgrade it from the first failing prompt.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Python | 3.9+ | measurement script is stdlib only |
| `bin/audit.py` | pack 2026.1.0 | `--min-body`, `--json`, `--only` |
| Agent Skills spec | 2026 | SKILL.md < 500 lines, < 5k tokens |
| Evidence inputs | trace, CI log, incident note | one artefact per failure row |
| Pack CI | `--net` pass | zero dead URLs before merge |

## Production Implementation

1. Write the failure as one sentence with a quoted artefact. If you cannot quote
   a line from a trace, a log, or a review comment, stop: there is nothing to
   upgrade yet.

```text
Before: "The skill should explain migration edge cases better."
After:  "Agent ran `prisma migrate dev` without `--create-only`, rewrote 3 pending
         migrations and exited 0. Trace: step 7, command_execution."
```

2. Measure the stub instead of eyeballing it. Save this as `/tmp/depth.py`.

```python
#!/usr/bin/env python3
"""Depth metrics for one SKILL.md. Stdlib only."""
import pathlib, re, sys

text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
body = text.split("---", 2)[2] if text.startswith("---") else text
marker = chr(96) * 3
parts = [p for p in body.split(marker)[1::2] if p.strip()]
code = sum(len(p.strip().splitlines()) - 1 for p in parts)
cmds = len(re.findall(r"^\s*(?:python3|npm|npx|git|curl|docker|rg|grep|find|bash)\b", body, re.M))
sec = re.search(r"^## Failure Modes & Fixes\n(.*?)(?=^## )", body, re.S | re.M)
rows = max(0, len([l for l in (sec.group(1) if sec else "").splitlines() if l.startswith("|")]) - 2)
print(f"body={len(body.splitlines())} code={code} cmds={cmds} failures={rows} fences={len(parts)}")
```

```bash
python3 /tmp/depth.py meta/skill-depth-upgrade/SKILL.md
# body=145 code=23 cmds=5 failures=7 fences=5
# a 35-line stub reports body<60, code<15, failures<3
```

3. Delete before you add. For each paragraph ask: "Would the agent get this wrong
   without this line?" Definitions of HTTP, PDFs, and "best practices" fail that
   test, and so do architecture overviews. Keep project conventions, exact
   commands, thresholds, and errors the model cannot infer.

4. Add the diagnosis command: one command the next agent runs before acting, whose
   output separates the failure from the success case. It belongs in
   `## Verification` and step 1 of the procedure refers to it. For the migration
   failure that is a status check, not a paragraph about migrations.

```bash
npx prisma migrate status --schema prisma/schema.prisma
git diff --stat prisma/migrations   # must be empty before applying anything
```

   A pending list, a drift warning, or a non-empty migration diff means stop and
   inspect; only a clean status allows `migrate dev` to run.

5. Add one failure row from the incident. Symptom is the exact string a user or a
   log shows, cause is the mechanism, fix is a command or a one-line edit. A row
   whose cause is "developer error" is not a row.

| Symptom | Cause | Fix |
| --- | --- | --- |
| `migrate dev` rewrote applied migrations | command run without `--create-only` | pin the flag, then verify with `prisma migrate status` |

6. Rewrite section by section against this checklist. Nothing else counts as depth.

| Section | Keep | Cut |
| --- | --- | --- |
| `description` | trigger words users type | scope summary, feature list |
| When to Use | symptoms, "not for" boundary | restating the title |
| Matrix | versions that change behaviour | every dependency in the lockfile |
| Implementation | numbered steps, runnable commands | prose that explains the product |
| Failure Modes | exact symptom + cause + fix | generic warnings |
| Verification | command + expected output | "check that it works" |
| Sources | pages you actually opened | search-result links |

7. Score the result out of 15. Below 11 it is still a stub with better formatting.

| Dimension | 0 | 1 | 2 | 3 |
| --- | --- | --- | --- | --- |
| Trigger fit | description is a topic | names the domain | names the symptom | symptom + boundary |
| Diagnosis | none | generic check | one command | output decides the branch |
| Evidence density | no code | snippets < 5 lines | one runnable block | blocks + real outputs |
| Failure rows | none or invented | 1 real row | 3 rows with causes | 5 rows from incidents |
| Verification | prose | one command | command + expected | command, expected, threshold |

8. Re-run the gates and record the numbers in the commit message: body lines,
   failure rows, dead URLs. Past 500 lines, move reference tables to
   `references/` and link them conditionally, not up front.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Stub became 140 lines and reads worse | padded with public documentation | delete any line not traceable to a trace, command, or URL |
| Audit passes, agent still guesses | no discriminating command | add it to Verification and reference it from step 1 |
| Third failure row is plausible but never happened | written from imagination | paste the exact log line; no artefact means no row |
| `description is 67 chars (max 80)` | scope crept into frontmatter | compress to "Use when <symptom>. <verb>." and move detail down |
| New `--net` failure after rewrite | URL guessed from memory | open the page, cite the section, or drop the claim |
| Duplicate pair appears after upgrade | two skills now teach one decision | merge into the shorter name; 0.86 similarity is rejected |
| Skill exceeds 5k tokens when loaded | references inlined | split into `references/<topic>.md` with load conditions |

## Verification

```bash
python3 bin/audit.py --root . --net
python3 /tmp/depth.py meta/skill-depth-upgrade/SKILL.md
```

Expected: `OK    all skills pass structure and depth gates`, then
`net: checked N unique source URL(s)` with no unreachable block, and
`body>=90 code>=20 cmds>=4 failures>=3` from the measurement. Re-run the trigger
prompts from `skill-selection-evals` and confirm the skill still fires.

## Sources (2026)

- https://agentskills.io/skill-creation/best-practices
- https://agentskills.io/specification
- https://cloud.google.com/blog/topics/developers-practitioners/evaluate-agent-skills-before-they-bloat-your-context-window
