# Experiment Audit Report

**Date**: 2026-06-28  
**Auditor**: Executor self-audit; external Codex reviewer backend unavailable in this environment  
**Project**: Portraiture

## Overall Verdict: WARN

## Integrity Status: warn

The experiment files and reported numbers are present and internally consistent, but the evaluation must be described as a proxy replay benchmark. The action labels are rule-derived from user text, not human annotations or an official benchmark ground truth. Scope is also single-user and small-sample.

## Checks

### A. Ground Truth Provenance: WARN

Evidence:

- `src/portraiture/replay/builder.py:135` writes `ground_truth_label=action_label`.
- `src/portraiture/replay/builder.py:89` computes `action_label = infer_action_label(...)`.
- `src/portraiture/replay/signals.py:225` defines `infer_state_hint_for_divergence`.
- `src/portraiture/replay/signals.py:63` and nearby logic derive action labels from text markers and similarity.

Details:

- The target user message is real historical chat data.
- The next-action label is not a dataset-provided human label. It is a rule-derived proxy label inferred from the target user text.
- This is acceptable for an early replay benchmark only if the paper explicitly calls it proxy-labeled replay evaluation.

Status: WARN, not FAIL, because the project documentation already frames this as a replay proxy and does not claim official labels.

### B. Score Normalization: PASS

Evidence:

- `src/portraiture/evaluation/replay.py:520-535` computes accuracy and macro-F1 from raw counts.
- No metric computation divides scores by the model's own maximum, minimum, or mean output.

Details:

- Accuracy is `correct / len(rows)`.
- Macro-F1 is computed from per-label TP/FP/FN.
- No suspicious self-normalized 0.99-style metric was found.

### C. Result File Existence: PASS

Evidence:

- `data/processed/evaluation/state_hint_learned_v2/metrics.jsonl` contains learned fixed test accuracy `0.55` and macro-F1 `0.29833333333333334`.
- `data/processed/evaluation/state_hint_heuristic_v2/metrics.jsonl` contains heuristic fixed test accuracy `0.2` and macro-F1 `0.10357142857142856`.
- `data/processed/evaluation/no_refinement/metrics.jsonl` contains no-refinement test accuracy `0.075` and macro-F1 `0.025974025974025976`.
- `data/processed/evaluation/robustness_state_prior_episode/metrics.jsonl` exists with 60 rows.
- `data/processed/evaluation/robustness_state_prior_conversation/metrics.jsonl` exists with 60 rows.
- `docs/paper_ready_experiment_conclusion.md` reports numbers matching these files.

Details:

- The main reported fixed-split and robustness numbers are backed by result files.
- Older leaky files still exist, but `docs/ablation_findings.md` explicitly warns not to use them as the paper source.

### D. Dead Code Detection: WARN

Evidence:

- `src/portraiture/evaluation/replay.py:511-535` defines and uses `compute_classification_metrics`.
- `src/portraiture/evaluation/robustness.py` imports and uses `compute_classification_metrics`.
- `src/portraiture/evaluation/report.py` exists but is not part of the current robustness chain.
- `src/portraiture/evaluation/relabel_candidates.py` exists but is diagnostic and not part of the main metric claim.

Details:

- Main metric functions are called and outputs appear in result files.
- Some diagnostic/reporting scripts are not part of the current paper claim path; this is acceptable but should not be cited as active evidence unless rerun.

### E. Scope Assessment: WARN

Evidence:

- `data/processed/replay/replay_examples.jsonl` has 257 replay examples.
- Robustness runs cover 5 random episode splits and 5 random conversation splits.
- The data appears to be single-user (`user_demo`) personal GPT chat logs.
- Fixed test split contains 40 examples, with strong label imbalance (`topic_shift` dominates).

Details:

- Scope is sufficient for a method prototype and benchmark-style paper draft.
- Scope is not sufficient for claims like "comprehensive digital twin evaluation" or "general personal AI behavior modeling".
- The paper should use careful language: "single-user proxy replay benchmark", "initial evidence", "state-aware replay", and "held-out replay prediction".

### F. Manual Label Audit: WARN

Evidence:

- A manual spot audit of 12 high-risk candidates was conducted from `data/processed/evaluation/relabel_candidates.jsonl`.
- Clear label errors: 6 / 12.
- Borderline cases: 1 / 12.
- Acceptable labels: 5 / 12.

Observed failure modes:

- `topic_shift` is overused for same-thread refinements and chapter/figure continuation.
- `follow_up_clarification` and `provide_more_context` are the most common boundary pair.
- `compare_options` looked stable in the reviewed sample.

Interpretation:

- The proxy labels are usable for a benchmark paper, but they are not clean enough to claim human-grade semantic ground truth.
- The audit strengthens the paper's limitations section, not the core quantitative claim.

### G. Evaluation Type: self_supervised_proxy

Classification:

- Evaluation type: `self_supervised_proxy`

Details:

- User text is real historical data.
- Labels are derived from rules over text and context, not human annotation.
- The evaluation measures agreement with a proxy action label, not direct semantic correctness judged by humans.

## Action Items

- Explicitly describe labels as rule-derived proxy labels in Abstract, Methods, and Limitations.
- Add a small manual label audit before submission if possible, even 50-100 examples, to estimate proxy-label noise.
- Treat macro-F1 as the main balanced metric because `state_prior` shows accuracy can be inflated by dominant action modes.
- Do not claim refinement improves held-out generalization.
- Do not claim persona facts are the main source of improvement.
- Do not claim a complete digital twin; claim state-aware replay prediction.

## Claim Impact

- C1: "Learned state routing improves replay next-action prediction over no-state and heuristic baselines." Supported with qualifier.
- C2: "Dynamic state is more useful than current static persona/refinement mechanisms." Supported with qualifier.
- C3: "The system is a complete personal digital twin." Unsupported.
- C4: "The benchmark provides robust evidence across multiple splits." Needs qualifier: robust across random episode/conversation splits for one user, not across users.

## Paper Writing Gate

Status: READY WITH WARNINGS.

The experiments are sufficient to begin paper writing if the paper is framed as:

- a single-user proxy replay benchmark,
- a state-aware method for personal chat-log replay,
- an empirical finding that learned state routing is the strongest current mechanism.

The experiments are not sufficient for a broad digital-twin or human-level simulation claim.
