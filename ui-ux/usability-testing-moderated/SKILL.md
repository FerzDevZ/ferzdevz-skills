---
name: usability-testing-moderated
description: Use when running moderated usability tests for decisions.
version: "2026.1.0"
metadata:
  hermes:
    tags: [usability, research, testing, ux]
    category: ui-ux
---

# Run five sessions and leave with decisions, not quotes

A moderated test earns its cost only if someone can act on the output the same week.
That means a decision written before recruiting, tasks built from user goals rather
than feature names, a moderator who stays quiet, and findings deduplicated down to
root causes with a severity that survives an argument with the roadmap owner.

## When to Use

- A release, redesign or onboarding change needs a go / no-go signal from real behaviour.
- Two teams disagree about a flow and the argument has run out of evidence.
- Analytics show a drop-off but not the reason, and support tickets disagree with each other.
- Do not use when you need prevalence or segment sizing; that is survey or analytics work.

## Compatibility & Stack Matrix (2026)

| Component | Version | Note |
| --- | --- | --- |
| Participants | 5 per distinct segment | 5 finds roughly 85% of issues when one user reveals ~31% |
| Session length | 30-45 min | 3 tasks maximum, plus warm-up and debrief |
| Remote tools | Zoom / Teams / Lookback | record only with written consent |
| Note capture | one CSV row per observation | timestamp, participant, task, type, severity |
| Severity scale | 0-4 | frequency × impact × persistence, not gut feel |

## Production Implementation

1. Write the decision before writing the script. If no decision depends on the answer,
   the study is a demo with extra steps.

```text
Decision: ship the new invoice form to all accounts, or keep it behind a flag.
Question: can a first-time user send an invoice without help?
Threshold: 4 of 5 create a correct invoice inside 8 minutes.
```

2. Build the task script from goals, never from UI labels. A task that says "click New
   invoice" tests the instruction, not the product.

```markdown
# Study: invoice creation (round 3)
Decision: ship to all accounts, or keep behind a flag.

## Warm-up (3 min)
- What do you use today to bill a client?

## Task 1 - bill a new client (8 min)
Scenario: You finished a project for "Northwind" and need to bill them today.
Start: signed in, dashboard, zero invoices.
Success: an invoice for Northwind, one line item, a due date.
Avoid saying: "New invoice", "sidebar", "top right".

## Task 2 - fix a mistake before sending (5 min)
Scenario: The amount should be 1,200, not 120. The invoice is still a draft.
Success: amount corrected, draft saved, nothing sent.

## Debrief (5 min)
- What was the hardest part? What did you expect that did not happen?
```

3. Recruit five per segment and screen for behaviour, not job title. Ask "when did you
   last send an invoice?" — a yes/no answer to "do you use invoicing software?" is noise.

4. Pilot the script with one person outside the team. Every task that needs an
   explanation during the pilot is a script bug, not a participant failure.

5. Moderate with silence and neutral prompts. Rescue only after two minutes of being
   genuinely stuck, and never point at the control.

| Moment | Say | Never say |
| --- | --- | --- |
| 10 s of silence | "What are you thinking?" | "The button is on the right." |
| Wrong path | "What did you expect to happen?" | "You need to go back first." |
| Asks for help | "What would you try next?" | "Just click Save." |
| Task finished | "How was that?" | "That was easy, right?" |

6. Log one row per observation and keep observation separate from interpretation.

```csv
ts,participant,task,type,detail,severity
00:04:12,P1,1,finding,Searched "bill" in top nav and missed the primary action,3
00:04:40,P1,1,quote,"I would look under clients for this",,
00:06:02,P1,2,success,Corrected amount in 1m10s and saved draft,,
```

7. Deduplicate before scoring. Five people hitting the same missing affordance is one
   finding with frequency 5, not five findings. Score 0-4 using the three factors, and
   record the factor that drove the score.

```python
import csv

rows = [r for r in csv.DictReader(open("study/log.csv")) if r["type"] == "finding"]
sev = [int(r["severity"]) for r in rows]
print(f"findings={len(rows)} mean={sum(sev) / len(sev):.1f} blockers={sum(s >= 3 for s in sev)}")
```

8. Turn every finding at severity 3 or 4 into a decision row with an owner and a
   re-test condition. Findings without a decision are notes, and notes do not ship.

```text
F-02  Primary create action not found (5/5, sev 3)
      Decision: move "New invoice" into the page header, drop the duplicate in the empty state
      Owner: checkout squad, by 2026-12-05
      Re-test: 5 new participants, expect >= 4 finds it unaided in 30 s
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| 30 "findings" from 5 sessions | every observation logged as an issue | dedupe by root cause; one row per cause, frequency as a column |
| Participants said they liked it, nothing changed | opinions were collected instead of behaviour | tasks with observable success criteria; log actions, not praise |
| Moderator explained the UI mid-task | rescue reflex under silence | hold 10 s, use a neutral prompt, hint only after two stuck minutes |
| Findings cannot be ranked against the roadmap | no severity basis | score 0-4 from frequency, impact and persistence |
| The study "confirms" the design the team already picked | tasks written from feature names | rewrite from user goals and pilot with someone outside the team |
| Same five people every round | recruiting from the team's own network | screen for behaviour and rotate participants each round |
| Complaint about recording after the session | consent taken verbally or skipped | written consent before recording; stop and delete on request |

## Verification

```bash
python3 - <<'PY'
import csv
rows = [r for r in csv.DictReader(open("study/log.csv")) if r["type"] == "finding"]
sev = [int(r["severity"]) for r in rows]
print(f"findings={len(rows)} mean_severity={sum(sev) / len(sev):.1f} blockers={sum(s >= 3 for s in sev)}")
PY
# expected: findings=9 mean_severity=2.8 blockers=3
```

Manual gate before the readout: every participant appears in the log, each task has a
success or failure row, and every severity 3-4 finding has a decision row with an owner.

## Sources (2026)

- https://www.nngroup.com/articles/why-you-only-need-to-test-with-5-users/ (L≈31%, ~85% at n=5)
- https://www.nngroup.com/articles/thinking-aloud-the-1-usability-tool/ (concurrent think-aloud)
- https://www.nngroup.com/articles/how-to-rate-the-severity-of-usability-problems/ (0-4 scale, three factors)
- https://www.nngroup.com/articles/task-scenarios-usability-testing/ (task wording)
