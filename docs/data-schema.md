# Data Schema

本文档定义项目当前阶段的 canonical data schema。目标是把研究中的抽象对象变成可实现、可验证、可扩展的数据契约。

设计原则：

- 先定义研究最需要的字段
- 每个对象只承担单一职责
- 证据链必须可回溯
- 字段命名服务于长期维护，而不是一次性 prompt 输出
- 兼容后续 Web 上传、可视化、问答和在线演示

---

## 1. Schema 分层

整个数据 schema 分为 5 层：

1. **Import Layer**
   外部原始导入。
2. **Canonical Conversation Layer**
   标准化后的聊天记录。
3. **Segmentation Layer**
   session / episode / turn 层级对象。
4. **Modeling Layer**
   persona / state / memory / event / evidence。
5. **Evaluation Layer**
   replay、prediction、divergence、refinement。

每一层都可以单独落盘，避免后续重复计算。

---

## 2. 文件组织建议

建议使用如下落盘方式：

```text
data/
├── raw/
│   └── imports/
│       └── <source_name>/
├── interim/
│   ├── normalized/
│   │   ├── conversations.jsonl
│   │   └── messages.jsonl
│   ├── segmented/
│   │   ├── sessions.jsonl
│   │   ├── episodes.jsonl
│   │   └── turns.jsonl
│   └── indexed/
│       ├── message_index.jsonl
│       └── evidence_index.jsonl
└── processed/
    ├── profiles/
    │   ├── persona_facts.jsonl
    │   └── profile_snapshots.jsonl
    ├── states/
    │   ├── dynamic_states.jsonl
    │   └── state_snapshots.jsonl
    ├── memories/
    │   ├── memory_nodes.jsonl
    │   └── event_nodes.jsonl
    ├── replay/
    │   ├── replay_examples.jsonl
    │   ├── predictions.jsonl
    │   └── divergences.jsonl
    └── eval/
        └── metrics.jsonl
```

当前阶段优先使用 `JSONL`，原因：

- 人可读
- 便于抽样检查
- 适合逐步追加
- 后续可平滑迁移到 Parquet / DB

---

## 3. 通用字段约定

所有对象尽量包含以下共通字段：

- `id`
  全局唯一标识。
- `user_id`
  当前研究对象标识。
- `source_id`
  来源文件或导入批次标识。
- `created_at`
  对象首次生成时间。
- `updated_at`
  对象最近更新时间。
- `version`
  schema 或对象版本号。

推荐 ID 命名：

- `conv_<...>`
- `msg_<...>`
- `sess_<...>`
- `ep_<...>`
- `turn_<...>`
- `pf_<...>`
- `st_<...>`
- `mem_<...>`
- `pred_<...>`
- `div_<...>`

---

## 4. Import Layer

### 4.1 `ImportedSource`

表示一次导入的数据源。

```json
{
  "id": "src_chatgpt_export_20260320_001",
  "user_id": "user_demo",
  "source_type": "chatgpt_export",
  "source_path": "data/raw/imports/chatgpt/export-2026-03-20.zip",
  "source_label": "chatgpt-main-export",
  "ingest_status": "imported",
  "notes": null,
  "created_at": "2026-03-20T10:00:00+08:00",
  "updated_at": "2026-03-20T10:00:00+08:00",
  "version": "v1"
}
```

字段说明：

- `source_type`
  导入来源类型，例如 `chatgpt_export`、`manual_json`。
- `source_path`
  原始文件位置。
- `ingest_status`
  `imported` / `parsed` / `failed`。

---

## 5. Canonical Conversation Layer

### 5.1 `Conversation`

表示一条原始会话容器。

```json
{
  "id": "conv_001",
  "user_id": "user_demo",
  "source_id": "src_chatgpt_export_20260320_001",
  "external_conversation_id": "chatgpt_conv_abc",
  "title": "数字分身想法讨论",
  "started_at": "2026-02-01T20:01:00+08:00",
  "ended_at": "2026-02-01T21:03:00+08:00",
  "message_count": 42,
  "primary_language": "zh",
  "metadata": {
    "model_slug": "gpt-4.1",
    "source_format": "chatgpt_export_v1"
  },
  "created_at": "2026-03-20T10:00:00+08:00",
  "updated_at": "2026-03-20T10:00:00+08:00",
  "version": "v1"
}
```

### 5.2 `Message`

表示标准化后的最小消息单元。

