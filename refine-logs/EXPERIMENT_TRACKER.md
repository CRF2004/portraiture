# Experiment Tracker

| Run ID | Milestone | Purpose | System / Variant | Split | Metrics | Priority | Status | Notes |
|--------|-----------|---------|------------------|-------|---------|----------|--------|-------|
| R001 | M0 | sanity | import + compile | n/a | pass/fail | MUST | DONE | `py_compile` passed for replay, hint router, and signals |
| R002 | M1 | baseline | off / train_refinement | test | acc, macro-F1 | MUST | DONE | train-only refinement stayed flat |
| R003 | M2 | main method | heuristic state hint | test | acc, macro-F1 | MUST | DONE | test acc 0.2000, macro-F1 0.1036 |
| R004 | M3 | decision | learned state hint | test | acc, macro-F1 | MUST | DONE | test acc 0.5500, macro-F1 0.2983 |
| R005 | M4 | polish | threshold sweep t10 / t70 | test | acc, macro-F1 | NICE | DONE | t10 matched learned; t70 only slightly lower |
| R006 | M4 | robustness | random episode splits: off / heuristic / learned | test | acc, macro-F1 | MUST | DONE | learned acc 0.4370 +/- 0.1116; macro-F1 0.2683 +/- 0.0511 across 5 seeds |
| R007 | M4 | robustness | random conversation splits: off / heuristic / learned | test | acc, macro-F1 | MUST | DONE | learned acc 0.4854 +/- 0.1093; macro-F1 0.2877 +/- 0.0445 across 5 seeds |
| R008 | M4 | stronger baseline | state_prior vs learned | random episode/conversation | acc, macro-F1 | MUST | DONE | state_prior has higher acc but much lower macro-F1; learned is more balanced |
| R009 | M5 | diagnosis | per-label and state-type contribution | fixed test | per-label acc | MUST | DONE | learned gain concentrated in topic_shift, active_problem, current_stance |
