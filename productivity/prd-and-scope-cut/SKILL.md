---
name: prd-and-scope-cut
description: Use when a request needs a one-page PRD and smaller scope.
version: "2026.1.0"
metadata:
  hermes:
    tags: [product, prd, scoping, prioritization, decision-log]
    category: productivity
---

# Write the one-page PRD, then cut half of it

A PRD that lists twelve capabilities is a wish, not a decision. The page is
useful only if it names one problem, one number, and the smallest slice that can
move that number — everything else belongs in the non-goals or the log.

## When to Use

- A stakeholder hands you a feature list with no problem statement attached.
- Two teams are quietly building overlapping halves of the same request.
- Scope grows at every review while the ship date stays fixed.
- You must say no this quarter and need the artifact that makes the no defensible.
- Skip this for a defect with a reproduction and one owner; write a ticket instead.

## Compatibility & Stack Matrix (2026)

| Component | Version/variant | Notes |
| --- | --- | --- |
| PRD format | Markdown one-pager, 1 screen | lives in the repo next to the code |
| Length budget | <= 600 words, <= 1 page | over that it stops being read |
| Slice budget | 1-2 weeks, one owner | longer slices hide integration risk |
| Metric | one primary + one guardrail | baseline, target, window, source table |
| Decision log | append-only table, dated | every rejected alternative recorded |
| Review | 8-question checklist, evidence required | a "no" blocks the build |

## Production Implementation

1. Open with the problem as a single story that carries numbers. One customer,
   one workflow, one measured loss beats a market-size paragraph.

```markdown
# PRD: <one-line name>            owner: <name>   status: draft|review|building
## Problem
<Segment> cannot <job> today; they do <workaround>. Evidence: <n> tickets in
<quarter>, <x>% drop at <funnel step>, <n> accounts asked for it.
Cost of not fixing: <revenue/churn/hours> per <period>.
```

   Every page carries the same six H2s — `Problem`, `Non-goals`, `Success metric`,
   `Smallest slice`, `Risks`, `Decision log` — so the check in Verification finds them.

2. Name the success metric as one number with a baseline, a target, a window and
   a source. Add exactly one guardrail so you cannot win the metric by damaging
   something else.

```text
primary   : % of new accounts that publish a report within 7 days
baseline  : 18% (trailing 90 days, analytics.fct_activation)
target    : 30% within 6 weeks of launch
guardrail : report publish error rate <= 1.5% (must not rise)
```

3. Find the **metric spine** before listing features. Write the causal chain from
   the user's first action to the metric moving, as 3-5 nodes. Anything not on the
   chain is cut, regardless of how often it was requested.

```text
spine: sign in -> create report -> see correct data -> share link -> recipient opens
cut  : saved views, 12 filters, CSV export, folder permissions, dark mode, mobile app
```

4. Run the cut table out loud. Each candidate gets one verdict and one reason, so
   the argument happens once instead of in every review.

| Candidate | On spine? | Verdict | Reason |
| --- | --- | --- | --- |
| 3 preset filters | yes | keep | without one filter the report shows wrong scope |
| 12 filter combinations | no | cut | presets cover 80% of tickets; revisit after launch |
| saved views | no | cut | users re-create a view in 20 seconds |
| CSV export | no | defer | sharing covers the reporting need for v1 |
| folder permissions | no | defer | single workspace until >20 accounts |

5. Write the slice as a sentence a user could read: "A user can <do the job>
   without <the thing you cut>." Then attach 3 acceptance checks that a reviewer
   can run, not adjectives.

```text
slice   : an analyst can build a report from 3 presets and share a read-only link
accept  : 1. new account publishes a report with no support contact
          2. recipient without an account opens the link and sees fresh data
          3. guardrail error rate stays under 1.5% for 7 days
```

6. List risks with a kill signal, not a severity word. Five rows is enough; a
   risk without a trigger date is a worry.

| Risk | Likelihood | Impact | Mitigation | Kill signal |
| --- | --- | --- | --- | --- |
| warehouse cannot serve shared links at p95 | med | high | cache the rendered report 5 min | p95 > 2s for 3 days |
| recipients expect live edit | high | med | read-only copy stated in the share dialog | >30% of shares edited |
| activation metric measures signups, not value | med | high | count publish, not login | baseline moves with marketing spend |

7. Keep a decision log in the same file. It is the only part that survives the
   launch and the only defense when someone asks "why was export dropped".

```markdown
## Decision log
| Date | Decision | Alternatives rejected | Owner | Revisit when |
| --- | --- | --- | --- | --- |
| 2026-02-03 | 3 preset filters only | full filter builder | A. Rivera | 20+ accounts request custom filters |
| 2026-02-03 | read-only sharing | collaborative editing | A. Rivera | edit requests exceed 30% of shares |
```

8. Freeze the one-pager at review. New asks do not get appended — one line in,
   one line out, or the ask waits for the next slice.

9. Review with eight questions, each answered with a link or a number. One "no"
   sends the PRD back; two "no"s means the slice is not shippable yet.

```text
[ ] 1. Problem is one story with a measured cost, not a category.
[ ] 2. Exactly one primary metric, with baseline, target and window.
[ ] 3. A guardrail metric exists and is measurable today.
[ ] 4. Non-goals are written as decisions with reasons, not as omissions.
[ ] 5. The slice is describable in one sentence a user would recognize.
[ ] 6. Every acceptance check is observable without reading the code.
[ ] 7. Each risk has a mitigation and a kill signal.
[ ] 8. Decision log names the rejected alternative for every contested call.
```

10. Non-goals carry the reason. "No CSV export because sharing covers v1" survives
    a meeting; "no CSV export" reads as an oversight and gets reopened.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| PRD is 4 pages by review 2 | scope negotiated inside the document | one-page budget; debate moves to the decision log |
| Everyone agrees, nothing ships | no owner and no acceptance checks | name one owner, one date, three observable checks |
| Metric green, users still unhappy | primary metric was a signup proxy | add a guardrail, re-baseline on the value event |
| Scope creeps at every review | new asks enter without removing anything | one in, one out; the displaced item goes to the next slice |
| Non-goals get reopened weekly | written as omissions without reasons | phrase as "not this slice because X, revisit when Y" |
| Nobody remembers why export was cut | decisions made in chat | log within 24h with the rejected alternative and a revisit trigger |

## Verification

- Structure: run this against the file and expect six `ok` lines and a word count under 600.

```bash
for h in "Problem" "Non-goals" "Success metric" "Smallest slice" "Risks" "Decision log"; do
  grep -qi "^## ${h}" prd.md && echo "ok   ${h}" || echo "MISS ${h}"
done
wc -w prd.md
```

- Expected output: `ok   Problem` through `ok   Decision log`, then `wc` reporting
  `<= 600` words; any `MISS` line means the page is not reviewable yet.
- `grep -c '^|' prd.md` counts decision-log rows; zero means no decision was ever
  recorded, so the scope has no paper trail.
- Manual: hand the page to an engineer who was not in the meeting. If they cannot
  state the non-goals back to you, the cut section failed.

## Sources (2026)

- https://basecamp.com/shapeup/1.5-chapter-06
- https://www.atlassian.com/agile/product-management/requirements
- https://www.productplan.com/glossary/product-requirements-document/
