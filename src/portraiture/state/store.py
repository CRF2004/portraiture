from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from portraiture.schemas import (
    DynamicState,
    MemoryNode,
    PersonaFact,
    ProfileSnapshot,
    RefinementAction,
    TimeScope,
)


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _slugify(value: str) -> str:
    cleaned: list[str] = []
    for ch in value.lower():
        if ch.isalnum():
            cleaned.append(ch)
        else:
            cleaned.append("_")
    slug = "".join(cleaned).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "item"


def _normalize_value(value: str) -> str:
    return " ".join(value.split())


def _contains_any(text: str, markers: list[str]) -> bool:
    return any(marker in text for marker in markers)


def extract_persona_fact_candidates(text: str) -> list[dict[str, Any]]:
    normalized = _normalize_value(text)
    if not normalized:
        return []

    preference_markers = ["我更喜欢", "我偏向", "我倾向", "我习惯", "我通常", "我一般", "我希望", "我最好"]
    planning_markers = ["先", "再", "框架", "步骤", "计划", "方案", "结构化", "分层"]
    explanation_markers = ["解释", "原理", "例子", "详细", "为什么", "含义"]
    decision_markers = ["对比", "比较", "权衡", "选择", "还是", "区别"]
    risk_markers = ["风险", "谨慎", "可行", "能不能", "是否", "行吗", "可不可以"]
    constraint_markers = ["不能", "不要", "必须", "不想", "不要", "最好"]
    interaction_markers = ["直接", "简洁", "明确", "条理", "一步一步", "分步骤"]

    candidates: list[dict[str, Any]] = []
    explicit_pref = _contains_any(normalized, preference_markers)

    if explicit_pref and _contains_any(normalized, planning_markers):
        candidates.append(
            {
                "field": "planning_preference",
                "value": "prefers_structured_research_plans",
                "confidence": 0.78,
                "notes": "explicit planning language detected",
            }
        )
    if explicit_pref and _contains_any(normalized, explanation_markers):
        candidates.append(
            {
                "field": "explanation_preference",
                "value": "prefers_concrete_step_by_step_explanations",
                "confidence": 0.74,
                "notes": "explicit explanation preference detected",
            }
        )
    if explicit_pref and _contains_any(normalized, decision_markers):
        candidates.append(
            {
                "field": "decision_style",
                "value": "prefers_explicit_tradeoff_comparison",
                "confidence": 0.76,
                "notes": "explicit decision language detected",
            }
        )
    if explicit_pref and _contains_any(normalized, risk_markers):
        candidates.append(
            {
                "field": "risk_preference",
                "value": "prefers_feasibility_checks_before_action",
                "confidence": 0.73,
                "notes": "explicit feasibility language detected",
            }
        )
    if explicit_pref and _contains_any(normalized, constraint_markers):
        candidates.append(
            {
                "field": "constraint_preference",
                "value": "treats_explicit_constraints_as_binding",
                "confidence": 0.8,
                "notes": "explicit constraint language detected",
            }
        )
    if explicit_pref and _contains_any(normalized, interaction_markers):
        candidates.append(
            {
                "field": "interaction_style",
                "value": "prefers_clear_structured_follow_up",
                "confidence": 0.7,
                "notes": "explicit interaction style detected",
            }
        )

    return candidates


