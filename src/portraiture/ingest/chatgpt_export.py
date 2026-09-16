from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from portraiture.schemas import Conversation, ImportedSource, Message
from portraiture.utils.config import load_config
from portraiture.utils.io import write_jsonl


VISIBLE_CONTENT_TYPES = {
    "text",
    "multimodal_text",
    "code",
    "execution_output",
    "system_error",
    "reasoning_recap",
}

SKIPPED_CONTENT_TYPES = {
    "model_editable_context",
    "user_editable_context",
    "thoughts",
    "tether_browsing_display",
    "computer_output",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest ChatGPT export JSON into canonical JSONL.")
    parser.add_argument(
        "--config",
        default="configs/data/chatgpt_export_v1.yaml",
        help="Path to the ingest config YAML.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on how many JSON conversations to ingest.",
    )
    return parser.parse_args()


def isoformat_from_timestamp(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().isoformat()


def slugify_path_component(value: str) -> str:
    cleaned = []
    for ch in value.lower():
        if ch.isalnum():
            cleaned.append(ch)
        elif ch in {"-", "_"}:
            cleaned.append(ch)
        else:
            cleaned.append("_")
    slug = "".join(cleaned).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "unknown"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_text_from_content(content: dict[str, Any]) -> str:
    content_type = content.get("content_type")
    if content_type not in VISIBLE_CONTENT_TYPES:
        return ""

    if content_type in {"text", "multimodal_text"}:
        parts = content.get("parts") or []
        text_parts = [part for part in parts if isinstance(part, str) and part.strip()]
        return "\n\n".join(text_parts).strip()

    if content_type == "code":
        return str(content.get("text") or "").strip()

    if content_type == "execution_output":
        return str(content.get("text") or "").strip()

    if content_type == "system_error":
        return str(content.get("text") or "").strip()

    if content_type == "reasoning_recap":
        return str(content.get("content") or "").strip()

    return ""


def discover_json_files(input_root: Path, limit: int | None = None) -> list[Path]:
    files = sorted(path for path in input_root.rglob("*.json") if path.is_file())
    if limit is not None:
        return files[:limit]
    return files


def preorder_nodes(mapping: dict[str, Any], root_id: str) -> list[str]:
    ordered: list[str] = []
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visited:
            return
        visited.add(node_id)
        ordered.append(node_id)
        node = mapping.get(node_id) or {}
        for child_id in node.get("children") or []:
            if child_id in mapping:
                visit(child_id)

    visit(root_id)
    for node_id in mapping:
        if node_id not in visited:
            visit(node_id)
    return ordered


def normalize_speaker(role: str | None, normalize_roles: dict[str, str]) -> str | None:
    if role is None:
        return None
    return normalize_roles.get(role, role)


def nearest_extracted_parent(node_id: str, mapping: dict[str, Any], extracted_node_to_message_id: dict[str, str]) -> str | None:
    current = (mapping.get(node_id) or {}).get("parent")
    while current:
        if current in extracted_node_to_message_id:
            return extracted_node_to_message_id[current]
        current = (mapping.get(current) or {}).get("parent")
    return None


def build_source_id(relative_path: Path) -> str:
    return f"src_{slugify_path_component(relative_path.as_posix())}"


def build_conversation_record(
    obj: dict[str, Any],
    source_id: str,
    user_id: str,
    relative_path: Path,
    created_at: str,
    updated_at: str,
    message_count: int,
) -> Conversation:
    metadata = {
        "default_model_slug": obj.get("default_model_slug"),
        "conversation_origin": obj.get("conversation_origin"),
        "relative_path": relative_path.as_posix(),
    }
    markdown_path = relative_path.with_suffix(".md")
    metadata["paired_markdown_path"] = markdown_path.as_posix()
    return Conversation(
        id=f"conv_{obj.get('conversation_id') or slugify_path_component(relative_path.stem)}",
        user_id=user_id,
        source_id=source_id,
        external_conversation_id=obj.get("conversation_id"),
        title=obj.get("title"),
        started_at=isoformat_from_timestamp(obj.get("create_time")),
        ended_at=isoformat_from_timestamp(obj.get("update_time")),
        message_count=message_count,
        primary_language=None,
        metadata=metadata,
        created_at=created_at,
        updated_at=updated_at,
    )


def iter_messages(
    obj: dict[str, Any],
    conversation_record: Conversation,
    source_id: str,
    normalize_roles: dict[str, str],
    user_id: str,
    created_at: str,
    updated_at: str,
) -> Iterable[Message]:
    mapping = obj.get("mapping") or {}
    root_id = "client-created-root" if "client-created-root" in mapping else next(iter(mapping), None)
    if root_id is None:
        return []

    node_order = preorder_nodes(mapping, root_id)
    extracted_node_to_message_id: dict[str, str] = {}
    extracted_records: list[Message] = []

    for node_id in node_order:
        node = mapping.get(node_id) or {}
        message = node.get("message")
        if not isinstance(message, dict):
            continue

        author = message.get("author") or {}
        original_role = author.get("role")
        speaker = normalize_speaker(original_role, normalize_roles)
        if speaker not in {"user", "assistant"}:
            continue

        content = message.get("content") or {}
        content_type = content.get("content_type")
        if content_type in SKIPPED_CONTENT_TYPES:
            continue

        content_text = extract_text_from_content(content)
        if not content_text:
            continue

        canonical_message_id = f"msg_{message.get('id') or slugify_path_component(node_id)}"
        extracted_node_to_message_id[node_id] = canonical_message_id
        extracted_records.append(
            Message(
                id=canonical_message_id,
                user_id=user_id,
                source_id=source_id,
                conversation_id=conversation_record.id,
                speaker=speaker,
                speaker_role=original_role or speaker,
                timestamp=isoformat_from_timestamp(message.get("create_time")),
                content=content_text,
                content_text=content_text,
                content_tokens_est=len(content_text.split()),
                reply_to_message_id=None,
                sequence_index=0,
                metadata={
                    "raw_node_id": node_id,
                    "raw_message_id": message.get("id"),
                    "content_type": content_type,
                    "recipient": message.get("recipient"),
                    "channel": message.get("channel"),
                    "author_metadata": author.get("metadata") or {},
                    "message_metadata": message.get("metadata") or {},
                },
                created_at=created_at,
                updated_at=updated_at,
            )
        )

    for idx, record in enumerate(extracted_records):
        raw_node_id = record.metadata["raw_node_id"]
        record.sequence_index = idx
        record.reply_to_message_id = nearest_extracted_parent(raw_node_id, mapping, extracted_node_to_message_id)

    return extracted_records


def ingest_file(path: Path, input_root: Path, normalize_roles: dict[str, str]) -> tuple[ImportedSource, Conversation, list[Message]]:
    obj = read_json(path)
    relative_path = path.relative_to(input_root)
    source_id = build_source_id(relative_path)
    user_id = "user_demo"
    now = datetime.now().astimezone().isoformat()

    source_record = ImportedSource(
        id=source_id,
        user_id=user_id,
        source_type="chatgpt_export",
        source_path=path.as_posix(),
        source_label=relative_path.as_posix(),
        ingest_status="parsed",
        notes=None,
        created_at=now,
        updated_at=now,
    )

    provisional_conversation = build_conversation_record(
        obj=obj,
        source_id=source_id,
        user_id=user_id,
        relative_path=relative_path,
        created_at=now,
        updated_at=now,
        message_count=0,
    )
    messages = list(
        iter_messages(
            obj=obj,
            conversation_record=provisional_conversation,
            source_id=source_id,
            normalize_roles=normalize_roles,
            user_id=user_id,
            created_at=now,
            updated_at=now,
        )
    )
    conversation_record = build_conversation_record(
        obj=obj,
        source_id=source_id,
        user_id=user_id,
        relative_path=relative_path,
        created_at=now,
        updated_at=now,
        message_count=len(messages),
    )
    for message in messages:
        message.conversation_id = conversation_record.id
    return source_record, conversation_record, messages


def main() -> None:
    args = parse_args()
    config_path = Path(args.config)
    config = load_config(config_path)
    input_root = Path(config["input_root"])
    outputs = config["outputs"]
    normalize_roles = config.get("message_extraction", {}).get("normalize_roles", {})

    imported_sources: list[dict[str, Any]] = []
    conversations: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = []

    files = discover_json_files(input_root=input_root, limit=args.limit)
    for path in files:
        source_record, conversation_record, message_records = ingest_file(
            path=path,
            input_root=input_root,
            normalize_roles=normalize_roles,
        )
        imported_sources.append(asdict(source_record))
        conversations.append(asdict(conversation_record))
        messages.extend(asdict(message) for message in message_records)

    write_jsonl(Path(outputs["imported_source_manifest"]), imported_sources)
    write_jsonl(Path(outputs["conversations"]), conversations)
    write_jsonl(Path(outputs["messages"]), messages)

    print(f"Ingested {len(files)} conversations")
    print(f"Wrote {len(imported_sources)} imported source records")
    print(f"Wrote {len(conversations)} conversation records")
    print(f"Wrote {len(messages)} message records")


if __name__ == "__main__":
    main()
