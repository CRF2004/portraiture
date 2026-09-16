# ECG XAI Zero-Masking Analysis

**Conversation ID:** `6a164a7f-b050-83ec-bfd9-42a0084dafb1`

**Model:** gpt-5-5-thinking

**Created:** 2026/5/27 09:36:17

**Last Updated:** 2026/5/27 09:36:58

---

## 👤 User (2026/5/27 09:36:16)


| 论点 | 证据/用途 | 引用格式 | URL |
| --- | --- | --- | --- |
| ECG perturbation-based XAI 中直接使用 zero-masking / setting-to-zero | Paralič et al. 在 12-lead ECG 的 perturbation explanation 方法中明确写道：被扰动区间的 values “are set to zero”。适合支撑“ECG 扰动解释中存在 zero-masking 实践”。([MDPI][2]) | Paralič, J., Kolárik, M., Paraličová, Z., Lohaj, O., & Jozefík, A. (2023). *Perturbation-Based Explainable AI for ECG Sensor Data*. **Applied Sciences, 13**(3), 1805. [https://doi.org/10.3390/app13031805](https://doi.org/10.3390/app13031805) | [https://www.mdpi.com/2076-3417/13/3/1805](https://www.mdpi.com/2076-3417/13/3/1805) |
| zero-masking / setting-to-zero 是 ECG XAI 中 frequently used 的扰动方案 | Goettling et al. 明确称其为 “frequently used scheme of setting values zero”，这是支持“常用”的最直接文献。但它支持的是 **frequently used**，不是严格统计意义上的 **most common**。([Nature][1]) | Goettling, M., Hammer, A., Malberg, H., et al. (2024). *xECGArch: A trustworthy deep learning architecture for interpretable ECG analysis considering short-term and long-term features*. **Scientific Reports, 14**, 13122. [https://doi.org/10.1038/s41598-024-63656-x](https://doi.org/10.1038/s41598-024-63656-x) | [https://www.nature.com/articles/s41598-024-63656-x](https://www.nature.com/articles/s41598-024-63656-x) |
| zero-masking 会引入 hard-boundary / out-of-distribution artifacts | Goettling et al. 指出 setting values to zero 会引入 noise，因为模型并未在包含 “sudden jumps to zero” 的数据上训练；这直接支持你句子里的 hard-boundary artifact / OOD artifact 论点。([Nature][1]) | Goettling, M., Hammer, A., Malberg, H., et al. (2024). *xECGArch: A trustworthy deep learning architecture for interpretable ECG analysis considering short-term and long-term features*. **Scientific Reports, 14**, 13122. [https://doi.org/10.1038/s41598-024-63656-x](https://doi.org/10.1038/s41598-024-63656-x) | [https://www.nature.com/articles/s41598-024-63656-x](https://www.nature.com/articles/s41598-024-63656-x) |
| 扰动算子会改变 explanation 结论 / XAI 方法排名 | Goettling et al. 比较 linear interpolation 与 setting-to-zero 后发现，不同 perturbation scheme 会让不同 XAI 方法看起来更优；zero perturbation 下 ITG 表现最好，而 interpolation 下 DTD 更可信。适合支撑“perturbation operator 本身应被审计”。([Nature][1]) | Goettling, M., Hammer, A., Malberg, H., et al. (2024). *xECGArch: A trustworthy deep learning architecture for interpretable ECG analysis considering short-term and long-term features*. **Scientific Reports, 14**, 13122. [https://doi.org/10.1038/s41598-024-63656-x](https://doi.org/10.1038/s41598-024-63656-x) | [https://www.nature.com/articles/s41598-024-63656-x](https://www.nature.com/articles/s41598-024-63656-x) |
| 生物医学时序信号 occlusion 中常见 zero-value window occlusion，且包括 ECG 实验 | Resta et al. 提出用于 biomedical signals 的 occlusion explanation，说明 windowed occlusion 中使用 zero values；其 PTBDB 分类实验是 ECG-only，并比较 zero 与 mean occlusion。([MDPI][3]) | Resta, M., Monreale, A., & Bacciu, D. (2021). *Occlusion-Based Explanations in Deep Recurrent Models for Biomedical Signals*. **Entropy, 23**(8), 1064. [https://doi.org/10.3390/e23081064](https://doi.org/10.3390/e23081064) | [https://www.mdpi.com/1099-4300/23/8/1064](https://www.mdpi.com/1099-4300/23/8/1064) |
| cardiac / ECG XAI 中解释评估不足，很多研究没有系统量化 explanation quality | Salih et al. 对 cardiac AI XAI evaluation 的综述显示，43% 的研究完全没有评估所用 XAI，只有部分研究使用专家、proxy 或统计分析评价解释质量。适合支撑“影响 seldom quantified / rarely audited”。([Springer][4]) | Salih, A. M., Galazzo, I. B., Gkontra, P., et al. (2024). *A review of evaluation approaches for explainable AI with applications in cardiology*. **Artificial Intelligence Review, 57**, 240. [https://doi.org/10.1007/s10462-024-10852-w](https://doi.org/10.1007/s10462-024-10852-w) | [https://link.springer.com/article/10.1007/s10462-024-10852-w](https://link.springer.com/article/10.1007/s10462-024-10852-w) |

建议你的原句改成更稳的版本：

> Second, the perturbation operator itself is rarely treated as an auditable methodological variable: a frequently used choice in ECG occlusion analysis is zero-masking, or setting signal samples/segments to zero, which can introduce hard-boundary and out-of-distribution artifacts; the downstream influence of this design choice on explanation conclusions is often insufficiently quantified.


你帮我核对一下这里对论文的观点提炼是否正确

---

## 🤖 Assistant (2026/5/27 09:36:17)

我会逐条核对这些论文是否真的支撑你列出的论点，重点看原文是否有“set to zero / frequently used / sudden jumps / evaluation不足”等关键表述，而不是只看摘要。

---

## 🤖 Assistant (2026/5/27 09:36:29)

总体判断：**大方向是对的，但有两处最好降调**。你这组证据可以支撑“ECG/biomedical time-series XAI 里存在 zero-masking/setting-to-zero 实践，并且它可能引入 OOD/noise artifact，甚至改变 XAI 方法排序”。但不要写成“most common”，也不要让 Salih et al. 看起来是在专门说“perturbation operator 的影响很少被量化”。

| 论点 | 核对结果 | 建议 |
|---|---|---|
| **Paralič et al. 支撑 ECG perturbation XAI 直接 set to zero** | **正确。**原文明确说，在他们的方法中，被扰动 interval 的 values “are set to zero”，而且上下文就是 12-lead ECG sensor data 的 perturbation explanation。citeturn648605view0 | 可放心使用。 |
| **Goettling et al. 支撑 zero-masking 是 frequently used scheme** | **基本正确。**他们确实写到为了比较新 perturbation scheme，使用了 “frequently used scheme of setting values zero”。citeturn533359view0 | 你已经提醒“不是 most common”，这个很稳。建议写 **a frequently used perturbation scheme**，不要写 **the dominant / most common scheme**。 |
| **Goettling et al. 支撑 hard-boundary / OOD artifacts** | **正确，但措辞要标成你的概括。**原文说 setting values to zero 会引入 noise，因为模型没有在带有 sudden jumps to zero 的数据上训练；他们还把问题放在“unknown from training data distribution”的语境下。citeturn533359view1 | “hard-boundary artifact / OOD artifact”是合理转述，但最好写成 **can introduce abrupt zero-jump artifacts outside the training distribution**，更贴近原文。 |
| **Goettling et al. 支撑 perturbation operator 会改变 XAI 方法排名/结论** | **正确。**线性插值下 DTD 表现最好/较好；zero perturbation 下 ITG 对两个模型导致最大 loss increase，而 DTD 分数明显变低；讨论中他们明确说 zero scheme 下 DTD 会被认为不合适，和 interpolation 结果相反。citeturn533359view2 | 这是你最强的一条证据。可以直接支撑“operator 本身应被审计”。 |
| **Resta et al. 支撑 biomedical signal occlusion 中使用 zero-value window occlusion，并包括 ECG/PTBDB** | **部分正确。**他们确实提出 biomedical sequential signals 的 occlusion method，定义 occlusion 为用给定值替换输入片段，并在实验中用 zero values 做 windowed occlusion；PTBDB 分类实验里 ECG 是唯一输入信号，并比较 zero 和 mean occlusion。citeturn993313view0 citeturn137014view1 | 但“常见”这个词不要主要靠 Resta 支撑。Resta 更适合支撑 **zero occlusion is used in biomedical/ECG time-series explanation experiments**。 |
| **Salih et al. 支撑 cardiac/ECG XAI evaluation 不足** | **正确，但范围要说清楚。**Salih et al. 是 cardiac AI XAI evaluation 综述，摘要中给出 37% literature-grounded、11% expert、11% proxy/statistical、43% no XAI assessment；正文也说 92 篇没有任何 XAI outcome evaluation，且 ECG 是这些未评估研究中最常见数据类型。citeturn648605view3 | 它能支撑“cardiac XAI explanation evaluation is often insufficient”，但不能单独支撑“perturbation operator 的 downstream influence seldom quantified”。后者主要靠 Goettling 的对比实验来支撑。 |

我建议你的句子稍微改得更严谨一点：

> Second, the perturbation operator itself is rarely treated as an auditable methodological variable. In ECG and biomedical time-series occlusion analyses, zero-masking—i.e., setting signal samples or segments to zero—is a documented and frequently used perturbation choice, but it can introduce abrupt zero-jump artifacts outside the model’s training distribution. Recent ECG evidence shows that the choice between zero-masking and interpolation can change which XAI method appears most trustworthy, while broader cardiology XAI reviews indicate that explanation quality is still often insufficiently evaluated.

这个版本比你原句更稳的地方是：  
**“rarely treated as auditable”** 被表述成综合判断；**“frequently used”** 主要挂在 Goettling 上；**“hard-boundary/OOD”** 改成更贴近原文的 **abrupt zero-jump artifacts outside training distribution**；最后一句把 Salih 的贡献限定为“broader cardiology XAI evaluation不足”，不让它承担过重论证。

