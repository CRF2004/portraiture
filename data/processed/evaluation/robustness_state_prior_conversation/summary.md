# Replay Robustness Summary

Random group-level splits. Metrics below are test-set mean +/- std across seeds.

| Mode | Accuracy | Macro-F1 | Coarse Accuracy | Coarse Macro-F1 | Seeds |
|---|---:|---:|---:|---:|---:|
| heuristic | 0.3559 +/- 0.1121 | 0.2298 +/- 0.0741 | 0.4139 +/- 0.1059 | 0.2991 +/- 0.1277 | 5 |
| learned | 0.4854 +/- 0.1093 | 0.2877 +/- 0.0445 | 0.4915 +/- 0.1014 | 0.3035 +/- 0.0465 | 5 |
| off | 0.2539 +/- 0.1319 | 0.1785 +/- 0.0606 | 0.3307 +/- 0.0738 | 0.2439 +/- 0.0492 | 5 |
| state_prior | 0.5296 +/- 0.0738 | 0.1017 +/- 0.0258 | 0.5296 +/- 0.0738 | 0.1520 +/- 0.0329 | 5 |
