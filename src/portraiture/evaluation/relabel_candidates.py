from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from portraiture.utils.io import read_jsonl, write_jsonl


SOURCE_PRIORITY = {
    "baseline": 0,
    "state_aware": 1,
    "refined": 2,
    "unknown": 3,
    "replay_only": 4,
}

TYPE_PRIORITY = {
    "state_under_specified": 0,
    "action_selection_error": 1,
    "reasoning_mismatch": 2,
    "persona_misalignment": 3,
    "memory_failure": 4,
    "surface_only_match": 5,
    "agreement_review": 99,
}

SUBTYPE_PRIORITY = {
    "state_under_specified": {
        "goal_shift_missed": 0,
        "blocking_issue_missed": 1,
        "time_pressure_missed": 2,
        "stance_change_missed": 3,
    },
    "action_selection_error": {
        "candidate_set_missing": 0,
        "ranking_error": 1,
        "task_label_too_coarse": 2,
        "wrong_turn_boundary": 3,
    },
    "reasoning_mismatch": {
        "wrong_priority_order": 0,
        "wrong_tradeoff_focus": 1,
        "wrong_intent_inference": 2,
        "wrong_conclusion_style": 3,
    },
    "persona_misalignment": {
        "unsupported_persona_fact": 0,
        "trait_overgeneralized": 1,
        "short_term_behavior_overfit": 2,
        "persona_conflict_unresolved": 3,
    },
    "memory_failure": {
        "missing_explicit_fact": 0,
        "wrong_event_order": 1,
        "stale_memory_selected": 2,
        "memory_conflict_unresolved": 3,
    },
}

BUCKET_QUOTAS = {
    "state_under_specified": 14,
    "action_selection_error": 12,
    "reasoning_mismatch": 8,
    "persona_misalignment": 4,
    "memory_failure": 2,
}

AGREEMENT_FOCUS_VARIANTS = (
    "Check whether the label assignment is consistent with the nearby examples and whether any coarse-label tightening is needed.",
    "Check whether the current state hint and the label agree, or whether the state cue is over-interpreted.",
    "Check whether the example belongs to the same coarse action bucket as similar contexts.",
    "Check whether the turn boundary is still the right place to make the label decision.",
    "Check whether the episode is stable enough for a clean manual relabel, or whether it needs more context.",
)