class ProfileStateStore:
    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        self.persona_facts: list[PersonaFact] = []
        self.dynamic_states: list[DynamicState] = []
        self.memory_nodes: list[MemoryNode] = []
        self._refinement_count = 0

    def _find_persona_fact(self, *, field: str, value: str) -> PersonaFact | None:
        for fact in self.persona_facts:
            if fact.field == field and fact.value == value and fact.status == "active":
                return fact
        return None

    def add_persona_fact(
        self,
        *,
        field: str,
        value: str,
        confidence: float,
        evidence_ids: list[str] | None = None,
        source_method: str | None = None,
        notes: str | None = None,
        observed_at: str | None = None,
    ) -> PersonaFact:
        now = _now()
        existing = self._find_persona_fact(field=field, value=value)
        if existing is not None:
            existing.updated_at = now
            existing.confidence = max(existing.confidence, confidence)
            existing.evidence_ids = sorted(set(existing.evidence_ids).union(set(evidence_ids or [])))
            existing.support_count += 1
            if observed_at is not None:
                if existing.first_observed_at is None:
                    existing.first_observed_at = observed_at
                existing.last_observed_at = observed_at
            if source_method is not None:
                existing.source_method = source_method
            if notes is not None:
                existing.notes = notes
            return existing

        fact = PersonaFact(
            id=f"pf_{_slugify(field)}_{len(self.persona_facts):03d}",
            user_id=self.user_id,
            created_at=now,
            updated_at=now,
            field=field,
            value=value,
            confidence=confidence,
            evidence_ids=list(evidence_ids or []),
            source_method=source_method,
            notes=notes,
            first_observed_at=observed_at,
            last_observed_at=observed_at,
            support_count=1,
        )
        self.persona_facts.append(fact)
        return fact

    def ingest_persona_signals(
        self,
        *,
        text: str,
        evidence_ids: list[str] | None = None,
        observed_at: str | None = None,
        source_method: str = "profile_extractor_v1",
    ) -> list[PersonaFact]:
        facts: list[PersonaFact] = []
        for candidate in extract_persona_fact_candidates(text):
            fact = self.add_persona_fact(
                field=candidate["field"],
                value=candidate["value"],
                confidence=candidate["confidence"],
                evidence_ids=evidence_ids,
                source_method=source_method,
                notes=candidate["notes"],
                observed_at=observed_at,
            )
            facts.append(fact)
        return facts

    def add_dynamic_state(
        self,
        *,
        state_type: str,
        state_value: str,
        confidence: float,
        evidence_ids: list[str] | None = None,
        episode_id: str | None = None,
        source_method: str | None = None,
    ) -> DynamicState:
        now = _now()
        state = DynamicState(
            id=f"st_{_slugify(state_type)}_{len(self.dynamic_states):03d}",
            user_id=self.user_id,
            created_at=now,
            updated_at=now,
            state_type=state_type,
            state_value=state_value,
            confidence=confidence,
            time_scope=TimeScope(start_episode_id=episode_id, end_episode_id=episode_id),
            evidence_ids=list(evidence_ids or []),
            derived_from_persona_ids=[],
            source_method=source_method,
        )
        self.dynamic_states.append(state)
        return state

    def add_memory_node(
        self,
        *,
        title: str,
        summary: str,
        evidence_ids: list[str] | None = None,
        source_episode_ids: list[str] | None = None,
        tags: list[str] | None = None,
        retrieval_text: str | None = None,
    ) -> MemoryNode:
        now = _now()
        memory = MemoryNode(
            id=f"mem_{_slugify(title)}_{len(self.memory_nodes):03d}",
            user_id=self.user_id,
            created_at=now,
            updated_at=now,
            memory_type="semantic",
            title=title,
            summary=summary,
            tags=list(tags or []),
            evidence_ids=list(evidence_ids or []),
            source_episode_ids=list(source_episode_ids or []),
            retrieval_text=retrieval_text or summary,
        )
        self.memory_nodes.append(memory)
        return memory

    def apply_refinement_action(
        self,
        action: RefinementAction,
        *,
        divergence_type: str,
        divergence_subtype: str | None = None,
        evidence_ids: list[str] | None = None,
        episode_id: str | None = None,
    ) -> dict[str, Any]:
        evidence_ids = list(evidence_ids or [])
        applied_object: dict[str, Any] | None = None

        if action.target_object_type == "dynamic_state":
            state_type = _state_type_for_divergence(divergence_type, divergence_subtype)
            state = self.add_dynamic_state(
                state_type=state_type,
                state_value=action.action_reason,
                confidence=0.62,
                evidence_ids=evidence_ids,
                episode_id=episode_id,
                source_method="refinement_action",
            )
            applied_object = state.to_dict()
            action.target_object_id = state.id
        elif action.target_object_type == "persona_fact":
            field = _persona_field_for_divergence(divergence_type, divergence_subtype)
            fact = self.add_persona_fact(
                field=field,
                value=_persona_fact_value_for_divergence(field, divergence_type, divergence_subtype, action.action_reason),
                confidence=0.58,
                evidence_ids=evidence_ids,
                source_method="refinement_action",
                notes=f"generated_from={divergence_type}; episode={episode_id}" if episode_id else f"generated_from={divergence_type}",
            )
            applied_object = fact.to_dict()
            action.target_object_id = fact.id
        else:
            memory = self.add_memory_node(
                title=action.target_object_type,
                summary=action.action_reason,
                evidence_ids=evidence_ids,
                source_episode_ids=[episode_id] if episode_id else [],
                tags=["refinement", divergence_type],
                retrieval_text=action.action_reason,
            )
            applied_object = memory.to_dict()
            action.target_object_id = memory.id

        action.applied = True
        action.updated_at = _now()
        self._refinement_count += 1
        return applied_object or {}

    def snapshot(self, *, label: str, source_run_id: str) -> ProfileSnapshot:
        now = _now()
        snapshot = ProfileSnapshot(
            id=f"ps_{_slugify(label)}",
            user_id=self.user_id,
            created_at=now,
            updated_at=now,
            snapshot_label=label,
            persona_fact_ids=[fact.id for fact in self.persona_facts],
            dynamic_state_ids=[state.id for state in self.dynamic_states],
            memory_node_ids=[memory.id for memory in self.memory_nodes],
            source_run_id=source_run_id,
        )
        return snapshot

    def export_records(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "persona_facts": [asdict(item) for item in self.persona_facts],
            "dynamic_states": [asdict(item) for item in self.dynamic_states],
            "memory_nodes": [asdict(item) for item in self.memory_nodes],
        }

    def profile_hint_label(self, episode_id: str | None = None) -> str | None:
        votes: dict[str, float] = {}

        if episode_id is not None:
            for memory in reversed(self.memory_nodes):
                if episode_id in memory.source_episode_ids:
                    hint = _hint_label_from_memory(memory.title)
                    if hint is not None:
                        votes[hint] = votes.get(hint, 0.0) + 1.5
            for state in reversed(self.dynamic_states):
                if state.time_scope.start_episode_id == episode_id or state.time_scope.end_episode_id == episode_id:
                    hint = _hint_label_from_state(state.state_type)
                    if hint is not None:
                        votes[hint] = votes.get(hint, 0.0) + 2.0
            for fact in self.persona_facts:
                if fact.notes and f"episode={episode_id}" in fact.notes:
                    hint = _hint_label_from_persona_field(fact.field)
                    if hint is not None:
                        votes[hint] = votes.get(hint, 0.0) + 1.0

        if not votes:
            for fact in self.persona_facts:
                hint = _hint_label_from_persona_field(fact.field)
                if hint is not None:
                    votes[hint] = votes.get(hint, 0.0) + 1.0

        if not votes:
            for memory in self.memory_nodes:
                hint = _hint_label_from_memory(memory.title)
                if hint is not None:
                    votes[hint] = votes.get(hint, 0.0) + 1.0

        if not votes:
            for state in self.dynamic_states:
                hint = _hint_label_from_state(state.state_type)
                if hint is not None:
                    votes[hint] = votes.get(hint, 0.0) + 1.0

        if not votes:
            return None

        best_hint, best_score = max(votes.items(), key=lambda item: (item[1], item[0]))
        if best_score < 1.5:
            return None
        return best_hint


