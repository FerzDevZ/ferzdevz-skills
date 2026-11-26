---
name: rag-retrieval-pipeline
description: Use when RAG misses exact terms or cites wrong passages.
version: "2026.1.0"
metadata:
  hermes:
    tags: [rag, retrieval, hybrid-search, rerank, citations]
    category: ml
---

# Retrieve with two rankers, rerank, then prove the citation

Dense-only retrieval fails on SKUs, error codes, dates and names; BM25-only fails
on paraphrases. Run both, fuse by rank, then rerank with a cross-encoder. Anthropic
reports Contextual Retrieval cuts failed retrievals by 49%, and by 67% with
reranking — on their corpora, so transfer the direction, not the number.

## When to Use

- Users paste exact identifiers and get semantically "close" but useless chunks.
- The right document is in the top 20 but never in the top 5.
- Answers cite a source that does not contain the quoted sentence.
- Multiple tenants or permission tiers share one index.
- Not for scoring answer quality over time (use `rag-evaluation-harness`).

## Compatibility & Stack Matrix (2026)

| Component | Versions | Notes |
| --- | --- | --- |
| Python | 3.11-3.13 | `rank_bm25`, `sentence-transformers` |
| Sparse index | BM25 (Lucene/`rank_bm25`) | per-language analyzers; keep raw text |
| Dense store | pgvector 0.8 / Qdrant 1.x | HNSW, cosine; filters must be pre-filter |
| Embeddings | any 1024-dim model | store model name + dim with the collection |
| Reranker | `BAAI/bge-reranker-v2-m3` | cross-encoder, 512-token limit per pair |
| Chunking | structure-aware, 200-400 tokens | parent doc id + section path retained |

## Production Implementation

1. Chunk on document structure, never on a fixed character count alone. Keep the
   heading path and the parent id: they become metadata filters and citations.

```python
import re
def chunk_markdown(text: str, doc_id: str, max_tokens: int = 320) -> list[dict]:
    chunks, path, buf = [], [], []
    for block in re.split(r"(?m)^(?=#{1,4} )", text):
        if not block.strip():
            continue
        head = block.splitlines()[0]
        if head.startswith("#"):
            level = len(head) - len(head.lstrip("#"))
            path = path[: level - 1]
            path.append(head.lstrip("# ").strip())
        body = block.strip()
        step = max_tokens * 4  # characters per chunk, then trim on a sentence edge
        for i in range(0, len(body), step):
            piece = body[i:i + step]
            cut = piece.rfind(". ")
            if 0 < cut < len(piece) - 40:
                piece = piece[: cut + 1]
            chunks.append({"doc_id": doc_id, "section": " > ".join(path),
                           "text": piece.strip(), "ordinal": len(chunks)})
    return chunks
```

2. Prepend a short situating line to each chunk before indexing it, so the embed-
   ding and BM25 both see what the chunk is about without the parent document.

```python
def contextualize(chunk: dict, doc_title: str, llm) -> dict:
    prompt = (f"Document: {doc_title}\nSection: {chunk['section']}\n\n"
              f"Chunk:\n{chunk['text']}\n\n"
              "Write one sentence placing this chunk in the document. No preamble.")
    prefix = llm(prompt).strip()
    return {**chunk, "index_text": f"{prefix}\n\n{chunk['text']}"}
```

3. Index the same `index_text` into BM25 and into the vector store, with ACL
   fields on every row. Never filter after ranking: post-filtering leaks rows and
   silently shrinks `k`.

```python
POINT = {"id": "chunk_id", "vector": [0.0],  # embedding of index_text
         "payload": {"doc_id": "", "section": "", "text": "", "ordinal": 0,
                     "tenant": "", "acl": ["group:eng"], "content_hash": "",
                     "updated_at": "2026-01-01T00:00:00Z"}}
ACCESS_FILTER = {"must": [{"key": "tenant", "match": {"value": "acme"}},
                          {"key": "acl", "match": {"any": ["group:eng"]}}]}
```

4. Fuse the two ranked lists with Reciprocal Rank Fusion. RRF needs no score
   calibration, which is why it survives a model swap.

```python
def rrf(rankings: list[list[str]], k: int = 60, limit: int = 50) -> list[str]:
    scores: dict[str, float] = {}
    for ranked in rankings:
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)[:limit]
```

5. Rerank the fused top 50 down to 8 with a cross-encoder, and cap the pair at
   the reranker's window. Truncated pairs score randomly; that reads as a rerank
   "not helping".

```python
from sentence_transformers import CrossEncoder
RERANKER = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=512)
def rerank(query: str, candidates: list[dict], top_n: int = 8) -> list[dict]:
    pairs = [(query, c["text"][:1800]) for c in candidates]
    for c, score in zip(candidates, RERANKER.predict(pairs)):
        c["rerank_score"] = float(score)
    return sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)[:top_n]
```

6. Carry a citation handle through generation and verify the quote exists in the
   chunk. A citation the model composed is not evidence; a substring match is.

```python
import unicodedata
def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    return " ".join(s.split())

def verify_citation(answer: str, chunk: dict) -> bool:
    quote = answer.split(f"[{chunk['doc_id']}#{chunk['ordinal']}]")[0].strip(" .\"\n")
    return norm(quote)[-160:] in norm(chunk["text"])
```

7. Handle freshness explicitly: content-hash each chunk, upsert on change, and
   tombstone deleted documents in the same transaction as the source delete.
   Serve `updated_at` with the answer so stale context is visible downstream.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Exact SKU or error code never retrieved | dense-only index; embeddings blur identifiers | add BM25 and RRF fusion (steps 3-4) |
| Right document at rank 12, never rank 5 | single-stage cosine ranking | rerank top 50 to 8 with a cross-encoder (step 5) |
| Answer cites a page that lacks the sentence | model writes citations from memory | require `doc#ordinal` handles and substring-verify (step 6) |
| Tenant sees another tenant's chunk | filter applied after top-k | pre-filter in the index query, assert tenant on every row |
| Rerank makes recall worse | pairs truncated past the model window | cap chunk size, cut text to 1800 chars before scoring |
| Edits do not appear for hours | reindex keyed on file mtime | key on content hash, tombstone deletes in the same transaction |
| Recall drops after chunk size change | fixed-size splits cut tables and lists | structure-aware chunking with section path (step 1) |

## Verification

```bash
python3 -m pytest tests/test_retrieval.py -q
# 6 passed in 1.90s   (fusion order, acl pre-filter, citation verify, tombstone)

python3 -m scripts.eval_retrieval --set eval/queries.jsonl --k 10
# n=120 recall@10=0.87 mrr@10=0.62 vs baseline recall@10=0.71
# PASS: recall delta +0.16 (paired bootstrap 95% CI +0.09..+0.23)

python3 -m scripts.verify_citations --answers eval/answers.jsonl
# citations 240  verified 236  unsupported 4  (ids: 31, 77, 102, 118)
```

Manual check: query a known SKU with `mode=bm25` and `mode=dense`; confirm each
mode alone misses cases the fused mode retrieves, or the corpus is too easy.

## Sources (2026)

- https://www.anthropic.com/news/contextual-retrieval
- https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview
- https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/
