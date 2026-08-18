# RESULTS — skill-ab-2026-08-10：siftline-research Skill A/B 非盲综合分析

评测日期：2026-08-10。范围：3 个只读研究任务 × 2 条件（baseline / siftline-research Skill）× 2 位盲评裁判（fresh DeepSeek V4 Flash `opencode-go/deepseek-v4-flash`、fresh Qwen 3.7 Max `opencode-go/qwen3.7-max`）。本文件由人工非盲分析产出，所有数字均可在下述原始产物中复核；**不修改任何 generated/judged 产物、mapping 或三个目标项目**。

数据来源：`output/generated/{task}/{condition}/{assistant.txt,meta.json,raw.jsonl}`（6 份）、`output/judged/{task}/{judge}/result.json` 与 `meta.json`（6 份）、`output/summary.json`、`mapping.json`、`rubric.md`。

---

## 1. 总判断：Skill 是否有用、适用边界

**结论：有用，但边界明确——Skill 改善的是「研究流程与输出结构」，不是「事实校验正确率」；质量胜负打平，效率优势一致。**

- **盲评胜负（解码后）**：task1（overclock）baseline 2-0；task2（worldloom）skill 2-0；task3（poiema）1-1。按裁判计：baseline 3、skill 3。
- **一致且可复现的优势（逐任务 vs 合计）**：**成本与墙钟时间在 3/3 任务上都是 skill 臂更低**（task1 $0.0097 vs $0.0100、task2 $0.0085 vs $0.0143、task3 $0.0114 vs $0.0138；墙钟 307/269/712s vs 368/497/1120s）；**合计** tokens −46%（skill 4,287,870 vs baseline 8,009,442）、ext_ops −16%（41 vs 49）。**不是逐任务一致**：task1/overclock 的 skill 臂 token 1,205,476 > baseline 912,056、ext_ops 16 > 10，task2 的 skill 臂正文 3743 字符也略长于 baseline 3657。skill 臂更严格遵守"siftline 优先"的搜索纪律（合计 siftline 调用 33 vs 21），在输出结构（证据阶梯、"证 X 未证 Y"近邻表、coverage boundary、拒绝合并分母）上明显更强。两名裁判在 task2 一致指出这些优势。
- **未赢得的方面**：在 `current_state_accuracy`（skill −1.0）与 `demand_pain_evidence`（skill −0.67）两个维度上 baseline 平均领先，主要由 task1/task3 中 skill 臂的**事实性失误**驱动（task1：README 文档漂移未抓出、TFWR 好评率 96.6% vs 实测 95.5%；task3：把 IMPLEMENTATION-STATUS 的 08-09 历史里程碑"1071/120"错记成 README 声称、且断言该文件"08-09 落后一个增量"——实为 08-10 且其顶部里程碑即当前树）。
- **适用边界**：当任务主要奖励**仓库当前状态的事实精度与文档归属核对**（task1、task3 的当前状态部分），Skill 的流程模板不能防止偶发数字/归属错误，且会被裁判重罚；当任务主要奖励**多机制结构、近邻归因与成本效率**（task2），Skill 的模板直接转化为可判定的质量差。**N=3，上述为方向而非定论**（见 §7）。

---

## 2. 三任务逐项

解码规则（`mapping.json`）：task1 X=skill / Y=baseline；task2 X=baseline / Y=skill；task3 X=skill / Y=baseline。`flash-xy` 按 X→Y 顺序展示，`qwenmax-yx` 按 Y→X 反序（抵消顺序偏差）。

### 2.1 task1 overclock-protocol — baseline 胜 2-0

| 裁判 | 模型 | winner | 解码 | X总分(skill) | Y总分(baseline) | 罚X | 罚Y | 置信 | 质量增量值得成本 |
|---|---|---|---|---|---|---|---|---|---|
| flash-xy | deepseek-v4-flash | Y | baseline | 65 | 69 | 2 | 0 | 8 | true |
| qwenmax-yx | qwen3.7-max | Y | baseline | 56 | 61 | 0 | 0 | 7 | true |

