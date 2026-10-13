# Decision 002: Small CPU inference and compatible bundles

Train in PyTorch, then export fixed item vectors and linear user projections for NumPy serving.
This avoids GPU/API dependencies on the request path. A parity test protects the export.
The small architecture is sufficient to investigate item-content and identity tradeoffs.

Use exact FAISS inner-product retrieval as a reference and HNSW as an approximate alternative.
Normalize embeddings first. Benchmark HNSW recall against exact vector neighbors separately
from recall against relevant held-out items. Better index recall cannot fix a weak embedding.

Package weights, transforms, mappings, ranker, indexes, and feature schema together. Verify
checksums and dimensions before activation. This prevents a healthy process from silently
serving an incompatible model/index combination.

Tradeoff: bundles occupy RAM, loading pauses a routing update, histories are static, and
single-host routing cannot coordinate a distributed fleet. These limits are explicit.
