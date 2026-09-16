# Divergence Taxonomy

本文档定义 `Critic / Refiner` 使用的偏差分类体系。目标不是把所有错误都塞进一个模糊的“预测不准”，而是把错误拆到可修正的表征层。

核心原则：

- 每个 divergence 都应映射到一个主要故障层
- 每个 divergence 都应对应一类可执行 refinement 动作
- 先支持低歧义的主类型，再逐步细化子类型

---

## 1. 设计目标

项目中的 divergence 分析服务于三件事：

1. 判断错误来自哪一层表示
2. 决定下一步应该更新 persona、state、memory 还是 simulator
3. 衡量 refinement 是否真的有效

因此 taxonomy 的最小要求不是学术上最优雅，而是：

- 对 replay 任务可用
- 对人工 case review 可解释
- 能直接驱动更新动作

---

## 2. 一级分类

当前建议使用 6 个一级类型。

### 2.1 `memory_failure`

系统没有正确调用或构造历史记忆。

典型表现：

- 忘记用户曾经明确说过的偏好
- 忘记重要历史事件
- 时间顺序混乱
- 记住了错误版本的事实

优先修正对象：

- `MemoryNode`
- `EventNode`
- 记忆检索策略

### 2.2 `persona_misalignment`

系统对长期稳定特征判断错误。

典型表现：

- 把短期偏好当成长期偏好
- 错估决策风格
- 错估解释偏好
- 长期兴趣或约束判断错误

优先修正对象：

- `PersonaFact`
- persona field set
- evidence aggregation 规则

### 2.3 `state_under_specified`

系统没有正确识别当前动态状态，导致预测偏泛或停留在旧状态。

典型表现：

- 抓到用户的长期倾向，但没抓到当下目标切换
- 没识别时间压力、情绪、阻塞点
- 没发现当前问题已经进入更具体阶段

优先修正对象：

- `DynamicState`
- state 更新规则
- recent-context 权重

当前实现会进一步把这一类错误拆成：

- `goal_shift_missed`
- `time_pressure_missed`
- `stance_change_missed`
- `blocking_issue_missed`

### 2.4 `reasoning_mismatch`

系统记住了用户和事实，但推理路径不一致。

典型表现：

- 关注因素不同
- 权衡顺序不同
- 收敛方式不同
- 推断出的高层意图与真实行为不一致

优先修正对象：

- simulator reasoning policy
- high-level action space
- explanation scaffolding

### 2.5 `action_selection_error`

系统识别出用户画像和状态，但最终预测的下一步行为不对。

典型表现：

- 预测成“继续追问”，真实却是“要求落地方案”
- 预测成“求解释”，真实却是“切换主题”
- 候选集缺失真实动作

优先修正对象：

- action label space
- candidate generation
- ranking logic

### 2.6 `surface_only_match`

系统只在措辞或语气上接近用户，但核心行为和推理不对。

典型表现：

- 文风像，但意图错
- 术语习惯像，但行为链错
- 输出看似合理，但缺乏真正支撑

优先修正对象：

- 评测权重
- response generation 目标
- replay task 设计

---

## 3. 二级子类

一级类型之下，建议保留一组轻量子类。

### `memory_failure`

- `missing_explicit_fact`
- `wrong_event_order`
- `stale_memory_selected`
- `memory_conflict_unresolved`

### `persona_misalignment`

- `trait_overgeneralized`
- `short_term_behavior_overfit`
- `unsupported_persona_fact`
- `persona_conflict_unresolved`

### `state_under_specified`

- `goal_shift_missed`
- `time_pressure_missed`
- `stance_change_missed`
- `blocking_issue_missed`

### `reasoning_mismatch`

- `wrong_priority_order`
- `wrong_tradeoff_focus`
- `wrong_intent_inference`
- `wrong_conclusion_style`

### `action_selection_error`

- `candidate_set_missing`
- `ranking_error`
- `task_label_too_coarse`
- `wrong_turn_boundary`

### `surface_only_match`

- `lexical_match_only`
- `tone_match_only`
- `template_like_response`

---

## 4. 标注协议

每个 `DivergenceRecord` 必须至少包含：

- `divergence_type`
- 可选 `divergence_subtype`
- `severity`
- `critic_summary`
- 最可能缺失或错误的对象引用
- 推荐 refinement 动作

如果一条错误横跨多层，采用：

- 1 个主要类型
- 0 到 2 个次要怀疑点

避免把每个错误都标成多标签复杂组合，否则 critic 输出很快失去可操作性。

---

## 5. 类型到修正动作映射

### `memory_failure`

推荐动作：

- 新建 `MemoryNode`
- 合并冲突记忆
- 提升某类记忆的检索优先级
- 增加 event 抽取

### `persona_misalignment`

推荐动作：

- 新建或修订 `PersonaFact`
- 降低 unsupported fact 的置信度
- 引入反例 evidence
- 把某个字段从 persona 降级到 state

### `state_under_specified`

推荐动作：

- 新建 `DynamicState`
- 缩短某状态时间范围
- 标记 state 已失效
- 提高最近 episode 在状态估计中的权重

### `reasoning_mismatch`

推荐动作：

- 调整 action schema
- 调整 reasoning scaffold
- 增加中间解释步骤
- 在 replay 样本中增加高层意图标签

### `action_selection_error`

推荐动作：

- 扩展动作标签空间
- 改写候选生成策略
- 增加 top-k 排序特征
- 重新定义 target turn

### `surface_only_match`

推荐动作：

- 降低 style fidelity 权重
- 提高 behavior / reasoning 指标权重
- 关闭或弱化自由生成作为主目标

---

## 6. 标注示例

### 示例 1

系统预测：

- 用户会请求“整体研究计划”

真实行为：

- 用户要求“把 architecture 和 data schema 直接搭出来”

推荐标注：

- `divergence_type = state_under_specified`
- `divergence_subtype = goal_shift_missed`

原因：

- 系统抓到了用户偏好结构化方案，但没抓到当前目标已经从宏观规划切换到具体落地。

### 示例 2

系统预测：

- 用户会继续讨论网页应用设计

真实行为：

- 用户强调先把 research 做通，再谈 Web

推荐标注：

- `divergence_type = memory_failure`
- `divergence_subtype = missing_explicit_fact`

或

- `divergence_type = persona_misalignment`
- `divergence_subtype = unsupported_persona_fact`

选择原则：

- 如果历史里已有明确证据但系统没调出来，优先标 `memory_failure`
- 如果系统基于少量样本误判了长期偏好，优先标 `persona_misalignment`

---

## 7. 当前阶段最小可用集合

如果第一版想尽快跑通，不必一次实现全部子类。建议先实现以下 6 个主类型加 8 个常见子类：

- `memory_failure.missing_explicit_fact`
- `memory_failure.wrong_event_order`
- `persona_misalignment.unsupported_persona_fact`
- `state_under_specified.goal_shift_missed`
- `state_under_specified.blocking_issue_missed`
- `reasoning_mismatch.wrong_tradeoff_focus`
- `action_selection_error.ranking_error`
- `surface_only_match.lexical_match_only`

这组已经足够支撑第一版 replay + refinement 闭环。
