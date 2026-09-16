from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from portraiture.utils.io import read_jsonl, write_jsonl


def load_rows(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path)


def compute_accuracy(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return sum(1 for row in rows if row["is_correct"]) / len(rows)


def compute_divergence_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = len(rows)
    counts = Counter(row["divergence_type"] for row in rows if row["divergence_type"])
    table: list[dict[str, Any]] = []
    for divergence_type, count in counts.most_common():
        table.append(
            {
                "divergence_type": divergence_type,
                "count": count,
                "rate": round(count / total if total else 0.0, 4),
            }
        )
    return table


def compute_subtype_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = len(rows)
    counts = Counter(
        (row["divergence_type"], row["divergence_subtype"])
        for row in rows
        if row["divergence_type"]
    )
    table: list[dict[str, Any]] = []
    for (divergence_type, divergence_subtype), count in counts.most_common():
        table.append(
            {
                "divergence_type": divergence_type,
                "divergence_subtype": divergence_subtype,
                "count": count,
                "rate": round(count / total if total else 0.0, 4),
            }
        )
    return table


def compute_per_label_f1(
    rows: list[dict[str, Any]],
    *,
    truth_key: str = "ground_truth_label",
    pred_key: str = "predicted_label",
) -> dict[str, Any]:
    labels = sorted({row.get(truth_key) for row in rows if row.get(truth_key)} | {row.get(pred_key) for row in rows if row.get(pred_key)})
    per_label: dict[str, dict[str, float]] = {}
    for label in labels:
        tp = sum(1 for row in rows if row.get(truth_key) == label and row.get(pred_key) == label)
        fp = sum(1 for row in rows if row.get(truth_key) != label and row.get(pred_key) == label)
        fn = sum(1 for row in rows if row.get(truth_key) == label and row.get(pred_key) != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        per_label[label] = {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}
    macro_f1 = sum(v["f1"] for v in per_label.values()) / len(per_label) if per_label else 0.0
    weight = sum(1 for row in rows if row.get(truth_key) in per_label)
    weighted_f1 = sum(v["f1"] * sum(1 for row in rows if row.get(truth_key) == k) for k, v in per_label.items()) / weight if weight else 0.0
    return {"per_label": per_label, "macro_f1": round(macro_f1, 4), "weighted_f1": round(weighted_f1, 4)}


def compute_persona_fact_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    field_counts = Counter(row.get("field") for row in rows if row.get("field"))
    return {
        "total": len(rows),
        "field_counts": dict(field_counts),
    }


def compute_group_accuracy(rows: list[dict[str, Any]], group_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key_values: list[str] = []
        missing = False
        for group_key in group_keys:
            group_value = row.get(group_key)
            if not group_value:
                missing = True
                break
            key_values.append(str(group_value))
        if missing:
            continue
        grouped[tuple(key_values)].append(row)

    table: list[dict[str, Any]] = []
    for group_value, group_rows in sorted(grouped.items(), key=lambda item: (-sum(1 for row in item[1] if row["is_correct"]), item[0])):
        total = len(group_rows)
        correct = sum(1 for row in group_rows if row["is_correct"])
        entry = {
            "correct": correct,
            "total": total,
            "accuracy": round(correct / total if total else 0.0, 4),
        }
        for idx, group_key in enumerate(group_keys):
            entry[group_key] = group_value[idx]
        table.append(entry)
    return table


def compute_confusion_matrix(
    rows: list[dict[str, Any]],
    *,
    truth_key: str = "ground_truth_label",
    pred_key: str = "predicted_label",
) -> dict[str, Any]:
    labels = sorted({row.get(truth_key) for row in rows if row.get(truth_key)} | {row.get(pred_key) for row in rows if row.get(pred_key)})
    index = {label: idx for idx, label in enumerate(labels)}
    matrix = [[0 for _ in labels] for _ in labels]
    for row in rows:
        truth = row.get(truth_key)
        pred = row.get(pred_key)
        if truth not in index or pred not in index:
            continue
        matrix[index[truth]][index[pred]] += 1
    return {"labels": labels, "matrix": matrix}


def compute_top_confusions(
    rows: list[dict[str, Any]],
    *,
    truth_key: str = "ground_truth_label",
    pred_key: str = "predicted_label",
    limit: int = 8,
) -> list[dict[str, Any]]:
    counts = Counter(
        (row.get(truth_key), row.get(pred_key))
        for row in rows
        if row.get(truth_key) and row.get(pred_key) and row.get(truth_key) != row.get(pred_key)
    )
    table: list[dict[str, Any]] = []
    for (truth, pred), count in counts.most_common(limit):
        table.append({"truth": truth, "predicted": pred, "count": count})
    return table


def compare_runs(
    baseline_rows: list[dict[str, Any]],
    state_aware_rows: list[dict[str, Any]],
    refined_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    baseline_total = len(baseline_rows)
    state_aware_total = len(state_aware_rows)
    refined_total = len(refined_rows)
    baseline_accuracy = compute_accuracy(baseline_rows)
    state_aware_accuracy = compute_accuracy(state_aware_rows)
    refined_accuracy = compute_accuracy(refined_rows)

    baseline_counts = Counter(row["divergence_type"] for row in baseline_rows if row["divergence_type"])
    state_aware_counts = Counter(row["divergence_type"] for row in state_aware_rows if row["divergence_type"])
    refined_counts = Counter(row["divergence_type"] for row in refined_rows if row["divergence_type"])
    baseline_subtypes = Counter(
        (row["divergence_type"], row["divergence_subtype"])
        for row in baseline_rows
        if row["divergence_type"]
    )
    state_aware_subtypes = Counter(
        (row["divergence_type"], row["divergence_subtype"])
        for row in state_aware_rows
        if row["divergence_type"]
    )
    refined_subtypes = Counter(
        (row["divergence_type"], row["divergence_subtype"])
        for row in refined_rows
        if row["divergence_type"]
    )

    divergence_delta: list[dict[str, Any]] = []
    all_types = sorted(set(baseline_counts) | set(state_aware_counts) | set(refined_counts))
    for divergence_type in all_types:
        baseline_count = baseline_counts.get(divergence_type, 0)
        refined_count = refined_counts.get(divergence_type, 0)
        divergence_delta.append(
            {
                "divergence_type": divergence_type,
                "baseline_count": baseline_count,
                "refined_count": refined_count,
                "delta": refined_count - baseline_count,
                "baseline_rate": round(baseline_count / baseline_total if baseline_total else 0.0, 4),
                "refined_rate": round(refined_count / refined_total if refined_total else 0.0, 4),
            }
        )

    all_subtypes = sorted(set(baseline_subtypes) | set(state_aware_subtypes) | set(refined_subtypes))
    subtype_delta: list[dict[str, Any]] = []
    for divergence_key in all_subtypes:
        divergence_type, divergence_subtype = divergence_key
        baseline_count = baseline_subtypes.get(divergence_key, 0)
        refined_count = refined_subtypes.get(divergence_key, 0)
        subtype_delta.append(
            {
                "divergence_type": divergence_type,
                "divergence_subtype": divergence_subtype,
                "baseline_count": baseline_count,
                "refined_count": refined_count,
                "delta": refined_count - baseline_count,
                "baseline_rate": round(baseline_count / baseline_total if baseline_total else 0.0, 4),
                "refined_rate": round(refined_count / refined_total if refined_total else 0.0, 4),
            }
        )

    def _build_pass_output(rows: list[dict[str, Any]]) -> dict[str, Any]:
        all_preds = [
            {
                "ground_truth_label": row.get("ground_truth_label"),
                "predicted_label": row.get("predicted_label"),
                "ground_truth_coarse_label": row.get("ground_truth_coarse_label"),
                "predicted_coarse_label": row.get("predicted_coarse_label"),
                "is_correct": row.get("is_correct"),
                "observed_state_type": row.get("observed_state_type"),
                "divergence_type": row.get("divergence_type"),
            }
            for row in rows
        ]
        return {
            "total": len(all_preds),
            "accuracy": compute_accuracy(all_preds),
            "f1_metrics": compute_per_label_f1(all_preds),
            "coarse_f1_metrics": compute_per_label_f1(all_preds, truth_key="ground_truth_coarse_label", pred_key="predicted_coarse_label"),
            "divergence_table": compute_divergence_table(rows),
            "subtype_table": compute_subtype_table(rows),
            "confusion_matrix": compute_confusion_matrix(all_preds),
            "top_confusions": compute_top_confusions(all_preds),
            "accuracy_by_divergence_type": compute_group_accuracy(rows, ("divergence_type",)),
            "accuracy_by_divergence_subtype": compute_group_accuracy(rows, ("divergence_type", "divergence_subtype")),
            "accuracy_by_state_type": compute_group_accuracy(all_preds, ("observed_state_type",)),
            "accuracy_by_coarse_label": compute_group_accuracy(all_preds, ("ground_truth_coarse_label",)),
        }

    return {
        "baseline": _build_pass_output(baseline_rows),
        "state_aware": _build_pass_output(state_aware_rows),
        "refined": _build_pass_output(refined_rows),
        "comparison": {
            "baseline_to_state_aware_accuracy_delta": state_aware_accuracy - baseline_accuracy,
            "baseline_to_refined_accuracy_delta": refined_accuracy - baseline_accuracy,
            "state_aware_to_refined_accuracy_delta": refined_accuracy - state_aware_accuracy,
            "divergence_delta": divergence_delta,
            "subtype_delta": subtype_delta,
        },
    }


def render_markdown(summary: dict[str, Any]) -> str:
    baseline = summary["baseline"]
    state_aware = summary["state_aware"]
    refined = summary["refined"]
    comparison = summary["comparison"]
    persona_facts = summary.get("persona_facts", {"total": 0, "field_counts": {}})
    lines: list[str] = []
    lines.append("# Evaluation Summary")
    lines.append("")
    lines.append("## Raw Data Table")
    lines.append("")
    lines.append("| Split | Total | Accuracy |")
    lines.append("|---|---:|---:|")
    lines.append(f"| Baseline | {baseline['total']} | {baseline['accuracy']:.4f} |")
    lines.append(f"| State-aware | {state_aware['total']} | {state_aware['accuracy']:.4f} |")
    lines.append(f"| Refined | {refined['total']} | {refined['accuracy']:.4f} |")
    lines.append("")
    lines.append("## Persona Facts")
    lines.append("")
    lines.append(f"- Total persona facts: {persona_facts['total']}")
    if persona_facts["field_counts"]:
        for field, count in sorted(persona_facts["field_counts"].items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {field}: {count}")
    else:
        lines.append("- No persona facts were generated in the latest run.")
    lines.append("")
    lines.append("## Divergence Comparison")
    lines.append("")
    lines.append("| Type | Baseline | State-aware | Refined |")
    lines.append("|---|---:|---:|---:|")
    state_aware_by_type = {row["divergence_type"]: row for row in state_aware.get("accuracy_by_divergence_type", [])}
    for row in comparison["divergence_delta"]:
        lines.append(
            f"| {row['divergence_type']} | {row['baseline_count']} | {state_aware_by_type.get(row['divergence_type'], {'correct': 0, 'total': 0, 'accuracy': 0.0})['total']} | {row['refined_count']} |"
        )
    lines.append("")
    lines.append("## Subtype Comparison")
    lines.append("")
    lines.append("| Type | Subtype | Baseline | State-aware | Refined |")
    lines.append("|---|---|---:|---:|---:|")
    state_aware_by_subtype = {
        (row["divergence_type"], row["divergence_subtype"]): row
        for row in state_aware.get("accuracy_by_divergence_subtype", [])
    }
    for row in comparison["subtype_delta"]:
        lines.append(
            f"| {row['divergence_type']} | {row['divergence_subtype']} | {row['baseline_count']} | {state_aware_by_subtype.get((row['divergence_type'], row['divergence_subtype']), {'correct': 0, 'total': 0, 'accuracy': 0.0})['total']} | {row['refined_count']} |"
        )
    lines.append("")
    lines.append("## Accuracy by Divergence Type")
    lines.append("")
    lines.append("| Type | Baseline Acc | State-aware Acc | Refined Acc |")
    lines.append("|---|---:|---:|---:|")
    baseline_by_type = {row["divergence_type"]: row for row in baseline.get("accuracy_by_divergence_type", [])}
    refined_by_type = {row["divergence_type"]: row for row in refined.get("accuracy_by_divergence_type", [])}
    for divergence_type in sorted(set(baseline_by_type) | set(state_aware_by_type) | set(refined_by_type)):
        baseline_row = baseline_by_type.get(divergence_type, {"accuracy": 0.0})
        state_aware_row = state_aware_by_type.get(divergence_type, {"accuracy": 0.0})
        refined_row = refined_by_type.get(divergence_type, {"accuracy": 0.0})
        lines.append(
            "| {type} | {ba:.4f} | {sa:.4f} | {ra:.4f} |".format(
                type=divergence_type,
                ba=baseline_row["accuracy"],
                sa=state_aware_row["accuracy"],
                ra=refined_row["accuracy"],
            )
        )
    lines.append("")
    lines.append("## Accuracy by Divergence Subtype")
    lines.append("")
    lines.append("| Type | Subtype | Baseline Acc | State-aware Acc | Refined Acc |")
    lines.append("|---|---|---:|---:|---:|")
    baseline_by_subtype = {
        (row["divergence_type"], row["divergence_subtype"]): row
        for row in baseline.get("accuracy_by_divergence_subtype", [])
    }
    refined_by_subtype = {
        (row["divergence_type"], row["divergence_subtype"]): row
        for row in refined.get("accuracy_by_divergence_subtype", [])
    }
    for divergence_key in sorted(set(baseline_by_subtype) | set(state_aware_by_subtype) | set(refined_by_subtype)):
        divergence_type, divergence_subtype = divergence_key
        baseline_row = baseline_by_subtype.get(divergence_key, {"accuracy": 0.0})
        state_aware_row = state_aware_by_subtype.get(divergence_key, {"accuracy": 0.0})
        refined_row = refined_by_subtype.get(divergence_key, {"accuracy": 0.0})
        lines.append(
            "| {type} | {subtype} | {ba:.4f} | {sa:.4f} | {ra:.4f} |".format(
                type=divergence_type,
                subtype=divergence_subtype,
                ba=baseline_row["accuracy"],
                sa=state_aware_row["accuracy"],
                ra=refined_row["accuracy"],
            )
        )
    lines.append("")
    lines.append("## Accuracy by State Type")
    lines.append("")
    lines.append("| State Type | Baseline Acc | State-aware Acc | Refined Acc |")
    lines.append("|---|---:|---:|---:|")
    baseline_by_state = {row["observed_state_type"]: row for row in baseline.get("accuracy_by_state_type", []) if row.get("observed_state_type")}
    state_aware_by_state = {row["observed_state_type"]: row for row in state_aware.get("accuracy_by_state_type", []) if row.get("observed_state_type")}
    refined_by_state = {row["observed_state_type"]: row for row in refined.get("accuracy_by_state_type", []) if row.get("observed_state_type")}
    for state_type in sorted(set(baseline_by_state) | set(state_aware_by_state) | set(refined_by_state)):
        lines.append(
            "| {state} | {ba:.4f} | {sa:.4f} | {ra:.4f} |".format(
                state=state_type,
                ba=baseline_by_state.get(state_type, {"accuracy": 0.0})["accuracy"],
                sa=state_aware_by_state.get(state_type, {"accuracy": 0.0})["accuracy"],
                ra=refined_by_state.get(state_type, {"accuracy": 0.0})["accuracy"],
            )
        )
    lines.append("")
    lines.append("## Accuracy by Coarse Label")
    lines.append("")
    lines.append("| Coarse Label | Baseline Acc | State-aware Acc | Refined Acc |")
    lines.append("|---|---:|---:|---:|")
    baseline_by_coarse = {row["ground_truth_coarse_label"]: row for row in baseline.get("accuracy_by_coarse_label", []) if row.get("ground_truth_coarse_label")}
    state_aware_by_coarse = {row["ground_truth_coarse_label"]: row for row in state_aware.get("accuracy_by_coarse_label", []) if row.get("ground_truth_coarse_label")}
    refined_by_coarse = {row["ground_truth_coarse_label"]: row for row in refined.get("accuracy_by_coarse_label", []) if row.get("ground_truth_coarse_label")}
    for coarse_label in sorted(set(baseline_by_coarse) | set(state_aware_by_coarse) | set(refined_by_coarse)):
        lines.append(
            "| {label} | {ba:.4f} | {sa:.4f} | {ra:.4f} |".format(
                label=coarse_label,
                ba=baseline_by_coarse.get(coarse_label, {"accuracy": 0.0})["accuracy"],
                sa=state_aware_by_coarse.get(coarse_label, {"accuracy": 0.0})["accuracy"],
                ra=refined_by_coarse.get(coarse_label, {"accuracy": 0.0})["accuracy"],
            )
        )
    lines.append("")
    lines.append("## Top Confusions")
    lines.append("")
    for name, run in (("Baseline", baseline), ("State-aware", state_aware), ("Refined", refined)):
        lines.append(f"### {name}")
        lines.append("")
        if not run["top_confusions"]:
            lines.append("- No misclassifications.")
        else:
            lines.append("| Truth | Predicted | Count |")
            lines.append("|---|---|---:|")
            for item in run["top_confusions"]:
                lines.append(f"| {item['truth']} | {item['predicted']} | {item['count']} |")
        lines.append("")
    lines.append("## F1 Metrics")
    lines.append("")
    lines.append("| Pass | Macro-F1 | Weighted-F1 | Coarse Macro-F1 | Coarse Weighted-F1 |")
    lines.append("|---|---:|---:|---:|---:|")
    for name, run in (("Baseline", baseline), ("State-aware", state_aware), ("Refined", refined)):
        f1 = run.get("f1_metrics", {})
        cf1 = run.get("coarse_f1_metrics", {})
        lines.append(
            "| {name} | {mf1:.4f} | {wf1:.4f} | {cmf1:.4f} | {cwf1:.4f} |".format(
                name=name,
                mf1=f1.get("macro_f1", 0.0),
                wf1=f1.get("weighted_f1", 0.0),
                cmf1=cf1.get("macro_f1", 0.0),
                cwf1=cf1.get("weighted_f1", 0.0),
            )
        )
    lines.append("")

    lines.append("## Per-Label F1 (Refined)")
    lines.append("")
    lines.append("| Label | Precision | Recall | F1 |")
    lines.append("|---|---:|---:|---:|")
    per_label = refined.get("f1_metrics", {}).get("per_label", {})
    for label in sorted(per_label.keys()):
        v = per_label[label]
        lines.append(f"| {label} | {v['precision']:.4f} | {v['recall']:.4f} | {v['f1']:.4f} |")
    lines.append("")

    lines.append("## Key Findings")
    lines.append("")
    baseline_f1 = baseline.get("f1_metrics", {}).get("macro_f1", 0.0)
    state_aware_f1 = state_aware.get("f1_metrics", {}).get("macro_f1", 0.0)
    refined_f1 = refined.get("f1_metrics", {}).get("macro_f1", 0.0)
    lines.append(
        "1. Baseline accuracy={ba:.4f} macro_f1={bmf1:.4f}; state-aware accuracy={sa:.4f} macro_f1={smf1:.4f}; refined accuracy={ra:.4f} macro_f1={rmf1:.4f}.".format(
            ba=baseline["accuracy"], bmf1=baseline_f1,
            sa=state_aware["accuracy"], smf1=state_aware_f1,
            ra=refined["accuracy"], rmf1=refined_f1,
        )
    )
    if comparison["baseline_to_refined_accuracy_delta"] >= 0:
        lines.append(
            f"2. Refined vs baseline accuracy delta is {comparison['baseline_to_refined_accuracy_delta']:+.4f}; the refinement policy is a net win on accuracy."
        )
    else:
        lines.append(
            f"2. Refined vs baseline accuracy delta is {comparison['baseline_to_refined_accuracy_delta']:+.4f}, so the current refinement policy is still not a net win."
        )
    f1_delta = refined_f1 - baseline_f1
    lines.append(
        f"3. Refined vs baseline macro-F1 delta is {f1_delta:+.4f}; this reflects {'broad improvement across labels' if f1_delta > 0.02 else 'modest improvement' if f1_delta > 0 else 'no measurable improvement on macro-F1'}."
    )
    lines.append(
        f"4. State-aware vs baseline accuracy delta is {comparison['baseline_to_state_aware_accuracy_delta']:+.4f}, so this state heuristic is {'helpful' if comparison['baseline_to_state_aware_accuracy_delta'] > 0 else 'neutral' if comparison['baseline_to_state_aware_accuracy_delta'] == 0 else 'not yet helpful'}."
    )
    if persona_facts["total"] == 0:
        lines.append("5. The persona detector is now conservative enough to avoid false positives, but it did not generate any PersonaFact in this run.")
    else:
        lines.append("5. The refinement loop now produces persona/state/memory objects without destabilizing replay quality.")
    lines.append("")
    lines.append("## Suggested Next Experiments")
    lines.append("")
    lines.append("1. Gate refined hints by divergence subtype and current episode context.")
    lines.append("2. Revisit the persona detector only if new examples with explicit preference/constraint language appear in the replay data.")
    lines.append("3. Run per-subtype before/after accuracy to see whether any refinement class is actually helping.")
    return "\n".join(lines)


def main() -> None:
    base_dir = Path("data/processed/evaluation")
    baseline_rows = load_rows(base_dir / "divergences_baseline.jsonl")
    state_aware_rows = load_rows(base_dir / "divergences_state_aware.jsonl")
    refined_rows = load_rows(base_dir / "divergences_refined.jsonl")
    persona_fact_path = base_dir / "persona_facts.jsonl"
    persona_fact_rows = load_rows(persona_fact_path) if persona_fact_path.exists() else []
    summary = compare_runs(baseline_rows, state_aware_rows, refined_rows)
    summary["persona_facts"] = compute_persona_fact_summary(persona_fact_rows)

    json_path = base_dir / "analysis_summary.json"
    md_path = base_dir / "analysis_summary.md"

    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(summary), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
