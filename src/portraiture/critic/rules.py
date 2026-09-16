from __future__ import annotations

from datetime import datetime

from portraiture.schemas import DivergenceRecord, RefinementAction
from portraiture.replay.signals import infer_state_subtype_from_text

FOLLOW_UP_BOUNDARY_LABELS = {"follow_up_clarification"}
CONTEXT_BOUNDARY_LABELS = {"provide_more_context"}
PLAN_BOUNDARY_LABELS = {"request_how_to", "feasibility_check"}


def classify_divergence(
    ground_truth_label: str,
    predicted_label: str,
    *,
    target_text: str | None = None,
) -> tuple[str, str | None, float, str]:
    if predicted_label == ground_truth_label:
        return "", None, 0.0, ""

    if target_text:
        explicit_persona_markers = [
            ("我更喜欢", "short_term_behavior_overfit", 0.9),
            ("我偏向", "short_term_behavior_overfit", 0.88),
            ("我倾向", "trait_overgeneralized", 0.86),
            ("我一般", "trait_overgeneralized", 0.84),
            ("我通常", "trait_overgeneralized", 0.84),
            ("我习惯", "short_term_behavior_overfit", 0.84),
            ("对我来说", "unsupported_persona_fact", 0.8),
            ("我必须", "unsupported_persona_fact", 0.8),
            ("我不能", "unsupported_persona_fact", 0.78),
            ("我不要", "unsupported_persona_fact", 0.78),
            ("我不想", "unsupported_persona_fact", 0.78),
            ("我最好", "trait_overgeneralized", 0.76),
            ("我希望", "trait_overgeneralized", 0.76),
            ("我建议", "decision_style", 0.76),
        ]
        for marker, subtype, severity in explicit_persona_markers:
            if _contains_persona_marker(target_text, marker):
                return (
                    "persona_misalignment",
                    subtype,
                    severity,
                    "The baseline missed a stable preference or constraint expressed in the target text.",
                )

    label_pair = {ground_truth_label, predicted_label}
    if label_pair <= {"topic_shift", "follow_up_clarification"}:
        return (
            "action_selection_error",
            "wrong_turn_boundary",
            0.78,
            "The baseline crossed a fine follow-up boundary and treated a same-topic clarification as a topic shift.",
        )
    if label_pair <= {"challenge_or_refine", "provide_more_context"}:
        return (
            "action_selection_error",
            "task_label_too_coarse",
            0.66,
            "The baseline confused a context-expanding follow-up with a challenge/refine move.",
        )
    if label_pair <= {"ask_definition", "provide_more_context"}:
        return (
            "action_selection_error",
            "ranking_error",
            0.62,
            "The baseline chose a clarification label instead of a context-expanding follow-up.",
        )
    if label_pair <= {"ask_definition", "request_how_to"}:
        return (
            "action_selection_error",
            "ranking_error",
            0.63,
            "The baseline confused a definition question with a how-to request.",
        )
    if label_pair <= PLAN_BOUNDARY_LABELS:
        return (
            "action_selection_error",
            "wrong_turn_boundary",
            0.72,
            "The baseline matched the plan-like topic but missed whether the user wanted feasibility or procedure.",
        )
    if label_pair <= {"follow_up_clarification", "provide_more_context"}:
        return (
            "action_selection_error",
            "task_label_too_coarse",
            0.64,
            "The baseline confused a same-topic follow-up question with a context-expanding follow-up.",
        )
    if label_pair <= {"topic_shift", "provide_more_context"}:
        return (
            "action_selection_error",
            "wrong_turn_boundary",
            0.76,
            "The baseline treated a context-expanding follow-up as a new topic shift.",
        )

    if target_text:
        state_signal_markers = [
            "先做",
            "先把",
            "目标",
            "计划",
            "方案",
            "框架",
            "步骤",
            "落地",
            "实现",
            "报错",
            "失败",
            "卡住",
            "无法",
            "不能",
            "尽快",
            "马上",
            "立刻",
            "快速",
            "赶紧",
            "我觉得",
            "我认为",
            "我倾向",
            "我偏向",
            "还是",
            "比较",
            "是否",
            "能不能",
            "可不可以",
            "行不行",
        ]
        if ground_truth_label == "topic_shift" or predicted_label == "topic_shift" or any(marker in target_text for marker in state_signal_markers):
            return (
                "state_under_specified",
                infer_state_subtype_from_text(
                    target_text,
                    ground_truth_label=ground_truth_label,
                    predicted_label=predicted_label,
                ),
                0.8,
                "The baseline missed an active goal or topic shift in the recent context.",
            )

    if ground_truth_label == "topic_shift" or predicted_label == "topic_shift":
        return (
            "state_under_specified",
            "goal_shift_missed",
            0.8,
            "The baseline missed an active goal or topic shift in the recent context.",
        )

    if ground_truth_label in {"challenge_or_refine", "compare_options"} or predicted_label in {"challenge_or_refine", "compare_options"}:
        return (
            "reasoning_mismatch",
            "wrong_intent_inference",
            0.7,
            "The baseline captured the topic but not the user's intended reasoning move.",
        )

    if ground_truth_label in {"ask_definition", "ask_why", "ask_for_example", "request_how_to", "feasibility_check", "follow_up_clarification", "provide_more_context"}:
        return (
            "action_selection_error",
            "ranking_error",
            0.6,
            "The baseline chose the wrong next-action label for a direct information-seeking move.",
        )

    return (
        "action_selection_error",
        "candidate_set_missing",
        0.6,
        "The baseline chose the wrong next-action label.",
    )


