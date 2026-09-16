# Evaluation

本文档定义 replay 评测口径，目标是把当前的 replay 样本集变成可重复运行、可对比的研究结果。

## 1. 评测对象

当前第一版只评测 `next_user_action`，但样本层会同时记录：

- 细粒度动作标签
- 高层 coarse 动作标签
- 上下文推断的动态状态提示

输入包括：

- `ReplayExample`
- 对应 `Turn`
- 对应 `Message`

输出包括：

- `PredictionRecord`
- `DivergenceRecord`
- `RefinementAction`
- `ProfileSnapshot`
- `PersonaFact`
- `DynamicState`
- `MemoryNode`
- `MetricRecord`

## 2. 基线定义

第一版基线使用两层策略：

- 训练集上的多数类标签作为默认预测
- 与当前上下文最相似的训练样本做 nearest-neighbor 标签投票

这不是最终方法，只是为了建立一个可量化的起点。

当前评测会并行跑三条线：

- `baseline`：纯上下文 + nearest-neighbor
- `state_aware`：上下文 + state hint
- `refined`：上下文 + persona hint + refinement 结果

另外会导出一份重标候选队列，优先包含：

- `state_under_specified.goal_shift_missed`
- `state_under_specified.blocking_issue_missed`

## 3. 指标

第一版最少记录以下指标：

- `accuracy`
- `macro_f1`
- coarse-label accuracy / macro_f1
- 按 observed state type 分组的 accuracy

按 `train`、`val`、`test` 三个 split 分别输出。

## 4. divergence 规则

当前使用规则版 critic：

- `topic_shift` 相关错误优先归到 `state_under_specified`
- `challenge_or_refine`、`compare_options` 相关错误优先归到 `reasoning_mismatch`
- 其余动作预测错归到 `action_selection_error`

这套规则的作用是先把错误分桶，方便后续 refinement。

## 5. 运行产物

默认输出到：

- `data/processed/evaluation/predictions_baseline.jsonl`
- `data/processed/evaluation/predictions_refined.jsonl`
- `data/processed/evaluation/divergences_baseline.jsonl`
- `data/processed/evaluation/divergences_refined.jsonl`
- `data/processed/evaluation/refinements.jsonl`
- `data/processed/evaluation/profile_snapshots_baseline.jsonl`
- `data/processed/evaluation/profile_snapshots_refined.jsonl`
- `data/processed/evaluation/persona_facts.jsonl`
- `data/processed/evaluation/dynamic_states.jsonl`
- `data/processed/evaluation/memory_nodes.jsonl`
- `data/processed/evaluation/metrics.jsonl`

## 6. 研究含义

只要这条链条能稳定运行，就说明项目已经跨过“只有数据和 schema”的阶段，进入“benchmark 可验证”的阶段。
