"""
Comprehensive evaluation: run all methods and compute bootstrap CIs + McNemar tests.

Uses the production code paths from the paper pipeline to ensure reproducibility.
Outputs a JSON results file for direct use in paper tables.

Usage:
  python -m portraiture.evaluation.comprehensive_eval
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
)
from portraiture.replay.hint_router import TextHintRouter
from portraiture.replay.signals import (
    infer_state_hint_from_context,
    state_hint_to_action_label,
)
from portraiture.utils.config import load_config
from portraiture.utils.io import read_jsonl, write_jsonl


# =========================================================================
# Metrics
# =========================================================================

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


def bootstrap_ci(y_true, y_pred, metric_fn, n_bootstrap=10000, seed=42):
    rng = np.random.RandomState(seed)
    n = len(y_true)
    estimates = np.zeros(n_bootstrap)
    for i in range(n_bootstrap):
        idx = rng.choice(n, size=n, replace=True)
        estimates[i] = metric_fn([y_true[j] for j in idx], [y_pred[j] for j in idx])
    return {
        "mean": float(np.mean(estimates)),
        "std": float(np.std(estimates, ddof=1)),
        "ci_95_lower": float(np.percentile(estimates, 2.5)),
        "ci_95_upper": float(np.percentile(estimates, 97.5)),
    }


def mcnemar_test(y_true, y_pred_a, y_pred_b):
    """McNemar's test with Yates continuity correction."""
    b = sum(1 for i in range(len(y_true)) if y_pred_a[i] == y_true[i] and y_pred_b[i] != y_true[i])
    c = sum(1 for i in range(len(y_true)) if y_pred_a[i] != y_true[i] and y_pred_b[i] == y_true[i])
    chi2 = (abs(b - c) - 1) ** 2 / (b + c) if (b + c) > 0 else 0.0
    from math import exp, sqrt as msqrt

    def normal_survival(x):
        if x < 0:
            return 1.0
        p = 0.2316419
        b1, b2, b3, b4, b5 = 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
        t = 1.0 / (1.0 + p * x)
        pdf = 0.3989422804014327 * exp(-0.5 * x * x)
        return pdf * (b1 * t + b2 * t * t + b3 * t * t * t + b4 * t * t * t * t + b5 * t * t * t * t * t)

    p_value = 2.0 * normal_survival(msqrt(chi2)) if chi2 > 0 else 1.0
    return {"chi2": float(chi2), "p_value": float(p_value),
            "significant_0.05": p_value < 0.05, "b": b, "c": c}


# =========================================================================
# Main
# =========================================================================

