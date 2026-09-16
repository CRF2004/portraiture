# Portraiture

基于个人与 GPT 聊天记录构建“数字分身”的研究与工程原型。

本项目当前不把目标定义为“模仿说话语气的聊天机器人”，而是定义为一个**显式、可校正、可解释的个人认知代理**：它从长期聊天轨迹中抽取稳定特征、动态状态与事件记忆，并在真实历史对话上做回放预测与误差修正，逐步逼近“像这个人如何思考、如何权衡、如何继续对话”。

---

## 1. 项目定位

### 1.1 一句话定义

**Personal digital twin from GPT chat logs** =
一个以聊天轨迹为观测数据、以显式 `persona/state/memory` 表征为中介、以 held-out 行为预测和交互表现为目标函数、通过 discrepancy-driven refinement 持续修正的对话代理。

### 1.2 问题锚点

- **Bottom-line problem**：
  给定一个人与 GPT 的长期聊天记录，构建一个能够在新情境中尽量复现该用户记忆、偏好、推理倾向与交互行为的数字分身。
- **Must-solve bottleneck**：
  不能只做“风格模仿”或“人格标签分类”；必须显式建模长期稳定特征、短期状态、事件记忆以及它们对下一步行为的影响。
- **Non-goals**：
  不追求心理测量学意义上的严格人格诊断。
  不把 Big Five 当作系统主体。
  不把“回复文本相似”视为唯一成功标准。
  第一阶段不追求直接 fine-tune 出一个端到端用户替身模型。
- **Constraints**：
  初始输入仅使用用户与 GPT 的聊天记录。
  记录中 assistant 话语既是上下文条件，也是诱发用户表达的环境变量。
  系统必须支持证据回溯，而不是黑箱给结论。
- **Success condition**：
  在保留集历史对话和新构造情境上，系统能更准确地预测用户的下一步回复、行为选择或权衡路径，并能指出支撑该预测的历史证据。

### 1.3 核心判断

项目的最小可行方向不是 `persona bot`，而是：

`evidence-backed persona graph + dynamic state tracker + memory system + simulator + critic`

这是一条“先做显式结构，再考虑蒸馏成流畅角色代理”的路线。

---

## 2. 研究对象与基本定义

### 2.1 Digital Twin

本项目中的 `digital twin` 指：

- 能利用该用户过去的长期聊天轨迹
- 在新问题或对话延续中
- 复现其相对稳定的偏好、习惯、推理风格、事件记忆与行为链倾向
- 且能解释“为什么这样预测”

它不是一个简单的“像我说话”的角色扮演器。

### 2.2 Persona / State / Memory

- **Persona**：
  跨会话相对稳定的特征，例如价值观、风险偏好、信息处理方式、解释偏好、常见兴趣、冲突风格、长期目标偏好。
- **State**：
  与当前阶段或当前 episode 强相关的动态变量，例如近期压力、当下目标、情绪状态、某个议题的临时立场、未决事项。
- **Memory**：
  来自历史对话的可检索事实与事件。
  其中分为：
  - `episodic memory`：某次对话里发生了什么
  - `semantic memory`：跨多次对话沉淀出的稳定事实或规律

### 2.3 Evidence-Backed Representation

任何画像结论都必须绑定：

- 证据片段 `evidence spans`
- 时间戳或 episode 位置
- 置信度
- 可能反例或冲突证据

系统输出的不是“你就是一个怎样的人”，而是“基于这些历史证据，我暂时推断你在这一维度更可能如此”。

### 2.4 Episode

`episode` 是建模和评估的基础单位，表示一段相对连续、围绕若干主题展开的对话片段。后续数据预处理需要把原始聊天记录切分为：

- session
- episode
- turn

并保留层级关系。

### 2.5 Behavior Chain

`behavior chain` 不是单句回复，而是用户在连续若干步中的行为模式，例如：

- 是继续追问还是切换主题
- 是请求解释、总结、举例还是行动计划
- 是表达犹豫、确认立场，还是开始收敛结论

本项目默认“行为链一致性”比“单句措辞相似度”更重要。

### 2.6 Cognitive Divergence

`cognitive divergence` 指数字分身与真实用户之间的偏差来源。典型来源包括：

- 记忆错误
- 长期偏好判断错误
- 当前状态估计错误
- 推理路径不一致
- 只在语气上相似，但行为选择不同

项目后续的 refinement 机制就是围绕 divergence 分析来设计。

---

## 3. 研究假设

### H1

仅使用聊天记录也可以恢复出一部分稳定 persona、动态 state 与长期 memory，但必须分层建模，不能单层直接拟合。

### H2

把用户表示为显式结构化对象，比把全部历史直接塞进上下文，更有利于长期一致性、可解释性和后续修正。

