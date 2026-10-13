"""PyTorch contrastive training; NumPy inference export for predictable CPU serving."""

import numpy as np
import pandas as pd
import torch
from scipy.sparse import csr_matrix
from torch import nn
from torch.nn import functional as F

from atlas.features import context
from atlas.features import fold_in_als as fold_in_als


class TwoTower(nn.Module):
    def __init__(self, item_count: int, content_dim: int, embedding_dim: int):
        super().__init__()
        self.user = nn.Linear(content_dim, embedding_dim, bias=False)
        self.item = nn.Linear(content_dim, embedding_dim, bias=False)
        self.identity = nn.Embedding(item_count + 1, embedding_dim, padding_idx=0)
        nn.init.normal_(self.identity.weight, std=0.03)
        with torch.no_grad():
            self.identity.weight[0].zero_()

    def forward(self, user_content, item_content, ids):
        return (
            F.normalize(self.user(user_content), dim=1),
            F.normalize(self.item(item_content) + self.identity(ids), dim=1),
        )


def multi_positive_loss(logits, item_ids, allowed):
    """Repeated positives share probability mass; earlier positives are masked as negatives."""
    positives = item_ids[:, None] == item_ids[None, :]
    allowed = allowed | positives
    denominator = torch.logsumexp(logits.masked_fill(~allowed, -torch.inf), dim=1)
    numerator = torch.logsumexp(logits.masked_fill(~positives, -torch.inf), dim=1)
    return (denominator - numerator).mean()


def training_examples(events, item_map, content, cfg):
    examples = []
    state = {}
    a = events[events.split == "retriever"]
    # Equal-time events are updated after all examples at that time have been generated.
    for _, group in a.groupby("timestamp", sort=True):
        for row in group.itertuples():
            old = state.get(str(row.user_id), [])
            idx = item_map[row.item_id]
            if row.rating >= cfg["positive_rating"] and old and idx not in old:
                examples.append((context(old, content, cfg["history_size"]), idx, set(old)))
        for row in group.itertuples():
            if row.rating >= cfg["positive_rating"]:
                state.setdefault(str(row.user_id), []).append(item_map[row.item_id])
    return examples


def train_tower(events: pd.DataFrame, item_map: dict, content: np.ndarray, popularity, cfg):
    torch.set_num_threads(cfg["threads"])
    torch.manual_seed(cfg["seed"])
    torch.use_deterministic_algorithms(True)
    model = TwoTower(len(content), content.shape[1], cfg["embedding_dim"])
    examples = training_examples(events, item_map, content, cfg)
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg["learning_rate"], weight_decay=0.001)
    rng = np.random.default_rng(cfg["seed"])
    losses = []
    c = torch.from_numpy(content)
    variant = cfg.get("item_variant", "hybrid")
    item_content = torch.zeros_like(c) if variant == "identity_only" else c
    for _ in range(cfg["epochs"]):
        total, steps = 0.0, 0
        order = rng.permutation(len(examples))
        for start in range(0, len(order), cfg["batch_size"]):
            batch = [examples[int(i)] for i in order[start : start + cfg["batch_size"]]]
            if len(batch) < 2:
                continue
            x = torch.from_numpy(np.stack([b[0] for b in batch]))
            raw = torch.tensor([b[1] for b in batch], dtype=torch.long)
            ids = raw + 1
            ids[torch.rand(len(ids)) < cfg["id_dropout"]] = 0
            if variant == "content_only":
                ids[:] = 0
            allowed = torch.tensor([[int(j) not in b[2] for j in raw] for b in batch])
            u, v = model(x, item_content[raw], ids)
            loss = multi_positive_loss(u @ v.T / 0.10, raw, allowed)
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            total += float(loss.detach())
            steps += 1
        losses.append(total / max(1, steps))
    # Items without positive A-window history use the content path only.
    exported_ids = np.arange(len(content)) + 1
    exported_ids[np.asarray(popularity) == 0] = 0
    if variant == "content_only":
        exported_ids[:] = 0
    model.eval()
    with torch.no_grad():
        vectors = F.normalize(
            model.item(item_content) + model.identity(torch.tensor(exported_ids)), dim=1
        )
    return (
        model,
        vectors.numpy().astype(np.float32),
        {
            "examples": len(examples),
            "epoch_losses": losses,
            "item_variant": variant,
            "status": "trained" if len(examples) >= 2 else "insufficient_personalized_examples",
        },
    )


def train_als(events, item_map, cfg):
    from implicit.cpu.als import AlternatingLeastSquares

    a = events[(events.split == "retriever") & (events.rating >= cfg["positive_rating"])]
    user_map = {u: i for i, u in enumerate(sorted(a.user_id.unique()))}
    rows = [user_map[u] for u in a.user_id]
    cols = [item_map[i] for i in a.item_id]
    matrix = csr_matrix(
        (np.ones(len(a), dtype=np.float32), (rows, cols)), shape=(len(user_map), len(item_map))
    )
    matrix.sum_duplicates()
    model = AlternatingLeastSquares(
        factors=cfg["embedding_dim"],
        regularization=0.1,
        alpha=20.0,
        iterations=cfg["als_iterations"],
        random_state=cfg["seed"],
        num_threads=cfg["threads"],
    )
    model.fit(matrix, show_progress=False)
    return model.item_factors.astype(np.float32), {
        "factors": cfg["embedding_dim"],
        "regularization": 0.1,
        "alpha": 20.0,
        "iterations": cfg["als_iterations"],
        "training_users": len(user_map),
    }