def should_create_refinement(
    divergence: DivergenceRecord,
    *,
    target_text: str | None = None,
) -> bool:
    if divergence.is_correct:
        return False

    if divergence.divergence_type == "surface_only_match":
        return False

    if divergence.divergence_type == "persona_misalignment":
        if not target_text:
            return False
        return any(
            marker in target_text
            for marker in (
                "我更喜欢",
                "我偏向",
                "我倾向",
                "我习惯",
                "我通常",
                "我一般",
                "我希望",
                "我最好",
                "我不能",
                "我不要",
                "我必须",
                "我不想",
            )
        )

    if divergence.divergence_type == "state_under_specified":
        return divergence.severity is not None and divergence.severity >= 0.75

    if divergence.divergence_type == "reasoning_mismatch":
        return divergence.severity is not None and divergence.severity >= 0.7

    if divergence.divergence_type == "action_selection_error":
        return divergence.severity is not None and divergence.severity >= 0.6

    return False


def build_refinement_actions(
    divergence: DivergenceRecord,
    *,
    run_id: str,
    evidence_ids: list[str] | None = None,
) -> list[RefinementAction]:
    if divergence.is_correct:
        return []

    evidence_ids = evidence_ids or []
    target_object_type = "evaluation_rule"
    action_type: str = "update"
    action_reason = divergence.critic_summary or "Refine the baseline based on this divergence."

    if divergence.divergence_type == "memory_failure":
        target_object_type = "memory_node"
        action_type = "create"
        action_reason = "Add or update memory evidence for the missing historical fact or event."
    elif divergence.divergence_type == "persona_misalignment":
        target_object_type = "persona_fact"
        action_type = "update"
        if divergence.divergence_subtype == "trait_overgeneralized":
            action_reason = "Update the long-term preference fact instead of overgeneralizing from one episode."
        elif divergence.divergence_subtype == "short_term_behavior_overfit":
            action_reason = "Preserve the stable interaction style instead of overfitting to a recent behavior pattern."
        elif divergence.divergence_subtype == "unsupported_persona_fact":
            action_reason = "Add an explicit constraint or preference fact backed by the target text."
        else:
            action_reason = "Revise the persona fact so long-term preference is not overfit from a short-term pattern."
    elif divergence.divergence_type == "state_under_specified":
        target_object_type = "dynamic_state"
        action_type = "create"
        action_reason = "Introduce a dynamic state entry for the missed goal or active problem."
    elif divergence.divergence_type == "reasoning_mismatch":
        target_object_type = "reasoning_policy"
        action_type = "update"
        action_reason = "Adjust the reasoning scaffold so the simulator respects the user's intent and tradeoff order."
    elif divergence.divergence_type == "action_selection_error":
        target_object_type = "action_space"
        action_type = "reprioritize"
        action_reason = "Re-rank candidate next actions and widen the action set if needed."
    elif divergence.divergence_type == "surface_only_match":
        target_object_type = "evaluation_rule"
        action_type = "update"
        action_reason = "Reduce style-only matching weight and increase behavioral accuracy weight."

    action_id = f"ref_{divergence.replay_example_id}"
    now = datetime.now().astimezone().isoformat()
    action = RefinementAction(
        id=action_id,
        user_id=divergence.user_id,
        created_at=now,
        updated_at=now,
        target_object_type=target_object_type,
        target_object_id=None,
        action_type=action_type,  # type: ignore[arg-type]
        action_reason=action_reason,
        evidence_ids=evidence_ids,
        triggered_by_divergence_id=divergence.id,
        applied=False,
        applied_in_run_id=run_id,
    )
    return [action]


def _contains_persona_marker(text: str, marker: str) -> bool:
    if marker.startswith("我") or marker.startswith("对我"):
        return marker in text
    return any(prefix in text for prefix in ("我", "我的", "对我来说")) and marker in text
