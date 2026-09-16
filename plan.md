# Portraiture 研究计划（短中长期版）

日期：2026-05-16

## 0. 总判断

当前最合适的路线不是一开始做端到端数字分身，而是：

> **显式结构建模作为骨架，深度学习作为可替换模块，最后再视效果决定是否蒸馏成更强的隐式模型。**

原因很直接：

- 现在最需要的是可解释、可调试、可回放
- 数据量和标签质量还不足以支撑直接端到端
- 当前瓶颈主要在状态建模和错误归因，而不是单纯生成能力

所以这份计划的主线不是“先把模型做大”，而是“先把问题拆清楚，再决定哪些部分值得学习化”。

### 0.1 当前状态

目前已经完成的最小闭环是：

- ingest ChatGPT export JSON
- segmentation（session / episode / turn）
- replay example 构造
- evaluation / report 生成
- 用 `dialogue_data_example` 跑通 smoke test

这说明工程骨架已经可用，接下来不该再优先做流水线拼接，而是应该把**schema、标签体系、评测口径**先稳定下来。

### 0.2 下一步

**下一步优先级最高的事情：固定 schema + 重整标签 + 做小规模重标。**

具体顺序：

1. 冻结当前核心 schema，不再随意加字段或改名
2. 把动作标签整理成高层 / 低层两层
3. 抽 30–50 个样本做重标，找出最主要混淆
4. 跑四组 ablation，验证 persona / state / refinement 的真实增益
5. 再决定是否继续引入更强的 learned 模块

---

## 1. 研究主问题

这一轮实验要回答的核心问题是：

1. 当前 replay 任务的收益上限，主要受限于什么？
   - 状态表示
   - 动作标签设计
   - 数据覆盖
   - persona 信号本身

2. 显式建模到底有没有带来真实增益？
   - 是否能稳定改善 next-action prediction
   - 是否能减少特定类型的 divergence
   - 是否比纯上下文/相似度 baseline 更可解释

3. 深度学习模块应该插在哪些位置？
   - 抽取
   - 检索
   - 重排
   - critic
   - 预测器

4. 在什么条件下，应该从显式模型走向混合模型，甚至端到端模型？

---

## 2. 短期目标：把显式建模做稳

时间范围：0–4 周

### 2.1 目标

先把当前系统的基础闭环做扎实，确认显式建模的真实边际收益。

### 2.2 要做的事

#### A. 固定最小 schema

先把下面这些对象稳定下来，不再频繁改名或扩字段：

- `Conversation`
- `Episode`
- `Turn`
- `PersonaFact`
- `DynamicState`
- `MemoryNode`
- `PredictionRecord`

要求：

- 每个字段都能追溯证据
- 每个字段都能说明它对预测有什么帮助
- 不引入没有评测意义的字段

#### B. 把任务拆成两层

当前不要把所有东西混成一个“下一步预测”任务，而是拆成：

1. **状态预测**
   - 当前目标
   - 是否有阻塞
   - 当前阶段
   - 当前关注点
   - 是否 topic shift

2. **动作预测**
   - clarify
   - expand
   - compare
   - challenge
   - plan
   - shift

这样可以区分：

- 是状态错了
- 还是动作选择错了
- 还是标签体系本身有噪声

#### C. 标签体系定稿

第一版标签体系按“两层”固定，不再继续扩散新 label，除非先进入下一轮专题扩展。

**高层 coarse 标签**（用于评测和汇总）：

- `clarify`
- `expand`
- `plan`
- `compare`
- `challenge`
- `shift`
- `other`

**细粒度标签**（用于 replay / 误差分析）：

- `ask_definition`
- `ask_why`
- `ask_for_example`
- `request_how_to`
- `feasibility_check`
- `compare_options`
- `challenge_or_refine`
- `follow_up_clarification`
- `topic_shift`
- `provide_more_context`

**定稿规则：**

- coarse 标签只负责稳定评测口径
- fine 标签只负责训练样本和 divergence 分析
- 任何新标签先放进 `other` 或现有子类，不直接扩张主标签空间
- 只有当某个细分标签样本数和错误贡献都足够大，才考虑升级为正式标签

#### D. 重标样本集定稿

本轮重标样本集固定为 **40 条**，来源是当前已跑通的 replay 样本池，按下面四个桶各取 10 条：

1. **清晰样本**
   - 标签边界明确
   - 作为锚点样本，用来检查标注一致性

2. **边界样本**
   - 介于 `ask_definition` / `request_how_to` / `follow_up_clarification` 之间
   - 或介于 `challenge_or_refine` / `compare_options` 之间

3. **topic shift 样本**
   - `ground_truth_label = topic_shift`
   - 或被 critic 判成 `state_under_specified.goal_shift_missed`

4. **state / persona 重依赖样本**
   - 预测是否正确明显依赖动态状态或 persona facts
   - 优先覆盖 `blocking_issue_missed`、`wrong_turn_boundary`、`reasoning_mismatch`

重标时只看三件事：

- 细粒度标签是否正确
- coarse 标签是否落到正确桶里
- 错误是否真的是标签问题，而不是 state / memory 问题

**重标输出：**

- 一份 `relabel_set_v1.jsonl`
- 一份标签对照表
- 一份混淆清单（只记录前 10 个最主要混淆）

#### E. 做一轮小规模重标

抽 40 个样本重标，检查：

- 哪些标签混淆最严重
- 哪些错误其实是 state 问题，不是动作问题
- 哪些样本只靠上下文就能判断，哪些必须依赖 persona / state