```json
{
  "id": "msg_001",
  "user_id": "user_demo",
  "source_id": "src_chatgpt_export_20260320_001",
  "conversation_id": "conv_001",
  "speaker": "user",
  "speaker_role": "user",
  "timestamp": "2026-02-01T20:05:12+08:00",
  "content": "我想做一个自己的数字分身。",
  "content_text": "我想做一个自己的数字分身。",
  "content_tokens_est": 14,
  "reply_to_message_id": null,
  "sequence_index": 5,
  "metadata": {
    "raw_message_id": "chatgpt_msg_123"
  },
  "created_at": "2026-03-20T10:00:00+08:00",
  "updated_at": "2026-03-20T10:00:00+08:00",
  "version": "v1"
}
```

字段约束：

- `speaker` 当前只允许 `user` 或 `assistant`
- `content_text` 是清洗后可供建模使用的正文
- `content` 保留原始规范化文本
- `sequence_index` 是 conversation 内稳定顺序

---

## 6. Segmentation Layer

### 6.1 `Session`

`Session` 表示时间上连续的一组消息集合。

```json
{
  "id": "sess_001",
  "user_id": "user_demo",
  "conversation_id": "conv_001",
  "start_message_id": "msg_001",
  "end_message_id": "msg_030",
  "started_at": "2026-02-01T20:01:00+08:00",
  "ended_at": "2026-02-01T20:45:00+08:00",
  "message_count": 30,
  "segmentation_method": "time_gap_v1",
  "created_at": "2026-03-20T10:10:00+08:00",
  "updated_at": "2026-03-20T10:10:00+08:00",
  "version": "v1"
}
```

### 6.2 `Episode`

`Episode` 是研究主单位，通常对应一个相对自洽的话题或问题求解片段。

```json
{
  "id": "ep_001",
  "user_id": "user_demo",
  "conversation_id": "conv_001",
  "session_id": "sess_001",
  "start_message_id": "msg_004",
  "end_message_id": "msg_012",
  "turn_ids": ["turn_002", "turn_003", "turn_004"],
  "topic_label": "research_scoping",
  "topic_summary": "用户讨论如何把聊天记录作为数字分身入口。",
  "episode_index": 1,
  "started_at": "2026-02-01T20:05:12+08:00",
  "ended_at": "2026-02-01T20:16:33+08:00",
  "segmentation_method": "topic_shift_v1",
  "created_at": "2026-03-20T10:20:00+08:00",
  "updated_at": "2026-03-20T10:20:00+08:00",
  "version": "v1"
}
```

### 6.3 `Turn`

`Turn` 表示一轮交互，通常是一个 user message 及其后续 assistant reply。

```json
{
  "id": "turn_002",
  "user_id": "user_demo",
  "conversation_id": "conv_001",
  "session_id": "sess_001",
  "episode_id": "ep_001",
  "user_message_id": "msg_004",
  "assistant_message_ids": ["msg_005"],
  "turn_index": 2,
  "started_at": "2026-02-01T20:05:12+08:00",
  "ended_at": "2026-02-01T20:06:08+08:00",
  "created_at": "2026-03-20T10:20:00+08:00",
  "updated_at": "2026-03-20T10:20:00+08:00",
  "version": "v1"
}
```

说明：

- `Turn` 是后续抽取 evidence、建立 replay 样本的主要锚点。
- 如果存在连续 user message 或连续 assistant message，可允许空数组或多消息数组。

---

## 7. Modeling Layer

### 7.1 `EvidenceSpan`

任何 persona/state/memory 结论都应由 `EvidenceSpan` 支撑。

```json
{
  "id": "ev_001",
  "user_id": "user_demo",
  "conversation_id": "conv_001",
  "episode_id": "ep_001",
  "turn_id": "turn_002",
  "message_id": "msg_004",
  "speaker": "user",
  "char_start": 0,
  "char_end": 18,
  "text": "我想做一个自己的数字分身。",
  "evidence_type": "explicit_goal",
  "notes": "直接陈述当前研究目标",
  "created_at": "2026-03-20T10:30:00+08:00",
  "updated_at": "2026-03-20T10:30:00+08:00",
  "version": "v1"
}
```

### 7.2 `PersonaFact`

表示稳定层中的一条画像事实。

```json
{
  "id": "pf_001",
  "user_id": "user_demo",
  "field": "planning_preference",
  "value": "prefers_structured_research_plans",
  "confidence": 0.82,
  "status": "active",
  "evidence_ids": ["ev_001", "ev_008"],
  "counter_evidence_ids": [],
  "support_count": 2,
  "first_observed_at": "2026-02-01T20:05:12+08:00",
  "last_observed_at": "2026-03-18T13:12:00+08:00",
  "source_method": "profiler_v1",
  "notes": "多次要求先定义框架再推进实现",
  "created_at": "2026-03-20T10:40:00+08:00",
  "updated_at": "2026-03-20T10:40:00+08:00",
  "version": "v1"
}
```

