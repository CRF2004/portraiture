from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from portraiture.evaluation.replay import compute_classification_metrics, evaluate_pass, seed_persona_facts_from_training_examples
from portraiture.replay.hint_router import TextHintRouter
from portraiture.replay.signals import coarse_label_for_action
from portraiture.state import ProfileStateStore
from portraiture.utils.config import load_config
from portraiture.utils.io import read_jsonl, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run split-robustness checks for replay state hint variants.")
    parser.add_argument("--config", default="configs/evaluation/replay_state_hint_learned_v2.yaml")
    parser.add_argument("--seeds", default="11,23,37,51,73", help="Comma-separated random seeds.")
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--router-min-probability", type=float, default=0.35)
    parser.add_argument("--output-dir", default="data/processed/evaluation/robustness")
    parser.add_argument(
        "--split-strategy",
        choices=["random_episode", "random_conversation"],
        default="random_episode",
    )
    return parser.parse_args()


def assign_random_episode_split(
    examples: list[dict[str, Any]],
    *,
    seed: int,
    train_ratio: float,
    val_ratio: float,
) -> list[dict[str, Any]]:
    rows = deepcopy(examples)
    episode_ids = sorted({row["episode_id"] for row in rows})
    rng = random.Random(seed)
    rng.shuffle(episode_ids)

    train_end = int(len(episode_ids) * train_ratio)
    val_end = train_end + int(len(episode_ids) * val_ratio)
    split_by_episode = {}
    for idx, episode_id in enumerate(episode_ids):
        if idx < train_end:
            split_by_episode[episode_id] = "train"
        elif idx < val_end:
            split_by_episode[episode_id] = "val"
        else:
            split_by_episode[episode_id] = "test"

    for row in rows:
        row["split"] = split_by_episode[row["episode_id"]]
    return rows


def assign_random_conversation_split(
    examples: list[dict[str, Any]],
    *,
    seed: int,
    train_ratio: float,
    val_ratio: float,
) -> list[dict[str, Any]]:
    rows = deepcopy(examples)
    conversation_ids = sorted({row.get("metadata", {}).get("conversation_id") for row in rows if row.get("metadata", {}).get("conversation_id")})
    rng = random.Random(seed)
    rng.shuffle(conversation_ids)

    train_end = int(len(conversation_ids) * train_ratio)
    val_end = train_end + int(len(conversation_ids) * val_ratio)
    split_by_conversation = {}
    for idx, conversation_id in enumerate(conversation_ids):
        if idx < train_end:
            split_by_conversation[conversation_id] = "train"
        elif idx < val_end:
            split_by_conversation[conversation_id] = "val"
        else:
            split_by_conversation[conversation_id] = "test"

    for row in rows:
        conversation_id = row.get("metadata", {}).get("conversation_id")
        row["split"] = split_by_conversation.get(conversation_id, "train")
    return rows


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(rows),
        "label_counts": dict(sorted(Counter(row["ground_truth_label"] for row in rows).items())),
        "state_counts": dict(sorted(Counter(row.get("observed_state_type") or "none" for row in rows).items())),
    }


def state_key(row: dict[str, Any]) -> tuple[str | None, str | None]:
    return row.get("observed_state_type"), row.get("observed_state_value")


def evaluate_state_prior_variant(
    *,
    replay_examples: list[dict[str, Any]],
    seed: int,
    split_strategy: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    train_examples = [row for row in replay_examples if row["split"] == "train"]
    if not train_examples:
        raise ValueError(f"No training examples for seed={seed}")
    default_label = Counter(row["ground_truth_label"] for row in train_examples).most_common(1)[0][0]

    counts_by_state: dict[tuple[str | None, str | None], Counter[str]] = {}
    for row in train_examples:
        counts_by_state.setdefault(state_key(row), Counter())[row["ground_truth_label"]] += 1

    scored_rows: list[dict[str, Any]] = []
    for row in replay_examples:
        state_counts = counts_by_state.get(state_key(row))
        predicted_label = state_counts.most_common(1)[0][0] if state_counts else default_label
        scored_rows.append(
            {
                "split": row["split"],
                "ground_truth_label": row["ground_truth_label"],
                "predicted_label": predicted_label,
                "ground_truth_coarse_label": row.get("ground_truth_coarse_label"),
                "predicted_coarse_label": coarse_label_for_action(predicted_label),
                "observed_state_type": row.get("observed_state_type"),
                "observed_state_value": row.get("observed_state_value"),
            }
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
                "seed": seed,
                "split_strategy": split_strategy,
                "state_hint_mode": "state_prior",
                "split": split,
                "n": len(split_rows),
                "accuracy": fine["accuracy"],
                "macro_f1": fine["macro_f1"],
                "coarse_accuracy": coarse["accuracy"],
                "coarse_macro_f1": coarse["macro_f1"],
                "default_label": default_label,
                "router_min_probability": None,
            }
        )

    diagnostics = [
        {
            "seed": seed,
            "state_hint_mode": "state_prior",
            "split_strategy": split_strategy,
            "split": split,
            **summarize_rows([row for row in replay_examples if row["split"] == split]),
        }
        for split in ("train", "val", "test")
    ]
    diagnostics.append(
        {
            "seed": seed,
            "state_hint_mode": "state_prior",
            "split_strategy": split_strategy,
            "split": "all",
            "state_mapping_count": len(counts_by_state),
        }
    )
    return metrics, diagnostics


