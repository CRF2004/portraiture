# NOW

Goal: 基于聊天记录构建数字分身 - 显式可校正的个人认知代理
Status: active
Current: paper remains 9 pages and now includes a conservative PersonaConvBench stress-test paragraph; Codex MCP registered; Reddit adapter, capped baseline, GPU MiniLM embedding baseline, and 90-example proxy-label audit implemented
Next: add per-label/confusion analysis OR run external reviewer with `paper/EXTERNAL_REVIEW_PROMPT_ROUND3.md` OR request GPU for embedding/full-scale PersonaConvBench baselines
Blockers:
- single-user scope remains main empirical weakness
- proxy labels (rule-derived, not human-annotated)
- paper quality estimate still needs fresh external re-review; key improvement path: multi-user validation

Open questions:
- PersonaConvBench (3878 users, Reddit) 是否可用于多用户验证
- 是否需要再跑一轮外部 reviewer
- 是否已达到投稿水平
- PersonaConvBench raw data is available at `data/raw/personaconvbench_repo/Raw_Data_Postized.json`; first converted dataset has 135,238 replay examples over 2,871 authors.
- First capped PersonaConvBench baseline: majority 0.4064 acc / 0.0642 macro-F1; TF-IDF NN 0.3144 / 0.1243; TF-IDF LR 0.2348 / 0.1448 on 5,000 held-out test examples from 95 users.
- GPU MiniLM embedding NN baseline: 0.2959 acc / 0.1292 macro-F1 on 10,000 held-out test examples from 196 users, runtime ~64 sec on NVIDIA vGPU-32GB.
- Reddit proxy-label audit: 90 stratified examples; 78 acceptable, 12 borderline, 0 likely errors under visible-rule-support criteria. Main caveat remains that this is not human semantic gold.

Updated: 2026-06-28