def main():
    config = load_config(Path("configs/evaluation/replay_baseline_v1.yaml"))
    inputs = config["inputs"]
    task = config["task"]
    eval_cfg = config["evaluation"]

    replay_examples = read_jsonl(Path(inputs["replay_examples"]))
    turns = read_jsonl(Path(inputs["turns"]))
    messages = read_jsonl(Path(inputs["messages"]))
    turns_by_id = {turn["id"]: turn for turn in turns}
    messages_by_id = {message["id"]: message for message in messages}

    train_exs = [e for e in replay_examples if e["split"] == "train"]
    val_exs = [e for e in replay_examples if e["split"] == "val"]
    test_exs = [e for e in replay_examples if e["split"] == "test"]

    default_label = Counter(e["ground_truth_label"] for e in train_exs).most_common(1)[0][0]
    sim_threshold = task["topic_shift_similarity_threshold"]
    y_test = [e["ground_truth_label"] for e in test_exs]

    print(f"Train: {len(train_exs)}, Val: {len(val_exs)}, Test: {len(test_exs)}")
    print(f"Default label: {default_label}")
    print(f"Test label distribution: {dict(Counter(y_test))}")

    # Fit learned state router
    print("Fitting learned state router...")
    learned_router = TextHintRouter.fit_state_router(
        train_exs, turns_by_id, messages_by_id, min_probability=0.35
    )

    # =========================================================================
    # Generate predictions for all methods
    # =========================================================================

    def predict_batch(test_examples, **base_kwargs):
        """Run choose_prediction for all test examples with given base kwargs."""
        preds = []
        for ex in test_examples:
            pred_label, _, _ = choose_prediction(
                example=ex,
                train_examples=train_exs,
                turns_by_id=turns_by_id,
                messages_by_id=messages_by_id,
                top_k=eval_cfg["top_k"],
                similarity_floor=eval_cfg["neighbor_similarity_floor"],
                default_label=default_label,
                similarity_threshold=sim_threshold,
                episode_id=ex["episode_id"],
                **base_kwargs,
            )
            preds.append(pred_label)
        return preds

    print("Generating predictions...")

    # Method 1: Off (jaccard k-NN, no state)
    off_preds = predict_batch(
        test_exs, neighbor_mode="lexical", use_state_hint=False,
        use_profile_hint=False, profile_store=None, state_hint_model=None,
    )

    # Method 2: Heuristic state (jaccard k-NN + heuristic state hints)
    heur_preds = predict_batch(
        test_exs, neighbor_mode="lexical", use_state_hint=True,
        use_profile_hint=False, profile_store=None, state_hint_model=None,
        state_hint_min_confidence=0.75,
    )

    # Method 3: Learned state router (jaccard k-NN + learned state)
    learned_preds = predict_batch(
        test_exs, neighbor_mode="lexical", use_state_hint=True,
        use_profile_hint=False, profile_store=None,
        state_hint_model=learned_router, state_hint_min_confidence=0.35,
    )

    # Method 4: Lexical NN (CJK char n-gram k-NN, no state)
    # This is the "semantic context NN" in the paper, renamed to "lexical"
    lexical_nn_preds = predict_batch(
        test_exs, neighbor_mode="semantic", use_state_hint=False,
        use_profile_hint=False, profile_store=None, state_hint_model=None,
    )

    # Method 5: Lexical + state (CJK char n-gram k-NN + learned state)
    lexical_state_preds = predict_batch(
        test_exs, neighbor_mode="semantic", use_state_hint=True,
        use_profile_hint=False, profile_store=None,
        state_hint_model=learned_router, state_hint_min_confidence=0.35,
    )

    # Method 6: LR baseline (TF-IDF + logistic regression)
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import LabelEncoder
    from sklearn.metrics import f1_score as sk_f1

    def build_sig(ex):
        texts = build_context_texts(ex, turns_by_id, messages_by_id)
        return " \n ".join(texts)

    X_train_text = [build_sig(e) for e in train_exs]
    X_val_text = [build_sig(e) for e in val_exs]
    X_test_text = [build_sig(e) for e in test_exs]
    y_train_labels = [e["ground_truth_label"] for e in train_exs]
    y_val_labels = [e["ground_truth_label"] for e in val_exs]

    vec = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(2, 5), max_features=8000,
        sublinear_tf=True, max_df=0.9, min_df=2,
    )
    X_train_tf = vec.fit_transform(X_train_text)
    X_val_tf = vec.transform(X_val_text)
    X_test_tf = vec.transform(X_test_text)

    le = LabelEncoder()
    le.fit(y_train_labels + y_val_labels + y_test)

    best_c, best_val_f1 = 1.0, 0.0
    for C in [0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]:
        lr = LogisticRegression(
            C=C, max_iter=2000, multi_class="multinomial", random_state=42,
            class_weight="balanced",
        )
        lr.fit(X_train_tf, le.transform(y_train_labels))
        val_pred = le.inverse_transform(lr.predict(X_val_tf))
        vf1 = sk_f1(y_val_labels, val_pred, average="macro", zero_division=0)
        if vf1 > best_val_f1:
            best_val_f1 = vf1
            best_c = C

    print(f"LR best C={best_c}, val macro-F1={best_val_f1:.4f}")
    lr = LogisticRegression(
        C=best_c, max_iter=2000, multi_class="multinomial", random_state=42,
        class_weight="balanced",
    )
    lr.fit(X_train_tf, le.transform(y_train_labels))
    lr_preds = list(le.inverse_transform(lr.predict(X_test_tf)))

    # Method 7: State prior (majority action per observed state)
    state_action_counts: dict[tuple, Counter] = {}
    for e in train_exs:
        key = (e.get("observed_state_type"), e.get("observed_state_value"))
        state_action_counts.setdefault(key, Counter())[e["ground_truth_label"]] += 1
    prior_preds = []
    for e in test_exs:
        key = (e.get("observed_state_type"), e.get("observed_state_value"))
        counts = state_action_counts.get(key)
        prior_preds.append(counts.most_common(1)[0][0] if counts else default_label)

    # =========================================================================
    # Collect all methods
    # =========================================================================
    all_methods = {
        "Off (no state)": off_preds,
        "Heuristic state": heur_preds,
        "Learned state router": learned_preds,
        "State prior": prior_preds,
        "Logistic regression": lr_preds,
        "Lexical context NN": lexical_nn_preds,
        "Lexical + state router": lexical_state_preds,
    }

    # =========================================================================
    # Point estimates
    # =========================================================================
    print(f"\n{'='*80}")
    print(f"Point Estimates (n={len(y_test)})")
    print(f"{'='*80}")
    for name, preds in all_methods.items():
        acc = accuracy_score(y_test, preds)
        mf1 = macro_f1_score(y_test, preds)
        print(f"  {name:30s}  acc={acc:.4f}  macro_f1={mf1:.4f}")

    # =========================================================================
    # Bootstrap CIs
    # =========================================================================
    print(f"\n{'='*80}")
    print(f"Bootstrap 95% CIs (10000 resamples)")
    print(f"{'='*80}")
    ci_results = {}
    for name, preds in all_methods.items():
        acc_ci = bootstrap_ci(y_test, preds, accuracy_score)
        mf1_ci = bootstrap_ci(y_test, preds, macro_f1_score)
        ci_results[name] = {"accuracy": acc_ci, "macro_f1": mf1_ci}
        print(f"  {name:30s}")
        print(f"    acc={acc_ci['mean']:.4f} [{acc_ci['ci_95_lower']:.4f}, {acc_ci['ci_95_upper']:.4f}]")
        print(f"    mf1={mf1_ci['mean']:.4f} [{mf1_ci['ci_95_lower']:.4f}, {mf1_ci['ci_95_upper']:.4f}]")

    # =========================================================================
    # McNemar tests (key comparisons only)
    # =========================================================================
    print(f"\n{'='*80}")
    print(f"McNemar Pairwise Tests")
    print(f"{'='*80}")
    key_pairs = [
        ("Off (no state)", "Lexical context NN"),
        ("Heuristic state", "Lexical context NN"),
        ("Learned state router", "Lexical context NN"),
        ("Logistic regression", "Lexical context NN"),
        ("Lexical context NN", "Lexical + state router"),
        ("Off (no state)", "Logistic regression"),
        ("Learned state router", "Logistic regression"),
        ("State prior", "Lexical context NN"),
    ]
    pairwise_tests = []
    for name_a, name_b in key_pairs:
        if name_a in all_methods and name_b in all_methods:
            result = mcnemar_test(y_test, all_methods[name_a], all_methods[name_b])
            result["method_a"] = name_a
            result["method_b"] = name_b
            pairwise_tests.append(result)
            sig = "*" if result["significant_0.05"] else ""
            print(f"  {name_a:30s} vs {name_b:30s}")
            print(f"    chi2={result['chi2']:.3f}  p={result['p_value']:.4f}{sig}  "
                  f"(b={result['b']}, c={result['c']})")

    # =========================================================================
    # Identity checks
    # =========================================================================
    n_nn_state = sum(1 for a, b in zip(lexical_nn_preds, lexical_state_preds) if a == b)
    n_heur_learned = sum(1 for a, b in zip(heur_preds, learned_preds) if a == b)
    print(f"\n{'='*80}")
    print(f"Identity Checks")
    print(f"{'='*80}")
    print(f"  Lexical NN == Lexical+State: {n_nn_state}/{len(y_test)} ({100*n_nn_state/len(y_test):.1f}%)")
    print(f"  Heuristic == Learned state: {n_heur_learned}/{len(y_test)} ({100*n_heur_learned/len(y_test):.1f}%)")

    # =========================================================================
    # Per-label breakdown for lexical NN
    # =========================================================================
    print(f"\n{'='*80}")
    print(f"Per-Label Breakdown (Lexical context NN)")
    print(f"{'='*80}")
    per_label = {}
    for label in sorted(set(y_test)):
        indices = [i for i, t in enumerate(y_test) if t == label]
        correct = sum(1 for i in indices if lexical_nn_preds[i] == label)
        per_label[label] = {"count": len(indices), "correct": correct,
                           "accuracy": correct / len(indices) if indices else 0.0}
        print(f"  {label:30s}  {correct}/{len(indices)} ({per_label[label]['accuracy']:.3f})")

    # =========================================================================
    # Save results
    # =========================================================================
    output_dir = Path("data/processed/evaluation/comprehensive")
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {
        "timestamp": datetime.now().astimezone().isoformat(),
        "n_train": len(train_exs),
        "n_val": len(val_exs),
        "n_test": len(y_test),
        "default_label": default_label,
        "test_label_distribution": dict(Counter(y_test)),
        "point_estimates": {
            name: {"accuracy": accuracy_score(y_test, preds),
                   "macro_f1": macro_f1_score(y_test, preds)}
            for name, preds in all_methods.items()
        },
        "bootstrap_ci": ci_results,
        "mcnemar_pairwise": pairwise_tests,
        "identity_checks": {
            "lexical_nn_vs_lexical_state": {"identical": n_nn_state, "total": len(y_test)},
            "heuristic_vs_learned": {"identical": n_heur_learned, "total": len(y_test)},
        },
        "per_label_lexical_nn": per_label,
    }

    write_jsonl(output_dir / "results.jsonl", [results])

    # Write paper-ready table
    paper_order = [
        "Off (no state)",
        "Heuristic state",
        "Learned state router",
        "State prior",
        "Logistic regression",
        "Lexical context NN",
    ]

    lines = [
        "# Comprehensive Evaluation Results",
        "",
        f"Test set: n={len(y_test)} | Bootstrap: 10000 resamples, 95% CI",
        "",
        "## Main Results Table (paper-ready)",
        "",
        "| Variant | Acc | Acc 95% CI | Macro-F1 | F1 95% CI |",
        "|---|---:|---|---:|---:|",
    ]
    for name in paper_order:
        if name not in all_methods:
            continue
        pt = results["point_estimates"][name]
        ci = ci_results[name]
        lines.append(
            f"| {name} | {pt['accuracy']:.4f} | [{ci['accuracy']['ci_95_lower']:.4f}, {ci['accuracy']['ci_95_upper']:.4f}] | "
            f"{pt['macro_f1']:.4f} | [{ci['macro_f1']['ci_95_lower']:.4f}, {ci['macro_f1']['ci_95_upper']:.4f}] |"
        )

    lines.extend([
        "",
        "## State Routing Ablation",
        "",
        "| Variant | Acc | Acc 95% CI | Macro-F1 | F1 95% CI |",
        "|---|---:|---|---:|---:|",
    ])
    for name in ["Lexical context NN", "Lexical + state router"]:
        if name not in all_methods:
            continue
        pt = results["point_estimates"][name]
        ci = ci_results[name]
        lines.append(
            f"| {name} | {pt['accuracy']:.4f} | [{ci['accuracy']['ci_95_lower']:.4f}, {ci['accuracy']['ci_95_upper']:.4f}] | "
            f"{pt['macro_f1']:.4f} | [{ci['macro_f1']['ci_95_lower']:.4f}, {ci['macro_f1']['ci_95_upper']:.4f}] |"
        )
    lines.append(f"")
    lines.append(f"Predictions identical: {n_nn_state}/{len(y_test)} ({100*n_nn_state/len(y_test):.0f}%).")
    if n_nn_state == len(y_test):
        lines.append("State routing adds zero additional signal on top of the lexical baseline.")

    lines.extend([
        "",
        "## Key Statistical Findings",
        "",
    ])
    for test in pairwise_tests:
        sig_str = "***" if test["p_value"] < 0.01 else ("**" if test["p_value"] < 0.05 else "n.s.")
        lines.append(
            f"- {test['method_a']} vs {test['method_b']}: "
            f"McNemar χ²={test['chi2']:.2f}, p={test['p_value']:.4f} ({sig_str})"
        )

    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nResults saved to {output_dir}")
    print(json.dumps({k: v for k, v in results.items() if k not in ("mcnemar_pairwise", "bootstrap_ci")},
                     ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
