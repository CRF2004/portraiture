"""
Stronger baselines using sklearn TF-IDF and logistic regression.

TF-IDF with char+word n-grams provides a much stronger text representation
than the hand-crafted char-n-gram cosine similarity currently used as the
"semantic" baseline. Logistic regression provides a calibrated linear
classifier baseline that complements the k-NN approaches.

Variants:
  - tfidf_nn: TF-IDF weighted k-NN (replaces semantic_context_nn)
  - tfidf_nn_state: TF-IDF k-NN + learned state routing
  - tfidf_lr: Logistic regression on TF-IDF features
  - tfidf_lr_state: LR + state features concatenated
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
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.preprocessing import LabelEncoder

from portraiture.replay.hint_router import TextHintRouter
from portraiture.replay.signals import (
    infer_state_hint_from_context,
    state_hint_to_action_label,
)
from portraiture.utils.config import load_config
from portraiture.utils.io import read_jsonl, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stronger baselines using TF-IDF and logistic regression."
    )
    parser.add_argument(
        "--config", default="configs/evaluation/replay_baseline_v1.yaml"
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed/evaluation/tfidf_baselines",
    )
    parser.add_argument(
        "--variant",
        choices=["tfidf_nn", "tfidf_nn_state", "tfidf_lr", "tfidf_lr_state"],
        default="tfidf_nn",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--similarity-floor", type=float, default=0.01)
    return parser.parse_args()


def build_context_signature(
    example: dict[str, Any],
    turns_by_id: dict[str, dict[str, Any]],
    messages_by_id: dict[str, dict[str, Any]],
) -> str:
    texts: list[str] = []
    for turn_id in example["context_turn_ids"]:
        turn = turns_by_id.get(turn_id)
        if not turn:
            continue
        user_message_id = turn.get("user_message_id")
        if not user_message_id:
            continue
        text = messages_by_id.get(user_message_id, {}).get("content_text", "")
        if text:
            texts.append(text)
    return " \n ".join(texts)


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


def compute_metrics(
    y_true: list[str], y_pred: list[str]
) -> dict[str, float]:
    if not y_true:
        return {"accuracy": 0.0, "macro_f1": 0.0}
    accuracy = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    return {"accuracy": float(accuracy), "macro_f1": float(macro_f1)}


def main() -> None:
    args = parse_args()
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

    # Build text signatures
    X_train_text = [
        build_context_signature(e, turns_by_id, messages_by_id)
        for e in train_examples
    ]
    X_val_text = [
        build_context_signature(e, turns_by_id, messages_by_id)
        for e in val_examples
    ]
    X_test_text = [
        build_context_signature(e, turns_by_id, messages_by_id)
        for e in test_examples
    ]
    y_train = [e["ground_truth_label"] for e in train_examples]
    y_val = [e["ground_truth_label"] for e in val_examples]
    y_test = [e["ground_truth_label"] for e in test_examples]

    # Label encoder for LR
    le = LabelEncoder()
    le.fit(y_train + y_val + y_test)

    # TF-IDF vectorizer: character n-grams (3-5) + word n-grams (1-2)
    # Character n-grams handle CJK well; word n-grams handle ASCII
    print("Fitting TF-IDF vectorizer...")
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 5),
        max_features=8000,
        sublinear_tf=True,
        max_df=0.9,
        min_df=2,
    )
    X_train_tfidf = vectorizer.fit_transform(X_train_text)
    X_val_tfidf = vectorizer.transform(X_val_text)
    X_test_tfidf = vectorizer.transform(X_test_text)
    print(f"  Vocabulary size: {len(vectorizer.vocabulary_)}")

    variant = args.variant
    created_at = datetime.now().astimezone().isoformat()
    all_predictions: list[dict[str, Any]] = []

    if variant in ("tfidf_nn", "tfidf_nn_state"):
        # Fit state router if needed
        state_hint_model = None
        if variant == "tfidf_nn_state":
            print("Fitting learned state router...")
            state_hint_model = TextHintRouter.fit_state_router(
                train_examples, turns_by_id, messages_by_id,
                min_probability=0.35,
            )

        for split_name, X_split, examples in [
            ("train", X_train_tfidf, train_examples),
            ("val", X_val_tfidf, val_examples),
            ("test", X_test_tfidf, test_examples),
        ]:
            if len(examples) == 0:
                continue
            # Cosine similarity between split and train
            from sklearn.metrics.pairwise import cosine_similarity
            sim_matrix = cosine_similarity(X_split, X_train_tfidf)

            for i, example in enumerate(examples):
                similarities = sim_matrix[i]
                weighted_votes: dict[str, float] = defaultdict(float)
                best_label = default_label
                best_score = -1.0

                for j, score in enumerate(similarities):
                    if score >= args.similarity_floor:
                        weighted_votes[y_train[j]] = (
                            weighted_votes.get(y_train[j], 0.0) + float(score)
                        )
                    if float(score) > best_score:
                        best_score = float(score)
                        best_label = y_train[j]

                if weighted_votes:
                    ranked = sorted(
                        weighted_votes.items(), key=lambda x: (-x[1], x[0])
                    )
                    predicted_label = ranked[0][0]
                else:
                    predicted_label = best_label

                # State routing overlay
                if state_hint_model is not None:
                    context_texts = build_context_texts(
                        example, turns_by_id, messages_by_id
                    )
                    state_hint = state_hint_model.predict(context_texts)
                    state_hint_label = state_hint_to_action_label(
                        state_hint.get("state_type"),
                        state_hint.get("state_value"),
                    )
                    state_conf = float(state_hint.get("confidence") or 0.0)
                    if state_hint_label and state_conf >= 0.35:
                        if weighted_votes:
                            # Boost the state-hinted label
                            if state_hint_label in weighted_votes:
                                weighted_votes[state_hint_label] += 0.3 * max(weighted_votes.values())
                            else:
                                weighted_votes[state_hint_label] = 0.3 * max(weighted_votes.values()) if weighted_votes else 0.1
                            ranked = sorted(
                                weighted_votes.items(), key=lambda x: (-x[1], x[0])
                            )
                            predicted_label = ranked[0][0]

                all_predictions.append(
                    {
                        "example_id": example["id"],
                        "split": example["split"],
                        "ground_truth_label": example["ground_truth_label"],
                        "predicted_label": predicted_label,
                        "ground_truth_coarse_label": example.get(
                            "ground_truth_coarse_label"
                        ),
                        "top_similarity": float(best_score),
                    }
                )

    elif variant in ("tfidf_lr", "tfidf_lr_state"):
        # Logistic regression
        if variant == "tfidf_lr_state":
            # Add state features
            print("Extracting state features...")
            # Get state type/value for each example as additional features
            def get_state_features(examples):
                state_types = set()
                for e in train_examples:
                    st = e.get("observed_state_type", "none")
                    state_types.add(st)
                state_type_list = sorted(state_types)
                features = np.zeros((len(examples), len(state_type_list)))
                for i, e in enumerate(examples):
                    st = e.get("observed_state_type", "none")
                    if st in state_type_list:
                        features[i, state_type_list.index(st)] = 1.0
                return features

            X_train_state = get_state_features(train_examples)
            X_val_state = get_state_features(val_examples)
            X_test_state = get_state_features(test_examples)

            from scipy.sparse import hstack
            X_train_combined = hstack([X_train_tfidf, X_train_state])
            X_val_combined = hstack([X_val_tfidf, X_val_state])
            X_test_combined = hstack([X_test_tfidf, X_test_state])
        else:
            X_train_combined = X_train_tfidf
            X_val_combined = X_val_tfidf
            X_test_combined = X_test_tfidf

        # Train LR with validation-based C selection
        best_c = 1.0
        best_val_f1 = 0.0
        for C in [0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]:
            lr = LogisticRegression(
                C=C,
                max_iter=2000,
                multi_class="multinomial",
                random_state=42,
                class_weight="balanced",
            )
            lr.fit(X_train_combined, le.transform(y_train))
            val_pred = le.inverse_transform(lr.predict(X_val_combined))
            val_f1 = f1_score(y_val, val_pred, average="macro", zero_division=0)
            if val_f1 > best_val_f1:
                best_val_f1 = val_f1
                best_c = C

        print(f"  Best C={best_c} (val macro-F1={best_val_f1:.4f})")

        lr = LogisticRegression(
            C=best_c,
            max_iter=2000,
            multi_class="multinomial",
            random_state=42,
            class_weight="balanced",
        )
        lr.fit(X_train_combined, le.transform(y_train))

        # Predict all splits
        for split_name, X_split, examples in [
            ("train", X_train_combined, train_examples),
            ("val", X_val_combined, val_examples),
            ("test", X_test_combined, test_examples),
        ]:
            if len(examples) == 0:
                continue
            y_pred_encoded = lr.predict(X_split)
            y_pred = le.inverse_transform(y_pred_encoded)
            for i, example in enumerate(examples):
                all_predictions.append(
                    {
                        "example_id": example["id"],
                        "split": example["split"],
                        "ground_truth_label": example["ground_truth_label"],
                        "predicted_label": y_pred[i],
                        "ground_truth_coarse_label": example.get(
                            "ground_truth_coarse_label"
                        ),
                    }
                )

    # Compute metrics per split
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics: list[dict[str, Any]] = []

    for split in ("train", "val", "test"):
        split_preds = [p for p in all_predictions if p["split"] == split]
        if not split_preds:
            continue
        y_true = [p["ground_truth_label"] for p in split_preds]
        y_pred = [p["predicted_label"] for p in split_preds]
        fine = compute_metrics(y_true, y_pred)

        # Coarse metrics
        y_true_coarse = [p.get("ground_truth_coarse_label", p["ground_truth_label"]) for p in split_preds]
        y_pred_coarse = [p.get("predicted_label", p["predicted_label"]) for p in split_preds]

        metrics.append(
            {
                "created_at": created_at,
                "split": split,
                "n": len(split_preds),
                "accuracy": fine["accuracy"],
                "macro_f1": fine["macro_f1"],
                "predictor_name": variant,
                "variant": variant,
            }
        )

    # Per-label breakdown for test split
    per_label: dict[str, dict[str, Any]] = {}
    test_preds = [p for p in all_predictions if p["split"] == "test"]
    if test_preds:
        all_labels = sorted(set(p["ground_truth_label"] for p in test_preds))
        for label in all_labels:
            label_preds = [p for p in test_preds if p["ground_truth_label"] == label]
            correct = sum(1 for p in label_preds if p["predicted_label"] == label)
            per_label[label] = {
                "count": len(label_preds),
                "correct": correct,
                "accuracy": correct / len(label_preds) if label_preds else 0.0,
            }

    write_jsonl(output_dir / "metrics.jsonl", metrics)
    write_jsonl(output_dir / "predictions.jsonl", all_predictions)

    print(
        json.dumps(
            {
                "variant": variant,
                "default_label": default_label,
                "test_metrics": [
                    m for m in metrics if m["split"] == "test"
                ],
                "per_label_test": per_label,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
