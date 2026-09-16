"""
Bootstrap confidence intervals and McNemar statistical tests for the
fixed-split replay evaluation.

Uses the actual production choose_prediction() from replay.py to ensure
numbers match the paper exactly. Bootstrap CIs and McNemar tests are then
computed on those predictions.

Usage:
  python -m portraiture.evaluation.bootstrap_stats
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import numpy as np

from portraiture.evaluation.replay import (
    build_context_texts,
    choose_prediction,
    cosine_similarity,
    jaccard_similarity,
    text_similarity,
)
from portraiture.replay.hint_router import TextHintRouter
from portraiture.replay.signals import (
    infer_state_hint_from_context,
    state_hint_to_action_label,
)
from portraiture.utils.config import load_config
from portraiture.utils.io import read_jsonl, write_jsonl


def bootstrap_metric(
    y_true: list[str],
    y_pred: list[str],
    metric_fn,
    n_bootstrap: int = 10000,
    random_seed: int = 42,
) -> dict[str, float]:
    """Bootstrap confidence interval for a metric."""
    rng = np.random.RandomState(random_seed)
    n = len(y_true)
    estimates = np.zeros(n_bootstrap)
    for i in range(n_bootstrap):
        indices = rng.choice(n, size=n, replace=True)
        y_true_sample = [y_true[j] for j in indices]
        y_pred_sample = [y_pred[j] for j in indices]
        estimates[i] = metric_fn(y_true_sample, y_pred_sample)
    return {
        "mean": float(np.mean(estimates)),
        "std": float(np.std(estimates, ddof=1)),
        "ci_95_lower": float(np.percentile(estimates, 2.5)),
        "ci_95_upper": float(np.percentile(estimates, 97.5)),
        "median": float(np.median(estimates)),
    }


def accuracy_score(y_true, y_pred):
    return sum(1 for t, p in zip(y_true, y_pred) if t == p) / max(len(y_true), 1)


def macro_f1_score(y_true, y_pred):
    labels = sorted(set(y_true) | set(y_pred))
    f1s = []
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        f1s.append(f1)
    return sum(f1s) / max(len(f1s), 1)


def mcnemar_test(
    y_true: list[str],
    y_pred_a: list[str],
    y_pred_b: list[str],
) -> dict[str, Any]:
    """McNemar's test with Yates continuity correction."""
    n = len(y_true)
    b = sum(1 for i in range(n) if y_pred_a[i] == y_true[i] and y_pred_b[i] != y_true[i])
    c = sum(1 for i in range(n) if y_pred_a[i] != y_true[i] and y_pred_b[i] == y_true[i])
    chi2 = (abs(b - c) - 1) ** 2 / (b + c) if (b + c) > 0 else 0.0
    from math import exp, sqrt as msqrt

    def normal_survival(x):
        if x < 0:
            return 1.0
        p = 0.2316419
        b1, b2, b3, b4, b5 = 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
        t = 1.0 / (1.0 + p * x)
        pdf = 0.3989422804014327 * exp(-0.5 * x * x)
        cdf = pdf * (b1 * t + b2 * t * t + b3 * t * t * t + b4 * t * t * t * t + b5 * t * t * t * t * t)
        return cdf

    p_value = 2.0 * normal_survival(msqrt(chi2)) if chi2 > 0 else 1.0
    return {
        "chi2_statistic": float(chi2),
        "p_value": float(p_value),
        "significant_at_0.05": p_value < 0.05,
        "significant_at_0.01": p_value < 0.01,
        "discordant_a_correct_b_wrong": b,
        "discordant_a_wrong_b_correct": c,
    }


