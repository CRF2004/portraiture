from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from math import sqrt
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from portraiture.schemas import (
    CandidateScore,
    DivergenceRecord,
    MetricRecord,
    PredictionRecord,
    ReplayExample,
)
from portraiture.critic import build_refinement_actions, classify_divergence, should_create_refinement
from portraiture.replay.hint_router import TextHintRouter
from portraiture.replay.signals import (
    coarse_label_for_action,
    infer_action_label,
    infer_state_hint_from_context,
    state_hint_to_action_label,
)
from portraiture.state import ProfileStateStore
from portraiture.utils.config import load_config
from portraiture.utils.io import read_jsonl, write_jsonl


def seed_persona_facts_from_training_examples(
    store: ProfileStateStore,
    train_examples: list[dict[str, Any]],
    messages_by_id: dict[str, dict[str, Any]],
) -> None:
    for example in train_examples:
        target_message_id = example.get("ground_truth_message_id")
        if not target_message_id:
            continue
        target_text = messages_by_id.get(target_message_id, {}).get("content_text", "").strip()
        if not target_text:
            continue
        store.ingest_persona_signals(
            text=target_text,
            evidence_ids=[target_message_id],
            observed_at=messages_by_id.get(target_message_id, {}).get("timestamp"),
            source_method="train_replay_seed",
        )

    total = len(train_examples)
    if total == 0:
        return

    label_groups = {
        "decision_style": {
            "labels": {"compare_options", "challenge_or_refine"},
            "threshold": 0.08,
            "value": "prefers_explicit_tradeoff_comparison",
            "confidence": 0.7,
            "notes": "inferred from repeated compare/refine behavior in training replay examples",
        },
        "explanation_preference": {
            "labels": {"ask_definition", "ask_why", "ask_for_example"},
            "threshold": 0.12,
            "value": "prefers_concrete_step_by_step_explanations",
            "confidence": 0.69,
            "notes": "inferred from repeated explanation-seeking behavior in training replay examples",
        },
        "planning_preference": {
            "labels": {"request_how_to", "feasibility_check", "provide_more_context"},
            "threshold": 0.14,
            "value": "prefers_structured_research_plans",
            "confidence": 0.68,
            "notes": "inferred from repeated planning and implementation-seeking behavior in training replay examples",
        },
        "interaction_style": {
            "labels": {"follow_up_clarification", "provide_more_context"},
            "threshold": 0.15,
            "value": "prefers_clear_structured_follow_up",
            "confidence": 0.66,
            "notes": "inferred from repeated clarifying and context-providing behavior in training replay examples",
        },
    }

    for field, spec in label_groups.items():
        support_examples = [example for example in train_examples if example.get("ground_truth_label") in spec["labels"]]
        support_ratio = len(support_examples) / total
        if support_ratio < spec["threshold"]:
            continue
        evidence_ids = [example["ground_truth_message_id"] for example in support_examples[:5] if example.get("ground_truth_message_id")]
        support_timestamps = [
            messages_by_id[example["ground_truth_message_id"]]["timestamp"]
            for example in support_examples
            if example.get("ground_truth_message_id") in messages_by_id and messages_by_id[example["ground_truth_message_id"]].get("timestamp")
        ]
        store.add_persona_fact(
            field=field,
            value=spec["value"],
            confidence=spec["confidence"],
            evidence_ids=evidence_ids,
            source_method="train_behavior_profile",
            observed_at=support_timestamps[0] if support_timestamps else None,
            notes=f"{spec['notes']}; support_ratio={support_ratio:.3f}; support_count={len(support_examples)}",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate replay baseline predictions.")
    parser.add_argument(
        "--config",
        default="configs/evaluation/replay_baseline_v1.yaml",
        help="Path to the replay evaluation config YAML.",
    )
    parser.add_argument(
        "--restricted-refinement-divergence-types",
        default="",
        help="Comma-separated divergence types eligible for refinement; empty keeps the default behavior.",
    )
    parser.add_argument(
        "--restricted-refinement-divergence-subtypes",
        default="",
        help="Comma-separated divergence subtypes eligible for refinement; empty keeps the default behavior.",
    )
    parser.add_argument(
        "--skip-baseline-refinement",
        action="store_true",
        help="Disable refinement updates during the baseline pass to isolate seed persona facts.",
    )
    parser.add_argument(
        "--refinement-splits",
        default="",
        help="Comma-separated replay splits eligible for refinement updates; empty allows all splits.",
    )
    parser.add_argument(
        "--state-hint-mode",
        choices=["heuristic", "learned", "off"],
        default="heuristic",
        help="State hint strategy used for state-aware prediction.",
    )
    parser.add_argument(
        "--state-hint-min-confidence",
        type=float,
        default=None,
        help="Override the minimum confidence required before applying a state hint.",
    )
    parser.add_argument(
        "--state-router-min-probability",
        type=float,
        default=None,
        help="Override the learned state router's minimum probability threshold.",
    )
    return parser.parse_args()


def simple_tokenize(text: str) -> set[str]:
    token = []
    tokens: set[str] = set()
    for ch in text.lower():
        if ch.isalnum():
            token.append(ch)
        else:
            if token:
                tokens.add("".join(token))
                token = []
    if token:
        tokens.add("".join(token))
    return tokens


def jaccard_similarity(left: str, right: str) -> float:
    left_tokens = simple_tokenize(left)
    right_tokens = simple_tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def semantic_tokenize(text: str) -> list[str]:
    normalized = " ".join(text.lower().split())
    tokens: list[str] = []
    ascii_token: list[str] = []
    cjk_buffer: list[str] = []

    def flush_ascii() -> None:
        if ascii_token:
            token = "".join(ascii_token)
            if len(token) > 1:
                tokens.append(token)
            ascii_token.clear()

    def flush_cjk_buffer() -> None:
        if not cjk_buffer:
            return
        for idx, ch in enumerate(cjk_buffer):
            tokens.append(ch)
            if idx + 1 < len(cjk_buffer):
                tokens.append(ch + cjk_buffer[idx + 1])
        cjk_buffer.clear()

    for ch in normalized:
        if ch.isascii() and ch.isalnum():
            flush_cjk_buffer()
            ascii_token.append(ch)
        elif "\u4e00" <= ch <= "\u9fff":
            flush_ascii()
            cjk_buffer.append(ch)
        else:
            flush_ascii()
            flush_cjk_buffer()
    flush_ascii()
    flush_cjk_buffer()
    return tokens


def cosine_similarity(left: str, right: str) -> float:
    left_tokens = Counter(semantic_tokenize(left))
    right_tokens = Counter(semantic_tokenize(right))
    if not left_tokens or not right_tokens:
        return 0.0
    shared = left_tokens.keys() & right_tokens.keys()
    dot = sum(left_tokens[token] * right_tokens[token] for token in shared)
    left_norm = sqrt(sum(value * value for value in left_tokens.values()))
    right_norm = sqrt(sum(value * value for value in right_tokens.values()))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def text_similarity(left: str, right: str, mode: str) -> float:
    if mode == "semantic":
        return cosine_similarity(left, right)
    return jaccard_similarity(left, right)


def episode_signature(example: dict[str, Any], turns_by_id: dict[str, dict[str, Any]], messages_by_id: dict[str, dict[str, Any]]) -> str:
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


def label_from_text(text: str, previous_text: str | None, similarity_threshold: float) -> str:
    return infer_action_label(text, previous_text, similarity_threshold)


def build_context_texts(example: dict[str, Any], turns_by_id: dict[str, dict[str, Any]], messages_by_id: dict[str, dict[str, Any]]) -> list[str]:
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


def choose_prediction(
    example: dict[str, Any],
    train_examples: list[dict[str, Any]],
    turns_by_id: dict[str, dict[str, Any]],
    messages_by_id: dict[str, dict[str, Any]],
    top_k: int,
    similarity_floor: float,
    default_label: str,
    similarity_threshold: float,
    neighbor_mode: str = "lexical",
    profile_store: ProfileStateStore | None = None,
    state_hint_model: TextHintRouter | None = None,
    use_profile_hint: bool = True,
    use_state_hint: bool = False,
    state_hint_min_confidence: float = 0.75,
    episode_id: str | None = None,
) -> tuple[str, list[CandidateScore], str]:
    context_texts = build_context_texts(example, turns_by_id, messages_by_id)
    current_signature = " \n ".join(context_texts)
    previous_text = context_texts[-1] if context_texts else ""

    weighted_votes: dict[str, float] = defaultdict(float)
    best_neighbor_label = default_label
    best_score = -1.0

    for train_example in train_examples:
        neighbor_context_texts = build_context_texts(train_example, turns_by_id, messages_by_id)
        neighbor_signature = " \n ".join(neighbor_context_texts)
        score = text_similarity(current_signature, neighbor_signature, neighbor_mode)
        if score >= similarity_floor:
            weighted_votes[train_example["ground_truth_label"]] += score
        if score > best_score:
            best_score = score
            best_neighbor_label = train_example["ground_truth_label"]

    if weighted_votes:
        ranked = sorted(weighted_votes.items(), key=lambda item: (-item[1], item[0]))
        predicted_label = ranked[0][0]
        candidates = [CandidateScore(label=label, score=score) for label, score in ranked[:top_k]]
    else:
        predicted_label = best_neighbor_label
        candidates = [CandidateScore(label=default_label, score=1.0)]

    if not candidates:
        candidates = [CandidateScore(label=default_label, score=1.0)]

    heuristic_label = (
        label_from_text(context_texts[-1], context_texts[-2] if len(context_texts) > 1 else None, similarity_threshold)
        if context_texts
        else None
    )

    profile_hint = profile_store.profile_hint_label(episode_id=episode_id) if profile_store is not None and use_profile_hint else None
    if use_state_hint:
        if state_hint_model is not None:
            state_hint = state_hint_model.predict(context_texts)
        else:
            state_hint = infer_state_hint_from_context(context_texts)
    else:
        state_hint = {"state_type": None, "state_value": None, "confidence": 0.0, "reason": "disabled"}
    state_hint_label = state_hint_to_action_label(state_hint.get("state_type"), state_hint.get("state_value")) if use_state_hint else None
    state_hint_confidence = float(state_hint.get("confidence") or 0.0) if use_state_hint else 0.0
    if profile_hint:
        top_score = candidates[0].score if candidates else 0.0
        hint_supported = False
        hint_compatible = heuristic_label == profile_hint

        for idx, candidate in enumerate(candidates):
            if candidate.label == profile_hint:
                candidates[idx] = CandidateScore(label=candidate.label, score=candidate.score + (0.75 if hint_compatible else 0.15))
                hint_supported = True
                break

        if not hint_supported and hint_compatible and top_score < 0.35:
            candidates.append(CandidateScore(label=profile_hint, score=top_score + 0.45))
            hint_supported = True
        elif not hint_supported:
            candidates.append(CandidateScore(label=profile_hint, score=0.05 if not hint_compatible else 0.15))

        candidates = sorted(candidates, key=lambda item: (-item.score, item.label))[:top_k]
        if candidates:
            predicted_label = candidates[0].label

    if state_hint_label and state_hint_confidence >= state_hint_min_confidence:
        top_score = candidates[0].score if candidates else 0.0
        hint_supported = False
        hint_compatible = heuristic_label == state_hint_label
        state_value = state_hint.get("state_value")
        state_boost = 0.6 if state_value == "topic_transition" else 0.45 if state_value == "needs_troubleshooting" else 0.25
        state_append_boost = 0.35 if state_value in {"topic_transition", "needs_troubleshooting"} else 0.18

        for idx, candidate in enumerate(candidates):
            if candidate.label == state_hint_label:
                candidates[idx] = CandidateScore(label=candidate.label, score=candidate.score + (state_boost if hint_compatible else state_append_boost))
                hint_supported = True
                break

        if not hint_supported and hint_compatible and top_score < 0.35:
            candidates.append(CandidateScore(label=state_hint_label, score=top_score + state_boost * 0.7))
            hint_supported = True
        elif not hint_supported:
            candidates.append(CandidateScore(label=state_hint_label, score=0.05 if not hint_compatible else 0.12))

        candidates = sorted(candidates, key=lambda item: (-item.score, item.label))[:top_k]
        if candidates:
            predicted_label = candidates[0].label

    if predicted_label == default_label and context_texts:
        if heuristic_label != "follow_up_clarification":
            predicted_label = heuristic_label
            candidates.insert(0, CandidateScore(label=heuristic_label, score=1.0))

    state_reason = state_hint.get("reason") if use_state_hint else "disabled"
    reasoning_summary = (
        f"{neighbor_mode}-neighbor baseline; best_neighbor_label={best_neighbor_label}; top_match_score={best_score:.3f}; "
        f"state_hint={state_hint_label or 'none'}; state_reason={state_reason}"
    )
    return predicted_label, candidates[:top_k], reasoning_summary


def evaluate_pass(
    *,
    replay_examples: list[dict[str, Any]],
    train_examples: list[dict[str, Any]],
    turns_by_id: dict[str, dict[str, Any]],
    messages_by_id: dict[str, dict[str, Any]],
    top_k: int,
    similarity_floor: float,
    default_label: str,
    similarity_threshold: float,
    predictor_name: str,
    profile_store: ProfileStateStore | None,
    state_hint_model: TextHintRouter | None = None,
    create_refinements: bool,
    run_id: str,
    use_profile_hint: bool,
    use_state_hint: bool,
    state_hint_min_confidence: float = 0.75,
    neighbor_mode: str = "lexical",
    emit_snapshots: bool,
    allowed_refinement_types: set[str] | None = None,
    allowed_refinement_subtypes: set[str] | None = None,
    allowed_refinement_splits: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    prediction_records: list[dict[str, Any]] = []
    divergence_records: list[dict[str, Any]] = []
    refinement_records: list[dict[str, Any]] = []
    all_prediction_rows: list[dict[str, Any]] = []
    profile_snapshot_records: list[dict[str, Any]] = []

    current_snapshot_id = None
    if profile_store is not None:
        current_snapshot = profile_store.snapshot(
            label=f"{predictor_name}_current",
            source_run_id=run_id,
        )
        current_snapshot_id = current_snapshot.id
        if emit_snapshots:
            profile_snapshot_records.append(asdict(current_snapshot))

    for example in replay_examples:
        predicted_label, candidates, reasoning_summary = choose_prediction(
            example=example,
            train_examples=train_examples,
            turns_by_id=turns_by_id,
            messages_by_id=messages_by_id,
            top_k=top_k,
            similarity_floor=similarity_floor,
            default_label=default_label,
            similarity_threshold=similarity_threshold,
            neighbor_mode=neighbor_mode,
            profile_store=profile_store,
            state_hint_model=state_hint_model,
            use_profile_hint=use_profile_hint,
            use_state_hint=use_state_hint,
            state_hint_min_confidence=state_hint_min_confidence,
            episode_id=example["episode_id"],
        )
        predicted_coarse_label = coarse_label_for_action(predicted_label)
        created_at = datetime.now().astimezone().isoformat()
        prediction = PredictionRecord(
            id=f"pred_{predictor_name}_{example['id']}",
            user_id=example["user_id"],
            created_at=created_at,
            updated_at=created_at,
            replay_example_id=example["id"],
            predictor_name=predictor_name,
            profile_snapshot_id=current_snapshot_id,
            predicted_task=example["prediction_task"],
            predicted_label=predicted_label,
            predicted_coarse_label=predicted_coarse_label,
            candidate_labels=candidates,
            predicted_response_text=None,
            reasoning_summary=reasoning_summary,
            used_persona_fact_ids=[],
            used_state_ids=[],
            used_memory_node_ids=[],
        )
        prediction_records.append(asdict(prediction))

        gt_label = example["ground_truth_label"] or ""
        all_prediction_rows.append(
            {
                "split": example["split"],
                "ground_truth_label": gt_label,
                "predicted_label": predicted_label,
                "ground_truth_coarse_label": example.get("ground_truth_coarse_label"),
                "predicted_coarse_label": predicted_coarse_label,
                "observed_state_type": example.get("observed_state_type"),
                "observed_state_value": example.get("observed_state_value"),
            }
        )

        target_text = example.get("metadata", {}).get("target_user_text")
        divergence_type, divergence_subtype, severity, critic_summary = classify_divergence(
            gt_label,
            predicted_label,
            target_text=target_text,
        )
        divergence = DivergenceRecord(
            id=f"div_{predictor_name}_{example['id']}",
            user_id=example["user_id"],
            created_at=created_at,
            updated_at=created_at,
            replay_example_id=example["id"],
            prediction_record_id=prediction.id,
            ground_truth_label=gt_label,
            ground_truth_coarse_label=example.get("ground_truth_coarse_label"),
            predicted_label=predicted_label,
            predicted_coarse_label=predicted_coarse_label,
            is_correct=predicted_label == gt_label,
            divergence_type=divergence_type,
            divergence_subtype=divergence_subtype,
            severity=severity,
            critic_summary=critic_summary,
            observed_state_type=example.get("observed_state_type"),
            observed_state_value=example.get("observed_state_value"),
            observed_state_confidence=example.get("observed_state_confidence"),
            suspected_missing_persona_fact_ids=[],
            suspected_missing_state_ids=[],
            suspected_missing_memory_node_ids=[],
            recommended_refinement_action_ids=[],
        )
        divergence_records.append(asdict(divergence))

        split_allowed = allowed_refinement_splits is None or example["split"] in allowed_refinement_splits
        if create_refinements and split_allowed and should_create_refinement(divergence, target_text=target_text):
            type_allowed = allowed_refinement_types is None or divergence.divergence_type in allowed_refinement_types
            subtype_allowed = (
                allowed_refinement_subtypes is None or divergence.divergence_subtype in allowed_refinement_subtypes
            )
            if type_allowed and subtype_allowed:
                refinement_actions = build_refinement_actions(divergence, run_id=run_id)
                divergence.recommended_refinement_action_ids = [action.id for action in refinement_actions]
                divergence_records[-1] = asdict(divergence)
                for action in refinement_actions:
                    if profile_store is not None:
                        profile_store.apply_refinement_action(
                            action,
                            divergence_type=divergence.divergence_type,
                            divergence_subtype=divergence.divergence_subtype,
                            evidence_ids=divergence.suspected_missing_state_ids
                            or divergence.suspected_missing_persona_fact_ids
                            or divergence.suspected_missing_memory_node_ids,
                            episode_id=example["episode_id"],
                        )
                    refinement_records.append(asdict(action))

    if profile_store is not None and emit_snapshots and create_refinements:
        refined_snapshot = profile_store.snapshot(
            label=f"{predictor_name}_after_refinement",
            source_run_id=run_id,
        )
        profile_snapshot_records.append(asdict(refined_snapshot))

    return prediction_records, divergence_records, refinement_records, profile_snapshot_records, all_prediction_rows


def compute_classification_metrics(
    rows: list[dict[str, Any]],
    *,
    ground_truth_key: str = "ground_truth_label",
    predicted_key: str = "predicted_label",
) -> dict[str, float]:
    if not rows:
        return {"accuracy": 0.0, "macro_f1": 0.0}

    labels = sorted({row.get(ground_truth_key) for row in rows if row.get(ground_truth_key)} | {row.get(predicted_key) for row in rows if row.get(predicted_key)})
    correct = sum(1 for row in rows if row.get(ground_truth_key) == row.get(predicted_key))
    accuracy = correct / len(rows)

    f1_scores: list[float] = []
    for label in labels:
        tp = sum(1 for row in rows if row.get(ground_truth_key) == label and row.get(predicted_key) == label)
        fp = sum(1 for row in rows if row.get(ground_truth_key) != label and row.get(predicted_key) == label)
        fn = sum(1 for row in rows if row.get(ground_truth_key) == label and row.get(predicted_key) != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        f1_scores.append(f1)

    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0
    return {"accuracy": accuracy, "macro_f1": macro_f1}


def main() -> None:
    args = parse_args()
    config = load_config(Path(args.config))
    allowed_refinement_types = {item.strip() for item in args.restricted_refinement_divergence_types.split(",") if item.strip()} or None
    allowed_refinement_subtypes = {
        item.strip() for item in args.restricted_refinement_divergence_subtypes.split(",") if item.strip()
    } or None
    allowed_refinement_splits = {item.strip() for item in args.refinement_splits.split(",") if item.strip()} or None
    inputs = config["inputs"]
    outputs = config["outputs"]
    task = config["task"]
    eval_cfg = config["evaluation"]

    replay_examples = read_jsonl(Path(inputs["replay_examples"]))
    turns = read_jsonl(Path(inputs["turns"]))
    messages = read_jsonl(Path(inputs["messages"]))

    turns_by_id = {turn["id"]: turn for turn in turns}
    messages_by_id = {message["id"]: message for message in messages}

    train_examples = [example for example in replay_examples if example["split"] == "train"]
    if not train_examples:
        raise ValueError("No training replay examples found.")

    default_label = Counter(example["ground_truth_label"] for example in train_examples).most_common(1)[0][0]
    baseline_store = ProfileStateStore(user_id="user_demo")
    seed_persona_facts_from_training_examples(baseline_store, train_examples, messages_by_id)

    state_hint_model: TextHintRouter | None = None
    state_hint_min_confidence = 0.75
    if args.state_hint_mode == "learned":
        router_min_probability = 0.35 if args.state_router_min_probability is None else args.state_router_min_probability
        state_hint_model = TextHintRouter.fit_state_router(
            train_examples,
            turns_by_id,
            messages_by_id,
            min_probability=router_min_probability,
        )
        state_hint_min_confidence = router_min_probability
    elif args.state_hint_mode == "off":
        state_hint_min_confidence = 1.0

    if args.state_hint_min_confidence is not None:
        state_hint_min_confidence = args.state_hint_min_confidence

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
        state_hint_model=None,
        create_refinements=not args.skip_baseline_refinement,
        run_id=eval_cfg["run_id"],
        use_profile_hint=False,
        use_state_hint=False,
        state_hint_min_confidence=state_hint_min_confidence,
        emit_snapshots=True,
        allowed_refinement_types=allowed_refinement_types,
        allowed_refinement_subtypes=allowed_refinement_subtypes,
        allowed_refinement_splits=allowed_refinement_splits,
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
        state_hint_model=state_hint_model,
        create_refinements=False,
        run_id=eval_cfg["run_id"],
        use_profile_hint=False,
        use_state_hint=args.state_hint_mode != "off",
        state_hint_min_confidence=state_hint_min_confidence,
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
        state_hint_model=None,
        create_refinements=False,
        run_id=eval_cfg["run_id"],
        use_profile_hint=True,
        use_state_hint=False,
        state_hint_min_confidence=state_hint_min_confidence,
        emit_snapshots=True,
    )

    metric_records: list[dict[str, Any]] = []
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
                metric = MetricRecord(
                    id=f"metric_{prefix}_{split}_{metric_name}",
                    user_id="user_demo",
                    created_at=datetime.now().astimezone().isoformat(),
                    updated_at=datetime.now().astimezone().isoformat(),
                    run_id=eval_cfg["run_id"],
                    metric_group="replay",
                    metric_name=metric_name,
                    metric_value=metric_value,
                    split=f"{prefix}:{split}",
                    config_ref=args.config,
                    notes=f"baseline_label={default_label}; predictor={eval_cfg['predictor_name']}; pass={prefix}",
                )
                metric_records.append(asdict(metric))
            for metric_name, metric_value in coarse_metrics.items():
                metric = MetricRecord(
                    id=f"metric_{prefix}_{split}_coarse_{metric_name}",
                    user_id="user_demo",
                    created_at=datetime.now().astimezone().isoformat(),
                    updated_at=datetime.now().astimezone().isoformat(),
                    run_id=eval_cfg["run_id"],
                    metric_group="replay_coarse",
                    metric_name=metric_name,
                    metric_value=metric_value,
                    split=f"{prefix}:{split}",
                    config_ref=args.config,
                    notes=f"baseline_label={default_label}; predictor={eval_cfg['predictor_name']}; pass={prefix}; coarse_labels=true",
                )
                metric_records.append(asdict(metric))

    metric_records.append(
        asdict(
            MetricRecord(
                id="metric_run_refinement_action_count",
                user_id="user_demo",
                created_at=datetime.now().astimezone().isoformat(),
                updated_at=datetime.now().astimezone().isoformat(),
                run_id=eval_cfg["run_id"],
                metric_group="refinement",
                metric_name="refinement_action_count",
                metric_value=float(len(refinement_records)),
                split="run",
                config_ref=args.config,
                notes=f"applied_actions={len(refinement_records)}",
            )
        )
    )
    metric_records.append(
        asdict(
            MetricRecord(
                id="metric_run_dynamic_state_count",
                user_id="user_demo",
                created_at=datetime.now().astimezone().isoformat(),
                updated_at=datetime.now().astimezone().isoformat(),
                run_id=eval_cfg["run_id"],
                metric_group="refinement",
                metric_name="dynamic_state_count",
                metric_value=float(len(baseline_store.dynamic_states)),
                split="run",
                config_ref=args.config,
                notes="materialized dynamic states after baseline refinement pass",
            )
        )
    )

    write_jsonl(Path(outputs["predictions_baseline"]), baseline_prediction_records)
    write_jsonl(Path(outputs["predictions_state_aware"]), state_aware_prediction_records)
    write_jsonl(Path(outputs["predictions_refined"]), refined_prediction_records)
    write_jsonl(Path(outputs["divergences_baseline"]), baseline_divergence_records)
    write_jsonl(Path(outputs["divergences_state_aware"]), state_aware_divergence_records)
    write_jsonl(Path(outputs["divergences_refined"]), refined_divergence_records)
    write_jsonl(Path(outputs["refinements"]), refinement_records)
    write_jsonl(Path(outputs["profile_snapshots_baseline"]), baseline_profile_snapshots)
    write_jsonl(Path(outputs["profile_snapshots_refined"]), refined_profile_snapshots)
    write_jsonl(Path(outputs["persona_facts"]), baseline_store.export_records()["persona_facts"])
    write_jsonl(Path(outputs["dynamic_states"]), baseline_store.export_records()["dynamic_states"])
    write_jsonl(Path(outputs["memory_nodes"]), baseline_store.export_records()["memory_nodes"])
    write_jsonl(Path(outputs["metrics"]), metric_records)

    baseline_summary = defaultdict(int)
    refined_summary = defaultdict(int)
    for row in baseline_rows:
        baseline_summary[row["split"]] += 1
    for row in refined_rows:
        refined_summary[row["split"]] += 1
    print(f"Evaluated {len(replay_examples)} replay examples in baseline, state-aware, and refined passes")
    print(f"Default label: {default_label}")
    print(f"Baseline split counts: {dict(baseline_summary)}")
    state_aware_summary = defaultdict(int)
    for row in state_aware_rows:
        state_aware_summary[row["split"]] += 1
    print(f"State-aware split counts: {dict(state_aware_summary)}")
    print(f"Refined split counts: {dict(refined_summary)}")


if __name__ == "__main__":
    main()
