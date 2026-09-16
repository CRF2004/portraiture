# State-Type and Label Contribution Analysis

This note analyzes where the learned state router improves the fixed held-out test split under the earlier relabeling pass. It is superseded in part by the stricter `topic_shift` rule and the semantic baseline results, which reduce the old `topic_shift` overuse effect.

## Compared systems

- `off`: baseline predictions from `no_refinement/predictions_baseline.jsonl`
- `heuristic`: state-aware predictions from `state_hint_heuristic_v2`
- `learned`: state-aware predictions from `state_hint_learned_v2`

All numbers below use the fixed test split in `data/processed/replay/replay_examples.jsonl`.

## Accuracy by fine label

| Label | Test Count | Off | Heuristic | Learned |
|---|---:|---:|---:|---:|
| ask_for_example | 2 | 0.000 | 0.500 | 0.500 |
| ask_why | 1 | 0.000 | 1.000 | 1.000 |
| compare_options | 3 | 0.000 | 0.000 | 0.000 |
| follow_up_clarification | 1 | 0.000 | 0.000 | 0.000 |
| provide_more_context | 2 | 0.000 | 0.000 | 0.000 |
| request_how_to | 3 | 0.000 | 0.000 | 0.667 |
| topic_shift | 28 | 0.107 | 0.214 | 0.643 |

## Accuracy by observed state type

| State Type | Test Count | Off | Heuristic | Learned |
|---|---:|---:|---:|---:|
| active_problem | 22 | 0.136 | 0.136 | 0.636 |
| blocking_issue | 9 | 0.000 | 0.444 | 0.444 |
| current_goal | 3 | 0.000 | 0.333 | 0.333 |
| current_stance | 6 | 0.000 | 0.000 | 0.500 |

## Top learned-router confusions

| Ground Truth | Predicted | Count |
|---|---|---:|
| topic_shift | challenge_or_refine | 3 |
| topic_shift | compare_options | 2 |
| compare_options | follow_up_clarification | 2 |
| topic_shift | ask_why | 2 |
| topic_shift | request_how_to | 2 |
| request_how_to | topic_shift | 1 |
| compare_options | topic_shift | 1 |
| provide_more_context | follow_up_clarification | 1 |
| topic_shift | follow_up_clarification | 1 |
| provide_more_context | request_how_to | 1 |
| ask_for_example | topic_shift | 1 |
| follow_up_clarification | topic_shift | 1 |

## Interpretation

1. The learned router's main fixed-split gain comes from recognizing `topic_shift`, especially in `active_problem` and `current_stance` contexts.
2. The learned router improves `request_how_to` on the fixed split, but the count is small.
3. `compare_options`, `follow_up_clarification`, and `provide_more_context` remain unresolved under the current labeler and predictor.
4. The result supports a paper claim about state-aware routing for replay prediction, not a broad claim that all user action categories are solved.

## Paper-ready claim boundary

Supported:

- Learned state routing improves held-out replay prediction over no-state and heuristic-state baselines.
- The strongest observed gain is in state-dependent topic-shift behavior.
- The method is still weak on minority action labels and should be framed as an early replay benchmark, not a complete digital twin.

Not supported:

- General user intent modeling across all action labels.
- Persona facts as the primary mechanism of improvement.
- Refinement as a held-out generalization mechanism.
