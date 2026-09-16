# Replay Robustness Summary

Random group-level splits. Metrics below are test-set mean +/- std across seeds.

| Mode | Accuracy | Macro-F1 | Coarse Accuracy | Coarse Macro-F1 | Seeds |
|---|---:|---:|---:|---:|---:|
| heuristic | 0.2214 +/- 0.1559 | 0.2142 +/- 0.0765 | 0.3143 +/- 0.1412 | 0.2522 +/- 0.1058 | 5 |
| learned | 0.3669 +/- 0.1202 | 0.2523 +/- 0.0485 | 0.3957 +/- 0.1168 | 0.2706 +/- 0.0572 | 5 |
| off | 0.1390 +/- 0.1019 | 0.1065 +/- 0.0615 | 0.3059 +/- 0.0679 | 0.2154 +/- 0.0754 | 5 |
| semantic | 0.3754 +/- 0.1029 | 0.3102 +/- 0.0597 | 0.4034 +/- 0.1066 | 0.3456 +/- 0.0982 | 5 |
| state_prior | 0.2885 +/- 0.0964 | 0.0790 +/- 0.0356 | 0.2930 +/- 0.0890 | 0.1163 +/- 0.0441 | 5 |
