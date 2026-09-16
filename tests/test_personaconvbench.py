from __future__ import annotations

from portraiture.ingest.personaconvbench import infer_reddit_action_label, split_for_author


def test_reddit_question_label() -> None:
    assert infer_reddit_action_label("Why would that happen?", "parent", 2) == "ask_question"


def test_reddit_evidence_label() -> None:
    assert infer_reddit_action_label("Source: https://example.com", "parent", 2) == "cite_evidence"


def test_reddit_disagree_label() -> None:
    assert infer_reddit_action_label("I disagree, that is not true.", "parent", 2) == "disagree_or_correct"


def test_split_is_deterministic() -> None:
    assert split_for_author("some_user") == split_for_author("some_user")