字段约束：

- `field` 应来自受控字段表
- `status` 建议为 `active` / `deprecated` / `uncertain`
- `value` 建议优先结构化枚举，不优先长文本自由描述

### 7.3 `DynamicState`

表示在某个时间范围内成立的动态状态判断。

```json
{
  "id": "st_001",
  "user_id": "user_demo",
  "state_type": "current_goal",
  "state_value": "formalize_research_scope",
  "confidence": 0.91,
  "time_scope": {
    "start_episode_id": "ep_001",
    "end_episode_id": "ep_003"
  },
  "evidence_ids": ["ev_001"],
  "derived_from_persona_ids": [],
  "status": "active",
  "source_method": "state_tracker_v1",
  "created_at": "2026-03-20T10:45:00+08:00",
  "updated_at": "2026-03-20T10:45:00+08:00",
  "version": "v1"
}
```

### 7.4 `MemoryNode`

表示长期可检索记忆节点。

```json
{
  "id": "mem_001",
  "user_id": "user_demo",
  "memory_type": "semantic",
  "title": "项目优先级偏好",
  "summary": "用户倾向先固化 research 和方法，再做产品形态。",
  "entities": ["research", "web_app", "method"],
  "tags": ["priority", "product_scope"],
  "evidence_ids": ["ev_001", "ev_020"],
  "source_episode_ids": ["ep_001", "ep_005"],
  "retrieval_text": "用户更重视先把 research 做扎实，再考虑网页应用和实时演示。",
  "status": "active",
  "created_at": "2026-03-20T10:50:00+08:00",
  "updated_at": "2026-03-20T10:50:00+08:00",
  "version": "v1"
}
```

### 7.5 `EventNode`

表示一段与行为变化、任务推进或关键决策有关的事件。

```json
{
  "id": "evt_001",
  "user_id": "user_demo",
  "event_type": "project_decision",
  "title": "先补 architecture 与 data schema",
  "summary": "用户决定先把研究文档和 schema 固化，再推进实现。",
  "conversation_id": "conv_001",
  "episode_id": "ep_002",
  "turn_ids": ["turn_008"],
  "evidence_ids": ["ev_020"],
  "event_time": "2026-03-20T11:00:00+08:00",
  "importance": 0.88,
  "created_at": "2026-03-20T11:00:00+08:00",
  "updated_at": "2026-03-20T11:00:00+08:00",
  "version": "v1"
}
```

### 7.6 `ProfileSnapshot`

用于记录某个时间点的画像快照，方便后续对比 refinement。

```json
{
  "id": "profile_snapshot_001",
  "user_id": "user_demo",
  "snapshot_label": "baseline_before_replay",
  "persona_fact_ids": ["pf_001", "pf_002"],
  "dynamic_state_ids": ["st_001"],
  "memory_node_ids": ["mem_001"],
  "source_run_id": "run_replay_baseline_v1",
  "created_at": "2026-03-20T11:10:00+08:00",
  "updated_at": "2026-03-20T11:10:00+08:00",
  "version": "v1"
}
```

---

## 8. Evaluation Layer

### 8.1 `ReplayExample`

定义一个 held-out 回放样本。

```json
{
  "id": "replay_001",
  "user_id": "user_demo",
  "episode_id": "ep_010",
  "target_turn_id": "turn_032",
  "context_turn_ids": ["turn_027", "turn_028", "turn_029", "turn_030", "turn_031"],
  "prediction_task": "next_user_action",
  "ground_truth_label": "request_structured_plan",
  "ground_truth_message_id": "msg_120",
  "eligible_profile_snapshot_id": "profile_snapshot_001",
  "split": "test",
  "created_at": "2026-03-20T11:20:00+08:00",
  "updated_at": "2026-03-20T11:20:00+08:00",
  "version": "v1"
}
```

### 8.2 `PredictionRecord`

记录某个样本上的预测结果。

