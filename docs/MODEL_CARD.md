# Model card

## Models

- Popularity: positive-event counts from retrieval-training window A.
- Category popularity: A popularity plus a documented user-category boost.
- Implicit ALS: the established `implicit` CPU implementation, alpha 20, regularization 0.1.
  User factors are folded in from pre-prediction history using frozen item factors.
- Content retrieval: TF-IDF/SVD item vectors and a weighted history representation.
- Two-tower: PyTorch linear user/content projections plus learned item-ID embeddings.
- Ranker: LightGBM LambdaRank over frozen-retriever candidates, trained with B-window labels.

The retrieval architecture is deliberately small. The user tower encodes a recency-weighted
mean of historical positive item content; it is not a Transformer or a trained sequential model.
The item tower projects content and adds an ID embedding. ID dropout is 30% for hybrid training.
Items with no A-positive history use the zero ID embedding at inference.

## Loss and inference

Normalized user/item vectors use inner-product similarity. Training uses temperature 0.10
and a multi-positive contrastive loss:

L = mean(logsumexp(allowed candidate logits) - logsumexp(same-item positive logits)).

Duplicate positive item IDs share numerator probability mass. Earlier positive history items
are masked as negatives. Unobserved batch items can still be false negatives; no exposure log
exists to resolve that assumption. Queries require earlier positive history and a previously
unseen target; the training report states how many examples satisfy this.

Serving exports linear weights and item vectors to NumPy. A parity test verifies user projection
against the PyTorch checkpoint. FAISS provides an exact inner-product index and an HNSW index.
Catalog filtering uses exact scoring to prevent post-filter candidate starvation.

Ranker features are shared across offline and serving code. Scores are relative ranking signals,
not calibrated probabilities. The ranker cannot recover a relevant item absent from retrieval.
Candidate groups with no relevant retrieved item are excluded from ranker fitting and counted.

## Selection and use

Validation macro NDCG@10 chooses the serving `auto` algorithm. Test data do not select it.
Explicit API modes expose all algorithms for debugging. Use the synthetic bundle for the
public demonstration; use real-data bundles locally for research comparisons.

## Known weaknesses

- Sparse histories and new users cause frequent popularity fallback.
- TF-IDF/SVD captures limited semantic meaning.
- Frozen popularity and histories become stale between bundle rebuilds.
- Popularity and catalog sampling can disadvantage long-tail products.
- Global temporal partitions create pronounced population shifts in MovieLens.
- One seed and small returning-user cohorts limit confidence in gains.
- The full ranker did not improve the recorded MovieLens final-test result.
- The system has no trained image model, language model, or sequential encoder.
- New catalog items are admitted through preprocessing/rebuilding, not live ingestion.

## Artifact trust

Bundles verify asset SHA256 values, feature order, array dimensions, index counts, and ranker
feature count. These checks detect corruption and mismatched components. They do not verify
the author or make untrusted pickle/joblib transforms safe. Serve only trusted, locally built
bundles. Activation validates first and swaps the routing file atomically.
