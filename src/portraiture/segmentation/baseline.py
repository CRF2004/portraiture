from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from portraiture.schemas import Episode, Session, Turn
from portraiture.utils.config import load_config
from portraiture.utils.io import read_jsonl, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Segment normalized messages into sessions, episodes, and turns.")
    parser.add_argument(
        "--config",
        default="configs/segmentation/baseline_v1.yaml",
        help="Path to the segmentation config YAML.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on how many conversations to segment.",
    )
    return parser.parse_args()


def parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def minutes_between(left: str | None, right: str | None) -> float | None:
    left_dt = parse_iso_timestamp(left)
    right_dt = parse_iso_timestamp(right)
    if left_dt is None or right_dt is None:
        return None
    return (right_dt - left_dt).total_seconds() / 60.0


def simple_tokenize(text: str) -> set[str]:
    token = []
    tokens: set[str] = set()
    for ch in text.lower():
        if ch.isalnum():
            token.append(ch)
            continue
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
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return overlap / union if union else 0.0


def should_start_new_session(previous_message: dict[str, Any], current_message: dict[str, Any], session_gap_minutes: int) -> bool:
    gap = minutes_between(previous_message.get("timestamp"), current_message.get("timestamp"))
    return gap is not None and gap > session_gap_minutes


def build_sessions(messages: list[dict[str, Any]], session_gap_minutes: int) -> list[list[dict[str, Any]]]:
    if not messages:
        return []

    sessions: list[list[dict[str, Any]]] = [[messages[0]]]
    for message in messages[1:]:
        previous = sessions[-1][-1]
        if should_start_new_session(previous, message, session_gap_minutes):
            sessions.append([message])
        else:
            sessions[-1].append(message)
    return sessions


