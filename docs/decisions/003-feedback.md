# Decision 003: Feedback provenance before automatic retraining

Log recommendation exposures before accepting feedback. Validate that feedback references
an exposed item, preserve model/route/source, and reject load-test events from the feedback
dataset. Duplicate event IDs represent retries, not new training examples.

Separate clicks, likes, and imported ratings. They have different meanings and selection bias.
Automatic pooling would create an ambiguous learning objective and permit demo/load traffic
to contaminate experiments. Export is staged for a later, explicit label policy.

Consequence: this version does not automatically retrain or instantly adapt a user's history.
That is a documented product limitation. A future ingestion job needs delayed outcomes,
source checks, temporal feature generation, and release quality gates.