def evaluate_variant(
    *,
    replay_examples: list[dict[str, Any]],
    turns_by_id: dict[str, dict[str, Any]],
    messages_by_id: dict[str, dict[str, Any]],
    config: dict[str, Any],
    state_hint_mode: str,
    router_min_probability: float,
    neighbor_mode: str,
    seed: int,
    split_strategy: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    task = config["task"]
    eval_cfg = config["evaluation"]
    train_examples = [row for row in replay_examples if row["split"] == "train"]
    if not train_examples:
        raise ValueError(f"No training examples for seed={seed}")

    default_label = Counter(row["ground_truth_label"] for row in train_examples).most_common(1)[0][0]

    state_hint_model = None
    state_hint_min_confidence = 0.75
    if state_hint_mode == "learned":
        state_hint_model = TextHintRouter.fit_state_router(
            train_examples,
            turns_by_id,
            messages_by_id,
            min_probability=router_min_probability,
        )
        state_hint_min_confidence = router_min_probability
    elif state_hint_mode == "off":
        state_hint_min_confidence = 1.0

    store = ProfileStateStore(user_id="user_demo")
    seed_persona_facts_from_training_examples(store, train_examples, messages_by_id)

    rows_to_score = replay_examples
    prediction_records, divergence_records, _, _, scored_rows = evaluate_pass(
        replay_examples=rows_to_score,
        train_examples=train_examples,
        turns_by_id=turns_by_id,
        messages_by_id=messages_by_id,
        top_k=eval_cfg["top_k"],
        similarity_floor=eval_cfg["neighbor_similarity_floor"],
        default_label=default_label,
        similarity_threshold=task["topic_shift_similarity_threshold"],
        predictor_name=f"robustness_seed_{seed}_{state_hint_mode}",
        profile_store=None,
        state_hint_model=state_hint_model,
        create_refinements=False,
        run_id=f"run_replay_robustness_seed_{seed}_{state_hint_mode}",
        use_profile_hint=False,
        use_state_hint=state_hint_mode != "off",
        state_hint_min_confidence=state_hint_min_confidence,
        neighbor_mode=neighbor_mode,
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
                "seed": seed,
                "split_strategy": split_strategy,
                "state_hint_mode": state_hint_mode,
                "split": split,
                "n": len(split_rows),
                "accuracy": fine["accuracy"],
                "macro_f1": fine["macro_f1"],
                "coarse_accuracy": coarse["accuracy"],
                "coarse_macro_f1": coarse["macro_f1"],
                "default_label": default_label,
                "router_min_probability": router_min_probability if state_hint_mode == "learned" else None,
            }
        )

    diagnostics = [
        {
            "seed": seed,
            "state_hint_mode": state_hint_mode,
            "split_strategy": split_strategy,
            "split": split,
            **summarize_rows([row for row in replay_examples if row["split"] == split]),
        }
        for split in ("train", "val", "test")
    ]
    diagnostics.append(
        {
            "seed": seed,
            "state_hint_mode": state_hint_mode,
            "split_strategy": split_strategy,
            "split": "all",
            "prediction_count": len(prediction_records),
            "divergence_count": len(divergence_records),
        }
    )
    return metrics, diagnostics


