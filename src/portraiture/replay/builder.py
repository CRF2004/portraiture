from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from portraiture.schemas import ReplayExample
from portraiture.replay.signals import coarse_label_for_action, infer_action_label, infer_state_hint_from_context
from portraiture.utils.config import load_config
from portraiture.utils.io import read_jsonl, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build replay examples from segmented conversations.")
    parser.add_argument(
        "--config",
        default="configs/replay/baseline_v1.yaml",
        help="Path to the replay builder config YAML.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on how many episodes to process.",
    )
    return parser.parse_args()


def normalize_text(text: str) -> str:
    return " ".join(text.split())


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


def assign_split_by_time(examples: list[dict[str, Any]], ratios: dict[str, float]) -> None:
    total = len(examples)
    train_end = int(total * ratios["train"])
    val_end = train_end + int(total * ratios["val"])
    for idx, example in enumerate(examples):
        if idx < train_end:
            example["split"] = "train"
        elif idx < val_end:
            example["split"] = "val"
        else:
            example["split"] = "test"


def build_examples(
    episodes: list[dict[str, Any]],
    turns_by_id: dict[str, dict[str, Any]],
    messages_by_id: dict[str, dict[str, Any]],
    max_context_turns: int,
    min_context_turns: int,
    similarity_threshold: float,
) -> list[dict[str, Any]]:
    now = datetime.now().astimezone().isoformat()
    examples: list[dict[str, Any]] = []

    for episode in episodes:
        turn_ids = episode["turn_ids"]
        if len(turn_ids) <= min_context_turns:
            continue

        for target_index in range(min_context_turns, len(turn_ids)):
            target_turn = turns_by_id[turn_ids[target_index]]
            target_message_id = target_turn.get("user_message_id")
            if target_message_id is None:
                continue

            context_start = max(0, target_index - max_context_turns)
            context_turn_ids = turn_ids[context_start:target_index]
            if len(context_turn_ids) < min_context_turns:
                continue

            target_text = messages_by_id[target_message_id]["content_text"]
            previous_text = None
            previous_turn = turns_by_id[turn_ids[target_index - 1]]
            previous_user_message_id = previous_turn.get("user_message_id")
            if previous_user_message_id:
                previous_text = messages_by_id[previous_user_message_id]["content_text"]

            action_label = infer_action_label(
                current_text=target_text,
                previous_text=previous_text,
                similarity_threshold=similarity_threshold,
            )
            coarse_label = coarse_label_for_action(action_label)
            context_texts: list[str] = []
            for turn_id in context_turn_ids:
                turn = turns_by_id.get(turn_id)
                if not turn:
                    continue
                user_message_id = turn.get("user_message_id")
                if not user_message_id:
                    continue
                message = messages_by_id.get(user_message_id)
                if not message:
                    continue
                context_text = message.get("content_text", "").strip()
                if context_text:
                    context_texts.append(context_text)
            state_hint = infer_state_hint_from_context(context_texts)

            example = ReplayExample(
                id=f"replay_{episode['id']}_{target_index:03d}",
                user_id=episode["user_id"],
                episode_id=episode["id"],
                target_turn_id=target_turn["id"],
                context_turn_ids=context_turn_ids,
                prediction_task="next_user_action",
                ground_truth_label=action_label,
                ground_truth_coarse_label=coarse_label,
                ground_truth_message_id=target_message_id,
                observed_state_type=state_hint["state_type"],
                observed_state_value=state_hint["state_value"],
                observed_state_confidence=state_hint["confidence"],
                eligible_profile_snapshot_id=None,
                split="train",
                created_at=now,
                updated_at=now,
            )
            example_dict = asdict(example)
            example_dict["metadata"] = {
                "target_user_text": target_text[:400],
                "previous_user_text": (previous_text or "")[:400],
                "conversation_id": episode["conversation_id"],
                "session_id": episode["session_id"],
                "target_timestamp": target_turn.get("started_at"),
                "state_hint_type": state_hint["state_type"],
                "state_hint_value": state_hint["state_value"],
                "state_hint_confidence": state_hint["confidence"],
                "state_hint_reason": state_hint["reason"],
            }
            examples.append(example_dict)

    examples.sort(key=lambda item: item["metadata"]["target_timestamp"] or "")
    return examples


def main() -> None:
    args = parse_args()
    config = load_config(Path(args.config))
    inputs = config["inputs"]
    outputs = config["outputs"]
    task = config["task"]
    split_cfg = config["split"]

    episodes = read_jsonl(Path(inputs["episodes"]))
    turns = read_jsonl(Path(inputs["turns"]))
    messages = read_jsonl(Path(inputs["messages"]))

    if args.limit is not None:
        episodes = episodes[: args.limit]
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
    write_jsonl(Path(outputs["replay_examples"]), examples)
    write_jsonl(
        Path(outputs["label_distribution"]),
        [
            {
                "label": label,
                "count": count,
            }
            for label, count in sorted(label_counts.items())
        ],
    )

    print(f"Built {len(examples)} replay examples")
    print(f"Labels: {dict(label_counts)}")


if __name__ == "__main__":
    main()
