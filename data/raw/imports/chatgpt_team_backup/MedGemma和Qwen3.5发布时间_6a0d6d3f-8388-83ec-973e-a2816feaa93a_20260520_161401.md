# MedGemma和Qwen3.5发布时间

**Conversation ID:** `6a0d6d3f-8388-83ec-973e-a2816feaa93a`

**Model:** gpt-5-5-thinking

**Created:** 2026/5/20 16:14:01

**Last Updated:** 2026/5/20 16:18:24

---

## 👤 User (2026/5/20 16:13:59)

medgemma是什么时候出的，qwen3.5呢

---

## 🤖 Assistant (2026/5/20 16:14:01)

我先核对一下公开发布信息，因为这两个名称都容易和不同版本/传闻混在一起。

---

## 🤖 Assistant (2026/5/20 16:14:07)

MedGemma 最早公开可用是在 **Google I/O 2025，约 2025 年 5 月 20 日**。Google 开发者博客当时写到 “MedGemma is available for use now”。后来 **MedGemma 1.5 4B** 是 **2026 年 1 月 13 日** 发布/更新的。citeturn867906search0turn521208search0

Qwen3.5 是 **2026 年 2 月 16 日** 阿里发布的。citeturn521208search1

所以按时间线：

| 模型 | 发布时间 |
|---|---:|
| MedGemma | 2025-05-20 左右 |
| MedGemma 1.5 | 2026-01-13 |
| Qwen3.5 | 2026-02-16 |

---

## 👤 User (2026/5/20 16:16:03)

qwen3.5-4B呢

---

## 🤖 Assistant (2026/5/20 16:16:14)

**Qwen3.5-4B 应该是 2026 年 3 月初发布的。**

我查到两个比较稳的线索：

1. **Hugging Face 的 Qwen/Qwen3.5-4B 页面显示日期为 2026 年 3 月 9 日**，这是模型卡/页面可见的时间点。citeturn628156search0  
2. Artificial Analysis 在 **2026 年 3 月 5 日** 写到阿里已经发布了 0.8B 到 9B 的 4 个小尺寸 Qwen3.5 模型，其中包括 **4B**。citeturn628156search4

所以更精确地说：**Qwen3.5 整个系列首发是 2026-02-16；Qwen3.5-4B 这一档小模型大约在 2026-03-05 到 2026-03-09 之间公开上线。**

---

## 👤 User (2026/5/20 16:18:05)

medgemma1.5是从去年那个medgemma蒸馏的吗

---

## 🤖 Assistant (2026/5/20 16:18:14)

不是简单地“从去年那个 MedGemma 蒸馏出来”的。

更准确说：**MedGemma 1.5 4B 是 MedGemma 1 4B 的更新版 / 延续版**，架构仍基于 **Gemma 3**，并在 MedGemma 1 的基础能力上继续训练、加入新数据、新任务和后训练流程。Google 的技术报告说它“expands on MedGemma 1”，并且 1.5 的 4B 模型继续使用 MedGemma 1 的 **MedSigLIP 视觉编码器**，语言解码器做了额外预训练。citeturn539141view1

但它**确实用了蒸馏**：报告里写到 1.5 的 post-training 包含 **distillation + RL**，而且蒸馏过程加入了更多领域专用 teacher model，以及更强的 instruction-tuned teacher。也就是说，蒸馏是训练流程的一部分，不是“拿 MedGemma 1 当唯一 teacher 直接蒸一个 1.5”。citeturn539141view3

一句话：**MedGemma 1.5 = MedGemma 1 4B 的升级迭代 + 新医学数据继续训练 + 多 teacher 蒸馏 + RL 对齐**。如果你说“是不是从旧 MedGemma 继续训练/升级来的”，答案是**是**；如果说“是不是由旧 MedGemma 单独蒸馏出来”，答案是**不是**。

