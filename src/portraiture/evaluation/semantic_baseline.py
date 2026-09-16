from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from portraiture.evaluation.replay import compute_classification_metrics, evaluate_pass
from portraiture.utils.config import load_config
from portraiture.utils.io import read_jsonl, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a semantic-context nearest-neighbor baseline.")
    parser.add_argument("--config", default="configs/evaluation/replay_baseline_v1.yaml")
    parser.add_argument("--output-dir", default="data/processed/evaluation/semantic_baseline")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(Path(args.config))
    inputs = config["inputs"]
    output_dir = Path(args.output_dir)

    replay_examples = read_jsonl(Path(inputs["replay_examples"]))
    turns = read_jsonl(Path(inputs["turns"]))
    messages = read_jsonl(Path(inputs["messages"]))
    turns_by_id = {turn["id"]: turn for turn in turns}
    messages_by_id = {message["id"]: message for message in messages}

    train_examples = [example for example in replay_examples if example["split"] == "train"]
    if not train_examples:
        raise ValueError("No training examples found for the semantic baseline.")

    default_label = Counter(example["ground_truth_label"] for example in train_examples).most_common(1)[0][0]
    prediction_records, divergence_records, _, _, scored_rows = evaluate_pass(
        replay_examples=replay_examples,
        train_examples=train_examples,
        turns_by_id=turns_by_id,
        messages_by_id=messages_by_id,
        top_k=config["evaluation"]["top_k"],
        similarity_floor=config["evaluation"]["neighbor_similarity_floor"],
        default_label=default_label,
        similarity_threshold=config["task"]["topic_shift_similarity_threshold"],
        predictor_name="semantic_context_nn",
        profile_store=None,
        state_hint_model=None,
        create_refinements=False,
        run_id="run_semantic_context_nn_v1",
        use_profile_hint=False,
        use_state_hint=False,
        state_hint_min_confidence=1.0,
        neighbor_mode="semantic",
        emit_snapshots=False,
    )

    metrics: list[dict[str, Any]] = []
    created_at = datetime.now().astimezone().isoformat()
    for split in ("train", "val", "test"):
        split_rows = [row for row in scored_rows if row["split"] == split]
        fine = compute_classification_metrics(split_rows)
        coarse = compute_classification_metrics(
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
                "predictor_name": "semantic_context_nn",
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "metrics.jsonl", metrics)
    write_jsonl(output_dir / "predictions.jsonl", prediction_records)
    write_jsonl(output_dir / "divergences.jsonl", divergence_records)

    print(
        json.dumps(
            {
                "predictor_name": "semantic_context_nn",
                "default_label": default_label,
                "test_metrics": [row for row in metrics if row["split"] == "test"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
