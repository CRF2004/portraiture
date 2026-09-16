# Portraiture Ablation Findings

基于 257 个 replay 样本的三组对比实验，评估显式建模（persona + refinement）的实际增量价值。

> 注意：这份记录对应的是早期版本的 refinement 流程，后来发现 baseline pass 会在完整 replay 集上更新 profile store，从而把 held-out 例子的信息泄漏进 refined pass。论文里请以 [`docs/ablation_findings_leakfree.md`](/mnt/chengrongfeng_private/cc_dump/portraiture/docs/ablation_findings_leakfree.md) 为准。

## 总体结果

| 条件 | Acc | Macro-F1 | vs 基线 |
|------|-----|----------|--------|
| Baseline (context only) | 53.7% | 0.488 | — |
| + State hint | 56.4% | 0.498 | +2.7% |
| + Persona + Refinement | **64.2%** | **0.555** | **+10.5%** |

**结论**: 显式建模带来了明确的增量增益。Refinement 优于纯 state-aware，说明动态画像修正比单次状态提示更有价值。

## 关键发现

### 1. Refinement 主要改善了 state_under_specified 错误

| Divergence | Baseline | Refined | Δ |
|------------|----------|---------|---|
| state_under_specified | 87 (33.9%) | 67 (26.1%) | **-20** |
| action_selection_error | 29 (11.3%) | 21 (8.2%) | -8 |
| goal_shift_missed (子类) | 69 (26.9%) | 53 (20.6%) | **-16** |
| ranking_error (子类) | 14 (5.5%) | 5 (2.0%) | -9 |

### 2. challenge_or_refine 标签 F1=0（全阶段均零）

该标签在所有三种配置下从未被正确预测。可能原因：
- 样本量不足
- 与 compare_options / follow_up_clarification 的区分度过低
- Jaccard 相似度基线无法捕捉反驳类动作特征

### 3. 按状态类型的精度差异

| State Type | Baseline | Refined | 改善 |
|------------|----------|---------|------|
| active_problem | 57.7% | **68.3%** | +10.6% |
| blocking_issue | 52.1% | **64.8%** | +12.7% |
| current_goal | 46.9% | 53.1% | +6.2% |
| current_stance | 35.3% | 52.9% | +17.6% |

state-aware hint 仅在 blocking_issue 上有显著边际增益（+9.9%），对其他类型几乎无影响。

### 4. Persona facts 抽取结果

仅 3 条自动抽取的 persona facts（占训练样本约 1.2%），置信度 0.66–0.70：
- prefers_explicit_tradeoff_comparison
- prefers_structured_research_plans
- prefers_clear_structured_follow_up

persona 信号直接贡献有限，主要通过 refine loop 间接改善预测。

## 当前瓶颈

1. **goal_shift_missed 仍占 20.6% 误差** — refinement 未能充分解决 topic transition 检测
2. **challenge_or_refine 全零** — 标签定义或特征表示需要重新审视
3. **State hint 增量仅 2.7%** — 当前的 state 注入方式不够有效
4. **Persona 信号稀疏** — 自动抽取策略需要更主动的证据收集

## 下一步建议

1. 手动重标 40 个候选样本（`relabel_candidates.jsonl`），聚焦 goal_shift_missed 和 challenge_or_refine
2. 检查 state hint 注入方式：当前的 heuristic 规则可能不够精确
3. 考虑引入深度模块：用轻量分类器替代 rule-based critic，改善 state_under_specified 归因

*生成日期: 2026-06-16*
