# Multi-seed temporal evaluation

The prior evaluation's user bootstrap excluded training-seed variation.
Stage 4 adds a bounded synthetic study that prepares one temporal dataset,
keeps evaluation-user sampling fixed across training seeds, completes all
validation selections, seals a selection lock, and only then evaluates test data.
Every existing algorithm remains in the validation and final reports. No seed is
chosen by its test score. Dataset, bundle and validation hashes are checked before
testing; the existing Bundle compatibility checks remain in place.

```bash
PYTHONPATH=src python -m scripts.temporal_study --output artifacts/stage4-study-001
python -m pytest tests/test_temporal_study.py tests/test_model_selection_audit.py -q
```

The source declares the protocol before execution: synthetic dataset seed
20261029, training seeds 17/29/41, evaluation seed 101, 32 users, 120 items,
2,400 generated events, two tower epochs, three ALS iterations, twelve ranker
trees, at most 32 evaluation users and one numerical thread. MLflow and external
data/model access are disabled. Existing directories are refused. Failures are
retained and never replaced with another seed. A failed seed makes the CLI exit
nonzero. Cohort sizes and null metrics remain explicit.

The executed study evaluated 25 eligible test users per seed. Validation chose
`category_popularity` in all three seeds. Test NDCG@10 was 0.76737 for that model
and 0.03179 for popularity on this deliberately structured synthetic fixture.
The tower scored 0.74269, 0.75636 and 0.75779: below the selected simple baseline
in all seeds. The ranker scored 0.65492, 0.78194 and 0.74973: below it in two
seeds. These unfavorable comparisons are retained, not used to retune selection.
There were zero new-user and zero low-history cohort users. Cold/head/zero-history
recall differences were zero; a 120-item catalog with up to 100 candidates makes
recall saturation a substantial limitation. No real-data or business uplift is
claimed. This test split is now exposed and must not be described as a new,
untouched evaluation in later tuning.

The 2,000-resample seed bootstrap describes variation on this one fixed fixture.
Its selected-model interval is degenerate because the same deterministic model
won all seeds. It excludes population, data and time-window uncertainty; three
seeds are not a powered significance study.

The model-selection audit also now rejects missing test algorithms rather than
allowing their absence to change the validation winner. Nonfinite, boolean and
out-of-range validation NDCG scores are rejected.

**VERIFIED:** one three-seed run, 52 local tests and lint/format checks. Local
dependencies were recorded and were not a fresh frozen-lock installation.
Compatibility checks were preserved. AI-assisted implementation; no independent
user contribution, production recommendation traffic or new branch CI is claimed.
