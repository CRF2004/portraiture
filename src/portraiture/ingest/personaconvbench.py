from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from portraiture.utils.io import write_jsonl


QUESTION_MARKERS = ("?", "？", "why", "how", "what", "where", "when", "who")
AGREE_MARKERS = (
    "agree",
    "exactly",
    "true",
    "yes",
    "yeah",
    "yep",
    "same",
    "correct",
    "right",
)
DISAGREE_MARKERS = (
    "disagree",
    "wrong",
    "false",
    "no,",
    "no.",
    "not true",
    "isn't",
    "aren't",
    "can't",
    "cannot",
    "however",
    "but ",
)
EVIDENCE_MARKERS = ("source", "link", "study", "data", "according", "evidence", "article")
PERSONAL_MARKERS = ("i ", "i'm", "i've", "my ", "me ", "we ", "our ")
HUMOR_MARKERS = ("lol", "lmao", "haha", "/s", "joke")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Reddit replay examples from PERSONA-Bench.")
    parser.add_argument(
        "--input",
        default="data/raw/personaconvbench_repo/Raw_Data_Postized.json",
        help="Raw PERSONA-Bench JSON file.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/personaconvbench/replay_examples.jsonl",
        help="Output JSONL replay examples.",
    )
    parser.add_argument(
        "--summary",
        default="data/processed/personaconvbench/summary.json",
        help="Output summary JSON.",
    )
    parser.add_argument("--max-posts", type=int, default=None)
    parser.add_argument("--min-context", type=int, default=1)
    parser.add_argument("--max-context", type=int, default=6)
    parser.add_argument("--min-author-examples", type=int, default=12)
    return parser.parse_args()


def normalize_text(text: str | None) -> str:
    return " ".join((text or "").split())


def text_tokens(text: str) -> set[str]:
    return {token.strip(".,!?;:\"'()[]{}").lower() for token in text.split() if token.strip()}


def jaccard(left: str, right: str) -> float:
    left_tokens = text_tokens(left)
    right_tokens = text_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def infer_reddit_action_label(body: str, parent_text: str, depth: int) -> str:
    text = normalize_text(body).lower()
    parent = normalize_text(parent_text)
    if not text:
        return "other"
    if any(marker in text for marker in QUESTION_MARKERS):
        return "ask_question"
    if any(marker in text for marker in EVIDENCE_MARKERS) or "http://" in text or "https://" in text:
        return "cite_evidence"
    if any(marker in text for marker in DISAGREE_MARKERS):
        return "disagree_or_correct"
    if any(marker in text for marker in AGREE_MARKERS):
        return "agree_or_affirm"
    if any(marker in text for marker in HUMOR_MARKERS):
        return "humor_or_reaction"
    if any(marker in text for marker in PERSONAL_MARKERS):
        return "personal_experience"
    if len(text) >= 240:
        return "elaborate_argument"
    if depth <= 1 or jaccard(text, parent) < 0.04:
        return "topic_branch"
    return "short_reply"


def split_for_author(author: str) -> str:
    bucket = sum(ord(ch) for ch in author) % 10
    if bucket < 7:
        return "train"
    if bucket < 8:
        return "val"
    return "test"


def iter_comment_paths(
    comments: list[dict[str, Any]],
    *,
    post: dict[str, Any],
    parent_chain: list[dict[str, Any]],
    depth: int,
) -> Iterable[dict[str, Any]]:
    for index, comment in enumerate(comments):
        body = normalize_text(comment.get("body"))
        author = normalize_text(comment.get("author"))
        if not body or not author or author in {"[deleted]", "AutoModerator"}:
            continue
        chain = parent_chain + [
            {
                "author": author,
                "text": body,
                "timestamp": comment.get("timestamp"),
                "score": comment.get("score"),
                "depth": depth,
                "index": index,
            }
        ]
        parent_text = parent_chain[-1]["text"] if parent_chain else normalize_text(post.get("content") or post.get("title"))
        yield {
            "comment": comment,
            "chain": chain,
            "parent_text": parent_text,
            "depth": depth,
            "index": index,
        }
        replies = comment.get("replies")
        if isinstance(replies, list) and replies:
            yield from iter_comment_paths(
                replies,
                post=post,
                parent_chain=chain,
                depth=depth + 1,
            )


def build_examples(
    posts: list[dict[str, Any]],
    *,
    min_context: int,
    max_context: int,
    min_author_examples: int,
) -> list[dict[str, Any]]:
    created_at = datetime.now().astimezone().isoformat()
    raw_examples: list[dict[str, Any]] = []

    for post_index, post in enumerate(posts):
        post_text = normalize_text(f"{post.get('title', '')}\n{post.get('content', '')}")
        post_context = {
            "author": normalize_text(post.get("author")),
            "text": post_text,
            "timestamp": post.get("timestamp"),
            "score": post.get("score"),
            "depth": 0,
            "index": -1,
        }
        for path_item in iter_comment_paths(
            post.get("comments") or [],
            post=post,
            parent_chain=[post_context],
            depth=1,
        ):
            chain = path_item["chain"]
            target = chain[-1]
            context_chain = chain[:-1]
            if len(context_chain) < min_context:
                continue
            context_items = context_chain[-max_context:]
            target_text = target["text"]
            label = infer_reddit_action_label(target_text, path_item["parent_text"], target["depth"])
            example_id = f"pcb_{post_index:05d}_{target['depth']:03d}_{path_item['index']:04d}_{len(raw_examples):07d}"
            raw_examples.append(
                {
                    "id": example_id,
                    "user_id": target["author"],
                    "thread_id": post.get("url") or f"post_{post_index}",
                    "subreddit": post.get("__sub__"),
                    "split": split_for_author(target["author"]),
                    "ground_truth_label": label,
                    "target_text": target_text,
                    "context_text": "\n".join(item["text"] for item in context_items if item.get("text")),
                    "context_authors": [item["author"] for item in context_items],
                    "target_timestamp": target.get("timestamp"),
                    "depth": target["depth"],
                    "score": target.get("score"),
                    "metadata": {
                        "post_title": post.get("title"),
                        "post_author": post.get("author"),
                        "post_timestamp": post.get("timestamp"),
                        "parent_text": path_item["parent_text"][:500],
                        "created_at": created_at,
                    },
                }
            )

    author_counts = Counter(example["user_id"] for example in raw_examples)
    examples = [
        example
        for example in raw_examples
        if author_counts[example["user_id"]] >= min_author_examples
    ]
    return examples


def main() -> None:
    args = parse_args()
    with Path(args.input).open(encoding="utf-8") as f:
        posts = json.load(f)
    if args.max_posts is not None:
        posts = posts[: args.max_posts]

    examples = build_examples(
        posts,
        min_context=args.min_context,
        max_context=args.max_context,
        min_author_examples=args.min_author_examples,
    )
    label_counts = Counter(example["ground_truth_label"] for example in examples)
    split_counts = Counter(example["split"] for example in examples)
    author_counts = Counter(example["user_id"] for example in examples)

    write_jsonl(Path(args.output), examples)
    summary = {
        "examples": len(examples),
        "authors": len(author_counts),
        "labels": dict(sorted(label_counts.items())),
        "splits": dict(sorted(split_counts.items())),
        "min_author_examples": args.min_author_examples,
        "max_posts": args.max_posts,
    }
    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    Path(args.summary).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
