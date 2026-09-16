"""
Critical experiment: Combine semantic (CJK-aware char n-gram) similarity
with learned state routing. This directly tests whether state adds predictive
signal beyond the strongest text-only baseline.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

from portraiture.evaluation.replay import (
    build_context_texts,
    choose_prediction,
    compute_classification_metrics,
    semantic_tokenize,
)
from portraiture.replay.hint_router import TextHintRouter
from portraiture.utils.config import load_config
from portraiture.utils.io import read_jsonl, write_jsonl


def build_context_signature(example, turns_by_id, messages_by_id):
    texts = build_context_texts(example, turns_by_id, messages_by_id)
    return " \n ".join(texts)


def cosine_similarity(left: str, right: str) -> float:
    left_tokens = Counter(semantic_tokenize(left))
    right_tokens = Counter(semantic_tokenize(right))
    if not left_tokens or not right_tokens:
        return 0.0
    shared = left_tokens.keys() & right_tokens.keys()
    dot = sum(left_tokens[token] * right_tokens[token] for token in shared)
    left_norm = sqrt(sum(v * v for v in left_tokens.values()))
    right_norm = sqrt(sum(v * v for v in right_tokens.values()))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def main():
    config = load_config(Path("configs/evaluation/replay_baseline_v1.yaml"))
    inputs = config["inputs"]

    replay_examples = read_jsonl(Path(inputs["replay_examples"]))
    turns = read_jsonl(Path(inputs["turns"]))
    messages = read_jsonl(Path(inputs["messages"]))
    turns_by_id = {t["id"]: t for t in turns}
    messages_by_id = {m["id"]: m for m in messages}

    train_examples = [e for e in replay_examples if e["split"] == "train"]
    val_examples = [e for e in replay_examples if e["split"] == "val"]
    test_examples = [e for e in replay_examples if e["split"] == "test"]

    default_label = Counter(
        e["ground_truth_label"] for e in train_examples
    ).most_common(1)[0][0]

    # Fit learned state router
    print("Fitting learned state router...")
    router = TextHintRouter.fit_state_router(
        train_examples, turns_by_id, messages_by_id, min_probability=0.35
    )

    # Build signatures for semantic similarity
    train_sigs = [
        build_context_signature(e, turns_by_id, messages_by_id)
        for e in train_examples
    ]
    train_labels = [e["ground_truth_label"] for e in train_examples]

    created_at = datetime.now().astimezone().isoformat()
    all_predictions: list[dict[str, Any]] = []

    for split_name, examples in [
        ("train", train_examples),
        ("val", val_examples),
        ("test", test_examples),
    ]:
        if not examples:
            continue
        for example in examples:
            sig = build_context_signature(example, turns_by_id, messages_by_id)

            # Semantic k-NN
            weighted_votes: dict[str, float] = defaultdict(float)
            best_label = default_label
            best_score = -1.0
            for j, train_ex in enumerate(train_examples):
                train_sig = train_sigs[j]
                score = cosine_similarity(sig, train_sig)
                if score >= 0.02:
                    weighted_votes[train_labels[j]] = (
                        weighted_votes.get(train_labels[j], 0.0) + score
                    )
                if score > best_score:
                    best_score = score
                    best_label = train_labels[j]

            if weighted_votes:
                ranked = sorted(
                    weighted_votes.items(), key=lambda x: (-x[1], x[0])
                )
                nn_pred = ranked[0][0]
            else:
                nn_pred = best_label

            # State routing: get state hint and use it to re-rank
            context_texts = build_context_texts(
                example, turns_by_id, messages_by_id
            )
            state_hint = router.predict(context_texts)
            state_label = state_hint.get("state_type")
            state_value = state_hint.get("state_value")
            state_conf = float(state_hint.get("confidence") or 0.0)

            # State hint to action label mapping (from replay.py)
            from portraiture.replay.signals import state_hint_to_action_label
            hint_label = (
                state_hint_to_action_label(state_label, state_value)
                if state_label and state_conf >= 0.35
                else None
            )

            # Combined prediction: semantic k-NN + state boost
            if hint_label and weighted_votes:
                boost = 0.3 * max(weighted_votes.values()) if weighted_votes else 0.1
                if hint_label in weighted_votes:
                    weighted_votes[hint_label] += boost
                else:
                    weighted_votes[hint_label] = boost
                ranked = sorted(
                    weighted_votes.items(), key=lambda x: (-x[1], x[0])
                )
                combined_pred = ranked[0][0]
            elif hint_label:
                combined_pred = hint_label
            else:
                combined_pred = nn_pred

            all_predictions.append(
                {
                    "example_id": example["id"],
                    "split": example["split"],
                    "ground_truth_label": example["ground_truth_label"],
                    "nn_pred": nn_pred,
                    "state_pred": hint_label,
                    "combined_pred": combined_pred,
                    "state_type": state_label,
                    "state_value": state_value,
                    "state_confidence": state_conf,
                    "top_similarity": float(best_score),
                }
            )

    output_dir = Path("data/processed/evaluation/semantic_state_combined")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Metrics for each predictor variant
    metrics = []
    for pred_key, pred_name in [
        ("nn_pred", "semantic_nn"),
        ("state_pred", "state_hint_only"),
        ("combined_pred", "semantic_state_combined"),
    ]:
        for split in ("train", "val", "test"):
            split_preds = [
                p for p in all_predictions if p["split"] == split
            ]
            if not split_preds:
                continue
            y_true = [p["ground_truth_label"] for p in split_preds]
            # Filter out None state preds
            if pred_key == "state_pred":
                valid = [
                    (p["ground_truth_label"], p["state_pred"])
                    for p in split_preds
                    if p["state_pred"] is not None
                ]
                if not valid:
                    continue
                y_true_v, y_pred_v = zip(*valid)
            else:
                y_true_v = y_true
                y_pred_v = [p[pred_key] for p in split_preds]

            from sklearn.metrics import accuracy_score, f1_score
            acc = accuracy_score(y_true_v, y_pred_v)
            mf1 = f1_score(y_true_v, y_pred_v, average="macro", zero_division=0)

            metrics.append(
                {
                    "created_at": created_at,
                    "split": split,
                    "n": len(y_true_v),
                    "accuracy": float(acc),
                    "macro_f1": float(mf1),
                    "predictor_name": pred_name,
                }
            )

    write_jsonl(output_dir / "metrics.jsonl", metrics)
    write_jsonl(output_dir / "predictions.jsonl", all_predictions)

    print("=== Results ===")
    for m in metrics:
        if m["split"] == "test":
            print(
                f"  {m['predictor_name']:30s}  acc={m['accuracy']:.4f}  "
                f"macro_f1={m['macro_f1']:.4f}"
            )


if __name__ == "__main__":
    main()
