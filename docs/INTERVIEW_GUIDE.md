# Interview guide: explain the system, then defend the evidence

Use this guide with the source open. The goal is to explain a decision, find its implementation,
and modify it under a new constraint. Do not claim personal experiments you have not performed.

## A 60-second project explanation

“Atlas is a recommendation system with retrieval, ranking, and a serving layer. I compare
popularity, ALS, content retrieval, a PyTorch two-tower model, and LightGBM ranking using four
chronological windows. A controlled item cohort has no supervised training interactions, so I
can study the contribution of item content. I measure full-catalog relevance separately from
FAISS approximation quality. The API logs exposures and feedback, validates compatible model
bundles, and supports deterministic canary routing and rollback. The reports show where the
complex models fail as well as where they help.”

Adapt the first-person wording only after you understand and have worked on these components.
Use the measured result file for numbers; do not describe the local workload as FAANG scale.

## Data and evaluation

**Why not a random train/test split?** Future interactions can influence historical user
representations or item popularity. `features.histories` uses strictly earlier timestamps,
and `models.training_examples` handles equal-time events together before updating history.

**Why four windows?** A trains retrieval; B trains ranking against a frozen A retriever;
validation selects a default; test measures its later behavior. This isolates ranking labels
from the retriever's training targets.

**What exactly is “cold start”?** The controlled cohort has every A/B event withheld. Its
metadata remains known under a catalog-snapshot assumption. This is not a verified product
launch experiment. Natural zero-history items are a separate cohort.

**Are you predicting purchases?** No. The public labels describe positive reviews or ratings.
Purchases, impressions, CTR, and revenue are not observed sufficiently to claim them.

**What are negative labels?** In-batch alternatives and ranker zeros are unobserved candidates.
They may be relevant items the user never encountered. This limitation prevents interpreting
the score as a purchase probability.

**Why full-catalog evaluation?** A small sampled-negative pool can make ranking artificially
easy. The recorded evaluator considers the catalog snapshot, applies exclusion rules, and
documents any user sampling independently of model performance.

**What does NDCG measure?** Discounted relevance near the top, normalized by the ideal ranking
for that query. Explain the worked test in `test_metrics_known_answer`. Precision@10 always
uses denominator 10, including when fewer items are returned.

**What does the bootstrap interval mean?** It resamples paired per-user metric differences.
It captures user-sampling variation conditional on this dataset and seed. It does not capture
all training randomness, population shift, or multiple-comparison uncertainty.

**Why can overall and returning-user metrics disagree?** Many global-time evaluation users
have no earlier positive history and receive popularity fallback. The overall metric is partly
a measurement of that fallback policy. Cohort sizes are necessary for interpretation.

## Modeling

**How does the two-tower model work?** A weighted mean of earlier item-content vectors enters a
linear user projection. Item content enters a separate projection and adds a learned ID vector.
Both outputs are normalized; their inner product is the retrieval score.

**What is the training loss?** The difference between logsumexp over allowed batch candidates
and logsumexp over same-item positives, averaged across queries. At temperature 0.10, the model
assigns probability mass to relevant pairs. Duplicate positive IDs are treated as multiple
positives, rather than contradicting labels.

**Why item-ID dropout?** It makes some training examples rely on content. At serving time an
item without A-positive history uses the zero ID embedding. A content path then remains usable.
The identity-only ablation removes that content path from item representations.

**Is this a sequential model?** No. Recency-weighted pooling uses order, but there is no trained
sequence encoder. A Transformer/GRU extension would need a separate quality/cost experiment.

**Why keep ALS?** It is a credible collaborative baseline that often competes with more complex
models. Inspect its actual result before claiming a neural improvement. It also reveals the
limits of content-only modeling and popularity effects.

**Why does ranking sometimes hurt?** Candidate recall limits the ranker's opportunity; small
informative training groups, weak labels, feature bias, and population shift can misorder
already good candidates. The recorded MovieLens ranker loses to ALS on final-test NDCG.

**Can the ranker fix retrieval misses?** No. Its output is a reorder of retrieved items. More
candidate budget may increase opportunity but also increases inference cost.

## Serving and reliability

**Why export NumPy inference from PyTorch?** The deployed user tower is a small linear operation.
Export avoids a GPU request path and is checked against PyTorch by a parity test. The container
still includes training libraries for demo bootstrap; a slimmer runtime image is future work.

**Exact FAISS versus HNSW?** Exact inner-product search provides the reference. HNSW trades
search work, index memory, and approximate-neighbor recall. `efSearch` and candidate count
are measured independently of model relevance.

**How do you prevent training/serving feature mismatch?** Both use `features.rank_features`.
Bundles verify feature order, ranker feature count, array dimensions, mapping/index sizes,
and asset hashes before activation.

**How does feedback retry work?** SQLite serializes the check/insert using an immediate
transaction. Same event/same payload is a duplicate; same event/different payload is a conflict.
Only exposed items are valid, and load-test feedback cannot enter the staging dataset.

**Is there online learning?** No. Feedback is logged and exported, not automatically joined to
ratings or used to update the current history. Explain the provenance/label policy you would
add before retraining.

**How does rollback work?** Atomically replace a validated routing-state file. The process
reloads it on its next request, while an in-flight request keeps its captured compatible bundle.
A canary rollback clears candidate traffic; a full activation rollback restores the previous
primary. The supplied guard demonstration is isolated and uses synthetic traffic.

**What does the latency result establish?** The report records one local host, one API worker,
a 10-second open-loop workload, warmup, request mix, queueing, and actual achieved throughput.
It does not establish a global SLA or millions-of-users scalability.

**Can the deadline interrupt FAISS?** No. The current implementation detects completion after
the budget and falls back. A hard deadline would require resource isolation/cancellation or
bounded algorithms; merely checking elapsed time is insufficient.

## System-design follow-ups

For ten times more items, first measure index memory and query work. Consider larger HNSW
settings, IVF/product quantization, filtering strategy, and memory budgets. For ten times more
requests, measure CPU, SQLite contention, and queueing before adding workers. Cross-host routing
needs coordinated artifact distribution and readiness, not just a shared JSON path.

For online quality measurement, define a meaningful outcome, randomize users consistently,
log exposures, establish guardrails and required sample size, then wait for delayed labels.
Synthetic requests can validate plumbing but cannot demonstrate lift.

## Five-minute demonstration

1. State the exact task and metadata assumption; show the results summary.
2. Request recommendations for an existing user and inspect feature diagnostics.
3. Compare a baseline and the two-stage pipeline without claiming every difference is an improvement.
4. Onboard a new user with category preferences and show score/fallback semantics.
5. Submit feedback, retry its event ID, and explain provenance.
6. Show the local HTTP benchmark configuration and limitations.
7. Run the canary regression demonstration and inspect the restored route.
8. Finish with one measured failure and the next experiment it motivates.

## Résumé wording

After reproducing and understanding the runs, use a factual bullet such as:

“Built and benchmarked an end-to-end recommendation platform with PyTorch two-tower retrieval,
FAISS, and LightGBM; evaluated six configurations over a 9,742-item MovieLens catalog and
implemented temporal leakage checks, idempotent feedback, compatible model bundles, and
canary rollback.”

Add the local p95/throughput numbers from `reports/movielens/http_load.json`, including that the
test was local. Do not claim conversion lift, production users, employer endorsement, or a
statistically established neural-model improvement that the reports do not support.
