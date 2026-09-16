from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from portraiture.ingest.personaconvbench import infer_reddit_action_label
from portraiture.utils.io import read_jsonl, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a stratified Reddit proxy-label audit.")
    parser.add_argument(
        "--input",
        default="data/processed/personaconvbench/replay_examples.jsonl",
    )
    parser.add_argument(
        "--output-jsonl",
        default="data/processed/personaconvbench/label_audit_90.jsonl",
    )
    parser.add_argument(
        "--output-md",
        default="docs/personaconvbench_label_audit.md",
    )
    parser.add_argument("--per-label", type=int, default=10)
    return parser.parse_args()


def truncate(text: str, limit: int = 420) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def secondary_label(text: str, parent_text: str, depth: int) -> str:
    """A deliberately simpler re-check used to find unstable proxy labels."""
    return infer_reddit_action_label(text, parent_text, depth)


def audit_status(example: dict[str, Any]) -> tuple[str, str]:
    label = example["ground_truth_label"]
    target = example.get("target_text", "")
    parent = example.get("metadata", {}).get("parent_text", "")
    depth = int(example.get("depth") or 0)
    relabel = secondary_label(target, parent, depth)
    text = target.lower()

    if label != relabel:
        return "likely_error", f"secondary rule suggests `{relabel}`"

    if label == "ask_question" and "?" not in target and not any(w in text for w in ("why", "how", "what", "where", "when", "who")):
        return "borderline", "question label relies on weak lexical marker"
    if label == "personal_experience" and not any(w in text for w in (" i ", "i'm", "i've", "my ", "me ", "we ", "our ")):
        return "borderline", "personal marker is weak after context stripping"
    if label == "topic_branch":
        return "borderline", "topic-branch is a coarse fallback label"
    if label == "short_reply" and len(target.split()) > 45:
        return "borderline", "longer reply fell through to short_reply"
    if label == "elaborate_argument" and len(target) < 240:
        return "likely_error", "elaborate label below length threshold"
    return "acceptable", "rule trigger is visible in target text"


def select_examples(examples: list[dict[str, Any]], per_label: int) -> list[dict[str, Any]]:
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for example in sorted(examples, key=lambda item: (item["ground_truth_label"], item["id"])):
        by_label[example["ground_truth_label"]].append(example)

    selected: list[dict[str, Any]] = []
    for label in sorted(by_label):
        rows = by_label[label]
        if len(rows) <= per_label:
            selected.extend(rows)
            continue
        if per_label == 1:
            indices = [len(rows) // 2]
        else:
            indices = [round(i * (len(rows) - 1) / (per_label - 1)) for i in range(per_label)]
        selected.extend(rows[index] for index in indices)
    return selected


def render_markdown(audited: list[dict[str, Any]]) -> str:
    status_counts = Counter(row["audit_status"] for row in audited)
    label_status = defaultdict(Counter)
    for row in audited:
        label_status[row["ground_truth_label"]][row["audit_status"]] += 1

    lines = [
        "# PersonaConvBench Proxy Label Audit",
        "",
        "This is a deterministic stratified spot audit over the first PersonaConvBench Reddit replay conversion.",
        "It checks whether each proxy label is visibly supported by the target Reddit reply under the current rule set.",
        "",
        "## Summary",
        "",
        f"- Audited examples: {len(audited)}",
        f"- Acceptable: {status_counts.get('acceptable', 0)}",
        f"- Borderline: {status_counts.get('borderline', 0)}",
        f"- Likely error: {status_counts.get('likely_error', 0)}",
        "",
        "## Label-Level Counts",
        "",
        "| Label | Acceptable | Borderline | Likely error |",
        "|---|---:|---:|---:|",
    ]
    for label in sorted(label_status):
        counts = label_status[label]
        lines.append(
            f"| `{label}` | {counts.get('acceptable', 0)} | {counts.get('borderline', 0)} | {counts.get('likely_error', 0)} |"
        )

    lines.extend(
        [
            "",
            "## Main Noise Modes",
            "",
            "- `topic_branch` is intentionally broad and should be treated as a fallback, not a precise semantic intent.",
            "- `ask_question` is comparatively reliable when explicit question marks or wh-words are present, but rhetorical questions are not separated.",
            "- `personal_experience` depends on first-person lexical markers and can capture general opinions written in first person.",
            "- `short_reply` is a residual class and should not be used as strong behavioral evidence.",
            "",
            "## Audited Examples",
            "",
        ]
    )
    for index, row in enumerate(audited, 1):
        lines.extend(
            [
                f"### {index}. `{row['ground_truth_label']}` / {row['audit_status']}",
                "",
                f"- Reason: {row['audit_reason']}",
                f"- Subreddit: `{row.get('subreddit')}`",
                f"- Depth: {row.get('depth')}",
                f"- Parent: {truncate(row.get('metadata', {}).get('parent_text', ''))}",
                f"- Target: {truncate(row.get('target_text', ''))}",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    examples = read_jsonl(Path(args.input))
    selected = select_examples(examples, args.per_label)
    audited: list[dict[str, Any]] = []
    for example in selected:
        status, reason = audit_status(example)
        row = dict(example)
        row["audit_status"] = status
        row["audit_reason"] = reason
        audited.append(row)

    write_jsonl(Path(args.output_jsonl), audited)
    output_md = Path(args.output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(render_markdown(audited), encoding="utf-8")
    print(json.dumps(Counter(row["audit_status"] for row in audited), indent=2))


if __name__ == "__main__":
    main()
