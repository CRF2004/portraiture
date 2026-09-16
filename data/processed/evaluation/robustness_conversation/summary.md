# Replay Robustness Summary

Random group-level splits. Metrics below are test-set mean +/- std across seeds.

| Mode | Accuracy | Macro-F1 | Coarse Accuracy | Coarse Macro-F1 | Seeds |
|---|---:|---:|---:|---:|---:|
| heuristic | 0.3144 +/- 0.1119 | 0.2383 +/- 0.0508 | 0.4253 +/- 0.0769 | 0.3382 +/- 0.0872 | 5 |
| learned | 0.4035 +/- 0.1644 | 0.3035 +/- 0.0895 | 0.4236 +/- 0.1737 | 0.3473 +/- 0.1288 | 5 |
| off | 0.2139 +/- 0.0971 | 0.1628 +/- 0.0588 | 0.3695 +/- 0.0681 | 0.2854 +/- 0.0446 | 5 |
| semantic | 0.4043 +/- 0.1443 | 0.3164 +/- 0.0742 | 0.4245 +/- 0.1536 | 0.3615 +/- 0.1292 | 5 |
| state_prior | 0.2040 +/- 0.0932 | 0.0593 +/- 0.0364 | 0.2181 +/- 0.0861 | 0.0889 +/- 0.0446 | 5 |
