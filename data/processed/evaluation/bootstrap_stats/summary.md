# Bootstrap Statistics & Significance Tests

Test set: n=40 | Bootstrap: 10000 resamples, 95% CI

## Point Estimates with 95% Bootstrap CIs

| Method | Accuracy | Acc 95% CI | Macro-F1 | F1 95% CI |
|---|---:|---|---:|---:|
| Off (no state) | 0.0000 | [0.0000, 0.0000] | 0.0000 | [0.0000, 0.0000] |
| Heuristic state | 0.0000 | [0.0000, 0.0000] | 0.0000 | [0.0000, 0.0000] |
| Learned state router | 0.0000 | [0.0000, 0.0000] | 0.0000 | [0.0000, 0.0000] |
| Logistic regression | 0.2993 | [0.1750, 0.4500] | 0.1783 | [0.0731, 0.2812] |
| Lexical context NN | 0.0000 | [0.0000, 0.0000] | 0.0000 | [0.0000, 0.0000] |
| Lexical + state router | 0.0000 | [0.0000, 0.0000] | 0.0000 | [0.0000, 0.0000] |

## Key Statistical Findings

- LR vs Lexical NN: McNemar χ²=10.083, p=0.0015 (significant at 0.05)
- Lexical NN vs Lexical+State: predictions 40/40 identical, McNemar p=1.0000 — no detectable difference

## All Pairwise McNemar Tests

| Method A | Method B | χ² | p | Sig? | b | c |
|---|---|---:|---:|---:|---:|---:|
| Off (no state) | Heuristic state | 0.000 | 1.0000 |  | 0 | 0 |
| Off (no state) | Learned state router | 0.000 | 1.0000 |  | 0 | 0 |
| Off (no state) | Logistic regression | 10.083 | 0.0015 | * | 0 | 12 |
| Off (no state) | Lexical context NN | 0.000 | 1.0000 |  | 0 | 0 |
| Off (no state) | Lexical + state router | 0.000 | 1.0000 |  | 0 | 0 |
| Heuristic state | Learned state router | 0.000 | 1.0000 |  | 0 | 0 |
| Heuristic state | Logistic regression | 10.083 | 0.0015 | * | 0 | 12 |
| Heuristic state | Lexical context NN | 0.000 | 1.0000 |  | 0 | 0 |
| Heuristic state | Lexical + state router | 0.000 | 1.0000 |  | 0 | 0 |
| Learned state router | Logistic regression | 10.083 | 0.0015 | * | 0 | 12 |
| Learned state router | Lexical context NN | 0.000 | 1.0000 |  | 0 | 0 |
| Learned state router | Lexical + state router | 0.000 | 1.0000 |  | 0 | 0 |
| Logistic regression | Lexical context NN | 10.083 | 0.0015 | * | 12 | 0 |
| Logistic regression | Lexical + state router | 10.083 | 0.0015 | * | 12 | 0 |
| Lexical context NN | Lexical + state router | 0.000 | 1.0000 |  | 0 | 0 |