def main() -> None:
    config = load_config(Path("configs/evaluation/replay_baseline_v1.yaml"))
    inputs = config["inputs"]
    task = config["task"]

    replay_examples = read_jsonl(Path(inputs["replay_examples"]))
    turns = read_jsonl(Path(inputs["turns"]))
    messages = read_jsonl(Path(inputs["messages"]))
    turns_by_id = {turn["id"]: turn for turn in turns}
    messages_by_id = {message["id"]: message for message in messages}

    train_examples = [e for e in replay_examples if e["split"] == "train"]
    val_examples = [e for e in replay_examples if e["split"] == "val"]
    test_examples = [e for e in replay_examples if e["split"] == "test"]

    print(f"Train: {len(train_examples)}, Val: {len(val_examples)}, Test: {len(test_examples)}")

    default_label = Counter(e["ground_truth_label"] for e in train_examples).most_common(1)[0][0]
    similarity_threshold = task["topic_shift_similarity_threshold"]
    print(f"Default label: {default_label}")

    # Fit learned state router
    print("Fitting learned state router...")
    learned_router = TextHintRouter.fit_state_router(
        train_examples, turns_by_id, messages_by_id, min_probability=0.35
    )

    # =========================================================================
    # Generate predictions using the production choose_prediction() function
    # =========================================================================
    y_test = [e["ground_truth_label"] for e in test_examples]

    def predict_all(method_name, **kwargs):
        """Run choose_prediction for all test examples with given kwargs."""
        preds = []
        for ex in test_examples:
            pred_label, cands, reasoning = choose_prediction(
                example=ex,
                train_examples=train_examples,
                turns_by_id=turns_by_id,
                messages_by_id=messages_by_id,
                top_k=5,
                similarity_floor=0.02,
                default_label=default_label,
                similarity_threshold=similarity_threshold,
                neighbor_mode=kwargs.pop("neighbor_mode", "lexical"),
                profile_store=kwargs.pop("profile_store", None),
                state_hint_model=kwargs.pop("state_hint_model", None),
                use_profile_hint=kwargs.pop("use_profile_hint", False),
                use_state_hint=kwargs.pop("use_state_hint", False),
                state_hint_min_confidence=kwargs.pop("state_hint_min_confidence", 0.75),
                episode_id=ex["episode_id"],
                **kwargs,
            )
            preds.append(pred_label)
        return preds

    print("Generating predictions (production choose_prediction)...")

    # Off: lexical neighbor mode, no state
    off_preds = predict_all("off", neighbor_mode="lexical", use_state_hint=False)

    # Heuristic state: lexical neighbor + heuristic state hints
    heur_preds = predict_all(
        "heuristic", neighbor_mode="lexical", use_state_hint=True,
        state_hint_model=None, state_hint_min_confidence=0.75,
    )

    # Learned state: lexical neighbor + learned state router
    learned_preds = predict_all(
        "learned", neighbor_mode="lexical", use_state_hint=True,
        state_hint_model=learned_router, state_hint_min_confidence=0.35,
    )

    # Lexical NN: CJK cosine similarity, no state (currently called "semantic" in paper)
    lexical_nn_preds = predict_all(
        "lexical_nn", neighbor_mode="semantic", use_state_hint=False,
    )

    # Lexical + state: CJK cosine similarity + learned state router
    lexical_state_preds = predict_all(
        "lexical_state", neighbor_mode="semantic", use_state_hint=True,
        state_hint_model=learned_router, state_hint_min_confidence=0.35,
    )

    # LR baseline: TF-IDF + logistic regression
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import LabelEncoder

    def build_context_signature(example):
        texts = build_context_texts(example, turns_by_id, messages_by_id)
        return " \n ".join(texts)

    X_train_text_lr = [build_context_signature(e) for e in train_examples]
    X_test_text_lr = [build_context_signature(e) for e in test_examples]
    X_val_text_lr = [build_context_signature(e) for e in val_examples]
    y_train_labels = [e["ground_truth_label"] for e in train_examples]
    y_val_labels = [e["ground_truth_label"] for e in val_examples]

    vectorizer = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(2, 5), max_features=8000,
        sublinear_tf=True, max_df=0.9, min_df=2,
    )
    X_train_tfidf = vectorizer.fit_transform(X_train_text_lr)
    X_test_tfidf = vectorizer.transform(X_test_text_lr)
    X_val_tfidf = vectorizer.transform(X_val_text_lr)

    le = LabelEncoder()
    le.fit(y_train_labels + y_val_labels + y_test)

    best_c, best_val_f1 = 1.0, 0.0
    for C in [0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]:
        lr = LogisticRegression(
            C=C, max_iter=2000, multi_class="multinomial", random_state=42,
            class_weight="balanced",
        )
        lr.fit(X_train_tfidf, le.transform(y_train_labels))
        val_pred = le.inverse_transform(lr.predict(X_val_tfidf))
        from sklearn.metrics import f1_score
        val_f1 = f1_score(y_val_labels, val_pred, average="macro", zero_division=0)
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_c = C

    print(f"LR: best C={best_c}, val macro-F1={best_val_f1:.4f}")
    lr = LogisticRegression(
        C=best_c, max_iter=2000, multi_class="multinomial", random_state=42,
        class_weight="balanced",
    )
    lr.fit(X_train_tfidf, le.transform(y_train_labels))
    lr_preds = list(le.inverse_transform(lr.predict(X_test_tfidf)))

    # =========================================================================
    # Point estimates
    # =========================================================================
    methods = {
        "Off (no state)": off_preds,
        "Heuristic state": heur_preds,
        "Learned state router": learned_preds,
        "Logistic regression": lr_preds,
        "Lexical context NN": lexical_nn_preds,
        "Lexical + state router": lexical_state_preds,
    }

    print(f"\n=== Point Estimates (fixed test split, n={len(y_test)}) ===")
    for name, preds in methods.items():
        acc = accuracy_score(y_test, preds)
        mf1 = macro_f1_score(y_test, preds)
        print(f"  {name:30s}  acc={acc:.4f}  macro_f1={mf1:.4f}")

    # =========================================================================
    # Bootstrap CIs
    # =========================================================================
    print(f"\n=== Bootstrap 95% CIs (10000 resamples, n={len(y_test)}) ===")
    ci_results = {}
    for name, preds in methods.items():
        acc_ci = bootstrap_metric(y_test, preds, accuracy_score)
        mf1_ci = bootstrap_metric(y_test, preds, macro_f1_score)
        ci_results[name] = {"accuracy": acc_ci, "macro_f1": mf1_ci}
        print(f"  {name:30s}  acc={acc_ci['mean']:.4f} [{acc_ci['ci_95_lower']:.4f}, {acc_ci['ci_95_upper']:.4f}]"
              f"  macro_f1={mf1_ci['mean']:.4f} [{mf1_ci['ci_95_lower']:.4f}, {mf1_ci['ci_95_upper']:.4f}]")

    # =========================================================================
    # McNemar tests
    # =========================================================================
    print(f"\n=== McNemar Pairwise Tests ===")
    method_names = list(methods.keys())
    pairwise_tests = []
    for i, name_a in enumerate(method_names):
        for j, name_b in enumerate(method_names):
            if i >= j:
                continue
            result = mcnemar_test(y_test, methods[name_a], methods[name_b])
            result["method_a"] = name_a
            result["method_b"] = name_b
            pairwise_tests.append(result)
            sig = "*" if result["significant_at_0.05"] else ""
            print(f"  {name_a:30s} vs {name_b:30s}  "
                  f"χ²={result['chi2_statistic']:.3f}  p={result['p_value']:.4f}{sig}"
                  f"  (b={result['discordant_a_correct_b_wrong']}, c={result['discordant_a_wrong_b_correct']})")

    # =========================================================================
    # Identity checks
    # =========================================================================
    n_identical_nn_state = sum(1 for a, b in zip(lexical_nn_preds, lexical_state_preds) if a == b)
    n_identical_heur_learned = sum(1 for a, b in zip(heur_preds, learned_preds) if a == b)
    print(f"\n=== Identity Checks ===")
    print(f"  Lexical NN == Lexical+State: {n_identical_nn_state}/{len(y_test)} ({100*n_identical_nn_state/len(y_test):.1f}%)")
    print(f"  Heuristic state == Learned state: {n_identical_heur_learned}/{len(y_test)} ({100*n_identical_heur_learned/len(y_test):.1f}%)")

    # =========================================================================
    # Save results
    # =========================================================================
    output_dir = Path("data/processed/evaluation/bootstrap_stats")
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {
        "timestamp": datetime.now().astimezone().isoformat(),
        "n_test": len(y_test),
        "n_train": len(train_examples),
        "n_val": len(val_examples),
        "point_estimates": {name: {"accuracy": accuracy_score(y_test, preds), "macro_f1": macro_f1_score(y_test, preds)}
                           for name, preds in methods.items()},
        "bootstrap_ci": {name: {
            "accuracy": {k: round(v, 6) if isinstance(v, float) else v for k, v in ci["accuracy"].items()},
            "macro_f1": {k: round(v, 6) if isinstance(v, float) else v for k, v in ci["macro_f1"].items()},
        } for name, ci in ci_results.items()},
        "mcnemar_pairwise": pairwise_tests,
        "identity_checks": {
            "lexical_nn_vs_lexical_state": {"identical": n_identical_nn_state, "total": len(y_test)},
            "heuristic_vs_learned_state": {"identical": n_identical_heur_learned, "total": len(y_test)},
        },
    }

    write_jsonl(output_dir / "results.jsonl", [results])

    # Readable summary
    lines = [
        "# Bootstrap Statistics & Significance Tests",
        "",
        f"Test set: n={len(y_test)} | Bootstrap: 10000 resamples, 95% CI",
        "",
        "## Point Estimates with 95% Bootstrap CIs",
        "",
        "| Method | Accuracy | Acc 95% CI | Macro-F1 | F1 95% CI |",
        "|---|---:|---|---:|---:|",
    ]
    for name in method_names:
        acc = ci_results[name]["accuracy"]
        mf1 = ci_results[name]["macro_f1"]
        lines.append(
            f"| {name} | {acc['mean']:.4f} | [{acc['ci_95_lower']:.4f}, {acc['ci_95_upper']:.4f}] | "
            f"{mf1['mean']:.4f} | [{mf1['ci_95_lower']:.4f}, {mf1['ci_95_upper']:.4f}] |"
        )

    lines.extend([
        "",
        "## Key Statistical Findings",
        "",
    ])
    # Find the LR vs Lexical NN comparison
    for test in pairwise_tests:
        if ("Logistic" in test["method_a"] and "Lexical context" in test["method_b"]):
            lines.append(f"- LR vs Lexical NN: McNemar χ²={test['chi2_statistic']:.3f}, p={test['p_value']:.4f} "
                        f"({'significant' if test['significant_at_0.05'] else 'not significant'} at 0.05)")
        if ("Lexical context NN" in test["method_a"] and "Lexical + state" in test["method_b"]):
            lines.append(f"- Lexical NN vs Lexical+State: predictions {n_identical_nn_state}/{len(y_test)} identical, "
                        f"McNemar p={test['p_value']:.4f} — no detectable difference")

    lines.extend([
        "",
        "## All Pairwise McNemar Tests",
        "",
        "| Method A | Method B | χ² | p | Sig? | b | c |",
        "|---|---|---:|---:|---:|---:|---:|",
    ])
    for test in pairwise_tests:
        lines.append(
            f"| {test['method_a']} | {test['method_b']} | {test['chi2_statistic']:.3f} | "
            f"{test['p_value']:.4f} | {'*' if test['significant_at_0.05'] else ''} | "
            f"{test['discordant_a_correct_b_wrong']} | {test['discordant_a_wrong_b_correct']} |"
        )

    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nResults saved to {output_dir}")
    print(json.dumps({k: v for k, v in results.items() if k != "mcnemar_pairwise"},
                     ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
