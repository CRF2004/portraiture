"""Tests for the portraiture label taxonomy."""

from __future__ import annotations

import json

import pytest

from portraiture.schemas.labels import (
    COARSE_ACTIONS,
    FINE_ACTIONS,
    FINE_TO_COARSE,
    COARSE_TO_FINE,
    Annotation,
    annotation_from_dict,
    annotation_to_dict,
    coarse_from_fine,
    describe,
)
from portraiture.replay.signals import state_hint_to_action_label


class TestLabelTaxonomy:
    def test_coarse_labels_count(self):
        assert len(COARSE_ACTIONS) == 7  # clarify, expand, plan, compare, challenge, shift, other

    def test_fine_labels_count(self):
        assert len(FINE_ACTIONS) == 11  # 10 specific + other

    def test_other_is_last_in_both(self):
        assert COARSE_ACTIONS[-1] == "other"
        assert FINE_ACTIONS[-1] == "other"

    def test_every_fine_maps_to_coarse(self):
        for fine in FINE_ACTIONS:
            coarse = FINE_TO_COARSE.get(fine)
            assert coarse is not None, f"{fine!r} has no coarse mapping"
            assert coarse in COARSE_ACTIONS, f"{fine!r} maps to unknown coarse {coarse!r}"

    def test_every_coarse_has_fine_children(self):
        for coarse in COARSE_ACTIONS:
            children = COARSE_TO_FINE.get(coarse)
            assert children is not None, f"{coarse!r} has no fine children"
            for child in children:
                assert child in FINE_ACTIONS, f"{child!r} not in FINE_ACTIONS"

    def test_other_maps_to_other(self):
        assert coarse_from_fine("other") == "other"

    def test_describe_known_labels(self):
        for coarse in COARSE_ACTIONS:
            desc = describe(coarse)
            assert isinstance(desc, str) and len(desc) > 5
        for fine in FINE_ACTIONS:
            desc = describe(fine)
            assert isinstance(desc, str) and len(desc) > 5

    def test_describe_unknown_returns_fallback(self):
        desc = describe("nonexistent_label")
        assert "Unknown" in desc


class TestAnnotation:
    def test_valid_annotation(self):
        ann = Annotation(turn_id="t1", coarse="clarify", fine="ask_definition")
        assert ann.turn_id == "t1"
        assert ann.coarse == "clarify"
        assert ann.fine == "ask_definition"

    def test_annotation_default_confidence(self):
        ann = Annotation(turn_id="t2", coarse="expand", fine="ask_for_example")
        assert ann.confidence == 1.0

    def test_annotation_custom_confidence(self):
        ann = Annotation(turn_id="t3", coarse="challenge", fine="challenge_or_refine", confidence=0.8)
        assert ann.confidence == 0.8

    def test_invalid_coarse_raises(self):
        with pytest.raises(ValueError, match="Invalid coarse"):
            Annotation(turn_id="t4", coarse="invalid_coarse", fine="other")  # type: ignore[arg-type]

    def test_invalid_fine_raises(self):
        with pytest.raises(ValueError, match="Invalid fine"):
            Annotation(turn_id="t5", coarse="other", fine="invalid_fine")  # type: ignore[arg-type]

    def test_mismatched_coarse_and_fine_raises(self):
        with pytest.raises(ValueError, match="maps to coarse"):
            Annotation(turn_id="t6", coarse="expand", fine="ask_definition")

    def test_serialization_roundtrip(self):
        ann = Annotation(turn_id="t7", coarse="plan", fine="request_how_to", confidence=0.9)
        d = annotation_to_dict(ann)
        restored = annotation_from_dict(d)
        assert restored.turn_id == ann.turn_id
        assert restored.coarse == ann.coarse
        assert restored.fine == ann.fine
        assert restored.confidence == ann.confidence

    def test_json_serialization(self):
        ann = Annotation(turn_id="t8", coarse="shift", fine="topic_shift")
        d = annotation_to_dict(ann)
        json_str = json.dumps(d)
        restored = annotation_from_dict(json.loads(json_str))
        assert restored.turn_id == "t8"
        assert restored.coarse == "shift"
        assert restored.fine == "topic_shift"


class TestFineToCoarseMapping:
    """Test that every fine label's coarse parent is correct."""

    @pytest.mark.parametrize(
        "fine, expected_coarse",
        [
            ("ask_definition", "clarify"),
            ("ask_why", "clarify"),
            ("follow_up_clarification", "clarify"),
            ("ask_for_example", "expand"),
            ("provide_more_context", "expand"),
            ("request_how_to", "plan"),
            ("feasibility_check", "plan"),
            ("compare_options", "compare"),
            ("challenge_or_refine", "challenge"),
            ("topic_shift", "shift"),
            ("other", "other"),
        ],
    )
    def test_mapping(self, fine: str, expected_coarse: str):
        assert coarse_from_fine(fine) == expected_coarse  # type: ignore[arg-type]


class TestStateHintToActionMapping:
    def test_current_goal_topic_transition_maps_to_shift(self):
        assert state_hint_to_action_label("current_goal", "topic_transition") == "topic_shift"

    def test_state_goal_maps_to_plan(self):
        assert state_hint_to_action_label("current_goal", "formalize_or_execute_next_step") == "request_how_to"

    def test_blocking_issue_maps_to_feasibility(self):
        assert state_hint_to_action_label("blocking_issue", "needs_troubleshooting") == "feasibility_check"

    def test_time_pressure_maps_to_clarification(self):
        assert state_hint_to_action_label("time_pressure", "need_fast_resolution") == "follow_up_clarification"

    def test_uncertainty_maps_to_definition(self):
        assert state_hint_to_action_label("uncertainty_level", "high_uncertainty") == "ask_definition"
