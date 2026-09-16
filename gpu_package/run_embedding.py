"""
GPU embedding baseline for Portraiture replay benchmark.

Self-contained script — no portraiture dependency.
Compares sentence-transformer embeddings against the lexical CJK n-gram baseline
and tests whether state routing adds signal on top of embedding similarity.

Usage:
  pip install -r requirements.txt
  python run_embedding.py

Output:
  results/embedding_results.json  — full results
  results/summary.md             — paper-ready tables
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

# Use HF mirror for Chinese networks (inherits from env, set here as fallback)
if "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
from datetime import datetime
from math import sqrt
from pathlib import Path

import numpy as np


# ============================================================================
# CJK char n-gram tokenizer (replicates portraiture semantic_tokenize)
# ============================================================================

def cjk_tokenize(text: str) -> list[str]:
    """CJK-aware character n-gram tokenization (unigrams + bigrams)."""
    normalized = " ".join(text.lower().split())
    tokens: list[str] = []
    ascii_token: list[str] = []
    cjk_buffer: list[str] = []

    def flush_ascii():
        if ascii_token:
            token = "".join(ascii_token)
            if len(token) > 1:
                tokens.append(token)
            ascii_token.clear()

    def flush_cjk():
        if not cjk_buffer:
            return
        for idx, ch in enumerate(cjk_buffer):
            tokens.append(ch)
            if idx + 1 < len(cjk_buffer):
                tokens.append(ch + cjk_buffer[idx + 1])
        cjk_buffer.clear()

    for ch in normalized:
        if ch.isascii() and ch.isalnum():
            flush_cjk()
            ascii_token.append(ch)
        elif "一" <= ch <= "鿿":
            flush_ascii()
            cjk_buffer.append(ch)
        else:
            flush_ascii()
            flush_cjk()

    flush_ascii()
    flush_cjk()
    return tokens


def cjk_cosine_similarity(left: str, right: str) -> float:
    """Cosine similarity with CJK char n-gram token counts."""
    left_counts = Counter(cjk_tokenize(left))
    right_counts = Counter(cjk_tokenize(right))
    if not left_counts or not right_counts:
        return 0.0
    shared = left_counts.keys() & right_counts.keys()
    dot = sum(left_counts[t] * right_counts[t] for t in shared)
    left_norm = sqrt(sum(v * v for v in left_counts.values()))
    right_norm = sqrt(sum(v * v for v in right_counts.values()))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


# ============================================================================
# Data loading
# ============================================================================

def load_jsonl(path: str) -> list[dict]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def build_context_signature(example, turns_by_id, messages_by_id) -> str:
    """Build concatenated context text for a replay example."""
    texts = []
    for turn_id in example["context_turn_ids"]:
        turn = turns_by_id.get(turn_id)
        if not turn:
            continue
        msg_id = turn.get("user_message_id")
        if not msg_id:
            continue
        msg = messages_by_id.get(msg_id)
        if msg:
            text = msg.get("content_text", "").strip()
            if text:
                texts.append(text)
    return " \n ".join(texts)


def build_context_texts(example, turns_by_id, messages_by_id) -> list[str]:
    """Build list of context texts for state routing."""
    texts = []
    for turn_id in example["context_turn_ids"]:
        turn = turns_by_id.get(turn_id)
        if not turn:
            continue
        msg_id = turn.get("user_message_id")
        if not msg_id:
            continue
        msg = messages_by_id.get(msg_id)
        if msg:
            text = msg.get("content_text", "").strip()
            if text:
                texts.append(text)
    return texts


# ============================================================================
# Simple state router (replicates learned state router logic)
# ============================================================================

class SimpleStateRouter:
    """Naive Bayes state router trained on context text."""

    def __init__(self):
        self.state_counts: dict[str, Counter] = defaultdict(Counter)
        self.state_totals: Counter = Counter()
        self.min_probability = 0.35

    def fit(self, train_examples, turns_by_id, messages_by_id):
        """Count word-state co-occurrences from training data."""
        for ex in train_examples:
            state_type = ex.get("observed_state_type")
            state_value = ex.get("observed_state_value")
            if not state_type:
                continue
            state_key = f"{state_type}|{state_value}"
            texts = build_context_texts(ex, turns_by_id, messages_by_id)
            for text in texts:
                for ch in text:
                    if ch.strip():
                        self.state_counts[state_key][ch] += 1
                        self.state_totals[state_key] += 1

    def predict(self, context_texts: list[str]) -> dict:
        """Predict state type/value from context texts."""
        if not self.state_counts:
            return {"state_type": None, "state_value": None, "confidence": 0.0}
        scores = {}
        text = " ".join(context_texts)
        total_chars = sum(self.state_totals.values())
        for state_key, char_counts in self.state_counts.items():
            prob = 0.0
            for ch in text:
                if ch.strip():
                    char_prob = (char_counts.get(ch, 0) + 1) / (self.state_totals[state_key] + total_chars)
                    prob += np.log(char_prob)
            scores[state_key] = prob
        if not scores:
            return {"state_type": None, "state_value": None, "confidence": 0.0}
        best_key = max(scores, key=scores.get)
        state_type, state_value = best_key.split("|", 1)
        # Normalize confidence
        vals = list(scores.values())
        max_val, min_val = max(vals), min(vals)
        if max_val > min_val:
            confidence = (scores[best_key] - min_val) / (max_val - min_val)
        else:
            confidence = 0.5
        return {
            "state_type": state_type,
            "state_value": state_value,
            "confidence": confidence,
        }


# Simple state-to-action mapping
def state_hint_to_action_label(state_type, state_value):
    if not state_type:
        return None
    mapping = {
        "active_problem": {
            "research_exploration": "request_how_to",
            "implementation": "request_how_to",
            "debugging": "provide_more_context",
            "planning": "request_how_to",
        },
        "blocking_issue": {
            "needs_troubleshooting": "provide_more_context",
            "needs_clarification": "follow_up_clarification",
            "needs_options": "compare_options",
        },
        "current_stance": {
            "topic_transition": "topic_shift",
            "exploring_alternatives": "compare_options",
            "seeking_validation": "ask_why",
            "deepening_understanding": "ask_for_example",
            "refining_request": "follow_up_clarification",
        },
    }
    state_map = mapping.get(state_type, {})
    return state_map.get(state_value)


# ============================================================================
# Metrics
# ============================================================================

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
    b = sum(1 for i in range(len(y_true)) if y_pred_a[i] == y_true[i] and y_pred_b[i] != y_true[i])
    c = sum(1 for i in range(len(y_true)) if y_pred_a[i] != y_true[i] and y_pred_b[i] == y_true[i])
    from math import exp, sqrt as msqrt
    chi2 = (abs(b - c) - 1) ** 2 / (b + c) if (b + c) > 0 else 0.0

    def normal_survival(x):
        if x < 0:
            return 1.0
        p = 0.2316419
        b1, b2, b3, b4, b5 = 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
        t = 1.0 / (1.0 + p * x)
        pdf = 0.3989422804014327 * exp(-0.5 * x * x)
        return pdf * (b1 * t + b2 * t * t + b3 * t * t * t + b4 * t * t * t * t + b5 * t * t * t * t * t)

    p_value = 2.0 * normal_survival(msqrt(chi2)) if chi2 > 0 else 1.0
    return {"chi2": float(chi2), "p_value": float(p_value), "significant_0.05": p_value < 0.05, "b": b, "c": c}


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 70)
    print("Portraiture GPU Embedding Baseline")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)

    # Load data
    print("\n[1/5] Loading data...")
    replay_examples = load_jsonl("data/replay_examples.jsonl")
    turns = load_jsonl("data/turns.jsonl")
    messages = load_jsonl("data/messages.jsonl")

    turns_by_id = {t["id"]: t for t in turns}
    messages_by_id = {m["id"]: m for m in messages}

    train_exs = [e for e in replay_examples if e["split"] == "train"]
    val_exs = [e for e in replay_examples if e["split"] == "val"]
    test_exs = [e for e in replay_examples if e["split"] == "test"]

    default_label = Counter(e["ground_truth_label"] for e in train_exs).most_common(1)[0][0]
    y_test = [e["ground_truth_label"] for e in test_exs]

    print(f"  Train: {len(train_exs)}, Val: {len(val_exs)}, Test: {len(test_exs)}")
    print(f"  Default label: {default_label}")
    print(f"  Test distribution: {dict(Counter(y_test))}")

    # Build context signatures
    print("\n[2/5] Building context signatures...")
    train_sigs = [build_context_signature(e, turns_by_id, messages_by_id) for e in train_exs]
    val_sigs = [build_context_signature(e, turns_by_id, messages_by_id) for e in val_exs]
    test_sigs = [build_context_signature(e, turns_by_id, messages_by_id) for e in test_exs]
    train_labels = [e["ground_truth_label"] for e in train_exs]

    # Fit state router
    print("  Fitting state router...")
    router = SimpleStateRouter()
    router.fit(train_exs, turns_by_id, messages_by_id)

    # =========================================================================
    # Lexical CJK baseline (no GPU needed)
    # =========================================================================
    print("\n[3/5] Running lexical CJK baseline...")

    def knn_predict(test_sigs, train_sigs, train_labels, similarity_fn, similarity_floor=0.02):
        preds = []
        for sig in test_sigs:
            weighted_votes = defaultdict(float)
            best_label = default_label
            best_score = -1.0
            for j, train_sig in enumerate(train_sigs):
                score = similarity_fn(sig, train_sig)
                if score >= similarity_floor:
                    weighted_votes[train_labels[j]] += score
                if score > best_score:
                    best_score = score
                    best_label = train_labels[j]
            if weighted_votes:
                preds.append(max(weighted_votes, key=weighted_votes.get))
            else:
                preds.append(best_label)
        return preds

    lexical_preds = knn_predict(test_sigs, train_sigs, train_labels, cjk_cosine_similarity)

    # Lexical + state
    lexical_state_preds = []
    for i, ex in enumerate(test_exs):
        sig = test_sigs[i]
        ctx_texts = build_context_texts(ex, turns_by_id, messages_by_id)
        state_hint = router.predict(ctx_texts)
        hint_label = state_hint_to_action_label(state_hint.get("state_type"), state_hint.get("state_value"))
        state_conf = state_hint.get("confidence", 0.0)

        weighted_votes = defaultdict(float)
        best_label = default_label
        best_score = -1.0
        for j, train_sig in enumerate(train_sigs):
            score = cjk_cosine_similarity(sig, train_sig)
            if score >= 0.02:
                weighted_votes[train_labels[j]] += score
            if score > best_score:
                best_score = score
                best_label = train_labels[j]

        if hint_label and state_conf >= 0.35 and weighted_votes:
            if hint_label in weighted_votes:
                weighted_votes[hint_label] += 0.3 * max(weighted_votes.values())
            else:
                weighted_votes[hint_label] = 0.3 * max(weighted_votes.values())

        if weighted_votes:
            lexical_state_preds.append(max(weighted_votes, key=weighted_votes.get))
        else:
            lexical_state_preds.append(hint_label or best_label)

    # =========================================================================
    # Embedding baselines (GPU)
    # =========================================================================
    print("\n[4/5] Running embedding baselines (GPU)...")

    embedding_results = {}

    # Try multiple models
    model_names = [
        "BAAI/bge-small-zh-v1.5",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    ]

    # Check if GPU is available
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"  PyTorch device: {device}")
        if device == "cuda":
            print(f"  GPU: {torch.cuda.get_device_name(0)}")
    except ImportError:
        device = "cpu"
        print("  PyTorch not installed, using CPU")

    for model_name in model_names:
        print(f"\n  Loading {model_name}...")
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(model_name, device=device)
            print(f"    Model loaded. Encoding {len(train_sigs) + len(test_sigs)} texts...")

            # Encode all texts
            all_texts = train_sigs + test_sigs
            all_embeddings = model.encode(
                all_texts,
                batch_size=32,
                show_progress_bar=True,
                normalize_embeddings=True,
            )
            train_emb = all_embeddings[: len(train_sigs)]
            test_emb = all_embeddings[len(train_sigs):]

            # Cosine similarity on normalized embeddings = dot product
            sim_matrix = test_emb @ train_emb.T

            # k-NN prediction
            embedding_preds = []
            embedding_state_preds = []
            for i in range(len(test_exs)):
                similarities = sim_matrix[i]
                weighted_votes = defaultdict(float)
                best_label = default_label
                best_score = -1.0
                for j, score in enumerate(similarities):
                    s = float(score)
                    if s >= 0.3:  # cosine similarity floor for normalized embeddings
                        weighted_votes[train_labels[j]] += s
                    if s > best_score:
                        best_score = s
                        best_label = train_labels[j]

                if weighted_votes:
                    nn_pred = max(weighted_votes, key=weighted_votes.get)
                else:
                    nn_pred = best_label

                # State routing on top
                ctx_texts = build_context_texts(test_exs[i], turns_by_id, messages_by_id)
                state_hint = router.predict(ctx_texts)
                hint_label = state_hint_to_action_label(state_hint.get("state_type"), state_hint.get("state_value"))
                state_conf = state_hint.get("confidence", 0.0)

                if hint_label and state_conf >= 0.35 and weighted_votes:
                    if hint_label in weighted_votes:
                        weighted_votes[hint_label] += 0.3 * max(weighted_votes.values())
                    else:
                        weighted_votes[hint_label] = 0.3 * max(weighted_votes.values())
                    state_pred = max(weighted_votes, key=weighted_votes.get)
                else:
                    state_pred = nn_pred if not hint_label else hint_label

                embedding_preds.append(nn_pred)
                embedding_state_preds.append(state_pred)

            # Compute metrics
            emb_nn_acc = accuracy_score(y_test, embedding_preds)
            emb_nn_mf1 = macro_f1_score(y_test, embedding_preds)
            emb_state_acc = accuracy_score(y_test, embedding_state_preds)
            emb_state_mf1 = macro_f1_score(y_test, embedding_state_preds)

            # Check identity
            n_identical = sum(1 for a, b in zip(embedding_preds, embedding_state_preds) if a == b)

            # Bootstrap CIs
            emb_nn_acc_ci = bootstrap_ci(y_test, embedding_preds, accuracy_score)
            emb_nn_mf1_ci = bootstrap_ci(y_test, embedding_preds, macro_f1_score)

            # McNemar: embedding vs lexical
            mcn_emb_vs_lex = mcnemar_test(y_test, embedding_preds, lexical_preds)

            model_key = model_name.split("/")[-1]
            embedding_results[model_name] = {
                "model_key": model_key,
                "embedding_dim": all_embeddings.shape[1],
                "point_estimates": {
                    "embedding_nn": {"accuracy": emb_nn_acc, "macro_f1": emb_nn_mf1},
                    "embedding_state": {"accuracy": emb_state_acc, "macro_f1": emb_state_mf1},
                },
                "bootstrap_ci": {
                    "embedding_nn_accuracy": emb_nn_acc_ci,
                    "embedding_nn_macro_f1": emb_nn_mf1_ci,
                },
                "identity_check": {
                    "nn_vs_state_identical": n_identical,
                    "total": len(y_test),
                    "fraction": n_identical / len(y_test),
                },
                "mcnemar_vs_lexical": mcn_emb_vs_lex,
            }

            print(f"    {model_key}: NN acc={emb_nn_acc:.4f} mf1={emb_nn_mf1:.4f}  "
                  f"+State acc={emb_state_acc:.4f} mf1={emb_state_mf1:.4f}  "
                  f"identical={n_identical}/{len(y_test)}")

        except Exception as e:
            print(f"    ERROR loading {model_name}: {e}")
            embedding_results[model_name] = {"error": str(e)}

    # =========================================================================
    # Results
    # =========================================================================
    print("\n[5/5] Computing final results...")
    Path("results").mkdir(exist_ok=True)

    # Lexical baseline CIs
    lexical_acc_ci = bootstrap_ci(y_test, lexical_preds, accuracy_score)
    lexical_mf1_ci = bootstrap_ci(y_test, lexical_preds, macro_f1_score)

    # State routing ablation (lexical)
    n_lexical_identical = sum(1 for a, b in zip(lexical_preds, lexical_state_preds) if a == b)

    all_results = {
        "timestamp": datetime.now().isoformat(),
        "n_train": len(train_exs),
        "n_val": len(val_exs),
        "n_test": len(y_test),
        "default_label": default_label,
        "test_label_distribution": dict(Counter(y_test)),
        "device": device,
        "lexical_baseline": {
            "point_estimates": {
                "lexical_nn": {"accuracy": accuracy_score(y_test, lexical_preds), "macro_f1": macro_f1_score(y_test, lexical_preds)},
                "lexical_state": {"accuracy": accuracy_score(y_test, lexical_state_preds), "macro_f1": macro_f1_score(y_test, lexical_state_preds)},
            },
            "bootstrap_ci": {
                "lexical_nn_accuracy": lexical_acc_ci,
                "lexical_nn_macro_f1": lexical_mf1_ci,
            },
            "state_ablation": {
                "identical": n_lexical_identical,
                "total": len(y_test),
                "fraction": n_lexical_identical / len(y_test),
            },
        },
        "embedding_baselines": embedding_results,
    }

    # Save full results
    with open("results/embedding_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    print("  Saved results/embedding_results.json")

    # Write summary
    lines = [
        "# Portraiture GPU Embedding Baseline Results",
        "",
        f"Test set: n={len(y_test)} | Device: {device}",
        f"Timestamp: {all_results['timestamp']}",
        "",
        "## Lexical CJK Baseline (no GPU)",
        "",
        f"- Lexical NN: acc={all_results['lexical_baseline']['point_estimates']['lexical_nn']['accuracy']:.4f} "
        f"[{lexical_acc_ci['ci_95_lower']:.4f}, {lexical_acc_ci['ci_95_upper']:.4f}]  "
        f"macro-F1={all_results['lexical_baseline']['point_estimates']['lexical_nn']['macro_f1']:.4f} "
        f"[{lexical_mf1_ci['ci_95_lower']:.4f}, {lexical_mf1_ci['ci_95_upper']:.4f}]",
        f"- Lexical+State: acc={all_results['lexical_baseline']['point_estimates']['lexical_state']['accuracy']:.4f} "
        f"macro-F1={all_results['lexical_baseline']['point_estimates']['lexical_state']['macro_f1']:.4f}",
        f"- State ablation: {n_lexical_identical}/{len(y_test)} predictions identical",
        "",
        "## Embedding Baselines (GPU)",
        "",
    ]

    for model_name, results in embedding_results.items():
        model_key = results.get("model_key", model_name)
        if "error" in results:
            lines.append(f"### {model_key}")
            lines.append(f"ERROR: {results['error']}")
            lines.append("")
            continue
        pt = results["point_estimates"]
        ci = results["bootstrap_ci"]
        ic = results["identity_check"]
        mc = results["mcnemar_vs_lexical"]
        lines.append(f"### {model_key} (dim={results['embedding_dim']})")
        lines.append("")
        lines.append("| Variant | Accuracy | Macro-F1 |")
        lines.append("|---|---:|---:|")
        lines.append(f"| Embedding NN | {pt['embedding_nn']['accuracy']:.4f} "
                     f"[{ci['embedding_nn_accuracy']['ci_95_lower']:.4f}, {ci['embedding_nn_accuracy']['ci_95_upper']:.4f}] | "
                     f"{pt['embedding_nn']['macro_f1']:.4f} "
                     f"[{ci['embedding_nn_macro_f1']['ci_95_lower']:.4f}, {ci['embedding_nn_macro_f1']['ci_95_upper']:.4f}] |")
        lines.append(f"| Embedding + State | {pt['embedding_state']['accuracy']:.4f} | {pt['embedding_state']['macro_f1']:.4f} |")
        lines.append("")
        lines.append(f"- State ablation: {ic['identical']}/{ic['total']} ({ic['fraction']*100:.0f}%) identical")
        sig_str = "***" if mc["p_value"] < 0.01 else ("**" if mc["p_value"] < 0.05 else "n.s.")
        lines.append(f"- vs Lexical NN: McNemar χ²={mc['chi2']:.2f}, p={mc['p_value']:.4f} ({sig_str})")
        lines.append("")

    summary = "\n".join(lines)
    with open("results/summary.md", "w", encoding="utf-8") as f:
        f.write(summary)
    print("  Saved results/summary.md")

    # Print key result
    print("\n" + "=" * 70)
    print("KEY RESULTS")
    print("=" * 70)
    print(f"Lexical CJK NN:      acc={lexical_acc_ci['mean']:.4f} [{lexical_acc_ci['ci_95_lower']:.4f}, {lexical_acc_ci['ci_95_upper']:.4f}]  "
          f"mf1={lexical_mf1_ci['mean']:.4f} [{lexical_mf1_ci['ci_95_lower']:.4f}, {lexical_mf1_ci['ci_95_upper']:.4f}]")
    for model_name, results in embedding_results.items():
        if "error" in results:
            print(f"{results['model_key']:30s}: ERROR - {results['error'][:60]}")
        else:
            pt = results["point_estimates"]
            ci = results["bootstrap_ci"]
            print(f"{results['model_key']:30s}: acc={ci['embedding_nn_accuracy']['mean']:.4f} "
                  f"[{ci['embedding_nn_accuracy']['ci_95_lower']:.4f}, {ci['embedding_nn_accuracy']['ci_95_upper']:.4f}]  "
                  f"mf1={ci['embedding_nn_macro_f1']['mean']:.4f} "
                  f"[{ci['embedding_nn_macro_f1']['ci_95_lower']:.4f}, {ci['embedding_nn_macro_f1']['ci_95_upper']:.4f}]")
    print("=" * 70)
    print("Done.")


if __name__ == "__main__":
    main()
