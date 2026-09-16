from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


RecordVersion = Literal["v1"]
Speaker = Literal["user", "assistant"]
MemoryType = Literal["episodic", "semantic"]
StatusType = Literal["active", "deprecated", "uncertain"]
ImportStatus = Literal["imported", "parsed", "failed"]


@dataclass(kw_only=True)
class BaseRecord:
    id: str
    user_id: str
    created_at: str
    updated_at: str
    version: RecordVersion = "v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(kw_only=True)
class ImportedSource(BaseRecord):
    source_type: str
    source_path: str
    source_label: str | None = None
    ingest_status: ImportStatus = "imported"
    notes: str | None = None


@dataclass(kw_only=True)
class Conversation(BaseRecord):
    source_id: str
    external_conversation_id: str | None = None
    title: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    message_count: int = 0
    primary_language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class Message(BaseRecord):
    source_id: str
    conversation_id: str
    speaker: Speaker
    speaker_role: str
    timestamp: str | None = None
    content: str = ""
    content_text: str = ""
    content_tokens_est: int | None = None
    reply_to_message_id: str | None = None
    sequence_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class Session(BaseRecord):
    conversation_id: str
    start_message_id: str
    end_message_id: str
    started_at: str | None = None
    ended_at: str | None = None
    message_count: int = 0
    segmentation_method: str | None = None


@dataclass(kw_only=True)
class Episode(BaseRecord):
    conversation_id: str
    session_id: str
    start_message_id: str
    end_message_id: str
    turn_ids: list[str] = field(default_factory=list)
    topic_label: str | None = None
    topic_summary: str | None = None
    episode_index: int = 0
    started_at: str | None = None
    ended_at: str | None = None
    segmentation_method: str | None = None


@dataclass(kw_only=True)
class Turn(BaseRecord):
    conversation_id: str
    session_id: str
    episode_id: str
    user_message_id: str | None = None
    assistant_message_ids: list[str] = field(default_factory=list)
    turn_index: int = 0
    started_at: str | None = None
    ended_at: str | None = None


@dataclass(kw_only=True)
class EvidenceSpan(BaseRecord):
    conversation_id: str
    episode_id: str
    turn_id: str
    message_id: str
    speaker: Speaker
    char_start: int
    char_end: int
    text: str
    evidence_type: str
    notes: str | None = None


@dataclass(kw_only=True)
class PersonaFact(BaseRecord):
    field: str
    value: str
    confidence: float
    status: StatusType = "active"
    evidence_ids: list[str] = field(default_factory=list)
    counter_evidence_ids: list[str] = field(default_factory=list)
    support_count: int = 0
    first_observed_at: str | None = None
    last_observed_at: str | None = None
    source_method: str | None = None
    notes: str | None = None


@dataclass(kw_only=True)
class TimeScope:
    start_episode_id: str | None = None
    end_episode_id: str | None = None


@dataclass(kw_only=True)
class DynamicState(BaseRecord):
    state_type: str
    state_value: str
    confidence: float
    time_scope: TimeScope
    evidence_ids: list[str] = field(default_factory=list)
    derived_from_persona_ids: list[str] = field(default_factory=list)
    status: StatusType = "active"
    source_method: str | None = None


@dataclass(kw_only=True)
class MemoryNode(BaseRecord):
    memory_type: MemoryType
    title: str
    summary: str
    entities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    source_episode_ids: list[str] = field(default_factory=list)
    retrieval_text: str = ""
    status: StatusType = "active"


@dataclass(kw_only=True)
class EventNode(BaseRecord):
    event_type: str
    title: str
    summary: str
    conversation_id: str
    episode_id: str
    turn_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    event_time: str | None = None
    importance: float | None = None


@dataclass(kw_only=True)
class ProfileSnapshot(BaseRecord):
    snapshot_label: str
    persona_fact_ids: list[str] = field(default_factory=list)
    dynamic_state_ids: list[str] = field(default_factory=list)
    memory_node_ids: list[str] = field(default_factory=list)
    source_run_id: str | None = None


@dataclass(kw_only=True)
class ReplayExample(BaseRecord):
    episode_id: str
    target_turn_id: str
    context_turn_ids: list[str] = field(default_factory=list)
    prediction_task: str = ""
    ground_truth_label: str | None = None
    ground_truth_coarse_label: str | None = None
    ground_truth_message_id: str | None = None
    observed_state_type: str | None = None
    observed_state_value: str | None = None
    observed_state_confidence: float | None = None
    eligible_profile_snapshot_id: str | None = None
    split: Literal["train", "val", "test"] = "train"


@dataclass(kw_only=True)
class CandidateScore:
    label: str
    score: float


@dataclass(kw_only=True)
class PredictionRecord(BaseRecord):
    replay_example_id: str
    predictor_name: str
    profile_snapshot_id: str | None = None
    predicted_task: str = ""
    predicted_label: str | None = None
    predicted_coarse_label: str | None = None
    candidate_labels: list[CandidateScore] = field(default_factory=list)
    predicted_response_text: str | None = None
    reasoning_summary: str | None = None
    used_persona_fact_ids: list[str] = field(default_factory=list)
    used_state_ids: list[str] = field(default_factory=list)
    used_memory_node_ids: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class DivergenceRecord(BaseRecord):
    replay_example_id: str
    prediction_record_id: str
    ground_truth_label: str | None = None
    ground_truth_coarse_label: str | None = None
    predicted_label: str | None = None
    predicted_coarse_label: str | None = None
    is_correct: bool = False
    divergence_type: str = ""
    divergence_subtype: str | None = None
    severity: float | None = None
    critic_summary: str | None = None
    observed_state_type: str | None = None
    observed_state_value: str | None = None
    observed_state_confidence: float | None = None
    suspected_missing_persona_fact_ids: list[str] = field(default_factory=list)
    suspected_missing_state_ids: list[str] = field(default_factory=list)
    suspected_missing_memory_node_ids: list[str] = field(default_factory=list)
    recommended_refinement_action_ids: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class RefinementAction(BaseRecord):
    target_object_type: str
    target_object_id: str | None = None
    action_type: Literal["create", "update", "deprecate", "merge", "reprioritize"] = "create"
    action_reason: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    triggered_by_divergence_id: str | None = None
    applied: bool = False
    applied_in_run_id: str | None = None


@dataclass(kw_only=True)
class MetricRecord(BaseRecord):
    run_id: str
    metric_group: str
    metric_name: str
    metric_value: float
    split: str
    config_ref: str | None = None
    notes: str | None = None
