from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from portraiture.evaluation.relabel_candidates import export_relabel_candidates
from portraiture.evaluation.report import compare_runs, compute_persona_fact_summary, render_markdown
from portraiture.evaluation.replay import compute_classification_metrics, evaluate_pass, seed_persona_facts_from_training_examples
from portraiture.ingest.chatgpt_export import discover_json_files, ingest_file
from portraiture.replay.builder import assign_split_by_time, build_examples
from portraiture.schemas import MetricRecord
from portraiture.segmentation.baseline import segment_conversation
from portraiture.state import ProfileStateStore
from portraiture.utils.config import load_config
from portraiture.utils.io import read_jsonl, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full portraiture pipeline end to end.")
    parser.add_argument(
        "--project-root",
        default=None,
        help="Project root used to resolve relative config and data paths.",
    )
    parser.add_argument(
        "--input-root",
        default=None,
        help="Override the ingest input root (e.g. a ChatGPT export directory).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on how many conversations to process at each stage.",
    )
    parser.add_argument(
        "--ingest-config",
        default="configs/data/chatgpt_export_v1.yaml",
        help="Path to the ingest config YAML.",
    )
    parser.add_argument(
        "--segmentation-config",
        default="configs/segmentation/baseline_v1.yaml",
        help="Path to the segmentation config YAML.",
    )
    parser.add_argument(
        "--replay-config",
        default="configs/replay/baseline_v1.yaml",
        help="Path to the replay builder config YAML.",
    )
    parser.add_argument(
        "--evaluation-config",
        default="configs/evaluation/replay_baseline_v1.yaml",
        help="Path to the replay evaluation config YAML.",
    )
    parser.add_argument(
        "--stage",
        choices=("all", "ingest", "segment", "replay", "evaluate"),
        default="all",
        help="Run only one stage or the full pipeline.",
    )
    return parser.parse_args()