### H3

“真实历史对话回放 + 预测误差驱动的画像修正”是比一次性 persona 提取更有效的建模路线。

### H4

系统的主要能力上限将首先受限于：

- 事件切分是否合理
- 证据抽取是否可靠
- state 更新是否敏感
- 评测是否真正测到行为链，而不是只测表面文风

---

## 4. 第一版系统定义

### 4.1 输入

第一阶段唯一输入源：

- 用户与 GPT 的历史聊天记录

输入记录至少应包含：

- `conversation_id`
- `turn_id`
- `speaker` (`user` / `assistant`)
- `timestamp`
- `content`
- 可选元数据：标题、模型名、用户手工标签

### 4.2 输出

第一版系统应支持四类输出：

1. **用户画像输出**
   结构化 persona/state/memory 表征及证据。
2. **下一步预测输出**
   给定上下文，预测用户下一步回复或行为分布。
3. **误差分析输出**
   指出预测偏差来自哪里。
4. **画像修正输出**
   根据误差更新 persona/state/memory 结构。

### 4.3 最小闭环

最小研究闭环定义为：

1. 从原始聊天记录切分 episode。
2. 从训练部分记录抽取初始 persona/state/memory。
3. 在 held-out episode 上预测用户下一步。
4. 将预测与真实回复/行为对比。
5. 标注 divergence 类型。
6. 更新画像。
7. 再次评估是否改进。

只要这个闭环能跑通，项目就具备研究价值和工程迭代基础。

---

## 5. 系统角色划分

项目第一版采用 5 个逻辑角色，不要求物理上一定是 5 个独立 agent，但职责要分清。

### 5.1 Archivist

负责数据整理与事件化：

- 对聊天记录做清洗、切分、去重、标准化
- 划分 session / episode / turn
- 抽取事件、决策点、反思段、情绪变化线索
- 为后续模块提供结构化中间表示

### 5.2 Profiler

负责稳定层建模：

- 抽取 trait、value、habit、preference、reasoning style
- 输出结论、证据、置信度、反例
- 形成可更新的 persona graph / schema

### 5.3 State Tracker

负责动态层建模：

- 识别当前目标、近期压力、未决问题、临时立场
- 建立随时间更新的 state
- 区分“稳定偏好”与“近期状态”

### 5.4 Simulator

负责行为预测：

- 输入当前上下文与显式画像
- 输出候选回复或候选行为分布
- 输出简要解释路径

### 5.5 Critic / Refiner

负责误差分析与修正：

- 对比模拟结果与真实用户轨迹
- 识别 divergence 来源
- 更新 persona/state/memory
- 追踪修正是否提高保留集表现

---

## 6. 数据与表示层设计

### 6.1 原始数据单元

建议统一到如下粒度：

- `Conversation`
- `Episode`
- `Turn`
- `Message`

### 6.2 中间表示

建议优先定义以下结构化对象：

- `PersonaFact`
  - `field`
  - `value`
  - `confidence`
  - `evidence_turn_ids`
  - `counter_evidence_turn_ids`
  - `updated_at`
- `DynamicState`
  - `state_type`
  - `state_value`
  - `time_scope`
  - `confidence`
  - `evidence_turn_ids`
- `MemoryNode`
  - `memory_type` (`episodic` / `semantic`)
  - `summary`
  - `time_range`
  - `entities`
  - `evidence_turn_ids`
- `PredictionRecord`
  - `context_episode_id`
  - `prediction_target`
  - `predicted_candidates`
  - `ground_truth`
  - `divergence_type`
  - `critic_notes`

### 6.3 基本字段原则

- 不做无证据字段
- 不做不可回溯字段
- 不做纯描述性、不可用于后续预测的字段
- 每个字段都要考虑“它将如何改善下一步行为预测”

---

## 7. 任务拆解

### Phase 0: 数据准备

目标：把聊天记录变成可建模语料。

任务：

- 定义统一导入格式
- 清洗导出数据
- 做会话切分和 episode 切分
- 明确训练集、验证集、测试集或 held-out replay 集

交付物：

- `data/` 目录规范
- 数据 schema 文档
- 一个可重复运行的数据预处理脚本

### Phase 1: 基线画像器

目标：从训练数据中抽取初始 persona/state/memory。

任务：

- 定义第一版 persona 字段表
- 定义 state 标签空间
- 定义 episodic / semantic memory 抽取方案
- 建立 evidence span 追踪机制

交付物：

- 初版结构化画像 JSON
- 画像字段说明文档
- 若干人工检查样例

### Phase 2: 回放预测基线

目标：建立第一个可量化的 replay benchmark。

任务：

