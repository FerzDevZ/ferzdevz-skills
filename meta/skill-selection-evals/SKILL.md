---
name: skill-selection-evals
description: Use when a skill may not change agent output. Eval it.
version: "2026.1.0"
metadata:
  hermes:
    tags: [meta, skills, evaluation, evals]
    category: meta
---

# Prove a skill earns its context, or retire it

"A skill exists" and "a skill works" are different claims. The router sees only the
name and description; the body loads after selection. That gives two independent
failures: never selected, and selected but no better than baseline. Paired evals
answer both with numbers you can keep in the repo and re-run on every model change.

## When to Use

- You shipped a skill and cannot say whether it fires on real prompts.
- The audit is green but outputs look identical with and without the skill.
- A model upgrade landed and you need a regression signal, not a vibe check.
- Two skills overlap and you need to know which one the router picks.
- Not for skills that mutate production state: sandbox them first, or eval only
  the read-only path.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Python | 3.9+ | runner and scoring are stdlib only |
| Agent runner | any non-interactive CLI | harness calls `$AGENT_CMD "<prompt>"` |
| Model | pinned id per run | a delta is only valid for that model |
| Repetitions | k=3 | consecutive identical runs disagree often |
| Thresholds | trigger 0.5, delta 0.15 | under both, the skill is context tax |

## Production Implementation

1. Write the eval set before touching the body: 6-10 realistic prompts, two of
   them should-not-trigger near misses that share vocabulary with the skill.
   Keep what "good" means in `checks`, not in your head.

```csv
id,should_trigger,prompt,checks
e1,true,"our prisma migrations got rewritten after a deploy, can you look","uses --create-only; runs migrate status"
e2,true,"why did the last migration apply twice on staging","reads migration history before editing"
e3,false,"write a prisma schema for a blog with posts and tags","no migration commands"
```

2. Keep the set in the repo next to the skill; it is code, not a scratch note.

```bash
mkdir -p evals/skill-selection-evals
mv prompts.csv evals/skill-selection-evals/prompts.csv
printf '%s\n' 'correctness 0-5 | steps 0-2 | tools_ok 0-2' > evals/skill-selection-evals/rubric.md
```

3. Run paired arms from a clean session. The runner swaps the skills directory so
   the baseline cannot see the skill; `AGENT_CMD` must honour `SKILLS_DIR`.

```python
#!/usr/bin/env python3
"""Paired eval runner: evals/run.py <relative/skill/path>."""
import csv, datetime, os, pathlib, shlex, subprocess, sys

skill = pathlib.Path(sys.argv[1]).resolve()
rows = list(csv.DictReader(open(f"evals/{skill.name}/prompts.csv", encoding="utf-8")))
stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M")
out = pathlib.Path("evals/runs") / f"{stamp}-{skill.name}"
empty = pathlib.Path("evals/empty"); empty.mkdir(parents=True, exist_ok=True)
cmd = shlex.split(os.environ["AGENT_CMD"])
for row in rows:
    for arm, skills_dir in (("with", skill), ("without", empty)):
        d = out / row["id"] / arm; d.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, SKILLS_DIR=str(skills_dir))
        p = subprocess.run(cmd + [row["prompt"]], env=env, capture_output=True, text=True)
        (d / "reply.md").write_text(p.stdout, encoding="utf-8")
        (d / "trace.log").write_text(p.stderr, encoding="utf-8")
print(out)
```

4. Grade blind. Rename `with`/`without` to A/B before the grader sees the replies,
   decode afterwards. Score three numbers per run: correctness 0-5, steps 0-2 (did
   it follow the numbered procedure), tools_ok 0-2 (tool calls within two of the
   expected count). Write `evals/scores.csv` with `skill,id,arm,correctness,steps,tools_ok`.

5. Compute the delta, never the with-skill average alone.

```python
#!/usr/bin/env python3
"""Mean paired delta per rubric dimension: evals/score.py <scores.csv>."""
import csv, statistics, sys

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
mean = lambda arm, key: statistics.mean(
    [float(r[key]) for r in rows if r["arm"] == arm]) if any(r["arm"] == arm for r in rows) else 0.0
for key in ("correctness", "steps", "tools_ok"):
    w, b = mean("with", key), mean("without", key)
    print(f"{key:11s} with={w:.2f} without={b:.2f} delta={w - b:+.2f}")
```

6. Test triggering separately from quality: 20 queries, 10 should and 10 should
   not, three runs each. Trigger rate is the share of runs whose trace shows the
   skill loaded. A positive passes at `>= 0.5`; a negative at `< 0.5`. Hold back
   40% of queries from description tuning so you can detect overfitting.

7. Read the result with this table. Zero delta with a loaded skill is a content
   problem; zero delta without a load is a description problem.

| Observation | Reading | Action |
| --- | --- | --- |
| delta >= +0.5, negatives quiet | the skill carries a real procedure | keep it, add the prompt to the set |
| delta +0.1 to +0.5 | partial overlap with model priors | keep only the non-obvious steps |
| delta 0, fewer tool calls | efficiency skill | keep if tokens also drop |
| delta <= 0 at equal cost | context tax | retire it or merge into a skill that fires |
| positives under 0.5 trigger | description mismatch | rewrite the description, not the body |
| negatives over 0.5 trigger | too broad or sibling hijack | add an explicit "not for" boundary |

8. Re-run on every model change and every description edit. Record model id, date,
   and delta in `evals/scores.csv`; delete any skill whose delta reaches zero.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| delta exactly 0.00 and no skill load in the trace | arm swap ignored `SKILLS_DIR` | assert the skill path appears in the with-arm trace before scoring |
| baseline arm is suspiciously strong | skill still installed globally under `~/.hermes/skills` | `find ~/.hermes/skills -name SKILL.md -path "*<name>*"` and remove it |
| the same prompt scores 1 then 4 | single-run grading | k=3, report median and pass@3 |
| all positives fire, negatives too | description matches a topic, not an intent | narrow to symptoms users type, add near-miss negatives |
| scores rise only on tuned prompts | overfit to eval wording | fixed 60/40 train/validation split |
| delta positive but tokens tripled | reference dump in the body | move references to `references/`, keep operational steps |
| eval passes on the old model only | model drift | pin the model id and rerun the matrix on upgrade |

## Verification

```bash
export AGENT_CMD="claude -p"   # must honour SKILLS_DIR; wrap it if your client differs
python3 evals/run.py meta/skill-depth-upgrade
python3 evals/score.py evals/scores.csv
```

Expected: one `with/` and one `without/` directory per prompt, then one line per
dimension such as `correctness with=4.20 without=2.80 delta=+1.40`. Reject the
skill when `delta <= 0` on all dimensions or when the positive trigger rate is
below 0.5. Commit `evals/` with the skill so the next model upgrade is measurable.

## Sources (2026)

- https://agentskills.io/skill-creation/evaluating-skills
- https://agentskills.io/skill-creation/optimizing-descriptions
- https://cloud.google.com/blog/topics/developers-practitioners/evaluate-agent-skills-before-they-bloat-your-context-window
