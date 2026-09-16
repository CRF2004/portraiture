from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from portraiture.utils.io import read_jsonl, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate PersonaConvBench Reddit replay baselines.")
    parser.add_argument(
        "--input",
        default="data/processed/personaconvbench/replay_examples.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed/personaconvbench/evaluation",
    )
    parser.add_argument("--max-features", type=int, default=30000)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-train", type=int, default=None)
    parser.add_argument("--max-val", type=int, default=None)
    parser.add_argument("--max-test", type=int, default=None)
    parser.add_argument("--nn-batch-size", type=int, default=500)
    return parser.parse_args()


def accuracy(y_true: list[str], y_pred: list[str]) -> float:
    if not y_true:
        return 0.0
    return sum(1 for gold, pred in zip(y_true, y_pred) if gold == pred) / len(y_true)


def macro_f1(y_true: list[str], y_pred: list[str]) -> float:
    labels = sorted(set(y_true) | set(y_pred))
    if not labels:
        return 0.0
    scores: list[float] = []
    for label in labels:
        tp = sum(1 for gold, pred in zip(y_true, y_pred) if gold == label and pred == label)
        fp = sum(1 for gold, pred in zip(y_true, y_pred) if gold != label and pred == label)
        fn = sum(1 for gold, pred in zip(y_true, y_pred) if gold == label and pred != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores)


def context_text(example: dict[str, Any]) -> str:
    return f"{example.get('subreddit', '')}\n{example.get('context_text', '')}"


def majority_label(examples: list[dict[str, Any]]) -> str:
    return Counter(example["ground_truth_label"] for example in examples).most_common(1)[0][0]


def predict_subreddit_prior(train: list[dict[str, Any]], test: list[dict[str, Any]]) -> list[str]:
    default = majority_label(train)
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for example in train:
        counts[example.get("subreddit") or ""][example["ground_truth_label"]] += 1
    priors = {
        subreddit: counter.most_common(1)[0][0]
        for subreddit, counter in counts.items()
    }
    return [priors.get(example.get("subreddit") or "", default) for example in test]


def predict_tfidf_nn(
    train: list[dict[str, Any]],
    test: list[dict[str, Any]],
    *,
    top_k: int,
    max_features: int,
    batch_size: int,
) -> list[str]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    train_texts = [context_text(example) for example in train]
    test_texts = [context_text(example) for example in test]
    train_labels = [example["ground_truth_label"] for example in train]
    default = majority_label(train)
    vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        max_features=max_features,
        sublinear_tf=True,
    )
    x_train = vectorizer.fit_transform(train_texts)
    x_test = vectorizer.transform(test_texts)
    predictions: list[str] = []
    for start in range(0, x_test.shape[0], batch_size):
        sim = cosine_similarity(x_test[start : start + batch_size], x_train)
        for row in sim:
            ranked = sorted(enumerate(row), key=lambda item: float(item[1]), reverse=True)[:top_k]
            votes: dict[str, float] = defaultdict(float)
            for index, score in ranked:
                if score > 0:
                    votes[train_labels[index]] += float(score)
            if votes:
                predictions.append(sorted(votes.items(), key=lambda item: (-item[1], item[0]))[0][0])
            else:
                predictions.append(default)
    return predictions


def predict_tfidf_lr(
    train: list[dict[str, Any]],
    test: list[dict[str, Any]],
    *,
    max_features: int,
) -> list[str]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline

    model = make_pipeline(
        TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.95,
            max_features=max_features,
            sublinear_tf=True,
        ),
        LogisticRegression(max_iter=1000, class_weight="balanced"),
    )
    model.fit([context_text(example) for example in train], [example["ground_truth_label"] for example in train])
    return list(model.predict([context_text(example) for example in test]))


def evaluate_variant(name: str, y_true: list[str], y_pred: list[str]) -> dict[str, Any]:
    return {
        "variant": name,
        "n": len(y_true),
        "accuracy": accuracy(y_true, y_pred),
        "macro_f1": macro_f1(y_true, y_pred),
        "prediction_distribution": dict(sorted(Counter(y_pred).items())),
    }


def cap_examples(examples: list[dict[str, Any]], limit: int | None) -> list[dict[str, Any]]:
    if limit is None or len(examples) <= limit:
        return examples
    return sorted(examples, key=lambda item: (item.get("user_id", ""), item.get("id", "")))[:limit]


def main() -> None:
    args = parse_args()
    examples = read_jsonl(Path(args.input))
    train = [example for example in examples if example["split"] == "train"]
    val = [example for example in examples if example["split"] == "val"]
    test = [example for example in examples if example["split"] == "test"]
    train = cap_examples(train, args.max_train)
    val = cap_examples(val, args.max_val)
    test = cap_examples(test, args.max_test)
    if not train or not test:
        raise ValueError("Need non-empty train and test splits.")

    y_test = [example["ground_truth_label"] for example in test]
    default = majority_label(train)
    results = [
        evaluate_variant("majority", y_test, [default] * len(test)),
        evaluate_variant("subreddit_prior", y_test, predict_subreddit_prior(train, test)),
        evaluate_variant(
            "tfidf_nn",
            y_test,
            predict_tfidf_nn(
                train,
                test,
                top_k=args.top_k,
                max_features=args.max_features,
                batch_size=args.nn_batch_size,
            ),
        ),
        evaluate_variant(
            "tfidf_lr",
            y_test,
            predict_tfidf_lr(train + val, test, max_features=args.max_features),
        ),
    ]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "input": args.input,
        "splits": {"train": len(train), "val": len(val), "test": len(test)},
        "train_users": len({example["user_id"] for example in train}),
        "test_users": len({example["user_id"] for example in test}),
        "test_label_distribution": dict(sorted(Counter(y_test).items())),
        "results": results,
    }
    (output_dir / "metrics.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_jsonl(output_dir / "metrics.jsonl", results)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
