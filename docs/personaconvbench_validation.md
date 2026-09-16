# PersonaConvBench Validation

## Status

PersonaConvBench / PERSONA-Bench raw Reddit data has been downloaded and converted into a first-pass multi-user proxy replay dataset.

This is not yet a paper-ready full validation because the label rules are still proxy rules, but it is now an executable multi-user experiment rather than a TODO. A first 90-example stratified proxy-label audit is available in `docs/personaconvbench_label_audit.md`.

## Raw Data

- Source: Hugging Face `PERSONABench/PERSONA-Bench`
- Local file: `data/raw/personaconvbench_repo/Raw_Data_Postized.json`
- License: MIT
- SHA256: `59cea85862f6779f90dc905d7f4691b83b5521bc9234e9859b054d99645a609e`
- Posts: 19,215
- Comments: 390,621
- Subreddits: 10

## Replay Construction

Adapter:

```bash
PYTHONPATH=src python -m portraiture.ingest.personaconvbench \
  --min-author-examples 12 \
  --output data/processed/personaconvbench/replay_examples.jsonl \
  --summary data/processed/personaconvbench/summary.json
```

The adapter flattens nested Reddit comment trees into replay examples:

- Context: root post plus parent-comment path, capped to recent context.
- Target: next Reddit comment by the target author.
- User: Reddit comment author.
- Split: deterministic user-disjoint split by author hash.
- Label: deterministic Reddit proxy action label.

Current full converted dataset:

| Quantity | Value |
|---|---:|
| Replay examples | 135,238 |
| Authors | 2,871 |
| Train examples | 93,268 |
| Validation examples | 14,064 |
| Test examples | 27,906 |

Label distribution:

| Label | Count |
|---|---:|
| ask_question | 50,774 |
| personal_experience | 23,956 |
| topic_branch | 17,620 |
| disagree_or_correct | 16,336 |
| short_reply | 9,914 |
| agree_or_affirm | 9,198 |
| cite_evidence | 4,095 |
| humor_or_reaction | 3,002 |
| elaborate_argument | 343 |

## First Baseline Run

Evaluator:

```bash
PYTHONPATH=src python -m portraiture.evaluation.personaconvbench_baseline \
  --input data/processed/personaconvbench/replay_examples.jsonl \
  --output-dir data/processed/personaconvbench/evaluation_capped_20k_5k \
  --max-train 20000 \
  --max-val 3000 \
  --max-test 5000 \
  --max-features 20000 \
  --nn-batch-size 250
```

This capped run uses 20,000 train examples, 3,000 validation examples, and 5,000 test examples from 95 held-out test users.

| Variant | Accuracy | Macro-F1 |
|---|---:|---:|
| majority | 0.4064 | 0.0642 |
| subreddit prior | 0.4064 | 0.0642 |
| TF-IDF NN | 0.3144 | 0.1243 |
| TF-IDF LR | 0.2348 | 0.1448 |

## GPU Embedding Baseline

We also ran a larger GPU embedding nearest-neighbor baseline on the remote vGPU server.
The model was `sentence-transformers/all-MiniLM-L6-v2`, loaded offline from a local snapshot because the server could not directly reach Hugging Face.

Command shape:

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 CUDA_VISIBLE_DEVICES=0 \
  /usr/bin/python3 -m portraiture.evaluation.personaconvbench_embedding \
  --model /root/models/all-MiniLM-L6-v2-min \
  --max-train 50000 \
  --max-val 5000 \
  --max-test 10000 \
  --encode-batch-size 256 \
  --search-batch-size 512 \
  --output-dir data/processed/personaconvbench/embedding_minilm_50k_10k
```

Downloaded local results:

- `data/processed/personaconvbench/embedding_minilm_50k_10k/metrics.json`
- `data/processed/personaconvbench/embedding_minilm_50k_10k/predictions.jsonl`

Run scale:

| Quantity | Value |
|---|---:|
| Train examples | 50,000 |
| Validation examples | 5,000 |
| Test examples | 10,000 |
| Train users | 1,090 |
| Test users | 196 |
| Runtime | 64 sec |

Result:

| Variant | Accuracy | Macro-F1 |
|---|---:|---:|
| MiniLM embedding NN | 0.2959 | 0.1292 |

## Interpretation

The first multi-user result mirrors the single-user paper's metric warning:

- Majority-style prediction obtains high accuracy by predicting `ask_question` for every example.
- Macro-F1 exposes that majority and subreddit-prior baselines collapse minority labels.
- TF-IDF LR has lower accuracy but the best macro-F1, suggesting better balanced behavior across proxy labels.
- TF-IDF NN predicts a broader label distribution than majority but remains dominated by `ask_question`.
- MiniLM embedding NN improves label diversity over majority prediction, but it does not outperform the TF-IDF LR macro-F1 result despite using a larger train/test cap.

This supports using macro-F1 as the primary metric in a multi-user Reddit replay setting.

## Proxy Label Audit

A deterministic stratified audit sampled 10 examples per proxy label, for 90 examples total.

| Status | Count |
|---|---:|
| Acceptable | 78 |
| Borderline | 12 |
| Likely error | 0 |

The audit checks visible support for each proxy label, not semantic gold correctness.
The main noise mode is `topic_branch`, which is a broad fallback label and should not be treated as precise intent.

## Caveats

- Labels are still deterministic proxy labels, not human annotations; the audit only checks rule support and obvious noise modes.
- Reddit replies differ from GPT user requests; the label space is not directly comparable to the main paper's ChatGPT-log label space.
- The first baseline run is capped for compute safety. The full converted dataset has 27,906 test examples.
- The current user split is deterministic by author hash and should be audited for deleted/bot accounts and subreddit imbalance.

## Next Steps

1. Add per-label F1 and confusion matrices to the evaluator.
2. Add a state-like Reddit feature set: thread depth, parent stance, subreddit, score bucket, and author-history summary.
3. Run approximate NN over the full 93k/28k split if a full-result table is needed.
4. Add a Reddit state/thread-feature baseline before claiming method-level generalization.
