---
name: llm-app-context-engineering
description: Use when an LLM app drifts, loops or overflows context.
version: "2026.1.0"
metadata:
  hermes:
    tags: [llm, context-window, structured-output, tools, evals]
    category: ml
---

# Treat the context window as a budget, not a bucket

A prompt that "works" in a notebook fails in production for four boring reasons:
no fixed system-prompt structure, a prose output contract, tools named after
endpoints, and no measurement. Context engineering curates the token set on every
call against a hard window (Anthropic, *Effective context engineering for AI agents*).

## When to Use

- You are writing or rewriting the system prompt for a product feature.
- The model returns valid JSON but semantically wrong values.
- Calls degrade after turn 3-6, or context-length errors appear under load.
- The model ignores a tool, calls the wrong one, or invents arguments.
- Not for retrieval quality (use `rag-retrieval-pipeline`) or training a model.

## Compatibility & Stack Matrix (2026)

| Component | Versions | Notes |
| --- | --- | --- |
| Python | 3.11-3.13 | dataclasses, `Literal` |
| OpenAI SDK | 1.x, Responses API | Structured Outputs constrains schema, not business rules |
| Pydantic | 2.7+ | schemas must be closed (`additionalProperties: false`) |

## Production Implementation

1. Freeze the system prompt into four ordered blocks so edits stay reviewable.

```python
def build_system(role: str, rules: list[str], tool_policy: str, contract: str) -> str:
    return "\n\n".join([
        f"<role>\n{role.strip()}\n</role>",
        "<rules>\n" + "\n".join(f"- {r}" for r in rules) + "\n</rules>",
        f"<tools>\n{tool_policy.strip()}\n</tools>",
        f"<output>\n{contract.strip()}\n</output>",
    ])
```

2. Give the window a budget and enforce it before the request, not after a 400.

```python
import tiktoken

ENC = tiktoken.get_encoding("o200k_base")

def enforce(messages: list[dict], window: int, reserve_out: int, reserve_tools: int) -> list[dict]:
    cap = window - reserve_out - reserve_tools
    used = sum(len(ENC.encode(m["content"])) for m in messages)
    while used > cap and len(messages) > 2:
        used -= len(ENC.encode(messages.pop(1)["content"]))  # never drop system
    if used > cap:
        raise ValueError(f"system+tools need {used} tokens, cap is {cap}")
    return messages
```

3. Write the output contract as a closed model, then enforce semantics the schema
   cannot express. Structured Outputs guarantees shape, not correctness.

```python
import os
from typing import Literal
from openai import OpenAI
from pydantic import BaseModel, Field
client = OpenAI()

class Triage(BaseModel):
    model_config = {"extra": "forbid"}
    category: Literal["billing", "bug", "account"]
    confidence: float = Field(ge=0, le=1)
    evidence_quote: str = Field(min_length=8)

def triage(ticket: str) -> Triage:
    resp = client.responses.parse(
        model=os.environ["MODEL"],
        input=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": ticket}],
        text_format=Triage,  # schema-constrained decoding
    )
    out = resp.output_parsed
    if out.confidence < 0.6 or out.evidence_quote not in " ".join(ticket.split()):
        raise ValueError("low confidence or quote not verbatim; escalate")
    return out
```

4. Define tools as verbs with a stated boundary, closed arguments, and errors
   returned as data instead of raised into the model loop.

```python
TOOLS = [{
    "name": "get_invoice",
    "description": "Fetch one invoice by id. Call only after the customer id is known. "
                   "Do not call for balances or refunds.",
    "input_schema": {"type": "object", "required": ["invoice_id"],
                     "properties": {"invoice_id": {"type": "string", "pattern": "^inv_[0-9a-f]{8}$"}},
                     "additionalProperties": False},
}]
def run_tool(name: str, args: dict, handlers: dict) -> dict:
    try:
        return {"ok": True, "data": handlers[name](**args)}
    except Exception as e:  # the model needs the failure, not a stack trace
        return {"ok": False, "error": type(e).__name__, "retryable": False, "detail": str(e)}
```

5. Compact history on a deterministic policy: summarise old turns, keep the tail
   verbatim, and drop tool output before prose because tool blobs are the fat.

```python
def compact(messages: list[dict], summarize, keep_last: int = 6) -> list[dict]:
    head, tail = messages[:1], messages[1:]
    if len(tail) <= keep_last:
        return messages
    old, recent = tail[:-keep_last], tail[-keep_last:]
    return head + [{"role": "user", "content": f"<summary>{summarize(old)}</summary>"}] + recent
```

6. Gate every prompt or tool edit on a golden set that asserts behaviour, not
   strings. Log `usage.input_tokens` and stop reasons beside the verdicts.

```python
def evaluate(cases: list[dict], run) -> dict:
    fails = []
    for c in cases:
        try: assert c["check"](run(c["input"]))
        except Exception as e: fails.append((c["id"], repr(e)))
    return {"pass_rate": round(1 - len(fails) / len(cases), 3), "fails": fails}

report = evaluate(CASES, triage)
assert report["pass_rate"] >= BASELINE_PASS_RATE - 0.02, report
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| JSON validates, answers are wrong | schema expresses shape; business rules live elsewhere | validate semantics after parse, escalate on failure |
| Model never calls the tool | description names an endpoint, not a situation | describe when to use and when not; test with 10 prompts |
| Context-length 400 at turn 5 | history grows unbounded; tool results dominate | budget (step 2) plus summary compaction (step 5) |
| Prompt edit silently regresses | no behavioural eval set | golden-set gate with per-case failures, not one score |
| Cost doubles after adding a tool | full schemas and docs re-sent every call | keep a static prefix, trim the tool set, cache the prefix |

## Verification

```bash
python3 -m pytest tests/test_context.py -q
# 7 passed in 0.41s   (budget, compaction, contract, tool-error cases)

python3 scripts/budget_report.py --window 200000
# prompt 1840 | tools 612 | history p95 9300 | headroom 188248

python3 scripts/run_eval.py --set eval/golden.jsonl
# pass_rate 0.94  baseline 0.92  delta +0.02  gate PASS
```

Manual check: delete one rule; the eval must name a failing case, or it is too narrow.

## Sources (2026)

- https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- https://platform.openai.com/docs/guides/structured-outputs
- https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview
