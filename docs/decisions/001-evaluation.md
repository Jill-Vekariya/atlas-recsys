# Decision 001: Time before model complexity

Use four global chronological windows and independent ranker targets. Random interaction
splits can reveal future preferences through histories or aggregate features. Training a ranker
on candidates from a retriever that already fitted the target interactions makes its task
unrealistically easy.

Cold items are selected by a seeded hash and withheld from both training windows. Catalog text
remains available under a declared snapshot assumption. This tests missing interactions,
not true historical product launches. Metadata cannot establish launch dates.

Consequence: the protocol produces many new users in both real-data workloads. Aggregate
metrics must be paired with cohort sizes. Full-catalog metrics are harder than sampled-negative
metrics, but describe the actual candidate-selection problem more honestly.

Future work: rolling prediction snapshots with clustered user uncertainty and a separate
untouched future window. Do not redesign the protocol based on final-test performance and
present the same test period as an independent confirmation.