**flash-xy 关键理由**（5 条 spot-check 全部核实）：baseline 的 Steam 数字与裁判实测完全一致（Wireworks 563、TFWR 9025、Mindustry 27744、Autonauts 522、Backpack Battles 20562），并主动抓出「README 声称 1024 tests vs 实测 1154/96 文件」的文档漂移；skill 臂有 Wireworks "559"（裁判实测 563）与 TFWR "96.6%"（实测 8623/9025=95.5%）两处小误差，且未发现 README 漂移 → 罚 2 分。baseline 的三个测试判据直接引用 `docs/18 §11` 的门槛（80%/70%/60%/<25%），口径可复核；skill 臂自创百分比阈值（≥60% 重试、≥70% 归因）无文档出处。两臂都抓住「组合未被证明」与两对张力，机制理解与反证基本打平。

**qwenmax-yx 关键理由**：Y（baseline）抓出 README 1024→1154 文档漂移、组合张力分析更深（三对冲突）、近邻归因更系统（每个近邻明确"只证明 X，未证明 Y"）、测试判据更量化。注意：qwenmax 自身实测 Wireworks 为 **559**，与 flash 实测 **563** 相左——两个裁判各自抓取时刻不同，各自认为对方数字略偏（详见 §5/§7 的裁判方差）。

**共识**：两臂都给出真实可访问的近邻链接，都认定「没有任何近邻证明整套组合；每个近邻靠另一核心机制/受众/分发取胜」。

### 2.2 task2 worldloom — skill 胜 2-0

| 裁判 | 模型 | winner | 解码 | X总分(baseline) | Y总分(skill) | 罚X | 罚Y | 置信 | 值得成本 |
|---|---|---|---|---|---|---|---|---|---|
| flash-xy | deepseek-v4-flash | Y | skill | 67 | 71 | 0 | 0 | 7 | true |
| qwenmax-yx | qwen3.7-max | Y | skill | 60 | 62 | 0 | 0 | 6 | true |

**flash-xy 关键理由**：skill 臂显式给出"证据等级 2–3 / 1–2"阶梯并标注 inferred/unverified（直接对应任务"每种乐趣独立证据与证据等级"要求）；近邻表逐行写"证明了什么/没证明了什么"，并新增两个真正相关的近邻 Spellmasons（唯一"组合+合作"）与 Cult of the Lamb（"run+持久枢纽"），点出真正竞争威胁是"已被占用的表层品类"；反证阈值带样本量（T1/T2 的 ≥50% / ≥40% / n=8–12）；成本效率差距明显——skill 臂 1.10M token / 269s / 13 次外部操作产出 3743 字符，baseline 臂 3.44M token / 497s / 19 次外部操作产出 3657 字符（约 1/3 token、约 1/2 成本）。两臂均无虚假事实（penalty 0）。baseline 的独特加分：实际编译两种蓝图给出指令流 `[split,emit]` 与 `[emit,on_hit,split,emit]`，Q1 显式三分"实际可玩/仅文档/纯推测"，机制理解与当前状态两维打平。

**qwenmax-yx 关键理由**：skill 臂严格遵守 siftline 优先（13 次 siftline、0 次 webfetch），baseline 臂用 4 次 webfetch 直接抓取且 siftline 仅 7 次——违反任务"优先使用 siftline"要求；skill 臂近邻表结构更清晰、信息密度更高；成本效率显著更优（$0.0085 vs $0.0143，约一半墙钟）。

**分歧点**：baseline 臂"实际编译蓝图做运行时实证"是 skill 臂没有的深度，但两裁判都认为该优势未转化为结论层面的差异，skill 臂以结构+效率胜出。

### 2.3 task3 poiema — 1-1（裁判意见分歧）

| 裁判 | 模型 | winner | 解码 | X总分(skill) | Y总分(baseline) | 罚X | 罚Y | 置信 | 值得成本 |
|---|---|---|---|---|---|---|---|---|---|
| flash-xy | deepseek-v4-flash | Y | baseline | 56 | 64 | 3 | 0 | 7 | true |
| qwenmax-yx | qwen3.7-max | X | skill | 65 | 59 | 0 | 0 | 7 | true |

