# Architecture

本文档把 [README.md](/mnt/c/Users/12879/Desktop/projects/portraiture/README.md) 里的研究定义落成可执行的系统架构。目标不是先设计一个大而全的平台，而是定义一套能支撑研究闭环、并且后续能自然扩展到网页应用的分层结构。

---

## 1. 设计原则

### 1.1 研究核心优先

当前阶段的首要目标是跑通：

`chat logs -> structured user model -> replay prediction -> divergence analysis -> refinement`

因此架构必须优先服务研究闭环，而不是优先服务产品页面或实时系统。

### 1.2 分层隔离

后续很可能增加：

- 用户上传聊天记录
- 实时展示分析过程
- 单点分析
- 问答与对话演示

这些都应建立在稳定的数据层和方法层之上，而不是反过来把研究逻辑塞进 Web handler 或临时脚本。

### 1.3 目录可扩展，但不预支复杂度

目录需要能容纳未来增长，但不能一开始就堆出一个空壳框架。原则是：

- 每一层只承载一种稳定职责
- 同一概念只保留一个 canonical location
- 尽量让“中间产物”和“最终产物”分开
- 方法代码与实验结果解耦

---

## 2. 总体分层

建议采用 6 层结构：

1. `docs/`
   研究定义、架构、schema、评测协议。
2. `data/`
   数据资产与中间产物。
3. `src/`
   核心方法实现。
4. `configs/`
   运行配置、提示词配置、评测配置。
5. `runs/`
   每次实验或分析运行的输出。
6. `apps/`
   后续 Web/API/演示层。

其中，`apps/` 在当前阶段可以不存在或保持空壳，不应反向依赖具体实验脚本。

---

## 3. 推荐目录结构

```text
portraiture/
├── README.md
├── guidance.md
├── docs/
│   ├── architecture.md
│   ├── data-schema.md
│   ├── evaluation.md
│   └── divergence-taxonomy.md
├── data/
│   ├── raw/
│   │   └── imports/
│   ├── interim/
│   │   ├── normalized/
│   │   ├── segmented/
│   │   └── indexed/
│   ├── processed/
│   │   ├── profiles/
│   │   ├── memories/
│   │   ├── states/
│   │   ├── replay/
│   │   └── eval/
│   └── artifacts/
│       ├── prompts/
│       ├── schemas/
│       └── labelsets/
├── src/
│   ├── portraiture/
│   │   ├── ingest/
│   │   ├── segmentation/
│   │   ├── extraction/
│   │   ├── memory/
│   │   ├── state/
│   │   ├── simulation/
│   │   ├── critic/
│   │   ├── evaluation/
│   │   ├── schemas/
│   │   ├── prompts/
│   │   └── utils/
├── configs/
│   ├── data/
│   ├── extraction/
│   ├── simulation/
│   ├── critic/
│   └── evaluation/
├── runs/
│   ├── experiments/
│   ├── analysis/
│   └── demos/
└── apps/
    ├── api/
    └── web/
```

---

## 4. 各层职责

### 4.1 `docs/`

只放长期稳定文档，不放一次性实验记录。

- `architecture.md`
  系统边界、模块关系、目录组织。
- `data-schema.md`
  canonical schema 定义。
- `evaluation.md`
  指标、split、基线和打分口径。
- `divergence-taxonomy.md`
  偏差类型定义和标注协议。

### 4.2 `data/`

`data/` 是研究资产层，不是脚本输出垃圾桶。需要清晰地区分原始数据、处理中间层和面向任务的最终层。

建议使用“三段式”：

- `raw/`
  不可逆、尽量不改写的原始导出数据。
- `interim/`
  规范化、切分、索引后的中间结果。
- `processed/`
  已经进入建模语义的结果，例如 persona/state/memory/replay 样本。

`artifacts/` 用于沉淀相对稳定的辅助资源，例如标签空间、schema 文件、提示词版本快照。

### 4.3 `src/portraiture/`

放核心方法实现，不放项目临时脚本。按逻辑子系统拆分，而不是按 notebook 或实验作者拆分。

- `ingest/`
  导入与格式适配。
- `segmentation/`
  session / episode / turn 切分。
- `extraction/`
  persona、event、evidence 等抽取逻辑。
- `memory/`
  episodic / semantic memory 构造与检索。
- `state/`
  dynamic state 更新。
- `simulation/`
  replay 预测与在线模拟。
- `critic/`
  divergence 分析和 refinement。
- `evaluation/`
  指标计算和报告。
- `schemas/`
  Pydantic/dataclass 等结构定义。
- `prompts/`
  提示模板。

### 4.4 `configs/`

配置与代码分离，避免后期 prompt、标签空间、阈值写死在模块内部。

推荐拆分：

- `data/`
  导入配置、字段映射、清洗规则。
- `extraction/`
  persona/state/memory 抽取配置。
- `simulation/`
  replay 配置、候选数、推理参数。
- `critic/`
  divergence 分类规则、修正阈值。
