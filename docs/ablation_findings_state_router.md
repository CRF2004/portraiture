# Portraiture State Router Findings

This note records the follow-up experiment where the state hint source was swapped from a rule-based heuristic to a learned router trained only on train split replay examples.

## Experiment variants

- `off`: no state hint
- `heuristic`: marker-based state inference + action mapping
- `learned`: Naive Bayes state router + action mapping

## Key results

### Test set

| Variant | Accuracy | Macro-F1 |
|---|---:|---:|
| off | 0.0750 | 0.0260 |
| heuristic | 0.2000 | 0.1036 |
| learned | 0.5500 | 0.2983 |

### Interpretation

1. The learned state router is a substantial improvement over the heuristic mapper on held-out replay.
2. The gain is large enough to matter for the paper story: the state selector is not just a cosmetic replacement.
3. The baseline/refinement passes remain unchanged, so this gain is isolated to the state hint source.
4. The current heuristic mapping is still useful as a simple baseline, but it is clearly dominated by the learned router on this split.
5. The gain is fairly stable to confidence threshold changes: `t10` matches the default learned result, and `t70` only drops slightly.

## Current research conclusion

For the replay benchmark, state hints are a real source of held-out gain, and a learned selector is the strongest version we have tested so far. The next question is whether this improvement holds under additional data splits or a larger candidate set.

## Next experimental direction

1. Check whether the learned gain comes from better coverage of `current_goal` / `blocking_issue` states rather than a few easy examples.
2. If needed, run one more split-based robustness check before freezing the paper tables.
3. Promote the learned state router to the paper's main state-aware baseline and write the results section.
