# Paper Plan

**Working title**: Beyond Persona: Dynamic State Routing for Personal Chat-Log Replay  
**Paper type**: Method-and-benchmark paper  
**Target style**: ML/AI workshop or short conference submission  
**Date**: 2026-06-28

## One-Sentence Contribution

We introduce a proxy replay benchmark for personal GPT chat logs and show that learned dynamic state routing is a stronger first-order signal for predicting a user's next conversational action than static persona facts or leakage-prone refinement.

## Claims-Evidence Matrix

| Claim | Evidence | Status | Section |
|---|---|---|---|
| C1: State-aware replay improves held-out next-action prediction. | Fixed split: learned router accuracy 0.5500 and macro-F1 0.2983 vs heuristic 0.2000/0.1036 and off 0.0750/0.0260. | Supported with proxy-label caveat | Experiments |
| C2: The learned router is directionally robust across split strategies. | Random episode split: learned macro-F1 0.2683 +/- 0.0511; random conversation split: learned macro-F1 0.2877 +/- 0.0445. | Supported for single-user data | Robustness |
| C3: Accuracy alone is insufficient because state priors exploit dominant modes. | `state_prior` has high accuracy but macro-F1 0.0917/0.1017 under episode/conversation splits. | Supported | Analysis |
| C4: Current persona extraction and refinement are not reliable held-out gain sources. | Leak-free ablation: train-only refinement does not improve test; persona facts alone weak. | Supported | Discussion |

## Paper Storyline

- Digital twins from chat logs should be evaluated by behavioral replay, not only by persona descriptions or style mimicry.
- A replay benchmark can be built from historical user turns using proxy next-action labels.
- Static persona facts and post-hoc refinement are not enough under leakage-free evaluation.
- Dynamic state routing is the main usable signal in the current prototype.
- The result is promising but limited: labels are proxy-derived, data is single-user, and minority labels remain weak.

## Section Plan

### Abstract
- State problem: personal digital twins from chat logs lack measurable behavioral replay evaluation.
- Method: proxy replay benchmark with explicit persona/state/memory representation and learned state routing.
- Evidence: fixed split and random split results.
- Caveat: single-user proxy labels.

### 1. Introduction
- Motivate personal assistants and digital twins.
- Gap: persona descriptions and long-context memory do not directly test whether a system predicts what the user does next.
- Contributions:
  1. A proxy replay formulation over personal GPT chat logs.
  2. A state-aware routing method for next-action prediction.
  3. Leakage-free ablations and robustness checks.
  4. A negative finding: static persona/refinement are currently weaker than dynamic state.

### 2. Related Work
- Generative agents and behavior simulation.
- Personalization and user modeling for LLMs.
- Long-term memory and digital twins.
- Positioning: this paper focuses on single-user historical replay with explicit state routing.

### 3. Replay Benchmark and Method
- Define conversation, episode, context, target turn, action labels.
- Explain proxy labels and limitations.
- Describe baselines: off, heuristic state hint, learned router, state_prior.
- Describe leakage-free split and refinement restriction.

### 4. Experiments
- Data: 257 replay examples from one user's GPT logs.
- Metrics: accuracy and macro-F1, with macro-F1 emphasized.
- Main fixed split table.
- Random episode/conversation robustness table.

### 5. Analysis
- State_prior shows accuracy can be misleading.
- Learned gains concentrate in topic_shift, active_problem, current_stance.
- Remaining failures: compare_options, follow_up_clarification, provide_more_context.

### 6. Limitations and Ethics
- Single user.
- Proxy labels.
- Privacy and consent.
- No claim of complete digital twin.

### 7. Conclusion
- State-aware replay is a practical path toward measurable personal digital twins.
- Next steps: manual label audit, multi-user data, stronger semantic evaluators.

## Figure/Table Plan

- Table 1: Fixed split main results.
- Table 2: Random episode and conversation robustness.
- Table 3: Fixed-split per-label/state-type diagnosis.
- Figure 1: Pipeline diagram from chat logs to proxy replay to state router.

