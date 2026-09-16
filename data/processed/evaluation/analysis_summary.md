# Evaluation Summary

## Raw Data Table

| Split | Total | Accuracy |
|---|---:|---:|
| Baseline | 257 | 0.5370 |
| State-aware | 257 | 0.5642 |
| Refined | 257 | 0.6420 |

## Persona Facts

- Total persona facts: 3
- explanation_preference: 1
- interaction_style: 1
- planning_preference: 1

## Divergence Comparison

| Type | Baseline | State-aware | Refined |
|---|---:|---:|---:|
| action_selection_error | 29 | 30 | 21 |
| persona_misalignment | 0 | 0 | 1 |
| reasoning_mismatch | 3 | 3 | 3 |
| state_under_specified | 87 | 79 | 67 |

## Subtype Comparison

| Type | Subtype | Baseline | State-aware | Refined |
|---|---|---:|---:|---:|
| action_selection_error | ranking_error | 14 | 15 | 5 |
| action_selection_error | task_label_too_coarse | 5 | 5 | 4 |
| action_selection_error | wrong_turn_boundary | 10 | 10 | 12 |
| persona_misalignment | trait_overgeneralized | 0 | 0 | 1 |
| reasoning_mismatch | wrong_intent_inference | 3 | 3 | 3 |
| state_under_specified | blocking_issue_missed | 12 | 8 | 8 |
| state_under_specified | goal_shift_missed | 69 | 64 | 53 |
| state_under_specified | stance_change_missed | 6 | 7 | 6 |

## Accuracy by Divergence Type

| Type | Baseline Acc | State-aware Acc | Refined Acc |
|---|---:|---:|---:|
| action_selection_error | 0.0000 | 0.0000 | 0.0000 |
| persona_misalignment | 0.0000 | 0.0000 | 0.0000 |
| reasoning_mismatch | 0.0000 | 0.0000 | 0.0000 |
| state_under_specified | 0.0000 | 0.0000 | 0.0000 |

## Accuracy by Divergence Subtype

| Type | Subtype | Baseline Acc | State-aware Acc | Refined Acc |
|---|---|---:|---:|---:|
| action_selection_error | ranking_error | 0.0000 | 0.0000 | 0.0000 |
| action_selection_error | task_label_too_coarse | 0.0000 | 0.0000 | 0.0000 |
| action_selection_error | wrong_turn_boundary | 0.0000 | 0.0000 | 0.0000 |
| persona_misalignment | trait_overgeneralized | 0.0000 | 0.0000 | 0.0000 |
| reasoning_mismatch | wrong_intent_inference | 0.0000 | 0.0000 | 0.0000 |
| state_under_specified | blocking_issue_missed | 0.0000 | 0.0000 | 0.0000 |
| state_under_specified | goal_shift_missed | 0.0000 | 0.0000 | 0.0000 |
| state_under_specified | stance_change_missed | 0.0000 | 0.0000 | 0.0000 |

## Accuracy by State Type

| State Type | Baseline Acc | State-aware Acc | Refined Acc |
|---|---:|---:|---:|
| active_problem | 0.5772 | 0.5772 | 0.6829 |
| blocking_issue | 0.5211 | 0.6197 | 0.6479 |
| current_goal | 0.4688 | 0.4688 | 0.5312 |
| current_stance | 0.3529 | 0.3529 | 0.5294 |
| time_pressure | 0.8000 | 0.8000 | 0.8000 |
| uncertainty_level | 0.5556 | 0.5556 | 0.5556 |

## Accuracy by Coarse Label

| Coarse Label | Baseline Acc | State-aware Acc | Refined Acc |
|---|---:|---:|---:|
| clarify | 0.5745 | 0.5745 | 0.5957 |
| compare | 0.6000 | 0.5333 | 0.6000 |
| expand | 0.7188 | 0.7500 | 0.7500 |
| plan | 0.6279 | 0.6744 | 0.7674 |
| shift | 0.4333 | 0.4750 | 0.5917 |

## Top Confusions

### Baseline

| Truth | Predicted | Count |
|---|---|---:|
| topic_shift | ask_why | 29 |
| topic_shift | ask_for_example | 8 |
| follow_up_clarification | topic_shift | 7 |
| topic_shift | request_how_to | 7 |
| topic_shift | feasibility_check | 6 |
| topic_shift | compare_options | 6 |
| topic_shift | challenge_or_refine | 5 |
| request_how_to | ask_why | 5 |

### State-aware

| Truth | Predicted | Count |
|---|---|---:|
| topic_shift | ask_why | 26 |
| follow_up_clarification | topic_shift | 7 |
| topic_shift | challenge_or_refine | 7 |
| topic_shift | request_how_to | 7 |
| topic_shift | feasibility_check | 6 |
| topic_shift | ask_for_example | 5 |
| topic_shift | compare_options | 5 |
| request_how_to | ask_why | 5 |

### Refined

| Truth | Predicted | Count |
|---|---|---:|
| topic_shift | request_how_to | 12 |
| follow_up_clarification | topic_shift | 10 |
| topic_shift | challenge_or_refine | 8 |
| topic_shift | ask_definition | 7 |
| topic_shift | feasibility_check | 6 |
| topic_shift | compare_options | 6 |
| topic_shift | ask_for_example | 4 |
| request_how_to | topic_shift | 4 |

## F1 Metrics

| Pass | Macro-F1 | Weighted-F1 | Coarse Macro-F1 | Coarse Weighted-F1 |
|---|---:|---:|---:|---:|
| Baseline | 0.4880 | 0.5773 | 0.4703 | 0.5594 |
| State-aware | 0.4978 | 0.6035 | 0.4894 | 0.5902 |
| Refined | 0.5552 | 0.6575 | 0.5357 | 0.6547 |

## Per-Label F1 (Refined)

| Label | Precision | Recall | F1 |
|---|---:|---:|---:|
| ask_definition | 0.3000 | 0.6000 | 0.4000 |
| ask_for_example | 0.7500 | 0.8824 | 0.8108 |
| ask_why | 0.4000 | 0.5000 | 0.4444 |
| challenge_or_refine | 0.0000 | 0.0000 | 0.0000 |
| compare_options | 0.4737 | 0.6000 | 0.5294 |
| feasibility_check | 0.6000 | 0.7059 | 0.6486 |
| follow_up_clarification | 0.7778 | 0.6176 | 0.6885 |
| provide_more_context | 0.8182 | 0.6000 | 0.6923 |
| request_how_to | 0.5833 | 0.8077 | 0.6774 |
| topic_shift | 0.7474 | 0.5917 | 0.6605 |

## Key Findings

1. Baseline accuracy=0.5370 macro_f1=0.4880; state-aware accuracy=0.5642 macro_f1=0.4978; refined accuracy=0.6420 macro_f1=0.5552.
2. Refined vs baseline accuracy delta is +0.1051; the refinement policy is a net win on accuracy.
3. Refined vs baseline macro-F1 delta is +0.0672; this reflects broad improvement across labels.
4. State-aware vs baseline accuracy delta is +0.0272, so this state heuristic is helpful.
5. The refinement loop now produces persona/state/memory objects without destabilizing replay quality.

## Suggested Next Experiments

1. Gate refined hints by divergence subtype and current episode context.
2. Revisit the persona detector only if new examples with explicit preference/constraint language appear in the replay data.
3. Run per-subtype before/after accuracy to see whether any refinement class is actually helping.