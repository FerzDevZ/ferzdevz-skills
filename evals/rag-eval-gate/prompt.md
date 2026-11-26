# rag-eval-gate

Prompt given to the agent (identical for both arms):

> Reviewers keep asking whether our RAG change is better and we answer with a screenshot.
> Write `eval_plan.md`: the frozen dataset row shape, the metrics, and how CI decides pass or
> fail.

Answer directory must contain `eval_plan.md`.
