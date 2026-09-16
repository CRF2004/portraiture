# Portraiture Leak-Free Ablation Findings

This note records the controlled runs after fixing refinement leakage so that refinement updates only use `train` split examples.

## Why this note exists

The earlier ablation table in `docs/ablation_findings.md` used a refinement pass that updated the profile store while iterating over the full replay set, including held-out examples. That setup inflated the apparent effect of refinement on `val` / `test`.

This note records the corrected, leakage-free comparisons.

## Experiment variants

- `no_refinement`: baseline store seeded only from training examples; no baseline refinement updates
- `train_refinement`: baseline refinement updates restricted to `train` split only
- `main`: previous leaky setting for reference

## Key results

### Test set

| Variant | Accuracy | Macro-F1 |
|---|---:|---:|
| no_refinement | 0.0750 | 0.0260 |
| train_refinement | 0.0750 | 0.0260 |
| state-aware only | 0.1750 | 0.0961 |

### Interpretation

1. Training-only refinement does not improve held-out replay performance.
2. Persona facts extracted from training data alone are not enough to move test performance.
3. The heuristic state hint is a real held-out gain, but it is now surpassed by the learned state router in the follow-up experiment.
4. The earlier large `refined` gain was caused by leakage from held-out examples into the refinement store.

## Additional controlled checks

| Variant | Test Accuracy | Test Macro-F1 | Observation |
|---|---:|---:|---|
| state_only | 0.5000 | 0.2150 | Restricting refinement to `state_under_specified` hurt performance vs the leaky setting |
| goal_shift_only | 0.4500 | 0.0900 | Narrowing further to `goal_shift_missed` hurt more |
| hybrid profile + state | 0.1750 | 0.0961 | Profile hints did not add to state hints at inference time |

## Current research conclusion

The present refinement mechanism is useful for debugging and offline error analysis, but it is not yet a leakage-free generalization gain on held-out replay examples. For the paper, the safe claim is:

- explicit state hints help modestly
- current persona facts alone are weak
- current refinement updates need a better non-leaky formulation before they can be claimed as a generalization improvement

## Next experimental direction

The next most promising question is whether a learned state selector can reliably replace the heuristic state hint without sacrificing calibration or stability.
