# Comprehensive Evaluation Results

Test set: n=40 | Bootstrap: 10000 resamples, 95% CI

## Main Results Table (paper-ready)

| Variant | Acc | Acc 95% CI | Macro-F1 | F1 95% CI |
|---|---:|---|---:|---:|
| Off (no state) | 0.0000 | [0.0000, 0.0000] | 0.0000 | [0.0000, 0.0000] |
| Heuristic state | 0.0750 | [0.0000, 0.1500] | 0.0858 | [0.0000, 0.1724] |
| Learned state router | 0.2250 | [0.1000, 0.3500] | 0.3039 | [0.0937, 0.4349] |
| State prior | 0.2750 | [0.1500, 0.4250] | 0.0816 | [0.0476, 0.1414] |
| Logistic regression | 0.3000 | [0.1750, 0.4500] | 0.1729 | [0.0731, 0.2812] |
| Lexical context NN | 0.3500 | [0.2000, 0.5000] | 0.3839 | [0.1453, 0.5319] |

## State Routing Ablation

| Variant | Acc | Acc 95% CI | Macro-F1 | F1 95% CI |
|---|---:|---|---:|---:|
| Lexical context NN | 0.3500 | [0.2000, 0.5000] | 0.3839 | [0.1453, 0.5319] |
| Lexical + state router | 0.3500 | [0.2000, 0.5000] | 0.3839 | [0.1453, 0.5319] |

Predictions identical: 40/40 (100%).
State routing adds zero additional signal on top of the lexical baseline.

## Key Statistical Findings

- Off (no state) vs Lexical context NN: McNemar χ²=12.07, p=0.0005 (***)
- Heuristic state vs Lexical context NN: McNemar χ²=9.09, p=0.0026 (***)
- Learned state router vs Lexical context NN: McNemar χ²=3.20, p=0.0736 (n.s.)
- Logistic regression vs Lexical context NN: McNemar χ²=0.05, p=0.8312 (n.s.)
- Lexical context NN vs Lexical + state router: McNemar χ²=0.00, p=1.0000 (n.s.)
- Off (no state) vs Logistic regression: McNemar χ²=10.08, p=0.0015 (***)
- Learned state router vs Logistic regression: McNemar χ²=0.21, p=0.6464 (n.s.)
- State prior vs Lexical context NN: McNemar χ²=0.17, p=0.6767 (n.s.)
