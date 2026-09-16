# Experiment Plan

**Problem**: Build a leakage-free replay benchmark for explicit user portrait modeling from chat logs.
**Method Thesis**: A learned state selector may outperform a heuristic state hint when mapping recent conversation context to the action label needed for replay prediction.
**Date**: 2026-06-28

## Claim Map
| Claim | Why It Matters | Minimum Convincing Evidence | Linked Blocks |
|-------|----------------|-----------------------------|---------------|
| C1 | State-aware replay improves held-out prediction beyond no state hint. | `heuristic` or `learned` state-aware pass beats `off` on test split, without leakage. | B1, B2 |
| C2 | A learned state selector is more robust than a hand-written heuristic mapper. | `learned` state-aware pass beats `heuristic` on test split or improves calibration/error coverage. | B2, B3 |
| C3 | The current refinement loop is not the source of the gain. | Train-only refinement stays flat or worse than state hint gains. | B1, B4 |

## Paper Storyline
- Main paper must prove:
  - The replay setup is leakage-free.
  - State hints provide a real, test-time usable gain.
  - Learned state routing is a plausible next step if it improves over heuristic routing.
- Appendix can support:
  - Confidence thresholds, candidate distributions, state label breakdowns, failure cases.
- Experiments intentionally cut:
  - More complex multi-stage refinement policies until the state router result is known.

## Experiment Blocks

### Block 1: Leakage-Free Replay Control
- Claim tested: train-only refinement does not inflate held-out performance.
- Why this block exists: it isolates whether any gain is genuine or caused by state leakage.
- Dataset / split / task: replay examples split into train / val / test; refinement only on train.
- Compared systems:
  - `off`
  - `train_refinement`
- Metrics:
  - accuracy, macro-F1 on train / val / test
- Setup details:
  - Use the current replay pipeline with `--skip-baseline-refinement` and `--refinement-splits train`.
- Success criterion:
  - Held-out metrics remain stable when refinement is restricted to train.
- Failure interpretation:
  - If train-only refinement helps a lot, the refinement policy may be genuinely useful.
- Table / figure target: main ablation table.
- Priority: MUST-RUN

### Block 2: Heuristic State Hint Baseline
- Claim tested: a simple context-derived state hint improves replay.
- Why this block exists: it is the current non-leaky baseline for state-aware prediction.
- Dataset / split / task: same replay benchmark, leakage-free evaluation.
- Compared systems:
  - `off`
  - `heuristic`
- Metrics:
  - test accuracy, macro-F1; secondary: state label coverage and confidence distribution.
- Setup details:
  - Current marker-based state inference plus action-label mapping.
- Success criterion:
  - Test gain over `off` that survives the current code changes.
- Failure interpretation:
  - The heuristic state router is too brittle and should be replaced or simplified.
- Table / figure target: main method comparison table.
- Priority: MUST-RUN

### Block 3: Learned State Selector
- Claim tested: learned routing from context to state label is better than the heuristic mapper.
- Why this block exists: it tests the first non-hand-written state selector.
- Dataset / split / task: train-fit router on train examples only; evaluate on held-out replay.
- Compared systems:
  - `heuristic`
  - `learned`
- Metrics:
  - test accuracy, macro-F1; secondary: confidence threshold behavior and candidate entropy.
- Setup details:
  - Lightweight Naive Bayes router over context text.
  - Use the same replay predictor, swapping only the state hint source.
- Success criterion:
  - Learned state-aware beats heuristic state-aware on held-out metrics or shows better coverage without hurting precision.
- Failure interpretation:
  - The router is too weak; keep heuristic state hint as the stronger low-cost option.
- Table / figure target: ablation table and a short failure analysis table.
- Priority: MUST-RUN

### Block 4: Refinement Sanity Check
- Claim tested: refinement is still not producing held-out gains once leakage is removed.
- Why this block exists: it keeps the paper honest about the refinement loop.
- Dataset / split / task: same replay benchmark, train-only refinement.
- Compared systems:
  - `train_refinement`
  - `heuristic`
- Metrics:
  - test accuracy, macro-F1; refinement action count.
- Setup details:
  - Refinement updates only on train examples.
- Success criterion:
  - No hidden leakage or train-only overfit masquerading as a general result.
- Failure interpretation:
  - If this starts to beat state hints, the refinement design is more valuable than expected.
- Table / figure target: appendix or notes section.
- Priority: MUST-RUN

## Run Order and Milestones
| Milestone | Goal | Runs | Decision Gate | Cost | Risk |
|-----------|------|------|---------------|------|------|
| M0 | Sanity | import + compile check | script imports and compiles | low | path or config mismatch |
| M1 | Baseline | `off`, `train_refinement` | train-only refinement stays flat | low | hidden leakage |
| M2 | Main method | `heuristic` | heuristic state hint remains a real gain | low | fragile rule mapping |
| M3 | Decision | `learned` | learned router beats heuristic or is clearly worse | low | router too weak or too sparse |
| M4 | Polish | metric table + failure notes | results are stable enough to cite | low | overclaiming from one run |

## Compute and Data Budget
- Total estimated GPU-hours: 0 to 1 (CPU-friendly replay evaluation).
- Data preparation needs: none beyond the existing replay JSONL files.
- Human evaluation needs: none for this round.
- Biggest bottleneck: whether the learned router has enough signal from the available train contexts.

## Risks and Mitigations
- Risk: learned state router overfits sparse labels.
  - Mitigation: keep the heuristic baseline and compare on held-out test only.
- Risk: state labels are too noisy to route reliably.
  - Mitigation: inspect state label coverage and confidence thresholds before changing the method.
- Risk: the heuristic mapper already encodes most of the useful gain.
  - Mitigation: use this result as the paper's low-cost state-aware baseline and postpone complexity.

## Final Checklist
- [ ] Main paper tables are covered
- [ ] Novelty is isolated
- [ ] Simplicity is defended
- [ ] Frontier contribution is justified or explicitly not claimed
- [ ] Nice-to-have runs are separated from must-run runs