def project_root_from_args(args: argparse.Namespace) -> Path:
    if args.project_root:
        return Path(args.project_root).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def resolve_path(project_root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (project_root / path).resolve()


def resolve_outputs(project_root: Path, outputs: dict[str, Any]) -> dict[str, Path]:
    resolved: dict[str, Path] = {}
    for key, value in outputs.items():
        resolved[key] = resolve_path(project_root, value)
    return resolved


def metric_record(
    *,
    metric_id: str,
    run_id: str,
    metric_group: str,
    metric_name: str,
    metric_value: float,
    split: str,
    config_ref: str,
    notes: str,
) -> dict[str, Any]:
    return asdict(
        MetricRecord(
            id=metric_id,
            user_id="user_demo",
            created_at="",
            updated_at="",
            run_id=run_id,
            metric_group=metric_group,
            metric_name=metric_name,
            metric_value=metric_value,
            split=split,
            config_ref=config_ref,
            notes=notes,
        )
    )


def run_ingest(project_root: Path, input_root_override: str | None, config_path: str, limit: int | None) -> dict[str, int]:
    config = load_config(resolve_path(project_root, config_path))
    input_root = resolve_path(project_root, input_root_override or config["input_root"])
    outputs = resolve_outputs(project_root, config["outputs"])
    normalize_roles = config.get("message_extraction", {}).get("normalize_roles", {})

    files = discover_json_files(input_root, limit=limit)

    imported_source_rows: list[dict[str, Any]] = []
    conversation_rows: list[dict[str, Any]] = []
    message_rows: list[dict[str, Any]] = []

    for path in files:
        source_record, conversation_record, messages = ingest_file(path, input_root, normalize_roles)
        imported_source_rows.append(asdict(source_record))
        conversation_rows.append(asdict(conversation_record))
        message_rows.extend(asdict(message) for message in messages)

    write_jsonl(outputs["imported_source_manifest"], imported_source_rows)
    write_jsonl(outputs["conversations"], conversation_rows)
    write_jsonl(outputs["messages"], message_rows)

    print(f"[ingest] files={len(files)} conversations={len(conversation_rows)} messages={len(message_rows)}")
    return {
        "files": len(files),
        "conversations": len(conversation_rows),
        "messages": len(message_rows),
    }


def run_segmentation(project_root: Path, config_path: str, limit: int | None) -> dict[str, int]:
    config = load_config(resolve_path(project_root, config_path))
    inputs = resolve_outputs(project_root, config["inputs"])
    outputs = resolve_outputs(project_root, config["outputs"])

    conversations = read_jsonl(inputs["conversations"])
    messages = read_jsonl(inputs["messages"])
    if limit is not None:
        conversations = conversations[:limit]
        allowed_conversation_ids = {conversation["id"] for conversation in conversations}
        messages = [message for message in messages if message["conversation_id"] in allowed_conversation_ids]

    messages_by_conversation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for message in messages:
        messages_by_conversation[message["conversation_id"]].append(message)

    sessions: list[dict[str, Any]] = []
    episodes: list[dict[str, Any]] = []
    turns: list[dict[str, Any]] = []

    for conversation in conversations:
        conversation_messages = sorted(
            messages_by_conversation.get(conversation["id"], []),
            key=lambda message: message["sequence_index"],
        )
        session_records, episode_records, turn_records = segment_conversation(
            conversation=conversation,
            messages=conversation_messages,
            config=config,
        )
        sessions.extend(asdict(record) for record in session_records)
        episodes.extend(asdict(record) for record in episode_records)
        turns.extend(asdict(record) for record in turn_records)

    write_jsonl(outputs["sessions"], sessions)
    write_jsonl(outputs["episodes"], episodes)
    write_jsonl(outputs["turns"], turns)

    print(f"[segment] conversations={len(conversations)} sessions={len(sessions)} episodes={len(episodes)} turns={len(turns)}")
    return {
        "conversations": len(conversations),
        "sessions": len(sessions),
        "episodes": len(episodes),
        "turns": len(turns),
    }


def run_replay(project_root: Path, config_path: str, limit: int | None) -> dict[str, int]:
    config = load_config(resolve_path(project_root, config_path))
    inputs = resolve_outputs(project_root, config["inputs"])
    outputs = resolve_outputs(project_root, config["outputs"])
    task = config["task"]
    split_cfg = config["split"]

    episodes = read_jsonl(inputs["episodes"])
    turns = read_jsonl(inputs["turns"])
    messages = read_jsonl(inputs["messages"])

    if limit is not None:
        episodes = episodes[:limit]
        allowed_episode_ids = {episode["id"] for episode in episodes}
        turns = [turn for turn in turns if turn["episode_id"] in allowed_episode_ids]

    turns_by_id = {turn["id"]: turn for turn in turns}
    messages_by_id = {message["id"]: message for message in messages}

    examples = build_examples(
        episodes=episodes,
        turns_by_id=turns_by_id,
        messages_by_id=messages_by_id,
        max_context_turns=task["max_context_turns"],
        min_context_turns=task["min_context_turns"],
        similarity_threshold=task["topic_shift_similarity_threshold"],
    )
    assign_split_by_time(examples, split_cfg)

    label_counts = Counter(example["ground_truth_label"] for example in examples)
    write_jsonl(outputs["replay_examples"], examples)
    write_jsonl(
        outputs["label_distribution"],
        [{"label": label, "count": count} for label, count in sorted(label_counts.items())],
    )

    print(f"[replay] episodes={len(episodes)} examples={len(examples)} labels={dict(label_counts)}")
    return {
        "episodes": len(episodes),
        "examples": len(examples),
    }


def run_evaluation(project_root: Path, config_path: str) -> dict[str, float]:
    config = load_config(resolve_path(project_root, config_path))
    inputs = resolve_outputs(project_root, config["inputs"])
    outputs = resolve_outputs(project_root, config["outputs"])
    task = config["task"]
    eval_cfg = config["evaluation"]

    replay_examples = read_jsonl(inputs["replay_examples"])
    turns = read_jsonl(inputs["turns"])
    messages = read_jsonl(inputs["messages"])

    turns_by_id = {turn["id"]: turn for turn in turns}
    messages_by_id = {message["id"]: message for message in messages}

    train_examples = [example for example in replay_examples if example["split"] == "train"]
    if not train_examples:
        raise ValueError("No training replay examples found.")

    default_label = Counter(example["ground_truth_label"] for example in train_examples).most_common(1)[0][0]
    baseline_store = ProfileStateStore(user_id="user_demo")
    seed_persona_facts_from_training_examples(baseline_store, train_examples, messages_by_id)

    baseline_prediction_records, baseline_divergence_records, refinement_records, baseline_profile_snapshots, baseline_rows = evaluate_pass(
        replay_examples=replay_examples,
        train_examples=train_examples,
        turns_by_id=turns_by_id,
        messages_by_id=messages_by_id,
        top_k=eval_cfg["top_k"],
        similarity_floor=eval_cfg["neighbor_similarity_floor"],
        default_label=default_label,
        similarity_threshold=task["topic_shift_similarity_threshold"],
        predictor_name=f"{eval_cfg['predictor_name']}_baseline",
        profile_store=baseline_store,
        create_refinements=True,
        run_id=eval_cfg["run_id"],
        use_profile_hint=False,
        use_state_hint=False,
        emit_snapshots=True,
    )

    state_aware_prediction_records, state_aware_divergence_records, _, _, state_aware_rows = evaluate_pass(
        replay_examples=replay_examples,
        train_examples=train_examples,
        turns_by_id=turns_by_id,
        messages_by_id=messages_by_id,
        top_k=eval_cfg["top_k"],
        similarity_floor=eval_cfg["neighbor_similarity_floor"],
        default_label=default_label,
        similarity_threshold=task["topic_shift_similarity_threshold"],
        predictor_name=f"{eval_cfg['predictor_name']}_state_aware",
        profile_store=None,
        create_refinements=False,
        run_id=eval_cfg["run_id"],
        use_profile_hint=False,
        use_state_hint=True,
        emit_snapshots=False,
    )

    refined_prediction_records, refined_divergence_records, _, refined_profile_snapshots, refined_rows = evaluate_pass(
        replay_examples=replay_examples,
        train_examples=train_examples,
        turns_by_id=turns_by_id,
        messages_by_id=messages_by_id,
        top_k=eval_cfg["top_k"],
        similarity_floor=eval_cfg["neighbor_similarity_floor"],
        default_label=default_label,
        similarity_threshold=task["topic_shift_similarity_threshold"],
        predictor_name=f"{eval_cfg['predictor_name']}_refined",
        profile_store=baseline_store,
        create_refinements=False,
        run_id=eval_cfg["run_id"],
        use_profile_hint=True,
        use_state_hint=False,
        emit_snapshots=True,
    )

    metric_records: list[dict[str, Any]] = []
    config_ref = str(resolve_path(project_root, config_path))
    for prefix, rows in (("baseline", baseline_rows), ("state_aware", state_aware_rows), ("refined", refined_rows)):
        for split in ("train", "val", "test"):
            split_rows = [row for row in rows if row["split"] == split]
            metrics = compute_classification_metrics(split_rows)
            coarse_metrics = compute_classification_metrics(
                split_rows,
                ground_truth_key="ground_truth_coarse_label",
                predicted_key="predicted_coarse_label",
            )
            for metric_name, metric_value in metrics.items():
                metric_records.append(
                    metric_record(
                        metric_id=f"metric_{prefix}_{split}_{metric_name}",
                        run_id=eval_cfg["run_id"],
                        metric_group="replay",
                        metric_name=metric_name,
                        metric_value=metric_value,
                        split=f"{prefix}:{split}",
                        config_ref=config_ref,
                        notes=f"baseline_label={default_label}; predictor={eval_cfg['predictor_name']}; pass={prefix}",
                    )
                )
            for metric_name, metric_value in coarse_metrics.items():
                metric_records.append(
                    metric_record(
                        metric_id=f"metric_{prefix}_{split}_coarse_{metric_name}",
                        run_id=eval_cfg["run_id"],
                        metric_group="replay_coarse",
                        metric_name=metric_name,
                        metric_value=metric_value,
                        split=f"{prefix}:{split}",
                        config_ref=config_ref,
                        notes=f"baseline_label={default_label}; predictor={eval_cfg['predictor_name']}; pass={prefix}; coarse_labels=true",
                    )
                )

    metric_records.append(
        metric_record(
            metric_id="metric_run_refinement_action_count",
            run_id=eval_cfg["run_id"],
            metric_group="refinement",
            metric_name="refinement_action_count",
            metric_value=float(len(refinement_records)),
            split="run",
            config_ref=config_ref,
            notes=f"applied_actions={len(refinement_records)}",
        )
    )
    metric_records.append(
        metric_record(
            metric_id="metric_run_dynamic_state_count",
            run_id=eval_cfg["run_id"],
            metric_group="refinement",
            metric_name="dynamic_state_count",
            metric_value=float(len(baseline_store.dynamic_states)),
            split="run",
            config_ref=config_ref,
            notes="materialized dynamic states after baseline refinement pass",
        )
    )

    write_jsonl(outputs["predictions_baseline"], baseline_prediction_records)
    write_jsonl(outputs["predictions_state_aware"], state_aware_prediction_records)
    write_jsonl(outputs["predictions_refined"], refined_prediction_records)
    write_jsonl(outputs["divergences_baseline"], baseline_divergence_records)
    write_jsonl(outputs["divergences_state_aware"], state_aware_divergence_records)
    write_jsonl(outputs["divergences_refined"], refined_divergence_records)
    write_jsonl(outputs["refinements"], refinement_records)
    write_jsonl(outputs["profile_snapshots_baseline"], baseline_profile_snapshots)
    write_jsonl(outputs["profile_snapshots_refined"], refined_profile_snapshots)
    export_records = baseline_store.export_records()
    write_jsonl(outputs["persona_facts"], export_records["persona_facts"])
    write_jsonl(outputs["dynamic_states"], export_records["dynamic_states"])
    write_jsonl(outputs["memory_nodes"], export_records["memory_nodes"])
    write_jsonl(outputs["metrics"], metric_records)

    summary = compare_runs(baseline_divergence_records, state_aware_divergence_records, refined_divergence_records)
    summary["persona_facts"] = compute_persona_fact_summary(export_records["persona_facts"])

    evaluation_dir = outputs["metrics"].parent
    analysis_json = evaluation_dir / "analysis_summary.json"
    analysis_md = evaluation_dir / "analysis_summary.md"
    analysis_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    analysis_md.write_text(render_markdown(summary), encoding="utf-8")

    relabel_divergence_rows: list[dict[str, Any]] = []
    for source_label, rows in (
        ("baseline", baseline_divergence_records),
        ("state_aware", state_aware_divergence_records),
        ("refined", refined_divergence_records),
    ):
        source_file = outputs[f"divergences_{source_label}"]
        for row in rows:
            annotated_row = dict(row)
            annotated_row["_source_file"] = str(source_file)
            relabel_divergence_rows.append(annotated_row)

    relabel_jsonl = evaluation_dir / "relabel_candidates.jsonl"
    relabel_md = evaluation_dir / "relabel_candidates.md"
    relabel_selected = export_relabel_candidates(
        relabel_divergence_rows,
        replay_examples,
        turns_by_id,
        messages_by_id,
        output_jsonl=relabel_jsonl,
        output_md=relabel_md,
        max_candidates=40,
        divergence_files=[str(outputs["divergences_baseline"]), str(outputs["divergences_state_aware"]), str(outputs["divergences_refined"])],
    )

    baseline_accuracy = summary["baseline"]["accuracy"]
    state_aware_accuracy = summary["state_aware"]["accuracy"]
    refined_accuracy = summary["refined"]["accuracy"]
    print(
        "[evaluate] examples={examples} baseline={baseline:.4f} state_aware={state_aware:.4f} refined={refined:.4f}".format(
            examples=len(replay_examples),
            baseline=baseline_accuracy,
            state_aware=state_aware_accuracy,
            refined=refined_accuracy,
        )
    )
    print(f"[evaluate] wrote {analysis_json}")
    print(f"[evaluate] wrote {analysis_md}")
    print(f"[evaluate] wrote {relabel_jsonl}")
    print(f"[evaluate] wrote {relabel_md}")
    print(f"[evaluate] exported {len(relabel_selected)} relabel candidates")
    return {
        "baseline_accuracy": baseline_accuracy,
        "state_aware_accuracy": state_aware_accuracy,
        "refined_accuracy": refined_accuracy,
    }


def main() -> None:
    args = parse_args()
    project_root = project_root_from_args(args)

    if args.stage in {"all", "ingest"}:
        run_ingest(project_root, args.input_root, args.ingest_config, args.limit)
    if args.stage in {"all", "segment"}:
        run_segmentation(project_root, args.segmentation_config, args.limit)
    if args.stage in {"all", "replay"}:
        run_replay(project_root, args.replay_config, args.limit)
    if args.stage in {"all", "evaluate"}:
        run_evaluation(project_root, args.evaluation_config)


if __name__ == "__main__":
    main()