```json
{
  "id": "pred_001",
  "user_id": "user_demo",
  "replay_example_id": "replay_001",
  "predictor_name": "simulator_v1",
  "profile_snapshot_id": "profile_snapshot_001",
  "predicted_task": "next_user_action",
  "predicted_label": "request_structured_plan",
  "candidate_labels": [
    {"label": "request_structured_plan", "score": 0.62},
    {"label": "ask_for_examples", "score": 0.25},
    {"label": "switch_topic", "score": 0.13}
  ],
  "predicted_response_text": null,
  "reasoning_summary": "用户当前目标是先收束定义，因此大概率请求结构化方案。",
  "used_persona_fact_ids": ["pf_001"],
  "used_state_ids": ["st_001"],
  "used_memory_node_ids": ["mem_001"],
  "created_at": "2026-03-20T11:30:00+08:00",
  "updated_at": "2026-03-20T11:30:00+08:00",
  "version": "v1"
}
```

### 8.3 `DivergenceRecord`

记录预测与真实行为之间的偏差。

```json
{
  "id": "div_001",
  "user_id": "user_demo",
  "replay_example_id": "replay_001",
  "prediction_record_id": "pred_001",
  "ground_truth_label": "ask_for_schema_details",
  "predicted_label": "request_structured_plan",
  "is_correct": false,
  "divergence_type": "state_under_specified",
  "severity": 0.71,
  "critic_summary": "模型抓到了结构化偏好，但没有识别当前请求已从宏观规划转向 schema 落地。",
  "suspected_missing_persona_fact_ids": [],
  "suspected_missing_state_ids": ["st_004"],
  "suspected_missing_memory_node_ids": [],
  "recommended_refinement_action_ids": ["ref_001"],
  "created_at": "2026-03-20T11:40:00+08:00",
  "updated_at": "2026-03-20T11:40:00+08:00",
  "version": "v1"
}
```

### 8.4 `RefinementAction`

表示一次具体修正动作。

```json
{
  "id": "ref_001",
  "user_id": "user_demo",
  "target_object_type": "dynamic_state",
  "target_object_id": "st_004",
  "action_type": "create",
  "action_reason": "用户当前目标已切换为 schema concretization",
  "evidence_ids": ["ev_020"],
  "triggered_by_divergence_id": "div_001",
  "applied": true,
  "applied_in_run_id": "run_refinement_v1",
  "created_at": "2026-03-20T11:45:00+08:00",
  "updated_at": "2026-03-20T11:45:00+08:00",
  "version": "v1"
}
```

### 8.5 `MetricRecord`

存储实验指标。

```json
{
  "id": "metric_001",
  "user_id": "user_demo",
  "run_id": "run_replay_baseline_v1",
  "metric_group": "replay",
  "metric_name": "next_action_accuracy",
  "metric_value": 0.57,
  "split": "test",
  "config_ref": "configs/evaluation/replay-baseline.yaml",
  "notes": null,
  "created_at": "2026-03-20T12:00:00+08:00",
  "updated_at": "2026-03-20T12:00:00+08:00",
  "version": "v1"
}
```

---

## 9. 受控字段建议

### 9.1 Persona `field` 候选

建议初版限制在少量高价值字段：

- `planning_preference`
- `explanation_preference`
- `risk_preference`
- `decision_style`
- `interaction_style`
- `topic_interest`
- `constraint_preference`
- `long_term_goal`

### 9.2 Dynamic State `state_type` 候选

- `current_goal`
- `active_problem`
- `time_pressure`
- `uncertainty_level`
- `emotional_tone`
- `current_stance`
- `blocking_issue`

### 9.3 Replay `prediction_task` 候选

建议先从高层行为开始，不先做自由生成：

- `next_user_action`
- `next_question_type`
- `next_intent_label`
- `next_topic_shift`

等 replay 基线稳定后，再加：

- `next_user_response_generation`

---

## 10. 版本与迁移原则

### 10.1 Schema versioning

每个对象保留 `version` 字段。文档层面当前统一为 `v1`。

### 10.2 不破坏历史结果

如果字段变更影响历史 JSONL，应新增迁移脚本或升级读取器，不直接覆盖旧数据。

### 10.3 保持 canonical object 稳定

未来即使接数据库、向量库或 Web API，也应把这里定义的对象当作 canonical contract，而不是让存储方式反过来定义研究对象。

---

## 11. 当前阶段最低实现要求

正式开工时，最少需要先把以下对象实现成代码结构：

- `Conversation`
- `Message`
- `Session`
- `Episode`
- `Turn`
- `EvidenceSpan`
- `PersonaFact`
- `DynamicState`
- `MemoryNode`
- `ReplayExample`
- `PredictionRecord`
- `DivergenceRecord`
- `RefinementAction`

只要这些对象稳定，后续再接：

- LLM 抽取器
- 评测器
- Web API
- 前端可视化

都不会导致研究核心反复改 schema。
