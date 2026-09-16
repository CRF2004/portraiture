from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from portraiture.evaluation.personaconvbench_baseline import accuracy, cap_examples, context_text, macro_f1
from portraiture.utils.io import read_jsonl, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GPU embedding k-NN for PersonaConvBench replay.")
    parser.add_argument(
        "--input",
        default="data/processed/personaconvbench/replay_examples.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed/personaconvbench/embedding_all_minilm_l6_v2",
    )
    parser.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--max-train", type=int, default=50000)
    parser.add_argument("--max-val", type=int, default=5000)
    parser.add_argument("--max-test", type=int, default=10000)
    parser.add_argument("--encode-batch-size", type=int, default=256)
    parser.add_argument("--search-batch-size", type=int, default=512)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--device", default="cuda")
    return parser.parse_args()


def normalize_rows(rows: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(rows, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return rows / norms


def encode_texts(texts: list[str], model_name: str, batch_size: int, device: str) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name, device=device)
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    return np.asarray(vectors, dtype=np.float32)


def predict_embedding_nn(
    train_vectors: np.ndarray,
    test_vectors: np.ndarray,
    train_labels: list[str],
    *,
    top_k: int,
    batch_size: int,
    device: str,
) -> list[str]:
    import torch

    train_tensor = torch.from_numpy(train_vectors).to(device)
    predictions: list[str] = []
    default_label = Counter(train_labels).most_common(1)[0][0]

    for start in range(0, len(test_vectors), batch_size):
        test_tensor = torch.from_numpy(test_vectors[start : start + batch_size]).to(device)
        scores = test_tensor @ train_tensor.T
        values, indices = torch.topk(scores, k=min(top_k, train_tensor.shape[0]), dim=1)
        values_cpu = values.detach().cpu().numpy()
        indices_cpu = indices.detach().cpu().numpy()
        for row_values, row_indices in zip(values_cpu, indices_cpu):
            votes: dict[str, float] = defaultdict(float)
            for score, index in zip(row_values, row_indices):
                if float(score) > 0:
                    votes[train_labels[int(index)]] += float(score)
            if votes:
                predictions.append(sorted(votes.items(), key=lambda item: (-item[1], item[0]))[0][0])
            else:
                predictions.append(default_label)
        del test_tensor, scores, values, indices
    return predictions


def evaluate(name: str, y_true: list[str], y_pred: list[str]) -> dict[str, Any]:
    return {
        "variant": name,
        "n": len(y_true),
        "accuracy": accuracy(y_true, y_pred),
        "macro_f1": macro_f1(y_true, y_pred),
        "prediction_distribution": dict(sorted(Counter(y_pred).items())),
    }


def main() -> None:
    args = parse_args()
    start_time = time.time()
    examples = read_jsonl(Path(args.input))
    train = cap_examples([e for e in examples if e["split"] == "train"], args.max_train)
    val = cap_examples([e for e in examples if e["split"] == "val"], args.max_val)
    test = cap_examples([e for e in examples if e["split"] == "test"], args.max_test)
    train_for_model = train + val
    if not train_for_model or not test:
        raise ValueError("Need non-empty train/val and test splits.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    train_texts = [context_text(e) for e in train_for_model]
    test_texts = [context_text(e) for e in test]
    train_labels = [e["ground_truth_label"] for e in train_for_model]
    y_test = [e["ground_truth_label"] for e in test]

    train_vectors = encode_texts(train_texts, args.model, args.encode_batch_size, args.device)
    test_vectors = encode_texts(test_texts, args.model, args.encode_batch_size, args.device)
    train_vectors = normalize_rows(train_vectors.astype(np.float32))
    test_vectors = normalize_rows(test_vectors.astype(np.float32))

    y_pred = predict_embedding_nn(
        train_vectors,
        test_vectors,
        train_labels,
        top_k=args.top_k,
        batch_size=args.search_batch_size,
        device=args.device,
    )
    result = evaluate(f"embedding_nn::{args.model}", y_test, y_pred)
    summary = {
        "input": args.input,
        "model": args.model,
        "splits": {"train": len(train), "val": len(val), "test": len(test)},
        "train_users": len({e["user_id"] for e in train}),
        "test_users": len({e["user_id"] for e in test}),
        "top_k": args.top_k,
        "runtime_sec": time.time() - start_time,
        "test_label_distribution": dict(sorted(Counter(y_test).items())),
        "results": [result],
    }
    (output_dir / "metrics.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    write_jsonl(output_dir / "predictions.jsonl", [
        {
            "example_id": example["id"],
            "ground_truth_label": gold,
            "predicted_label": pred,
            "user_id": example["user_id"],
            "subreddit": example.get("subreddit"),
        }
        for example, gold, pred in zip(test, y_test, y_pred)
    ])
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
