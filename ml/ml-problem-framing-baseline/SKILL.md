---
name: ml-problem-framing-baseline
description: Use when a product idea needs an ML metric and baseline.
version: "2026.1.0"
metadata:
  hermes:
    tags: [ml, framing, metrics, baselines, leakage]
    category: ml
---

# Frame the decision, beat a rule, then train a model

Most ML projects fail before training: the metric is a proxy nobody acted on, the
split leaks the future, or nobody wrote the heuristic the model had to beat. The
Rules of ML put this first — simple model before complex, and launch decisions are
a proxy for long-term product goals (Rule #39). This skill produces the one-page
artifact that decides whether training is justified.

## When to Use

- A stakeholder says "we should use AI for this" without a decision attached.
- You need to choose the primary metric and its guardrails before modelling.
- A model scores well offline and nobody believes it will in production.
- A dataset has timestamps and someone proposes `train_test_split(random_state=42)`.
- Not for tuning an existing model, and not for LLM prompt work.

## Compatibility & Stack Matrix (2026)

| Component | Versions | Notes |
| --- | --- | --- |
| Python | 3.11-3.13 | |
| pandas | 2.2+ | as-of joins via `merge_asof` |
| scikit-learn | 1.5+ | `roc_auc_score`, `DummyClassifier` |
| numpy | 1.26+ | bootstrap intervals |
| Tracking | one JSON per experiment | metric, split hash, baseline score, sample size |

## Production Implementation

1. Write the decision, the action and the cost of a wrong action. If no action
   changes on a different prediction, ML adds latency and no value.

```text
Decision: which accounts get a retention call this week (capacity 200/week)
Action:   rep call, 20 minutes, ~$40 loaded cost
Errors:   false positive wastes $40; false negative loses ~$900 margin
Metric:   incremental retained margin per 1,000 accounts contacted
```

2. Pick one primary metric tied to that action, plus guardrails you refuse to
   trade away. Optimise the metric, monitor the guardrails, never average them.

```python
FRAMING = {
    "primary": "incremental_retained_margin_per_1k",
    "guardrails": {"precision_at_200": 0.55, "contact_rate": 0.02},
    "evaluation_window_days": 60,
    "baseline_rule": "no_login_14d AND plan in ('pro','team')",
}
```

3. Build the heuristic baseline first and freeze its score on the same rows the
   model will see. A baseline evaluated on a different split is not a baseline.

```python
import pandas as pd
def baseline_flag(df: pd.DataFrame) -> pd.Series:
    return (df["days_since_login"] >= 14) & df["plan"].isin(["pro", "team"])

def score_at_capacity(scores: pd.Series, labels: pd.Series, capacity: int) -> dict:
    top = scores.nlargest(capacity).index
    tp = int(labels.loc[top].sum())
    return {"precision_at_capacity": tp / capacity,
            "recall_at_capacity": tp / max(int(labels.sum()), 1)}
```

4. Split by time, not at random, whenever rows have a timestamp. Random splits let
   the model memorise the future and inflate every number.

```python
def time_split(df: pd.DataFrame, ts: str, cutoff: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.sort_values(ts)
    train = df[df[ts] < pd.Timestamp(cutoff, tz="UTC")]
    test = df[df[ts] >= pd.Timestamp(cutoff, tz="UTC")]
    assert train[ts].max() < test[ts].min(), "overlapping windows"
    return train, test
```

5. Scan for leakage before modelling. Two cheap detectors catch most of it: a
   feature whose timestamp is after the label, and a single feature that predicts
   almost perfectly on its own.

```python
from sklearn.metrics import roc_auc_score

def leakage_scan(train: pd.DataFrame, features: list[str], label: str,
                 asof: dict[str, str]) -> list[dict]:
    findings = []
    for f in features:
        if f in asof and (train[asof[f]] > train["label_ts"]).any():
            findings.append({"feature": f, "why": "timestamped after label"})
            continue
        auc = roc_auc_score(train[label], train[f].fillna(train[f].median()))
        if max(auc, 1 - auc) > 0.97:
            findings.append({"feature": f, "why": f"single-feature auc {auc:.3f}"})
    return findings
```

6. Check the sample can support the claim. With 200 decisions per week and a
   noisy label, a 2-point lift is invisible; report the interval, not the mean.

```python
import numpy as np

def lift_ci(model: np.ndarray, base: np.ndarray, iters: int = 5000) -> tuple[float, float]:
    d = model - base
    rng = np.random.default_rng(11)
    boots = rng.choice(d, size=(iters, d.size), replace=True).mean(axis=1)
    return float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))
```

7. Decide with an explicit rule, written before the results: ship ML only if the
   baseline is below target, the model beats it with a CI that excludes zero, and
   every guardrail holds. Otherwise ship the rule and revisit when volume grows.

```python
def go_no_go(baseline: float, model: float, ci_low: float, ci_high: float,
             guardrails: dict[str, tuple[float, float]]) -> str:
    if any(value < floor for value, floor in guardrails.values()):
        return "no-go: guardrail breach"
    if ci_low <= 0:
        return "no-go: lift not distinguishable from zero"
    return "go: ML expected to beat the rule" if model > baseline else "no-go: rule wins"
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Offline AUC 0.95, production 0.60 | feature joined after the label timestamp | as-of join + timestamp scan (step 5) |
| Metric up, product flat | optimising a proxy (clicks) detached from the goal | tie primary metric to the action, add guardrails (step 2) |
| Model beats baseline offline, loses online | baseline scored on a different split or population | same rows, same split, same capacity (steps 3-4) |
| Random split on time-ordered data | `train_test_split` default | time cutoff with non-overlapping windows (step 4) |
| No one can say if ML helped | no frozen baseline | commit baseline JSON with split hash before training |
| Lift "significant" then vanishes | tiny n, no interval | paired bootstrap CI, author the decision rule first (steps 6-7) |

## Verification

```bash
python3 -m pytest tests/test_framing.py -q
# 6 passed in 0.62s   (time_split, leakage_scan, lift_ci, go_no_go)

python3 -m scripts.leakage_scan --data data/accounts.parquet --label churned_60d
# features 41  scanned 41  violations 2
# account_age_days: timestamped after label | support_tickets_60d: single-feature auc 0.981

python3 -m scripts.framing_report --config framing/retention.yaml
# baseline precision@200 0.41  model 0.58  lift +0.17 CI [+0.09, +0.24]
# guardrails: contact_rate 0.021 ok | decision: go
```

Manual check: drop the flagged features, rerun; if AUCs do not fall, the leak is
in the join, not the feature list.

## Sources (2026)

- https://developers.google.com/machine-learning/guides/rules-of-ml
- https://developers.google.com/machine-learning/problem-framing
- https://developers.google.com/machine-learning/guides/text-classification/step-2
