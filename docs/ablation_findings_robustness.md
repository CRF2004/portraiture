# Portraiture Split Robustness Findings

This note records the random episode-level and random conversation-level split robustness checks for the state hint variants.

## Why this note exists

The fixed chronological split showed a strong learned state router result, but that result could still depend on one favorable time split. These experiments reassign splits across five random seeds and compare:

- `off`: no state hint
- `heuristic`: rule-based state hint
- `learned`: Naive Bayes state router trained only on the random train split

The experiment does not use refinement and does not overwrite the main evaluation outputs.

## Setup: Random Episode Split

- Seeds: `11, 23, 37, 51, 73`
- Split strategy: random episode-level split
- Split ratio: train `0.70`, val `0.15`, test `0.15`
- Router threshold: `0.35`
- Outputs:
  - `data/processed/evaluation/robustness/metrics.jsonl`
  - `data/processed/evaluation/robustness/diagnostics.jsonl`
  - `data/processed/evaluation/robustness/summary.md`

## Key results

Test-set mean +/- std across five random episode splits:

| Mode | Accuracy | Macro-F1 | Coarse Accuracy | Coarse Macro-F1 |
|---|---:|---:|---:|---:|
| off | 0.1641 +/- 0.0872 | 0.1370 +/- 0.0408 | 0.2670 +/- 0.0680 | 0.2293 +/- 0.0458 |
| heuristic | 0.2348 +/- 0.1315 | 0.2195 +/- 0.0764 | 0.2876 +/- 0.1338 | 0.2307 +/- 0.0901 |
| learned | 0.4370 +/- 0.1116 | 0.2683 +/- 0.0511 | 0.4598 +/- 0.1116 | 0.3061 +/- 0.0529 |

## Per-seed interpretation

- Learned beats `off` on accuracy and macro-F1 in all 5 seeds.
- Learned beats `heuristic` on accuracy in all 5 seeds.
- Learned beats `heuristic` on macro-F1 in 4 of 5 seeds; seed `51` is the exception, where learned has higher accuracy but slightly lower macro-F1.
- Variance is non-trivial, so the paper should report robustness as a directional result rather than a single precise effect size.

## Setup: Random Conversation Split

- Seeds: `11, 23, 37, 51, 73`
- Split strategy: random conversation-level split
- Split ratio: train `0.70`, val `0.15`, test `0.15`
- Router threshold: `0.35`
- Outputs:
  - `data/processed/evaluation/robustness_conversation/metrics.jsonl`
  - `data/processed/evaluation/robustness_conversation/diagnostics.jsonl`
  - `data/processed/evaluation/robustness_conversation/summary.md`

Test-set mean +/- std across five random conversation splits:

| Mode | Accuracy | Macro-F1 | Coarse Accuracy | Coarse Macro-F1 |
|---|---:|---:|---:|---:|
| off | 0.2539 +/- 0.1319 | 0.1785 +/- 0.0606 | 0.3307 +/- 0.0738 | 0.2439 +/- 0.0492 |
| heuristic | 0.3559 +/- 0.1121 | 0.2298 +/- 0.0741 | 0.4139 +/- 0.1059 | 0.2991 +/- 0.1277 |
| learned | 0.4854 +/- 0.1093 | 0.2877 +/- 0.0445 | 0.4915 +/- 0.1014 | 0.3035 +/- 0.0465 |

Conversation split interpretation:

- Learned beats `off` on average for accuracy and macro-F1.
- Learned beats `heuristic` on average for accuracy and macro-F1, but the macro-F1 margin is modest.
- Learned's strongest advantage is accuracy; class-balanced behavior still needs per-label diagnosis.

## Current research conclusion

The learned state router is not just an artifact of the original chronological split. Across random episode-level and conversation-level splits, it remains the strongest state-hint variant on average and provides a robust improvement over no state hint.

The safe paper claim is:

- state-aware routing is the strongest current mechanism for replay behavior prediction
- a learned state selector improves over no-state and heuristic-state variants across random episode and conversation splits

The unsafe claim remains:

- refinement improves held-out generalization
- persona facts are the main driver of improvement
- the current router is fully proven under topic-held-out or user-held-out settings

## Next experimental direction

1. Add leave-topic-out or topic-cluster evaluation to test whether the router transfers across semantic clusters.
2. Add a simple retrieval/profile baseline so the learned router is not only compared against weak rules.
3. Analyze which state types drive the learned gain, especially `current_goal`, `blocking_issue`, and `active_problem`.
4. Run per-label failure analysis because learned improves accuracy more clearly than macro-F1.