**flash-xy → baseline（罚 skill 3 分）**：skill 臂有两处可复核的事实错误——声称「README 声称 1071/120」并断言「IMPLEMENTATION-STATUS 最后更新 2026-08-09 落后一个增量」；裁判实测 README 为「1001 通过 / 0 失败、E2E 116/116」，IMPLEMENTATION-STATUS 为「Last updated: 2026-08-10」且其顶部里程碑（系统通知）已是当前树 1102/1101/0fail、e2e 124/124——"1071/120"实为该文件 08-09 历史里程碑的数字，skill 臂归属与日期均错。skill 臂还自相矛盾：矩阵判「成本簇 5/7（含 N39=implemented）」、判「N1-N10 10/10、长任务 8/8 全 implemented」，但其 §5 又自认"成本仅 token 估算非真实计费"、"跨设备偏好不同步"。baseline 臂在 README/STATUS 归属上正确、成本与 N4 判定更贴合代码，但误标 N45（本地模型实为 planned 却判 implemented）、外部检索 20 次明显超限且未自报。

**qwenmax-yx → skill**：skill 臂明确拒绝合并单一覆盖率数字（"两个分母不可合并"），方法论更诚实；验证更具体可执行（文件落点 5–8 人/10 秒判据、非开发者 10 人全程测试）；信息密度更高（4617 vs 5791 字符）；外部搜索预算更守（12 vs 20 次）。baseline 臂给出 73%/25%/2% 的百分比估算，有"精确假覆盖率"风险（注：baseline 原文其实已自警"此比例……非产品承诺的覆盖率"，两裁判对这句话的加权不同）。

**本次复核（只读，poiema README/IMPLEMENTATION-STATUS）**：README 第 77 行实为「npm test 1001 通过 / 0 失败」→ flash/baseline 对、skill 臂的"1071/120"归属错误成立；IMPLEMENTATION-STATUS 首行「Last updated: 2026-08-10」且当前里程碑记 1102/1101/0fail、e2e 124/124（其内嵌的 08-09 历史里程碑确为 1071/120）→ flash/baseline 对、skill 臂"08-09 落后"判断错误。两臂共同正确的关键事实（裁判均 spot-check 通过）：`npm test` ≈1102、e2e 124/124、`check`/`audit` 0 漏洞、daemon 无 delete/clear/export-all 端点、无 `globalShortcut`、handshake `poiema.local/v1alpha1` + 13 capabilities + schema v14、needs-radar 49/49、56 条分母（N1–N56）与 DESIGN 20 族盲区。

**判读**：1-1 不是"一臂明显更好"，而是**对同一组事实，两个裁判给了不同权重**——flash 更看重可复核的事实归属与矩阵内部自洽（skill 臂确实有错）；qwenmax 更看重方法论诚实（拒绝合并分母）、信息密度与预算纪律（baseline 臂确实超限更多）。两者引用的都是真实观察，分歧在于"哪种错误更致命"。

---

## 3. 效率与篇幅对比

### 3.1 逐臂（`output/generated/*/meta.json`）

| 任务/臂 | 条件 | tokens | cost USD | 墙钟 s | 正文 字符 | steps | bash/read/webfetch | siftline | ext_ops |
|---|---|---|---|---|---|---|---|---|---|
| task1/baseline | baseline | 912,056 | 0.0100 | 368.4 | 5007 | 19 | 15/12/7 | 3 | 10 |
| task1/skill | skill | 1,205,476 | 0.0097 | 307.3 | 3532 | 21 | 19/9/4 | 12 | 16 |
| task2/baseline | baseline | 3,441,696 | 0.0143 | 496.7 | 3657 | 44 | 40/25/4 | 7 | 19 |
| task2/skill | skill | 1,097,616 | 0.0085 | 269.3 | 3743 | 22 | 23/12/0 | 13 | 13 |
| task3/baseline | baseline | 3,655,690 | 0.0138 | 1120.1 | 5791 | 64 | 66/14/1 | 11 | 20 |
| task3/skill | skill | 1,984,778 | 0.0114 | 712.0 | 4617 | 32 | 38/12/0 | 8 | 12 |