def _state_type_for_divergence(divergence_type: str, divergence_subtype: str | None) -> str:
    if divergence_type != "state_under_specified":
        return "active_problem"
    if divergence_subtype == "time_pressure_missed":
        return "time_pressure"
    if divergence_subtype == "stance_change_missed":
        return "current_stance"
    if divergence_subtype == "blocking_issue_missed":
        return "blocking_issue"
    return "current_goal"


def _persona_field_for_divergence(divergence_type: str, divergence_subtype: str | None) -> str:
    if divergence_type == "persona_misalignment":
        if divergence_subtype == "trait_overgeneralized":
            return "decision_style"
        if divergence_subtype == "short_term_behavior_overfit":
            return "interaction_style"
        if divergence_subtype == "unsupported_persona_fact":
            return "constraint_preference"
        return "long_term_goal"
    return "interaction_style"


def _persona_fact_value_for_divergence(
    field: str,
    divergence_type: str,
    divergence_subtype: str | None,
    fallback_reason: str,
) -> str:
    if divergence_type != "persona_misalignment":
        return fallback_reason

    mapping: dict[str, dict[str | None, str]] = {
        "decision_style": {
            "trait_overgeneralized": "prefers explicit tradeoff comparison before committing",
            "unsupported_persona_fact": "needs a grounded decision rule, not a guessed preference",
            None: "prefers explicit tradeoff comparison before committing",
        },
        "interaction_style": {
            "short_term_behavior_overfit": "keeps the stable interaction pattern across episodes",
            "unsupported_persona_fact": "expects the assistant to respect expressed constraints",
            None: "keeps the stable interaction pattern across episodes",
        },
        "constraint_preference": {
            "unsupported_persona_fact": "treats the stated constraint as binding for the current episode",
            None: "treats the stated constraint as binding for the current episode",
        },
        "long_term_goal": {
            "trait_overgeneralized": "has a stable long-term objective that should not be overwritten by a single turn",
            None: "has a stable long-term objective that should not be overwritten by a single turn",
        },
        "planning_preference": {
            None: "prefers a structured plan before execution",
        },
        "explanation_preference": {
            None: "prefers a concrete explanation with explicit steps",
        },
        "risk_preference": {
            None: "prefers feasibility checks before action",
        },
    }

    field_map = mapping.get(field)
    if field_map is not None:
        return field_map.get(divergence_subtype, field_map.get(None, fallback_reason))
    return fallback_reason


def _hint_label_from_state(state_type: str) -> str | None:
    if state_type in {"current_goal", "active_problem"}:
        return "request_how_to"
    if state_type == "blocking_issue":
        return "feasibility_check"
    if state_type == "time_pressure":
        return "follow_up_clarification"
    if state_type == "current_stance":
        return "challenge_or_refine"
    return None


def _hint_label_from_memory(title: str) -> str | None:
    if title == "reasoning_policy":
        return "challenge_or_refine"
    if title == "action_space":
        return "compare_options"
    if title == "evaluation_rule":
        return "follow_up_clarification"
    return None


def _hint_label_from_persona_field(field: str) -> str | None:
    if field in {"decision_style", "planning_preference"}:
        return "compare_options"
    if field == "explanation_preference":
        return "ask_definition"
    if field == "risk_preference":
        return "feasibility_check"
    if field == "interaction_style":
        return "follow_up_clarification"
    if field == "topic_interest":
        return "topic_shift"
    if field == "constraint_preference":
        return "feasibility_check"
    if field == "long_term_goal":
        return "request_how_to"
    return None
