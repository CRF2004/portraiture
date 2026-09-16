"""Label taxonomy for user action classification in portraiture.

Two-layer hierarchy:
  - Coarse (high-level) labels: stable evaluation categories
  - Fine (fine-grained) labels: detailed action types for training & error analysis

Stability rules:
  - Coarse labels are frozen; changes require explicit experiment revision.
  - Fine labels can be added as ``other`` sub-categories until proven useful.
  - New fine labels only graduate when sample count AND error contribution are
    large enough to justify a dedicated category.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


# ── Coarse label space ─────────────────────────────────────────────────

CoarseAction = Literal[
    "clarify",
    "expand",
    "plan",
    "compare",
    "challenge",
    "shift",
    "other",
]

COARSE_ACTIONS: tuple[CoarseAction, ...] = (
    "clarify",
    "expand",
    "plan",
    "compare",
    "challenge",
    "shift",
    "other",
)

COARSE_DESCRIPTIONS: dict[CoarseAction, str] = {
    "clarify":   "User seeks clarification or definition (e.g., 'What does X mean?')",
    "expand":    "User provides more context or elaborates on a point",
    "plan":      "User discusses plans, steps, or feasibility ('How do I ... ?')",
    "compare":   "User compares options, trade-offs, or alternatives",
    "challenge": "User challenges, refines, or pushes back on the assistant's response",
    "shift":     "User changes topic or introduces a new line of inquiry",
    "other":     "None of the above — catch-all for rare or ambiguous actions",
}


# ── Fine label space ───────────────────────────────────────────────────

FineAction = Literal[
    "ask_definition",
    "ask_why",
    "ask_for_example",
    "request_how_to",
    "feasibility_check",
    "compare_options",
    "challenge_or_refine",
    "follow_up_clarification",
    "topic_shift",
    "provide_more_context",
    "other",
]

FINE_ACTIONS: tuple[FineAction, ...] = (
    "ask_definition",
    "ask_why",
    "ask_for_example",
    "request_how_to",
    "feasibility_check",
    "compare_options",
    "challenge_or_refine",
    "follow_up_clarification",
    "topic_shift",
    "provide_more_context",
    "other",
)

FINE_DESCRIPTIONS: dict[FineAction, str] = {
    "ask_definition":            "What is X? / Define Y",
    "ask_why":                   "Why / reasoning / justification request",
    "ask_for_example":           "Give me an example / Show me a case",
    "request_how_to":            "How do I achieve X? / Step-by-step guidance",
    "feasibility_check":         "Is X feasible? / What are the constraints?",
    "compare_options":           "Compare A vs B / Which is better?",
    "challenge_or_refine":       "That's not quite right because ... / Actually, ...",
    "follow_up_clarification":   "To clarify what I meant earlier ... / More specifically, ...",
    "topic_shift":               "Changing the subject / Switching to a new topic",
    "provide_more_context":      "Adding more background / For context, ...",
    "other":                     "None of the above",
}


# ── Mapping: fine → coarse ────────────────────────────────────────────

FINE_TO_COARSE: dict[FineAction, CoarseAction] = {
    "ask_definition":            "clarify",
    "ask_why":                   "clarify",
    "ask_for_example":           "expand",
    "request_how_to":            "plan",
    "feasibility_check":         "plan",
    "compare_options":           "compare",
    "challenge_or_refine":       "challenge",
    "follow_up_clarification":   "clarify",
    "topic_shift":               "shift",
    "provide_more_context":      "expand",
    "other":                     "other",
}

COARSE_TO_FINE: dict[CoarseAction, list[FineAction]] = {
    "clarify":   ["ask_definition", "ask_why", "follow_up_clarification"],
    "expand":    ["ask_for_example", "provide_more_context"],
    "plan":      ["request_how_to", "feasibility_check"],
    "compare":   ["compare_options"],
    "challenge": ["challenge_or_refine"],
    "shift":     ["topic_shift"],
    "other":     ["other"],
}


# ── Utility functions ──────────────────────────────────────────────────


def coarse_from_fine(fine: FineAction, default: CoarseAction = "other") -> CoarseAction:
    """Map a fine-grained label to its coarse parent."""
    return FINE_TO_COARSE.get(fine, default)


def describe(label: str) -> str:
    """Return the description of a label (works for both coarse and fine)."""
    if label in COARSE_DESCRIPTIONS:
        return COARSE_DESCRIPTIONS[label]  # type: ignore[typeddict-item]
    if label in FINE_DESCRIPTIONS:
        return FINE_DESCRIPTIONS[label]  # type: ignore[typeddict-item]
    return f"Unknown label: {label}"


# ── Annotation record ──────────────────────────────────────────────────


@dataclass
class Annotation:
    """A single annotation record for one user turn."""

    turn_id: str
    coarse: CoarseAction
    fine: FineAction
    confidence: float = 1.0   # annotator confidence (0–1)

    def __post_init__(self) -> None:
        if self.coarse not in COARSE_ACTIONS:
            raise ValueError(f"Invalid coarse label: {self.coarse!r}")
        if self.fine not in FINE_ACTIONS:
            raise ValueError(f"Invalid fine label: {self.fine!r}")
        parent = coarse_from_fine(self.fine)
        if parent != self.coarse:
            raise ValueError(
                f"Fine label {self.fine!r} maps to coarse {parent!r}, "
                f"but annotation has coarse={self.coarse!r}"
            )


# ── Serialisation ──────────────────────────────────────────────────────


def annotation_to_dict(ann: Annotation) -> dict[str, str | float]:
    return {
        "turn_id": ann.turn_id,
        "coarse": ann.coarse,
        "fine": ann.fine,
        "confidence": ann.confidence,
    }


def annotation_from_dict(d: dict[str, str | float]) -> Annotation:
    return Annotation(
        turn_id=str(d["turn_id"]),
        coarse=str(d["coarse"]),          # type: ignore[arg-type]
        fine=str(d["fine"]),              # type: ignore[arg-type]
        confidence=float(d.get("confidence", 1.0)),
    )