### 3.2 合计（skill vs baseline）

| 指标 | skill（3 臂） | baseline（3 臂） | 差值 |
|---|---|---|---|
| tokens | 4,287,870 | 8,009,442 | **−46%** |
| cost USD | 0.0296 | 0.0381 | **−22%** |
| 墙钟 s | 1,289 | 1,985 | **−35%** |
| 外部操作 ext_ops | 41 | 49 | −16% |
| siftline 调用 | 33 | 21 | skill +57% |
| 正文字符 | 11,892 | 14,455 | −18% |

**要点**：**仅成本与墙钟时间是 3/3 同方向（skill 更低）**；tokens、ext_ops、正文字符等其余指标是**合计**优势（tokens −46%、ext_ops −16%、字符 −18%），其中 task1/overclock 的 skill 臂 token 1,205,476 > baseline 912,056、ext_ops 16 > 10，task2 的 skill 臂正文 3743 略长于 baseline 3657——**合计优势不代表逐任务一致**。skill 臂用 siftline 更多、用手工 webfetch 更少（task2/task3 的 skill 臂 webfetch=0），与 Skill 的"平台路由/结构化传感器"指令直接对应。**但 6 臂全部超出任务"外部搜索/抓取≤8 次"上限**（10/16/19/13/20/12），预算纪律是共同弱点，仅 task3/skill 自报"8 次"（其 siftline 计数恰为 8，但启发式 ext_ops=12）。

### 3.3 裁判会话成本（`output/judged/*/meta.json`）

| 任务/裁判 | 模型 | cost USD | tokens | 墙钟 s | 正文字符 | 工具 |
|---|---|---|---|---|---|---|
| task1/flash-xy | deepseek-v4-flash | 0.0042 | 222,436 | 182 | 2734 | bash7/webfetch7 |
| task1/qwenmax-yx | qwen3.7-max | 0.1006 | 56,839 | 69 | 1535 | bash2/webfetch1 |
| task2/flash-xy | deepseek-v4-flash | 0.0084 | 961,915 | 312 | 3996 | bash37/read4/webfetch3 |
| task2/qwenmax-yx | qwen3.7-max | 0.1375 | 52,171 | 78 | 2159 | webfetch4 |
| task3/flash-xy | deepseek-v4-flash | 0.0077 | 714,484 | 549 | 4121 | bash31 |
| task3/qwenmax-yx | qwen3.7-max | 0.1013 | 58,039 | 178 | 1506 | bash6 |

裁判合计 ≈ $0.360，生成合计 ≈ $0.068，**本轮评测总成本 ≈ $0.43**。本次 6 次裁判会话中，每个 qwen3.7-max 会话的总成本分别约为对应 flash 会话的 **13–24 倍**（task1 0.1006/0.0042≈24、task2 0.1375/0.0084≈16、task3 0.1013/0.0077≈13）。注意两者 token 口径与模型计费不同（qwen 会话 token 远少于 flash 会话却更贵），**据此只能说明本轮各会话的实际账单对比，不能推断两模型的一般单价比例**。

---

## 4. Skill 真正改善/恶化的维度

按 6 次裁判打分（每臂每维 6 分：3 任务 × 2 裁判）求平均，skill − baseline：

| 维度 | skill 均分 | baseline 均分 | 差 (skill−baseline) |
|---|---|---|---|
| task_fidelity 任务忠实 | 8.33 | 8.83 | **−0.50** |
| current_state_accuracy 当前状态准确 | 7.50 | 8.50 | **−1.00** |
| mechanism_understanding 机制理解 | 8.17 | 8.33 | −0.17 |
| relation_platform_search 关系/平台搜索 | 7.67 | 7.17 | **+0.50** |
| demand_pain_evidence 需求/痛点证据校准 | 7.67 | 8.33 | **−0.67** |
| counterevidence_boundary 反证边界 | 8.17 | 8.17 | 0.00 |
| action_value 行动价值 | 8.17 | 8.00 | +0.17 |
| cost_length_efficiency 成本/篇幅效率 | 7.83 | 6.33 | **+1.50** |

