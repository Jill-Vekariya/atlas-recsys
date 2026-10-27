# Atlas — interview practice

## Five-sentence technical summary

Atlas compares recommendation approaches for users and products with limited interaction history. It includes PyTorch retrieval, FAISS search, LightGBM ranking and simpler baselines. Temporal splits separate training, validation selection and final evaluation. The engineering purpose is to study recommendation quality together with serving cost and reliability. The browser catalog is synthetic, and the repository preserves the real-data result where the selected model lost to popularity.

This explains the project’s engineering purpose. Describe your own motivation and role using actual experience; this document does not invent either.

## Ten questions and simple answers

1. **What is cold start?** A user or item has little useful interaction history. Atlas studies controlled withheld-item cohorts and new-user behavior, rather than claiming a verified real product launch.

2. **Why keep popularity?** It is a useful strong baseline, especially for new users. A complex model is not useful merely because it is complex.

3. **What does the two-tower model do?** It maps users/history and items/content into vectors so candidate items can be retrieved efficiently. The ranker then scores the retrieved candidates.

4. **Why use FAISS?** It supports nearest-neighbor search over item vectors. Approximate neighbor recall and recommendation relevance are different measurements.

5. **How is leakage controlled?** Chronological windows separate learning stages and evaluation, and controlled cold items have training interactions withheld. Catalog content still has a documented transductive availability assumption.

6. **Which split selects the serving model?** Validation NDCG@10 selects it. Final test reports the choice’s outcome and must not be repeatedly used for tuning.

7. **Why did popularity win the final test?** The recorded result shows that validation selection did not guarantee generalization. Cohort sizes, new-user fallback and workload differences matter; a controlled new experiment is needed to establish a cause.

8. **Does it meet 50 RPS and 150 ms?** The recorded Windows synthetic high-load diagnostic missed that target. A lower-load case passed; these observations do not establish a production SLA.

9. **What runs on GitHub Pages?** Exported trained-model inference over a synthetic catalog runs in the browser. FastAPI, persistent feedback, FAISS serving and rollback belong to the separate Python/Docker application.

10. **Do likes retrain the model?** No. Browser session feedback changes session preferences, while Python feedback export is staged data. Automatic retraining and business uplift are not established.

## Study before an interview

- Derive the tower loss and connect it to the implementation.
- Trace chronological windows, controlled cold items and seen-item exclusion.
- Compare candidate recall, NDCG and approximate-index recall.
- Explain immutable bundles, checksums, idempotent feedback and rollback.
- Reproduce the failed selection result and one latency measurement with its workload.

See [current status](CURRENT_STATUS.md) and the existing project-specific interview and ownership material. These answers are practice aids, not completed personal contributions.
