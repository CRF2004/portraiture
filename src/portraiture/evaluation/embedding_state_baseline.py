"""
Combined embedding + state routing baseline.

This directly tests the core research question: does learned state routing
add predictive signal beyond what strong multilingual embeddings already
capture from conversation context?
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from portraiture.replay.hint_router import TextHintRouter
from portraiture.replay.signals import infer_state_hint_from_context, state_hint_to_action_label
from portraiture.utils.config import load_config
from portraiture.utils.io import read_jsonl, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Embedding + state routing combined baseline."
    )
    parser.add_argument(
        "--config", default="configs/evaluation/replay_baseline_v1.yaml"
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed/evaluation/embedding_state",
    )
    parser.add_argument(
        "--model-name",
        default="paraphrase-multilingual-MiniLM-L12-v2",
    )
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--similarity-floor", type=float, default=0.02)
    parser.add_argument(
        "--state-mode",
        choices=["learned", "heuristic", "off"],
        default="learned",
    )
    return parser.parse_args()


def build_context_texts(
    example: dict[str, Any],
    turns_by_id: dict[str, dict[str, Any]],
    messages_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    texts: list[str] = []
    for turn_id in example["context_turn_ids"]:
        turn = turns_by_id.get(turn_id)
        if not turn:
            continue
        user_message_id = turn.get("user_message_id")
        if not user_message_id:
            continue
        text = messages_by_id.get(user_message_id, {}).get("content_text", "").strip()
        if text:
            texts.append(text)
    return texts


def build_context_signature(
    example: dict[str, Any],
    turns_by_id: dict[str, dict[str, Any]],
    messages_by_id: dict[str, dict[str, Any]],
) -> str:
    return " \n ".join(
        build_context_texts(example, turns_by_id, messages_by_id)
    )


def compute_metrics(
    rows: list[dict[str, Any]],
    ground_truth_key: str = "ground_truth_label",
    predicted_key: str = "predicted_label",
) -> dict[str, float]:
    if not rows:
        return {"accuracy": 0.0, "macro_f1": 0.0}
    labels = sorted(
        {row.get(ground_truth_key) for row in rows if row.get(ground_truth_key)}
        | {row.get(predicted_key) for row in rows if row.get(predicted_key)}
    )
    correct = sum(
        1 for row in rows if row.get(ground_truth_key) == row.get(predicted_key)
    )
    accuracy = correct / len(rows)
    f1_scores: list[float] = []
    for label in labels:
        tp = sum(
            1
            for row in rows
            if row.get(ground_truth_key) == label
            and row.get(predicted_key) == label
        )
        fp = sum(
            1
            for row in rows
            if row.get(ground_truth_key) != label
            and row.get(predicted_key) == label
        )
        fn = sum(
            1
            for row in rows
            if row.get(ground_truth_key) == label
            and row.get(predicted_key) != label
        )
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (
            (2 * precision * recall / (precision + recall))
            if precision + recall
            else 0.0
        )
        f1_scores.append(f1)
    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0
    return {"accuracy": accuracy, "macro_f1": macro_f1}


def main() -> None:
    args = parse_args()

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print(
            "sentence-transformers is not installed.",
            file=sys.stderr,
        )
        sys.exit(1)

    config = load_config(Path(args.config))
    inputs = config["inputs"]

    replay_examples = read_jsonl(Path(inputs["replay_examples"]))
    turns = read_jsonl(Path(inputs["turns"]))
    messages = read_jsonl(Path(inputs["messages"]))
    turns_by_id = {turn["id"]: turn for turn in turns}
    messages_by_id = {message["id"]: message for message in messages}

    train_examples = [e for e in replay_examples if e["split"] == "train"]
    val_examples = [e for e in replay_examples if e["split"] == "val"]
    test_examples = [e for e in replay_examples if e["split"] == "test"]

    if not train_examples:
        raise ValueError("No training examples found.")

    default_label = Counter(
        e["ground_truth_label"] for e in train_examples
    ).most_common(1)[0][0]

    # Fit learned state router on training data
    state_hint_model = None
    if args.state_mode == "learned":
        print("Fitting learned state router on training data...")
        state_hint_model = TextHintRouter.fit_state_router(
            train_examples, turns_by_id, messages_by_id, min_probability=0.35
        )
        print(
            f"  Router fitted: {len(state_hint_model._state_type_counts)} state types"
        )

    # Load embedding model
    print(f"Loading embedding model: {args.model_name}")
    model = SentenceTransformer(args.model_name)

    # Encode all training examples
    train_signatures = [
        build_context_signature(e, turns_by_id, messages_by_id)
        for e in train_examples
    ]
    train_labels = [e["ground_truth_label"] for e in train_examples]
    print(f"Encoding {len(train_signatures)} training examples...")
    train_embeddings = model.encode(
        train_signatures, show_progress_bar=True, convert_to_numpy=True
    )
    train_norm = train_embeddings / (
        np.linalg.norm(train_embeddings, axis=1, keepdims=True) + 1e-10
    )

    all_rows: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    created_at = datetime.now().astimezone().isoformat()

    for split_name, examples in [
        ("train", train_examples),
        ("val", val_examples),
        ("test", test_examples),
    ]:
        if not examples:
            continue
        signatures = [
            build_context_signature(e, turns_by_id, messages_by_id)
            for e in examples
        ]
        print(f"Encoding {len(signatures)} {split_name} examples...")
        test_embeddings = model.encode(
            signatures, show_progress_bar=True, convert_to_numpy=True
        )
        test_norm = test_embeddings / (
            np.linalg.norm(test_embeddings, axis=1, keepdims=True) + 1e-10
        )
        sim_matrix = test_norm @ train_norm.T

        for i, example in enumerate(examples):
            similarities = sim_matrix[i]
            weighted_votes: dict[str, float] = defaultdict(float)
            best_label = default_label
            best_score = -1.0

            for j, score in enumerate(similarities):
                if score >= args.similarity_floor:
                    label = train_labels[j]
                    weighted_votes[label] = weighted_votes.get(label, 0.0) + float(score)
                if float(score) > best_score:
                    best_score = float(score)
                    best_label = train_labels[j]

            if weighted_votes:
                ranked = sorted(weighted_votes.items(), key=lambda x: (-x[1], x[0]))
                predicted_label = ranked[0][0]
                candidates = [
                    {"label": label, "score": float(score)}
                    for label, score in ranked[: args.top_k]
                ]
            else:
                predicted_label = best_label
                candidates = [{"label": default_label, "score": 1.0}]

            # --- State routing overlay ---
            context_texts = build_context_texts(
                example, turns_by_id, messages_by_id
            )
            if args.state_mode == "learned" and state_hint_model is not None:
                state_hint = state_hint_model.predict(context_texts)
            elif args.state_mode == "heuristic":
                state_hint = infer_state_hint_from_context(context_texts)
            else:
                state_hint = {
                    "state_type": None,
                    "state_value": None,
                    "confidence": 0.0,
                    "reason": "disabled",
                }

            state_hint_label = (
                state_hint_to_action_label(
                    state_hint.get("state_type"),
                    state_hint.get("state_value"),
                )
                if args.state_mode != "off"
                else None
            )
            state_conf = float(state_hint.get("confidence") or 0.0)

            # If state hint is confident, boost/re-rank candidates
            if state_hint_label and state_conf >= 0.35:
                top_score = candidates[0]["score"] if candidates else 0.0
                state_value = state_hint.get("state_value")
                boost = (
                    0.45
                    if state_value == "topic_transition"
                    else 0.30
                    if state_value == "needs_troubleshooting"
                    else 0.15
                )
                found = False
                for c in candidates:
                    if c["label"] == state_hint_label:
                        c["score"] += boost
                        found = True
                        break
                if not found and top_score < 0.5:
                    candidates.append(
                        {"label": state_hint_label, "score": top_score + boost * 0.7}
                    )
                candidates.sort(key=lambda x: -x["score"])
                candidates = candidates[: args.top_k]
                if candidates:
                    predicted_label = candidates[0]["label"]

            all_rows.append(
                {
                    "split": example["split"],
                    "ground_truth_label": example["ground_truth_label"],
                    "predicted_label": predicted_label,
                    "ground_truth_coarse_label": example.get(
                        "ground_truth_coarse_label"
                    ),
                    "predicted_coarse_label": predicted_label,
                    "observed_state_type": example.get("observed_state_type"),
                    "observed_state_value": example.get("observed_state_value"),
                }
            )
            predictions.append(
                {
                    "id": f"pred_embedding_state_{example['id']}",
                    "user_id": example["user_id"],
                    "created_at": created_at,
                    "updated_at": created_at,
                    "replay_example_id": example["id"],
                    "predictor_name": f"embedding_{args.state_mode}_state",
                    "predicted_label": predicted_label,
                    "candidate_labels": candidates,
                    "top_similarity": best_score,
                    "state_hint_label": state_hint_label,
                    "state_confidence": state_conf,
                }
            )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics: list[dict[str, Any]] = []
    for split in ("train", "val", "test"):
        split_rows = [r for r in all_rows if r["split"] == split]
        if not split_rows:
            continue
        fine = compute_metrics(split_rows)
        coarse = compute_metrics(
            split_rows,
            ground_truth_key="ground_truth_coarse_label",
            predicted_key="predicted_coarse_label",
        )
        metrics.append(
            {
                "created_at": created_at,
                "split": split,
                "n": len(split_rows),
                "accuracy": fine["accuracy"],
                "macro_f1": fine["macro_f1"],
                "coarse_accuracy": coarse["accuracy"],
                "coarse_macro_f1": coarse["macro_f1"],
                "default_label": default_label,
                "predictor_name": f"embedding_{args.state_mode}_state",
                "model_name": args.model_name,
            }
        )

    write_jsonl(output_dir / "metrics.jsonl", metrics)
    write_jsonl(output_dir / "predictions.jsonl", predictions)

    print(
        json.dumps(
            {
                "predictor_name": f"embedding_{args.state_mode}_state",
                "model_name": args.model_name,
                "default_label": default_label,
                "metrics": [m for m in metrics if m["split"] == "test"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