**Skill 一致改善的维度**：
- **成本/篇幅效率（+1.50，最大）**——与 §3 的 3/3 客观效率数据互相印证，不是单次偶然。
- **关系/平台搜索（+0.50）**——task2 的近邻"证 X 未证 Y"表与真实链接、task3 skill 臂的矩阵外证列有真实 URL（baseline task3 该维仅 6/6，外部证据列多为"—"）。这与 Skill references 的平台路由/真链接纪律一致。

**Skill 未改善甚至略降的维度**：
- **当前状态准确（−1.00）**——由 task1（README 漂移未抓出 + 两处数字误差）与 task3（README/IMPLEMENTATION-STATUS 归属错误）的 skill 臂失误驱动；task2 两臂打平。**不是跨任务普遍规律，而是"事实核验环节 Skill 没能兜底"。**
- **需求/痛点证据校准（−0.67）**——由 task1（baseline 用文档门槛、skill 自创阈值）与 task3 flash（baseline 痛点粒度更贴代码）驱动。
- **任务忠实（−0.50）**——task2 baseline 的 Q1 三分与蓝图实证得 flash 10 分、task3 flash 因事实错误连坐任务忠实。

**必须声明**：以上维度差都在 0–1.5 分区间、样本 6 分/臂/维、两裁判量纲不同（flash 打分 6–10 更宽、qwenmax 7–8 更平），且盲化不完美（见 §7）。**不得把任一维度的差值当作普遍规律**；唯一能称"跨任务一致"的是效率/成本维度与"skill 更多用 siftline"的行为差异。

---

## 5. Schema 与映射核查（不猜字段）

- **mapping.json ↔ 代码**：task1 X=skill/Y=baseline、task2 X=baseline/Y=skill、task3 X=skill/Y=baseline，与 `run_ab.py` 中 `MAPPING` 及 `output/summary.json` 的 `winner_condition` 解码一致。
- **result.json 字段**（6 份全部）：`task_id/judge_id/model/arm_order/scores/penalty/totals/winner/confidence/reasons/winner_biggest_defect/quality_increment_worth_cost/spot_checks`，与 `rubric.md` 规定的 schema 完全一致；`scores` 恒含 rubric 定义的 8 个维度、`winner ∈ {X,Y}`、`confidence ∈ 0..10`、`reasons ≥ 4` 条（实测 4–6 条）、`penalty` 0 或 2/3（仅 task1/skill 与 task3/skill 被罚）、`quality_increment_worth_cost` 均为布尔。
- **数学一致性**：`totals[arm] == Σ(scores[arm]) − penalty[arm]` 在 **5/6** 份成立；**task1/qwenmax-yx 不一致**——其 X 写 56（Σ=57−0）、Y 写 61（Σ=63−0），各差 1 与 2 分。**两种口径下 winner 都是 Y（baseline）**（61>56 且 63>57），故不影响胜负，但该裁判的自报总分存在算术误差，`summary.json` 沿用了其自报值。
- **罚分分布**：仅 flash 两位判罚过（task1 skill −2、task3 skill −3），均为其 spot-check 复验过的具体数字/归属错误；qwenmax 全部 0 罚。

---

## 6. 下一版 Skill 的改进优先级