def build_turns(session_messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    current_turn: dict[str, Any] | None = None

    for message in session_messages:
        speaker = message["speaker"]
        if speaker == "user":
            if current_turn is not None:
                turns.append(current_turn)
            current_turn = {
                "user_message_id": message["id"],
                "assistant_message_ids": [],
                "messages": [message],
            }
            continue

        if current_turn is None:
            current_turn = {
                "user_message_id": None,
                "assistant_message_ids": [message["id"]],
                "messages": [message],
            }
        else:
            current_turn["assistant_message_ids"].append(message["id"])
            current_turn["messages"].append(message)

    if current_turn is not None:
        turns.append(current_turn)
    return turns


def user_text_for_turn(turn: dict[str, Any], message_by_id: dict[str, dict[str, Any]]) -> str:
    message_id = turn.get("user_message_id")
    if message_id is None:
        return ""
    return message_by_id[message_id]["content_text"]


def should_start_new_episode(
    previous_turn: dict[str, Any],
    current_turn: dict[str, Any],
    message_by_id: dict[str, dict[str, Any]],
    episode_gap_minutes: int,
    similarity_threshold: float,
    min_user_chars_for_similarity: int,
) -> bool:
    previous_messages = previous_turn["messages"]
    current_messages = current_turn["messages"]
    gap = minutes_between(previous_messages[-1].get("timestamp"), current_messages[0].get("timestamp"))
    if gap is not None and gap > episode_gap_minutes:
        return True

    previous_text = user_text_for_turn(previous_turn, message_by_id).strip()
    current_text = user_text_for_turn(current_turn, message_by_id).strip()
    if not previous_text or not current_text:
        return False
    if len(previous_text) < min_user_chars_for_similarity or len(current_text) < min_user_chars_for_similarity:
        return False

    similarity = jaccard_similarity(previous_text, current_text)
    return similarity < similarity_threshold


def build_episodes(
    turns: list[dict[str, Any]],
    message_by_id: dict[str, dict[str, Any]],
    episode_gap_minutes: int,
    similarity_threshold: float,
    min_user_chars_for_similarity: int,
) -> list[list[dict[str, Any]]]:
    if not turns:
        return []

    episodes: list[list[dict[str, Any]]] = [[turns[0]]]
    for turn in turns[1:]:
        previous_turn = episodes[-1][-1]
        if should_start_new_episode(
            previous_turn=previous_turn,
            current_turn=turn,
            message_by_id=message_by_id,
            episode_gap_minutes=episode_gap_minutes,
            similarity_threshold=similarity_threshold,
            min_user_chars_for_similarity=min_user_chars_for_similarity,
        ):
            episodes.append([turn])
        else:
            episodes[-1].append(turn)
    return episodes


def summarise_episode_topic(turns: list[dict[str, Any]], message_by_id: dict[str, dict[str, Any]], max_chars: int) -> str | None:
    user_texts = []
    for turn in turns:
        text = user_text_for_turn(turn, message_by_id).strip()
        if text:
            user_texts.append(text)
        if len(user_texts) >= 2:
            break
    if not user_texts:
        return None
    summary = " ".join(user_texts)
    return summary[:max_chars]


def segment_conversation(
    conversation: dict[str, Any],
    messages: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[list[Session], list[Episode], list[Turn]]:
    heuristics = config["heuristics"]
    session_gap_minutes = heuristics["session_gap_minutes"]
    episode_gap_minutes = heuristics["episode_gap_minutes"]
    similarity_threshold = heuristics["topic_shift_similarity_threshold"]
    min_user_chars_for_similarity = heuristics["min_user_chars_for_similarity"]
    topic_summary_chars = heuristics["topic_summary_chars"]
    now = datetime.now().astimezone().isoformat()

    message_by_id = {message["id"]: message for message in messages}
    sessions_data = build_sessions(messages, session_gap_minutes=session_gap_minutes)

    sessions: list[Session] = []
    episodes: list[Episode] = []
    turns: list[Turn] = []

    for session_index, session_messages in enumerate(sessions_data):
        session_id = f"sess_{conversation['external_conversation_id']}_{session_index:03d}"
        session_record = Session(
            id=session_id,
            user_id=conversation["user_id"],
            conversation_id=conversation["id"],
            start_message_id=session_messages[0]["id"],
            end_message_id=session_messages[-1]["id"],
            started_at=session_messages[0].get("timestamp"),
            ended_at=session_messages[-1].get("timestamp"),
            message_count=len(session_messages),
            segmentation_method=config["session_method"],
            created_at=now,
            updated_at=now,
        )
        sessions.append(session_record)

        turns_data = build_turns(session_messages)
        session_turn_records: list[Turn] = []
        for turn_index, turn_data in enumerate(turns_data):
            turn_messages = turn_data["messages"]
            turn_record = Turn(
                id=f"turn_{conversation['external_conversation_id']}_{session_index:03d}_{turn_index:03d}",
                user_id=conversation["user_id"],
                conversation_id=conversation["id"],
                session_id=session_id,
                episode_id="",
                user_message_id=turn_data["user_message_id"],
                assistant_message_ids=turn_data["assistant_message_ids"],
                turn_index=turn_index,
                started_at=turn_messages[0].get("timestamp"),
                ended_at=turn_messages[-1].get("timestamp"),
                created_at=now,
                updated_at=now,
            )
            turns.append(turn_record)
            session_turn_records.append(turn_record)
            turn_data["turn_id"] = turn_record.id

        episodes_data = build_episodes(
            turns=turns_data,
            message_by_id=message_by_id,
            episode_gap_minutes=episode_gap_minutes,
            similarity_threshold=similarity_threshold,
            min_user_chars_for_similarity=min_user_chars_for_similarity,
        )

        for episode_index, episode_turns in enumerate(episodes_data):
            episode_turn_ids = [turn["turn_id"] for turn in episode_turns]
            episode_messages = [message for turn in episode_turns for message in turn["messages"]]
            episode_id = f"ep_{conversation['external_conversation_id']}_{session_index:03d}_{episode_index:03d}"
            episode_record = Episode(
                id=episode_id,
                user_id=conversation["user_id"],
                conversation_id=conversation["id"],
                session_id=session_id,
                start_message_id=episode_messages[0]["id"],
                end_message_id=episode_messages[-1]["id"],
                turn_ids=episode_turn_ids,
                topic_label=None,
                topic_summary=summarise_episode_topic(episode_turns, message_by_id, topic_summary_chars),
                episode_index=episode_index,
                started_at=episode_messages[0].get("timestamp"),
                ended_at=episode_messages[-1].get("timestamp"),
                segmentation_method=config["episode_method"],
                created_at=now,
                updated_at=now,
            )
            episodes.append(episode_record)

            episode_turn_id_set = set(episode_turn_ids)
            for turn_record in session_turn_records:
                if turn_record.id in episode_turn_id_set:
                    turn_record.episode_id = episode_id

    return sessions, episodes, turns


def main() -> None:
    args = parse_args()
    config = load_config(Path(args.config))
    inputs = config["inputs"]
    outputs = config["outputs"]

    conversations = read_jsonl(Path(inputs["conversations"]))
    messages = read_jsonl(Path(inputs["messages"]))
    if args.limit is not None:
        conversations = conversations[: args.limit]
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

    write_jsonl(Path(outputs["sessions"]), sessions)
    write_jsonl(Path(outputs["episodes"]), episodes)
    write_jsonl(Path(outputs["turns"]), turns)

    print(f"Segmented {len(conversations)} conversations")
    print(f"Wrote {len(sessions)} sessions")
    print(f"Wrote {len(episodes)} episodes")
    print(f"Wrote {len(turns)} turns")


if __name__ == "__main__":
    main()
