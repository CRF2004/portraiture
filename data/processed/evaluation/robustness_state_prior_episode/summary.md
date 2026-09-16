# Replay Robustness Summary

Random group-level splits. Metrics below are test-set mean +/- std across seeds.

| Mode | Accuracy | Macro-F1 | Coarse Accuracy | Coarse Macro-F1 | Seeds |
|---|---:|---:|---:|---:|---:|
| heuristic | 0.2348 +/- 0.1315 | 0.2195 +/- 0.0764 | 0.2876 +/- 0.1338 | 0.2307 +/- 0.0901 | 5 |
| learned | 0.4370 +/- 0.1116 | 0.2683 +/- 0.0511 | 0.4598 +/- 0.1116 | 0.3061 +/- 0.0529 | 5 |
| off | 0.1641 +/- 0.0872 | 0.1370 +/- 0.0408 | 0.2670 +/- 0.0680 | 0.2293 +/- 0.0458 | 5 |
| state_prior | 0.4768 +/- 0.1161 | 0.0917 +/- 0.0265 | 0.4768 +/- 0.1161 | 0.1366 +/- 0.0314 | 5 |
