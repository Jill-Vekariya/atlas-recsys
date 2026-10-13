# Build your own technical ownership

The implementation and documentation are a starting point. You become interview-ready by
reproducing results, modifying behavior, checking consequences, and explaining the decisions
without relying on a script. The checklist below is not marked completed on your behalf.

## First: reproduce

- Install from the lockfile in a clean environment.
- Run tests and the synthetic workflow with a new config/version.
- Run the HTTP/UI verifier and canary demo.
- Recreate one real-data report and compare checksums and cohort counts.
- Explain why synthetic results are not evidence of real-world recommendation improvement.

## Make three substantive changes

**Experiment 1: ID dropout.** Create new configs for 0%, 30%, and 60%. Change only that setting.
Compare validation cold-cohort recall, overall NDCG, and returning-user counts. Include a
content-only baseline. Do not use the existing final-test period to repeatedly select settings.

**Experiment 2: retrieval budget.** Sweep candidate count and HNSW `efSearch`. Compare exact
neighbor recall, relevance NDCG, p95 latency, and memory. State which setting you would choose
for a latency-constrained application and why.

**Experiment 3: feedback labeling.** Design a staged-data importer that keeps clicks and likes
separate, validates referenced item IDs, preserves source timestamps, and rejects load-test
events. Add tests for malformed and late events. Decide the intended target before merging
any sources into training.

An optional fourth contribution is rolling temporal evaluation. Implement histories as of
each prediction, keep user-level uncertainty clustered, and reserve a new untouched period.

## Demonstrate debugging

Find a case where popularity beats personalized retrieval. Inspect history length, metadata,
candidate recall, exclusion rules, and item popularity. Propose a failure mechanism and a
controlled experiment. Do not simply increase model size.

Introduce a wrong feature order and show that bundle validation rejects it. Introduce a
retrieval exception and show fallback. Retry feedback concurrently and explain why only one
event is inserted. Explain the current deadline's inability to preempt native code.

## Write a personal decision log

Fill this template using experiments you actually run:

| Field | Your evidence |
|---|---|
| Question | What did you want to learn? |
| Hypothesis | What would happen, and why? |
| Controlled change | Which single variable changed? |
| Fixed conditions | Dataset, windows, seed, candidates, hardware |
| Result | Actual metrics and uncertainty |
| Failure analysis | What did not behave as expected? |
| Decision | Keep, reject, or investigate further |
| Reproduction | Config, commands, report, commit |

Use meaningful commits after your changes. Do not fabricate a months-long history, team
collaboration, internship experience, or a personal experiment narrative.

## Before applying

- Explain the loss mathematically and point to its code.
- Explain one leakage test and one reliability test.
- Modify a feature or endpoint and verify it.
- Discuss the failed ranker result candidly.
- Explain the difference between ranking quality and ANN approximation quality.
- State what is deployed and what remains only locally verified.
- Use metrics you reproduced in your résumé.
- Prepare coding, SQL, probability, and ML fundamentals alongside this project.

A technically honest, well-understood project is a stronger interview asset than unsupported
claims of novelty or scale. This project cannot guarantee interview selection or an internship.
