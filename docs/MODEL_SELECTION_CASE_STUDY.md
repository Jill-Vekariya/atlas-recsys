# Model selection: a reproducible interview case study

## Question

Why did the validation-selected two-tower system underperform a simpler popularity
baseline on held-out MovieLens test data?

## Reproduce (read-only)

From the repository root, after `uv sync --frozen --extra dev`:

```bash
uv run python scripts/model_selection_audit.py --report-dir reports/movielens
uv run python scripts/model_selection_audit.py --report-dir reports/amazon
uv run pytest -q tests/test_model_selection_audit.py
```

The script uses the **existing recorded reports**. It prints JSON to stdout,
does not retrain, does not overwrite bundles or reports, and never uses test
results to choose a model. Its validation-only selection follows the existing
training pipeline's tie-breaking order.

## Observed MovieLens result

- Validation NDCG@10: tower **0.293296**, popularity **0.291418**.
- The recorded validation-selected algorithm was **tower**.
- Held-out test NDCG@10: tower **0.233961**, popularity **0.259801**.
- Selected-minus-popularity test difference: **-0.025840** absolute NDCG@10.
- Controlled-cold Recall@100: tower **0.016431**, popularity **0**.

These are previously recorded experiment outputs, not fresh training results.
The test difference is descriptive; this comparison alone supplies no confidence
interval or claim of statistical significance. Training used a single seed,
and the returning-user population is small.

## What this demonstrates

A valid model selection decision can still underperform an alternative on a
future cohort. Content features may recover some controlled cold-start items
without improving aggregate NDCG. Shipping the most complex model by default
would therefore not be an evidence-backed policy.

## Next experiment (not yet performed)

Investigate performance by new versus returning users, candidate retrieval
ceiling, positive candidate availability during LightGBM training, and
catalog/head-item distributions. Run sensitivity analyses and repeated seeds
using **validation or newly reserved evaluation data**. Preserve the original
held-out test: do not repeatedly tune against this published test result.

## Interview questions

**Why was tower selected if popularity won the test?** The model-selection
rule uses validation macro NDCG@10 only. The test result assesses whether
that choice generalized; it must not retroactively select the winner.

**Why not remove the ranker?** Its current recorded test result is weak, but
the experiment does not prove the model class is universally worse. Investigate
candidate recall, feature usefulness, and group-label limitations before
deciding whether the serving complexity is justified.

**What would justify another release?** A documented improvement on a new
validation protocol or prospective dataset, adequate uncertainty estimates,
and acceptable measured latency/reliability cost.