- `evaluation/`
  指标权重、数据 split、报告模板。

### 4.5 `runs/`

所有一次性运行输出都放这里，避免污染 `data/`。

- `experiments/`
  研究实验运行记录。
- `analysis/`
  单次离线分析结果。
- `demos/`
  未来面向演示的运行快照。

建议每次运行使用独立 run id，例如：

`runs/experiments/2026-03-20-replay-baseline-v1/`

其中包含：

- 使用的配置快照
- 指标输出
- 关键中间摘要
- case study

### 4.6 `apps/`

未来产品层。当前阶段不承载研究逻辑，只负责调用稳定的服务接口或 pipeline。

- `api/`
  上传、查询、问答、任务状态接口。
- `web/`
  用户交互页面、可视化、分析过程展示。

研究方法跑通前，不应为了前端方便改动底层 schema。

---

## 5. 核心研究流水线

### 5.1 Stage A: Ingest

输入：

- 外部导出的聊天记录

输出：

- `NormalizedConversation`
- `NormalizedMessage`

职责：

- 解析原始导出格式
- 统一 speaker / timestamp / content / metadata
- 记录导入来源和解析日志

### 5.2 Stage B: Segmentation

输入：

- 标准化后的 conversation/message

输出：

- `Session`
- `Episode`
- `Turn`

职责：

- 切分连续对话
- 标记主题转移
- 保留层级与顺序

### 5.3 Stage C: Extraction

输入：

- episode 及其上下文

输出：

- `PersonaFact`
- `DynamicState`
- `MemoryNode`
- `EvidenceSpan`
- `EventNode`

职责：

- 抽取稳定画像
- 抽取动态状态
- 生成 episodic / semantic memory
- 追踪证据链

### 5.4 Stage D: Simulation

输入：

- 历史画像
- 当前状态
- 检索到的记忆
- 当前 held-out 上下文

输出：

- `PredictionRecord`
- 候选行为/候选回复
- 简要解释路径

职责：

- 预测用户下一步
- 支持 replay benchmark
- 为后续 critic 提供可比较对象

### 5.5 Stage E: Critic / Refinement

输入：

- 预测输出
- ground truth
- 相关 evidence

输出：

- `DivergenceRecord`
- `RefinementAction`
- 更新后的 persona/state/memory

职责：

- 定位偏差来源
- 决定修改哪一层表示
- 追踪修正后是否真的提升

### 5.6 Stage F: Evaluation

输入：

- baseline 与 refinement 后结果

输出：

- 指标表
- 误差分布
- 案例报告

职责：

- 评估记忆、行为链、推理一致性、解释能力
- 支撑研究结论

---

## 6. 模块依赖原则

### 6.1 单向依赖

推荐依赖方向：

`ingest -> segmentation -> extraction -> simulation -> critic -> evaluation`

允许读取共享 schema 和配置，但不允许低层模块反向依赖高层模块。

### 6.2 Canonical schema 单点定义

所有结构化对象只在一个地方定义，例如 `src/portraiture/schemas/`。文档中的字段定义和代码中的对象定义必须保持一致。

### 6.3 Prompt 不是 schema

提示词模板是实现细节，不应代替数据契约。也就是说，系统必须先有明确字段，再让 prompt 去填这些字段，而不是先写 prompt，再从 prompt 输出里猜 schema。

---

## 7. 面向未来 Web 应用的兼容性要求

虽然现在先做 research，但架构要预留后续产品扩展空间。

### 7.1 上传与导入分离

未来前端上传只负责把文件送进 `raw/imports/` 或等效存储；真正的解析、清洗、切分仍由 `ingest/` 和 `segmentation/` 处理。

### 7.2 离线产物与在线查询分离

未来的“单点分析”和“问答”应尽量读取已经沉淀好的结构化画像与记忆索引，而不是每次临时从原始聊天记录全量重算。

### 7.3 可视化基于中间对象

后续如果要实时演示分析过程，页面应展示：

- 当前 episode
- 抽取出的 evidence spans
- persona/state 更新前后变化
- replay 预测和 divergence 分析

这要求中间对象本身足够干净和稳定，而不是只能从日志里反推。

---

## 8. 当前阶段建议先落地的文件

在正式写代码前，建议最先补齐以下文件和目录：

- `docs/evaluation.md`
- `docs/divergence-taxonomy.md`
- `configs/data/`
- `configs/extraction/`
- `src/portraiture/schemas/`

其中 `schemas/` 应优先和 [data-schema.md](/mnt/c/Users/12879/Desktop/projects/portraiture/docs/data-schema.md) 对齐。

---

## 9. 当前不建议做的事

- 不先搭 Web 页面再倒逼研究逻辑
- 不先做全量向量库和复杂检索基础设施
- 不先做多用户、多租户、权限系统
- 不先做端到端 fine-tune 管线
- 不把实验输出和正式数据资产混在一起

当前最重要的是：定义稳定对象，跑通最小闭环，建立可复现实验路径。