#### E. 做完整 ablation

至少跑四组：

1. context only
2. context + similarity
3. context + persona facts
4. context + persona facts + dynamic state / refinement

重点看：

- 总准确率
- macro-F1
- per-label F1
- confusion matrix
- 三类 divergence 的变化

### 2.3 短期交付物

- 一版稳定的 schema
- 一版两层标签体系
- 一份 40 条重标样本集（`relabel_set_v1.jsonl`）
- 一组完整 ablation 结果
- 一份 case study：成功、失败、边界样本各几例

### 2.4 短期判断标准

如果短期结果显示：

- 状态层明显影响预测
- persona 的增益有限但可解释
- refinement 能减少特定 divergence

那说明显式建模值得继续。

如果短期结果显示：

- 标签噪声远大于方法差异
- 状态 schema 不稳定
- persona 基本没有边际贡献

那就说明需要先修问题定义，而不是继续堆模型。

---

## 3. 中期目标：把深度学习放进合适的模块

时间范围：1–3 个月

### 3.1 目标

不是立刻端到端，而是把深度学习引入到最有价值的子模块里，形成 **hybrid system**。

### 3.2 推荐插入点

#### A. 状态抽取器

用深度模型从 episode / turn 中提取动态状态：

- 当前目标
- 阻塞点
- 当前阶段
- 关注点
- 情绪/压力线索

这里的关键不是“模型越大越好”，而是：

- 是否比规则更稳定
- 是否对不同数据桶泛化更好
- 是否能降低 state_under_specified

#### B. 证据检索 / 重排器

让深度模型负责：

- 找相关历史 evidence spans
- 给 persona facts / memory nodes 做 rerank
- 区分强证据和弱证据

这一步特别适合深度学习，因为它擅长语义匹配，但不必把最终决策黑箱化。

#### C. Critic / divergence 分类器

把当前规则 critic 升级为一个更稳的分类器，判断：

- state_under_specified
- reasoning_mismatch
- action_selection_error

目标不是取代规则，而是提高归因质量。

#### D. 候选动作 reranker

保留显式候选动作生成，但让学习模型重排：

- 先给 top-k 候选
- 再由 judge/reranker 选最合理的

这通常比直接端到端生成更容易验证。

### 3.3 中期实验设计

要比较三种系统：

1. **纯显式**
2. **显式 + 深度模块**
3. **更强的 learned baseline**

对比时保持相同的：

- 数据 split
- 标签定义
- 评测口径
- error taxonomy

### 3.4 中期要补的数据

把数据按类型分桶，不要混成一锅：

- 任务讨论型
- 决策反思型
- 长期往返型
- 自由交流型

每个桶单独看：

- 能抽出什么 persona
- 哪些 state 更稳定
- 哪些标签最容易混淆

### 3.5 中期交付物

- 一个 hybrid prototype
- 一组模块级 ablation
- 一份按数据桶分析的结果
- 一份“显式 vs hybrid”对照报告

### 3.6 中期判断标准

如果 hybrid 明显优于纯显式，而且还能保持可解释性，那就说明深度学习模块找对位置了。

如果 hybrid 只是微弱改善，甚至引入更多不可解释误差，那说明现阶段还是应该坚持显式主导。

---

## 4. 长期目标：再决定要不要端到端

时间范围：3–6 个月以上

### 4.1 目标

只有在 schema 稳定、数据更丰富、评测更清楚之后，才考虑更强的隐式模型或端到端蒸馏。

### 4.2 长期可能的方向

#### A. 结构蒸馏

把显式 persona / state / memory graph 蒸馏进一个学习模型：

- 保留结构信息
- 压缩中间表示
- 降低手工规则依赖

#### B. Learned cognitive model

让模型自己学习：

- 稳定偏好
- 半稳定习惯
- 动态状态
- 记忆调用策略

但前提是这些概念已经在显式系统里定义清楚。

#### C. 更强的在线交互评测

不只看离线 replay，而是看：

- twin 在新对话里的稳定性
- 记忆调用是否持续正确
- 状态更新是否跟得上
- 行为链是否连续

### 4.3 长期交付物

- 一个更强的 learned twin 原型
- 一个可在线交互的评测脚本
- 一个从显式结构到隐式模型的蒸馏实验

### 4.4 长期判断标准

只有当下面条件同时基本满足时，才值得往端到端靠：

- 大量高质量数据
- 标签和 schema 已经稳定
- 显式模型性能进入平台期
- 解释性需求可以部分让位给预测性能

如果这些条件不成立，端到端只会让系统更难调试。

---

## 5. 推荐决策顺序

### 先做什么

1. 固定 schema
2. 重整标签
3. 做状态/动作拆分
4. 跑完整 ablation
5. 看 persona 和 state 的真实边际贡献

### 再做什么

6. 在状态抽取、检索重排、critic 上引入深度学习
7. 对比纯显式和 hybrid
8. 按数据桶检查泛化

### 最后再决定

9. 是否蒸馏成更强的 learned twin
10. 是否走向更接近端到端的结构

---

## 6. 当前最重要的结论

这份计划的核心判断是：

- **短期**：显式建模优先，因为它最适合现在的问题形态
- **中期**：深度学习应该作为模块增强，而不是一口气端到端
- **长期**：如果结构稳定、数据足够，再考虑蒸馏或更强隐式模型

换句话说，路线不是“显式 vs 深度学习”的二选一，而是：

> **先用显式模型把问题讲清楚，再用深度学习去吃掉最有价值、最稳定的那部分。**
