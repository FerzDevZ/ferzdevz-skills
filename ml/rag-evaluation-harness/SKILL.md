---
name: rag-evaluation-harness
description: Use when reviewers ask if a RAG change is better.
version: "2026.1.0"
metadata:
  hermes:
    tags: [rag, evaluation, ragas, ci, regression]
    category: ml
---

# Gate retrieval and generation on a frozen set, not on a demo

A RAG demo is five questions you already know the answers to. A harness is a
frozen set of real queries, deterministic metrics where possible, a pinned judge
where not, and a paired comparison against the last release. Faithfulness alone
misses a retriever that fetched the wrong passage consistently.

## When to Use

- You are about to change chunking, embeddings, reranker or the answer prompt.
- Reviewers ask "is this better?" and the answer is a screenshot.
- Faithfulness is high while users still report wrong answers.
- Judge costs are growing faster than the product.
- Not for building the pipeline itself (use `rag-retrieval-pipeline`).

## Compatibility & Stack Matrix (2026)

| Component | Versions | Notes |
| --- | --- | --- |
| Python | 3.11-3.13 | `numpy`, `pytest` |
| Ragas | 0.4+/stable | `Faithfulness`, `ResponseRelevancy`, `ContextPrecision`, `ContextRecall` |
| Judge model | pinned snapshot | record model id + prompt hash in every report |
| Storage | JSONL, one row per case | committed, hash-locked |
| CI | any runner | exit code decides the gate; report is an artifact |

## Production Implementation

1. Define the row before collecting anything. Retrieval labels are what make the
   set usable for both retrieval and generation metrics.

```python
import json, hashlib, pathlib

def load_set(path: str) -> tuple[list[dict], str]:
    rows = [json.loads(l) for l in pathlib.Path(path).read_text().splitlines() if l.strip()]
    for r in rows:
        assert {"id", "question", "reference", "relevant_chunk_ids", "split"} <= r.keys()
        assert r["split"] in {"dev", "test"}
    digest = hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()[:12]
    return rows, digest
```

2. Build the set from three sources and record the mix: real logged queries with
   human labels (majority), synthetic multi-hop cases from a knowledge graph
   (Ragas testset generation traverses a graph to compose multi-document queries),
   and adversarial cases (ambiguous, unanswerable, wrong-tenant).

```bash
python3 -m scripts.mine_queries --logs 30d --min-count 3 --out eval/candidates.jsonl
python3 -m scripts.label --in eval/candidates.jsonl --sample 120 --out eval/labeled.jsonl
# keep dev/test split fixed at collection time; never re-split after tuning starts
```

3. Run retrieval metrics that do not need a judge: recall@k, MRR, and citation
   validity. These are cheap enough for every commit.

```python
def recall_at_k(rows: list[dict], retrieved: dict[str, list[str]], k: int) -> float:
    hits = sum(bool(set(retrieved[r["id"]][:k]) & set(r["relevant_chunk_ids"])) for r in rows)
    return hits / len(rows)

def mrr_at_k(rows: list[dict], retrieved: dict[str, list[str]], k: int) -> float:
    total = 0.0
    for r in rows:
        gold = set(r["relevant_chunk_ids"])
        for rank, cid in enumerate(retrieved[r["id"]][:k], start=1):
            if cid in gold:
                total += 1.0 / rank
                break
    return total / len(rows)
```

4. Add generation metrics from the same rows, and keep the definitions explicit.
   Faithfulness is supported claims over total claims; Response Relevancy
   embeds the question and three questions generated from the answer and averages
   cosine similarity. Both are judge-based, so both need step 5.

```python
from ragas.metrics.collections import Faithfulness, ResponseRelevancy

async def score_generation(result: dict, judge) -> dict:
    faith = await Faithfulness(llm=judge).ascore(
        user_input=result["question"], response=result["answer"],
        retrieved_contexts=result["contexts"])
    rel = await ResponseRelevancy(llm=judge, embeddings=EMB).ascore(
        user_input=result["question"], response=result["answer"])
    return {"faithfulness": faith.value, "answer_relevancy": rel.value}
```

5. Cache judge calls by content hash and pin the judge. An unpinned judge that
   gets upgraded upstream moves your numbers while your code stands still.

```python
import sqlite3
def cached_score(db: sqlite3.Connection, key_parts: list[str], compute):
    key = hashlib.sha256("|".join(key_parts).encode()).hexdigest()
    row = db.execute("SELECT v FROM score_cache WHERE k = ?", (key,)).fetchone()
    if row:
        return float(row[0])
    value = float(compute())
    db.execute("INSERT INTO score_cache(k, v) VALUES(?, ?)", (key, value))
    db.commit()
    return value
```

6. Compare paired per-case deltas with a bootstrap interval. Unpaired averages on
   a small set flip sign between runs; pairing removes case difficulty.

```python
import numpy as np
def paired_ci(new: list[float], old: list[float], iters: int = 5000) -> tuple[float, float, float]:
    d = np.asarray(new) - np.asarray(old)
    rng = np.random.default_rng(7)
    boots = rng.choice(d, size=(iters, d.size), replace=True).mean(axis=1)
    return float(d.mean()), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))
```

7. Fail the build on the lower bound, not on the point estimate, and require every
   metric floor plus one retrieval floor. A single composite score hides the
   failure you care about.

```yaml
- run: python3 -m eval.run --config eval/ci.yaml --split test --out report.json
- run: python3 -m eval.gate --report report.json --min-faithfulness 0.85 --min-recall 0.80
  # exit 1 when any floor fails or paired CI lower bound < -0.02
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Scores move 5 points with no code change | judge model upgraded upstream | pin the snapshot, store judge id + prompt hash in the report |
| Faithfulness 1.0, users still complain | answer is consistent with the wrong context | add recall@k and context precision to the gate |
| Gate fails on unrelated PRs | too few cases; unpaired means | paired bootstrap on >= 60 test cases |
| Eval spend exceeds serving spend | every case judged by a large model | cache by hash, judge a stratified 25%, deterministic metrics on all |
| Dev numbers great, test flat | tuning against the test split | freeze the split, inspect dev only, unseal test at release |

## Verification

```bash
python3 -m pytest tests/test_eval_harness.py -q
# 9 passed in 2.30s   (dataset schema, recall, mrr, bootstrap, gate exit codes)

python3 -m eval.run --config eval/ci.yaml --split test --out report.json
# cases 180  faithfulness 0.88  answer_relevancy 0.81  recall@10 0.84
# delta vs release-2026.04: +0.03 [+0.01, +0.05]  cost_usd 0.42  cache_hit 0.71

python3 -m eval.gate --report report.json
# gate PASS  floors: faithfulness>=0.85 ok  recall>=0.80 ok  ci_lower>=-0.02 ok
```

Manual check: corrupt one reference answer; the harness must name that case id.

## Sources (2026)

- https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/
- https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_relevance/
- https://docs.ragas.io/en/stable/concepts/test_data_generation/rag/