def write_summary(metrics: list[dict[str, Any]], output_path: Path) -> None:
    test_rows = [row for row in metrics if row["split"] == "test"]
    modes = sorted({row["state_hint_mode"] for row in test_rows})
    lines = [
        "# Replay Robustness Summary",
        "",
        "Random group-level splits. Metrics below are test-set mean +/- std across seeds.",
        "",
        "| Mode | Accuracy | Macro-F1 | Coarse Accuracy | Coarse Macro-F1 | Seeds |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for mode in modes:
        rows = [row for row in test_rows if row["state_hint_mode"] == mode]
        if not rows:
            continue
        lines.append(
            "| {mode} | {acc:.4f} +/- {acc_std:.4f} | {f1:.4f} +/- {f1_std:.4f} | "
            "{cacc:.4f} +/- {cacc_std:.4f} | {cf1:.4f} +/- {cf1_std:.4f} | {n} |".format(
                mode=mode,
                acc=mean(row["accuracy"] for row in rows),
                acc_std=std(row["accuracy"] for row in rows),
                f1=mean(row["macro_f1"] for row in rows),
                f1_std=std(row["macro_f1"] for row in rows),
                cacc=mean(row["coarse_accuracy"] for row in rows),
                cacc_std=std(row["coarse_accuracy"] for row in rows),
                cf1=mean(row["coarse_macro_f1"] for row in rows),
                cf1_std=std(row["coarse_macro_f1"] for row in rows),
                n=len(rows),
            )
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def mean(values: Any) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


def std(values: Any) -> float:
    vals = list(values)
    if len(vals) < 2:
        return 0.0
    avg = mean(vals)
    return (sum((val - avg) ** 2 for val in vals) / (len(vals) - 1)) ** 0.5


def main() -> None:
    args = parse_args()
    config = load_config(Path(args.config))
    inputs = config["inputs"]
    output_dir = Path(args.output_dir)
    seeds = [int(item.strip()) for item in args.seeds.split(",") if item.strip()]

    replay_examples = read_jsonl(Path(inputs["replay_examples"]))
    turns = read_jsonl(Path(inputs["turns"]))
    messages = read_jsonl(Path(inputs["messages"]))
    turns_by_id = {turn["id"]: turn for turn in turns}
    messages_by_id = {message["id"]: message for message in messages}

    all_metrics: list[dict[str, Any]] = []
    all_diagnostics: list[dict[str, Any]] = []
    for seed in seeds:
        if args.split_strategy == "random_episode":
            split_examples = assign_random_episode_split(
                replay_examples,
                seed=seed,
                train_ratio=args.train_ratio,
                val_ratio=args.val_ratio,
            )
        else:
            split_examples = assign_random_conversation_split(
                replay_examples,
                seed=seed,
                train_ratio=args.train_ratio,
                val_ratio=args.val_ratio,
            )
        for mode in ("off", "heuristic", "learned"):
            metrics, diagnostics = evaluate_variant(
                replay_examples=split_examples,
                turns_by_id=turns_by_id,
                messages_by_id=messages_by_id,
                config=config,
                state_hint_mode=mode,
                router_min_probability=args.router_min_probability,
                neighbor_mode="lexical",
                seed=seed,
                split_strategy=args.split_strategy,
            )
            all_metrics.extend(metrics)
            all_diagnostics.extend(diagnostics)
        metrics, diagnostics = evaluate_variant(
            replay_examples=split_examples,
            turns_by_id=turns_by_id,
            messages_by_id=messages_by_id,
            config=config,
            state_hint_mode="off",
            router_min_probability=args.router_min_probability,
            neighbor_mode="semantic",
            seed=seed,
            split_strategy=args.split_strategy,
        )
        for metric in metrics:
            metric["state_hint_mode"] = "semantic"
        for diagnostic in diagnostics:
            diagnostic["state_hint_mode"] = "semantic"
        all_metrics.extend(metrics)
        all_diagnostics.extend(diagnostics)
        metrics, diagnostics = evaluate_state_prior_variant(
            replay_examples=split_examples,
            seed=seed,
            split_strategy=args.split_strategy,
        )
        all_metrics.extend(metrics)
        all_diagnostics.extend(diagnostics)

    write_jsonl(output_dir / "metrics.jsonl", all_metrics)
    write_jsonl(output_dir / "diagnostics.jsonl", all_diagnostics)
    write_summary(all_metrics, output_dir / "summary.md")

    test_metrics = [row for row in all_metrics if row["split"] == "test"]
    print(json.dumps({"test_metrics": test_metrics}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