DIVERGENCE_FOCUS_VARIANTS = {
    "state_under_specified": (
        "Check whether the episode boundary should move earlier/later or whether the target should be relabeled as follow_up_clarification instead of topic_shift.",
        "Check whether the current goal or blocker is explicit enough to justify a state label.",
        "Check whether the label depends on a missing surrounding turn rather than the target utterance itself.",
    ),
    "action_selection_error": (
        "Check whether the action label space is too coarse for this sample.",
        "Check whether the target belongs in a neighboring action bucket instead of the current one.",
        "Check whether this is a turn-boundary problem rather than a label problem.",
    ),
    "reasoning_mismatch": (
        "Check whether the label is capturing intent or only surface form.",
        "Check whether the example is a tradeoff / challenge move rather than a request for definition.",
        "Check whether the coarse action bucket is masking a finer intent distinction.",
    ),
    "persona_misalignment": (
        "Check whether the prompt expresses a stable preference, a short-term behavior, or an unsupported persona fact.",
        "Check whether this is a long-term persona signal or just a one-off episode detail.",
        "Check whether the evidence window is enough to support a stable preference fact.",
    ),
    "memory_failure": (
        "Check whether the sample needs a memory node, a better event ordering, or a stronger evidence link.",
        "Check whether the example refers to a past fact that should be attached to memory instead of persona.",
        "Check whether the target depends on a missing historical event description.",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export high-value replay samples for manual relabeling.")
    parser.add_argument(
        "--divergence-files",
        nargs="*",
        default=[
            "data/processed/evaluation/divergences_baseline.jsonl",
            "data/processed/evaluation/divergences_state_aware.jsonl",
            "data/processed/evaluation/divergences_refined.jsonl",
        ],
        help="Divergence records to combine when constructing review candidates.",
    )
    parser.add_argument(
        "--replay-examples",
        default="data/processed/replay/replay_examples.jsonl",
        help="Replay examples with labels and state hints.",
    )
    parser.add_argument(
        "--output-jsonl",
        default="data/processed/evaluation/relabel_candidates.jsonl",
        help="Where to write the review candidates.",
    )
    parser.add_argument(
        "--output-md",
        default="data/processed/evaluation/relabel_candidates.md",
        help="Where to write the review summary.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=40,
        help="Maximum number of samples to export.",
    )
    return parser.parse_args()


def _source_label_from_path(path: str | Path | None) -> str:
    if path is None:
        return "unknown"
    name = Path(path).stem.lower()
    if "baseline" in name:
        return "baseline"
    if "state" in name:
        return "state_aware"
    if "refined" in name:
        return "refined"
    return "unknown"


def _pick_review_focus(divergence_type: str | None, divergence_subtype: str | None) -> str:
    if divergence_type in DIVERGENCE_FOCUS_VARIANTS and divergence_type is not None:
        variants = DIVERGENCE_FOCUS_VARIANTS[divergence_type]
        if divergence_subtype and divergence_type == "state_under_specified":
            if divergence_subtype == "goal_shift_missed":
                return variants[0]
            if divergence_subtype == "blocking_issue_missed":
                return variants[1]
            return variants[2]
        if divergence_subtype and divergence_type == "action_selection_error":
            if divergence_subtype == "ranking_error":
                return variants[0]
            if divergence_subtype == "candidate_set_missing":
                return variants[1]
            return variants[2]
        if divergence_subtype and divergence_type == "reasoning_mismatch":
            if divergence_subtype == "wrong_intent_inference":
                return variants[0]
            if divergence_subtype == "wrong_priority_order":
                return variants[1]
            return variants[2]
        if divergence_subtype and divergence_type == "persona_misalignment":
            if divergence_subtype == "unsupported_persona_fact":
                return variants[0]
            if divergence_subtype == "trait_overgeneralized":
                return variants[1]
            return variants[2]
        if divergence_subtype and divergence_type == "memory_failure":
            if divergence_subtype == "missing_explicit_fact":
                return variants[0]
            if divergence_subtype == "wrong_event_order":
                return variants[1]
            return variants[2]
        return variants[0]
    if divergence_type == "state_under_specified":
        return "Review the current goal / state boundary."
    if divergence_type == "action_selection_error":
        return "Check whether the action label space is too coarse for this sample."
    if divergence_type == "reasoning_mismatch":
        return "Check whether the label is capturing intent or only surface form."
    if divergence_type == "persona_misalignment":
        return "Check whether the prompt expresses a stable preference, a short-term behavior, or an unsupported persona fact."
    if divergence_type == "memory_failure":
        return "Check whether the sample needs a memory node, a better event ordering, or a stronger evidence link."
    return "Review the label and the surrounding episode boundary."


def _agreement_review_focus(example: dict[str, Any], variant_index: int) -> str:
    state_type = example.get("observed_state_type") or example.get("metadata", {}).get("state_hint_type")
    if state_type == "blocking_issue":
        return "Check whether this should be treated as a blocker or a routine help request."
    if state_type == "active_problem":
        return AGREEMENT_FOCUS_VARIANTS[variant_index % len(AGREEMENT_FOCUS_VARIANTS)]
    return AGREEMENT_FOCUS_VARIANTS[(variant_index + 2) % len(AGREEMENT_FOCUS_VARIANTS)]


def _normalize_text(text: str | None) -> str:
    return " ".join((text or "").split())


def _context_user_texts(example: dict[str, Any], turns_by_id: dict[str, dict[str, Any]], messages_by_id: dict[str, dict[str, Any]], *, max_items: int = 3) -> list[str]:
    context_turn_ids = list(example.get("context_turn_ids") or [])[-max_items:]
    texts: list[str] = []
    for turn_id in context_turn_ids:
        turn = turns_by_id.get(turn_id)
        if not turn:
            continue
        user_message_id = turn.get("user_message_id")
        if not user_message_id:
            continue
        text = _normalize_text(messages_by_id.get(user_message_id, {}).get("content_text"))
        if text:
            texts.append(text)
    return texts


def _rank_key(item: dict[str, Any]) -> tuple[int, int, int, int, float, str]:
    divergence_type = item.get("divergence_type") or "agreement_review"
    divergence_subtype = item.get("divergence_subtype") or ""
    split = item.get("split") or "train"
    split_priority = {"test": 0, "val": 1, "train": 2}.get(split, 3)
    source_priority = SOURCE_PRIORITY.get(item.get("source_label") or "unknown", 3)
    type_priority = TYPE_PRIORITY.get(divergence_type, 99)
    subtype_priority = SUBTYPE_PRIORITY.get(divergence_type, {}).get(divergence_subtype, 99)
    severity = float(item.get("severity") or 0.0)
    return (source_priority, split_priority, type_priority, subtype_priority, -severity, item.get("candidate_id") or item.get("replay_example_id") or "")


def _build_divergence_candidate(
    row: dict[str, Any],
    replay: dict[str, Any],
    *,
    source_label: str,
    turns_by_id: dict[str, dict[str, Any]],
    messages_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    metadata = replay.get("metadata", {})
    context_user_texts = _context_user_texts(replay, turns_by_id, messages_by_id)
    divergence_type = row.get("divergence_type") or "unknown"
    divergence_subtype = row.get("divergence_subtype") or "none"
    return {
        "candidate_id": f"{source_label}:{replay.get('id')}:{divergence_type}:{divergence_subtype}",
        "replay_example_id": row.get("replay_example_id"),
        "episode_id": replay.get("episode_id"),
        "conversation_id": metadata.get("conversation_id"),
        "session_id": metadata.get("session_id"),
        "split": replay.get("split"),
        "source_label": source_label,
        "divergence_type": row.get("divergence_type"),
        "divergence_subtype": row.get("divergence_subtype"),
        "severity": row.get("severity"),
        "ground_truth_label": row.get("ground_truth_label"),
        "predicted_label": row.get("predicted_label"),
        "ground_truth_coarse_label": row.get("ground_truth_coarse_label"),
        "predicted_coarse_label": row.get("predicted_coarse_label"),
        "observed_state_type": row.get("observed_state_type"),
        "observed_state_value": row.get("observed_state_value"),
        "observed_state_confidence": row.get("observed_state_confidence"),
        "target_user_text": metadata.get("target_user_text"),
        "previous_user_text": metadata.get("previous_user_text"),
        "context_user_texts": context_user_texts,
        "context_turn_ids": list(replay.get("context_turn_ids") or []),
        "state_hint_type": metadata.get("state_hint_type"),
        "state_hint_value": metadata.get("state_hint_value"),
        "state_hint_confidence": metadata.get("state_hint_confidence"),
        "state_hint_reason": metadata.get("state_hint_reason"),
        "review_bucket": divergence_type,
        "review_focus": _pick_review_focus(row.get("divergence_type"), row.get("divergence_subtype")),
    }


def _build_agreement_candidates(replay: dict[str, Any], source_label: str = "replay_only") -> list[dict[str, Any]]:
    metadata = replay.get("metadata", {})
    base = {
        "replay_example_id": replay.get("id"),
        "episode_id": replay.get("episode_id"),
        "conversation_id": metadata.get("conversation_id"),
        "session_id": metadata.get("session_id"),
        "split": replay.get("split"),
        "source_label": source_label,
        "divergence_type": "agreement_review",
        "divergence_subtype": None,
        "severity": 0.0,
        "ground_truth_label": replay.get("ground_truth_label"),
        "predicted_label": replay.get("ground_truth_label"),
        "ground_truth_coarse_label": replay.get("ground_truth_coarse_label"),
        "predicted_coarse_label": replay.get("ground_truth_coarse_label"),
        "observed_state_type": replay.get("observed_state_type"),
        "observed_state_value": replay.get("observed_state_value"),
        "observed_state_confidence": replay.get("observed_state_confidence"),
        "target_user_text": metadata.get("target_user_text"),
        "previous_user_text": metadata.get("previous_user_text"),
        "context_user_texts": [],
        "context_turn_ids": list(replay.get("context_turn_ids") or []),
        "state_hint_type": metadata.get("state_hint_type"),
        "state_hint_value": metadata.get("state_hint_value"),
        "state_hint_confidence": metadata.get("state_hint_confidence"),
        "state_hint_reason": metadata.get("state_hint_reason"),
        "review_bucket": "agreement_review",
    }
    return [
        {
            **base,
            "candidate_id": f"{source_label}:{replay.get('id')}:agreement_label",
            "review_focus": "Check whether the label assignment is consistent with the nearby examples and whether any coarse-label tightening is needed.",
        },
        {
            **base,
            "candidate_id": f"{source_label}:{replay.get('id')}:agreement_state",
            "review_focus": _agreement_review_focus(replay, 1),
        },
        {
            **base,
            "candidate_id": f"{source_label}:{replay.get('id')}:agreement_boundary",
            "review_focus": _agreement_review_focus(replay, 2),
        },
        {
            **base,
            "candidate_id": f"{source_label}:{replay.get('id')}:agreement_coarse",
            "review_focus": "Check whether the coarse label should be moved to a neighboring bucket even if the fine label stays plausible.",
        },
        {
            **base,
            "candidate_id": f"{source_label}:{replay.get('id')}:agreement_evidence",
            "review_focus": "Check whether the evidence window is sufficient, or whether the current label depends on missing surrounding turns.",
        },
    ]


def build_relabel_candidates(
    divergence_rows: list[dict[str, Any]],
    replay_examples: list[dict[str, Any]],
    turns_by_id: dict[str, dict[str, Any]],
    messages_by_id: dict[str, dict[str, Any]],
    *,
    max_candidates: int = 40,
) -> list[dict[str, Any]]:
    replay_by_id = {row["id"]: row for row in replay_examples}
    selected: dict[str, dict[str, Any]] = {}

    normalized_rows: list[dict[str, Any]] = []
    for row in divergence_rows:
        divergence_type = row.get("divergence_type")
        if not divergence_type or divergence_type == "surface_only_match":
            continue
        replay_id = row.get("replay_example_id")
        if not replay_id:
            continue
        replay = replay_by_id.get(replay_id)
        if not replay:
            continue
        normalized_rows.append(
            _build_divergence_candidate(
                row,
                replay,
                source_label=_source_label_from_path(row.get("_source_file")),
                turns_by_id=turns_by_id,
                messages_by_id=messages_by_id,
            )
        )

    agreement_rows: list[dict[str, Any]] = []
    for replay in replay_examples:
        if replay.get("ground_truth_label"):
            agreement_rows.extend(_build_agreement_candidates(replay, source_label="replay_only"))

    pool = normalized_rows + agreement_rows
    bucketed: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in BUCKET_QUOTAS}
    agreement_review: list[dict[str, Any]] = []
    overflow: list[dict[str, Any]] = []
    for candidate in pool:
        bucket = candidate.get("review_bucket") or ""
        if bucket in bucketed:
            bucketed[bucket].append(candidate)
        elif bucket == "agreement_review":
            agreement_review.append(candidate)
        else:
            overflow.append(candidate)

    for bucket, items in bucketed.items():
        items.sort(key=_rank_key)
        for candidate in items[: BUCKET_QUOTAS[bucket]]:
            selected[candidate["candidate_id"]] = candidate

    remaining_pool = sorted(pool + overflow + agreement_review, key=_rank_key)
    for candidate in remaining_pool:
        if len(selected) >= max_candidates:
            break
        selected.setdefault(candidate["candidate_id"], candidate)

    return sorted(selected.values(), key=_rank_key)[:max_candidates]



def _build_summary_lines(selected: list[dict[str, Any]], divergence_rows: list[dict[str, Any]], divergence_files: list[str]) -> str:
    lines: list[str] = []
    lines.append("# Relabel Candidates")
    lines.append("")
    lines.append("This file collects the highest-value samples for manual review.")
    lines.append("")
    lines.append(f"- Total candidates exported: {len(selected)}")
    lines.append(f"- Source divergence files: {', '.join(divergence_files)}")
    lines.append(f"- Total divergence rows scanned: {len(divergence_rows)}")
    lines.append("")

    bucket_counts = Counter(item.get("review_bucket") or "unknown" for item in selected)
    lines.append("## Bucket Counts")
    lines.append("")
    lines.append("| Bucket | Count |")
    lines.append("|---|---:|")
    for bucket, count in sorted(bucket_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {bucket} | {count} |")
    lines.append("")

    subtype_counts = Counter((item.get("review_bucket") or "unknown", item.get("divergence_subtype") or "") for item in selected)
    lines.append("## Subtype Counts")
    lines.append("")
    lines.append("| Bucket | Subtype | Count |")
    lines.append("|---|---|---:|")
    for (bucket, subtype), count in sorted(subtype_counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1])):
        lines.append(f"| {bucket} | {subtype} | {count} |")
    lines.append("")

    lines.append("## Review Priorities")
    lines.append("")
    lines.append("- `state_under_specified`: check whether the current goal, blocker, or topic shift was missed.")
    lines.append("- `action_selection_error`: check whether the label space is too coarse or the turn boundary is wrong.")
    lines.append("- `reasoning_mismatch`: check whether the sample captures intent or only surface form.")
    lines.append("- `persona_misalignment`: check whether this is a stable preference, a short-term behavior, or an unsupported persona fact.")
    lines.append("")

    lines.append("## Top Samples")
    lines.append("")
    for idx, item in enumerate(selected[:20], start=1):
        lines.append(f"### {idx}. {item['candidate_id']}")
        lines.append("")
        lines.append(f"- source: `{item.get('source_label')}`")
        lines.append(f"- divergence: `{item['divergence_type']}` / `{item['divergence_subtype']}`")
        lines.append(f"- gt: `{item['ground_truth_label']}`")
        lines.append(f"- pred: `{item['predicted_label']}`")
        lines.append(f"- state: `{item['observed_state_type']}` / `{item['observed_state_value']}`")
        lines.append(f"- focus: {item['review_focus']}")
        if item.get("context_user_texts"):
            lines.append("- context:")
            for text in item["context_user_texts"]:
                lines.append(f"  - {text}")
        if item.get("target_user_text"):
            lines.append(f"- target: {item['target_user_text']}")
        lines.append("")

    return "\n".join(lines)


def export_relabel_candidates(
    divergence_rows: list[dict[str, Any]],
    replay_examples: list[dict[str, Any]],
    turns_by_id: dict[str, dict[str, Any]],
    messages_by_id: dict[str, dict[str, Any]],
    *,
    output_jsonl: Path,
    output_md: Path,
    max_candidates: int = 40,
    divergence_files: list[str] | None = None,
) -> list[dict[str, Any]]:
    selected = build_relabel_candidates(
        divergence_rows,
        replay_examples,
        turns_by_id,
        messages_by_id,
        max_candidates=max_candidates,
    )
    write_jsonl(output_jsonl, selected)
    summary = _build_summary_lines(selected, divergence_rows, divergence_files or [])
    output_md.write_text(summary, encoding="utf-8")
    return selected


def main() -> None:
    args = parse_args()
    divergence_rows: list[dict[str, Any]] = []
    for file_path in args.divergence_files:
        path = Path(file_path)
        rows = read_jsonl(path)
        for row in rows:
            row["_source_file"] = str(path)
        divergence_rows.extend(rows)

    replay_examples = read_jsonl(Path(args.replay_examples))
    turns_by_id = {turn["id"]: turn for turn in read_jsonl(Path("data/interim/segmented/turns.jsonl"))}
    messages_by_id = {message["id"]: message for message in read_jsonl(Path("data/interim/normalized/messages.jsonl"))}

    selected = export_relabel_candidates(
        divergence_rows,
        replay_examples,
        turns_by_id,
        messages_by_id,
        output_jsonl=Path(args.output_jsonl),
        output_md=Path(args.output_md),
        max_candidates=args.max_candidates,
        divergence_files=[str(Path(path)) for path in args.divergence_files],
    )
    print(f"Wrote {args.output_jsonl}")
    print(f"Wrote {args.output_md}")
    print(f"Exported {len(selected)} relabel candidates")


if __name__ == "__main__":
    main()
