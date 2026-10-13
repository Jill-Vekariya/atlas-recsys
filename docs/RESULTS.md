# Recorded results

These are observed runs, not promised future performance.

Model selection used validation only. Catalog text is a later snapshot. One seed was run.

## Amazon

Synthetic: **False**. Test users: 300 of 2311 eligible users.

| Algorithm | Recall@100 | NDCG@10 | Coverage@10 | Returning-user NDCG@10 | Cold Recall@100 |
|---|---:|---:|---:|---:|---:|
| popularity | 0.1200 | 0.0067 | 0.0025 | 0.0000 | 0.0000 |
| category_popularity | 0.1200 | 0.0067 | 0.0025 | 0.0000 | 0.0000 |
| als | 0.1200 | 0.0067 | 0.0070 | 0.0000 | 0.0000 |
| content | 0.1200 | 0.0067 | 0.0070 | 0.0000 | 0.0000 |
| tower | 0.1200 | 0.0067 | 0.0070 | 0.0000 | 0.0000 |
| ranked | 0.1200 | 0.0067 | 0.0070 | 0.0000 | 0.0000 |

Returning users with positive pre-cutoff history: **2**.
Users with controlled-cold eligible targets: **47**.
Personalized retriever training examples: **27**.

Validation-selected default: **popularity**. It was not reselected on test.

- ranked_minus_als: absolute NDCG delta 0.00000; paired user bootstrap 95% interval [0.00000, 0.00000].
- tower_minus_content: absolute NDCG delta 0.00000; paired user bootstrap 95% interval [0.00000, 0.00000].

## Movielens

Synthetic: **False**. Test users: 96 of 96 eligible users.

| Algorithm | Recall@100 | NDCG@10 | Coverage@10 | Returning-user NDCG@10 | Cold Recall@100 |
|---|---:|---:|---:|---:|---:|
| popularity | 0.1966 | 0.2598 | 0.0073 | 0.1106 | 0.0000 |
| category_popularity | 0.1758 | 0.2566 | 0.0117 | 0.1002 | 0.0000 |
| als | 0.1902 | 0.2468 | 0.0187 | 0.0689 | 0.0000 |
| content | 0.1685 | 0.2284 | 0.0227 | 0.0101 | 0.0064 |
| tower | 0.1749 | 0.2340 | 0.0243 | 0.0279 | 0.0164 |
| ranked | 0.1744 | 0.2321 | 0.0246 | 0.0220 | 0.0111 |

Returning users with positive pre-cutoff history: **30**.
Users with controlled-cold eligible targets: **87**.
Personalized retriever training examples: **24336**.

Validation-selected default: **tower**. It was not reselected on test.

- ranked_minus_als: absolute NDCG delta -0.01465; paired user bootstrap 95% interval [-0.03240, -0.00115].
- tower_minus_content: absolute NDCG delta 0.00556; paired user bootstrap 95% interval [-0.00275, 0.01544].

## Synthetic

Synthetic: **True**. Test users: 99 of 99 eligible users.

| Algorithm | Recall@100 | NDCG@10 | Coverage@10 | Returning-user NDCG@10 | Cold Recall@100 |
|---|---:|---:|---:|---:|---:|
| popularity | 0.3449 | 0.0485 | 0.0800 | 0.0485 | 0.0000 |
| category_popularity | 1.0000 | 0.2739 | 0.7000 | 0.2739 | 1.0000 |
| als | 0.6377 | 0.3011 | 0.7733 | 0.3011 | 0.0000 |
| content | 1.0000 | 0.2420 | 0.5367 | 0.2420 | 1.0000 |
| tower | 1.0000 | 0.2717 | 0.5900 | 0.2717 | 1.0000 |
| ranked | 1.0000 | 0.2577 | 0.7367 | 0.2577 | 1.0000 |

Returning users with positive pre-cutoff history: **99**.
Users with controlled-cold eligible targets: **73**.
Personalized retriever training examples: **1698**.

Validation-selected default: **als**. It was not reselected on test.

- ranked_minus_als: absolute NDCG delta -0.04339; paired user bootstrap 95% interval [-0.09314, 0.00408].
- tower_minus_content: absolute NDCG delta 0.02972; paired user bootstrap 95% interval [-0.01617, 0.08039].

## Interpretation

The sampled Amazon category provides very little repeat-user history. Its personalized models receive too few training examples, and popularity fallback dominates evaluation. This is evidence about this sampled workload, not evidence that recommendation systems fail.

MovieLens supplies more historical interactions, but the global temporal split still creates many new users. The validation-selected tower loses to popularity on final-test NDCG. The ranker also loses to ALS in this run. Retain these results: a complex model is not automatically the best serving policy. Do not tune repeatedly against the same final test.

The hybrid tower has nonzero controlled-cold recall while popularity and ALS have zero in the MovieLens run. That specialized benefit is small and does not establish overall superiority. Check returning-user counts and uncertainty before claiming improvement.

The synthetic fixture intentionally has a strong category signal. Its results validate the mechanics and cold-start paths rather than a real business hypothesis.

## Movielens HTTP benchmark

Catalog: 9,742 items; 500 requests over 10 seconds, after 30 warmup requests.

| Metric | Observed |
|---|---:|
| Target arrival rate | 50.0 requests/s |
| Achieved successful throughput | 49.86 requests/s |
| p50 | 47.94 ms |
| p95 | 55.95 ms |
| p99 | 63.50 ms |
| Request error rate | 0.00% |
| Fallback rate | 20.00% |

Open-loop planned arrival to HTTP completion; includes queueing. 80% existing positive histories, 20% new user. Local host, short run, one API worker; no fleet-scale conclusion.

Fallback includes expected new-user responses. It does not imply the same proportion of service failures. Response caching is disabled; models and indexes are resident in RAM.

## Synthetic HTTP benchmark

Catalog: 300 items; 500 requests over 10 seconds, after 30 warmup requests.

| Metric | Observed |
|---|---:|
| Target arrival rate | 50.0 requests/s |
| Achieved successful throughput | 49.96 requests/s |
| p50 | 47.96 ms |
| p95 | 52.19 ms |
| p99 | 56.00 ms |
| Request error rate | 0.00% |
| Fallback rate | 20.00% |

Open-loop planned arrival to HTTP completion; includes queueing. 80% existing positive histories, 20% new user. Local host, short run, one API worker; no fleet-scale conclusion.

Fallback includes expected new-user responses. It does not imply the same proportion of service failures. Response caching is disabled; models and indexes are resident in RAM.

## Rollback demonstration

Synthetic local TestClient traffic; no online quality or business claim.

Injected condition: Canary-only 25 ms delay and retrieval exception. Guard: Canary retrieval-failure rate exceeds primary by 0.2.

Rollback triggered: **True**. Post-rollback route: **primary**, bundle **synthetic-v1**.

## Verification boundaries

Python dependency installation, unit/integration checks, real HTTP requests, and Streamlit application flows were exercised. Docker, GitHub Actions, GHCR publication, and public hosting were not run in this environment. No online business A/B test, multi-node scaling test, or internship outcome is established.