- 在 held-out episode 上预测用户下一步
- 设计“回复预测”和“行为预测”两种任务
- 记录 top-k 候选及解释

交付物：

- replay benchmark 样本集
- baseline predictor
- 初版评测脚本

### Phase 3: Critic 与 Refinement

目标：让系统不是“一次性画像”，而是可更新画像。

任务：

- 定义 divergence taxonomy
- 设计 critic 规则或 LLM-based critic
- 根据误差修正 persona/state/memory
- 比较修正前后 replay 表现

交付物：

- divergence 标注规范
- refinement loop 原型
- before/after 对比报告

### Phase 4: 在线交互原型

目标：测试 twin 在新对话中的持续一致性。

任务：

- 构建 interview-style 或 task-style evaluation
- 让 twin 在新回合中与测试 agent 交互
- 观察长期一致性、记忆调用和状态更新质量

交付物：

- online evaluation 脚本
- 若干案例分析
- 失效模式总结

---

## 8. 评测定义

第一版不追求一个大而全的单指标，采用多维评测。

### 8.1 Memory Accuracy

系统是否能正确复现：

- 用户长期偏好
- 历史事件
- 事件顺序
- 已明确表达的边界与约束

### 8.2 Reasoning Alignment

系统给出的权衡路径是否接近真实用户：

- 是否关注相似因素
- 是否按相似顺序组织思路
- 是否做出相似的收敛方式

### 8.3 Behavior Chain Accuracy

系统是否能正确预测下一步高层行为：

- 追问
- 求例子
- 求计划
- 表达保留
- 切换话题
- 收敛结论

### 8.4 Response Fidelity

只作为辅助指标，而不是主指标：

- 回复语义接近度
- 风格相似度
- 术语习惯相似度

### 8.5 Explainability

系统是否能说明：

- 为什么做出该预测
- 用到了哪些历史证据
- 哪些证据彼此冲突
- 当前结论有多大不确定性

### 8.6 Improvement Under Refinement

这是本项目的重要研究指标：

- 加入 refinement 之后，保留集表现是否改进
- 哪类 divergence 最容易被修正
- 哪类误差最顽固

---

## 9. 与常见路线的边界

### 本项目不等于

- 普通 RAG 聊天机器人
- 只做 persona prompt 的角色扮演
- Big Five 人格测试器
- 单纯模仿语气的 style clone
- 端到端监督微调的 user simulator

### 本项目更接近

- 可解释个体建模
- 长期个性化对话系统
- 显式 persona / state / memory graph
- behavior replay + discrepancy-driven refinement
- 轻量 Theory-of-Mind / inverse planning 风格的用户建模

---

## 10. 第一版实现原则

- **显式优先**：
  能结构化表示的，不先藏进 prompt。
- **证据优先**：
  没有 evidence span 的画像字段默认不可信。
- **回放优先**：
  先在历史 replay 上证明有效，再谈在线交互。
- **最小机制优先**：
  先跑通最小闭环，不急于堆 agent、堆训练或堆复杂图结构。
- **可校正优先**：
  第一次画像不要求完美，但必须允许后续更新。

---

## 11. 当前建议的近期任务

这是接下来最值得优先完成的一组任务。

1. 明确聊天记录的原始导出格式，建立统一解析入口。
2. 定义 `Conversation / Episode / Turn / PersonaFact / MemoryNode / PredictionRecord` 的 schema。
3. 实现一个最小预处理管线，把原始聊天记录转成结构化 JSONL。
4. 做一个初版 `Profiler`，至少能抽取稳定偏好、长期兴趣和若干显式边界。
5. 做一个 held-out replay 任务，先预测“用户下一步会做什么类型的动作”。
6. 做一个 `Critic`，把错误分成几类并输出修正建议。
7. 基于修正前后对比，确认这条路线是否真的优于简单 persona prompt baseline。

---

## 12. 后续文档角色

本 `README` 是项目当前的主定义文档，后续工作默认以它为基线推进。后续可以按需补充：

- `docs/data-schema.md`
- `docs/evaluation.md`
- `docs/divergence-taxonomy.md`
- `docs/architecture.md`
- `tasks/roadmap.md`

如与 `guidance.md` 有冲突，以本 `README` 中冻结后的问题定义和任务拆解为准；`guidance.md` 作为研究动机与相关工作参考。


## 服务器停用归档（2026-09-16）

本仓库为私有归档，保存服务器当前项目文件和数据。大型数据、字体和部分图片使用 Git LFS，恢复时先运行：

```bash
git lfs install
git lfs pull
```

然后按本文已有启动步骤恢复环境。真实访问凭据通过环境变量配置；原始生产配置保留在本地原始备份中。归档范围、原目录和排除内容见 `ARCHIVE_NOTES.md`。
