# Paper-Ready Experiment Conclusion

Date: 2026-06-28

## Thesis

The strongest current paper thesis is:

> In personal digital-twin construction from GPT chat logs, dynamic state routing is a useful signal for replaying user behavior, but strong semantic context modeling is still a stronger comparator once proxy labels are tightened. The benchmark still shows gains over no-state baselines, but minority action labels remain unresolved.

## Evidence package

### Main fixed split

| Variant | Test Accuracy | Test Macro-F1 |
|---|---:|---:|
| off / no refinement | 0.0000 | 0.0000 |
| heuristic state hint | 0.0750 | 0.0858 |
| learned state router | 0.0750 | 0.0858 |
| semantic context NN | 0.3500 | 0.3839 |

### Random episode robustness

| Variant | Test Accuracy | Test Macro-F1 |
|---|---:|---:|
| off | 0.1390 +/- 0.1019 | 0.1065 +/- 0.0615 |
| heuristic | 0.2214 +/- 0.1559 | 0.2142 +/- 0.0765 |
| learned | 0.3669 +/- 0.1202 | 0.2523 +/- 0.0485 |
| semantic | 0.3754 +/- 0.1029 | 0.3102 +/- 0.0597 |
| state_prior | 0.2885 +/- 0.0964 | 0.0790 +/- 0.0356 |

### Random conversation robustness

| Variant | Test Accuracy | Test Macro-F1 |
|---|---:|---:|
| off | 0.2139 +/- 0.0971 | 0.1628 +/- 0.0588 |
| heuristic | 0.3144 +/- 0.1119 | 0.2383 +/- 0.0508 |
| learned | 0.4035 +/- 0.1644 | 0.3035 +/- 0.0895 |
| semantic | 0.4043 +/- 0.1443 | 0.3164 +/- 0.0742 |
| state_prior | 0.2040 +/- 0.0932 | 0.0593 +/- 0.0364 |

## What the state-prior baseline means

`state_prior` reaches moderate accuracy but very low macro-F1. This means simple state-action majority mapping can recover dominant behavior modes, but it collapses minority labels. The semantic baseline is the better balanced predictor and is therefore the stronger paper comparator if macro-F1 is treated as the main metric.

## Mechanism diagnosis

The old learned-router gain was concentrated in:

- `topic_shift`: 0.107 off -> 0.214 heuristic -> 0.643 learned
- `active_problem`: 0.136 off -> 0.136 heuristic -> 0.636 learned
- `current_stance`: 0.000 off -> 0.000 heuristic -> 0.500 learned

Still weak:

- `compare_options`: 0.000 learned accuracy on fixed test
- `follow_up_clarification`: 0.000 learned accuracy on fixed test
- `provide_more_context`: 0.000 learned accuracy on fixed test

## Claims to write

Supported main claim:

- State-aware replay is a meaningful signal for personal GPT logs, but it should be compared against stronger semantic baselines.

Supported secondary claim:

- Static persona extraction and current refinement are not yet reliable sources of held-out gain; dynamic state is useful but not the only actionable bottleneck.

Required caveat:

- Current evaluation is single-user and proxy-labeled by rules derived from user text. The results show a measurable replay benchmark and method signal, not a completed human digital twin.

## Decision

The project is ready to start paper writing if the paper is framed as a method-and-benchmark paper around state-aware replay and semantic context comparison, not as a full digital twin system.

Recommended paper title direction:

- "State-Aware Replay for Personal Digital Twins from GPT Chat Logs"
- "Beyond Persona: Dynamic State Routing for Personal Chat-Log Replay"
- "Measuring Personal Digital Twin Fidelity with State-Aware Behavior Replay"