1. **P0 — 把"点用核实"从规则变成强制动作**。本轮两处最重的罚分都源于 skill 臂**未逐字核对文档快照**（task1 的 README 1024→1154 漂移没抓出；task3 把 IMPLEMENTATION-STATUS 的 08-09 历史里程碑"1071/120"错记成 README 声称、并误判其日期落后）。建议：SKILL.md 增加一条硬性检查——凡引用 README/STATUS/文档里的数字，必须 `rg` 出文件原文再对照实测，并在报告中给出"原文引文 + 实测值 + 归属文件"三列。
2. **P1 — 搜索预算的运行时守约，而不是只写在文档里**。6 臂全部超"≤8 次"上限且多数未自报。建议：Skill 提供运行中查询计数，超限前停；报告必须自报"实际外部操作次数 + 是否超限"（task3/skill 自报"8 次"但启发式 ext_ops=12，说明自报与测量口径要统一）。
3. **P2 — 禁止自造判据阈值**。task1 skill 自创 ≥60%/≥70% 无出处被点名为"自造数字"。建议：任何量化判据必须引用项目内权威来源（如 docs/18 §11），否则标注"建议值，非判据"。
4. **P3 — 数字类证据去时间化表述**。Wireworks 559 vs 563 之争说明 Steam 等移动计数在抓取间漂移。建议：计数证据统一写 `约 N（检索日 YYYY-MM-DD，端点 X）`。
5. **P4 — 固化并保留已验证的强项**：siftline 优先路由、证据等级阶梯（2–3/1–2 的写法）、近邻"证 X 未证 Y"表、拒绝合并分母、coverage boundary 段落——这五样在本轮直接转化为 task2 的胜利与 task3 qwenmax 的高分，值得提炼进 references 作为默认模板。

---

## 7. 统计局限与 provider 挂起/重跑（口径）

**统计局限**：
- **N=3 任务 × 2 裁判 = 6 次配对判定**（每次判定同时覆盖两个臂，涉及 12 个臂评分）；**不是 12 次独立判定**。无法做显著性检验；结果只用于发现方向性差异。
- 两位裁判模型不同、打分量纲不同（flash 6–10、qwenmax 7–8），跨裁判平均混入了量纲差；同一裁判内两臂可比（配对设计，臂序已反序抵消）。
- **盲化不完美**：裁判收到的匿名臂元数据含 siftline 调用数、成本、字符数，足以反推条件（qwenmax 在 task2 明说"Y 严格遵守 siftline 优先"即据此推断），存在锚定风险。
- **裁判方差真实存在**：task3 1-1 且双方引用同一组事实给出相反评价（flash 罚 skill 的归属错误、qwenmax 赞 skill 的分母诚实）；task1 两裁判对 Wireworks 计数各自实测 563 / 559 并各自认为对方数字略偏——在移动指标上做"决定性虚假事实罚分"本身脆弱，且结果随抓取时刻漂移。
- **一次数学误差**：task1/qwenmax-yx 的 `totals` 与其 `scores` 之和不一致（差 1–2 分），winner 不受影响（见 §5）。

**provider 挂起与重跑**（口径限制：当前产物只能复核"成功重跑后"的状态）：
- **当前产物可复核的**：`task1/skill` 为重跑后的成功 run——`SUCCESS` 存在、`timed_out=false`、`timeout_seconds=1200`；6 份 judge `meta.json` 均为 `timeout_seconds: 1200`、`timed_out: false`；6 份生成臂中仅 task1/skill 带 `timeout_seconds`（其余 5 臂在超时功能上线前运行，无该字段）。`raw.jsonl` 相邻事件最大间隔达 **53–142 秒**（task3 两臂 >2 分钟；task3/baseline 全流程 1120s 墙钟），显示 provider 响应慢/卡顿，但最终 12 次 run 全部完成、stderr.log 全空、无残留失败产物。
- **不可从当前产物复核的**：失败产物已被成功重跑覆盖，因此"首次运行挂起/手动终止"只能作为**运行过程观察**记录，不能声称当前产物能验证该事件（例如无法复核首次失败的具体原因、当时是否超时或手动终止）。超时后不写 SUCCESS、保留 partial 输出的机制保证重跑不产生伪造产物，但该机制只约束重跑后的状态。

---

## 8. 附录：只读校验结果（本文件写入后执行）

校验内容：6 个 generation SUCCESS、6 个 judge SUCCESS、6 个 result.json 可解析、totals 数学一致。

```
generation SUCCESS 6/6   |   judge SUCCESS 6/6   |   result.json parseable 6/6
result.json schema: 5/6 完全一致（totals = Σscores − penalty）；1/6（task1/qwenmax-yx）
  totals 与 scores 之和差 1–2 分，winner 在两种口径下均不变。
```
