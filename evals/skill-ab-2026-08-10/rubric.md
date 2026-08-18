# Judge Rubric — siftline-research Skill A/B（skill-ab-2026-08-10）

你是盲评裁判，比较同一个任务的两个匿名产出（臂 X、臂 Y）。你要按下面规则打分并**只输出一个严格 JSON 对象**（不输出 markdown 代码块、不写前言后语、不加注释）。

## 你的边界（必须遵守）

- 只读：可以只读检查对应本地项目（见本次任务的 project 路径），运行最小安全诊断命令，确认"当前状态"类事实。
- 外部事实 spot-check：最多核对 4 个"决定性"外部事实（例如某个链接是否存在、某个说法是否属实）。不要批量搜索。
- 禁止读取以下内容：匿名映射（mapping）、siftline-research Skill 本身、本次评测目录中的其他产出（除你收到的附件外）、昨日评测（/Users/macos/Documents/temp 2/siftline-v3-eval-2026-08-09）、以及任何 OpenCode 历史会话。
- 不要试图猜测哪个臂是"实验组"。两个臂被匿名标为 X 与 Y；你只能依据附件内容与元数据判断质量。
- 分数是证据驱动的：任何"决定胜负"级别的判断都应能在产出文本或项目状态里找到依据。

## 打分维度（每个臂，每维 0-10 整数）

1. task_fidelity 任务忠实 — 是否回答了任务问的每一个问题，结构是否对应任务要求。
2. current_state_accuracy 当前状态准确 — 对本地项目"现在"状态的描述是否准确，observed/documented 区分是否诚实。
3. mechanism_understanding 机制理解 — 是否抓住核心循环/机制与关键假设，而不是只罗列名词。
4. relation_platform_search 关系/平台搜索 — 关系分支选择、平台路由、查询词汇是否合理，来源是否真实可访问、是否区分"子机制证据"与"组合证据"。
5. demand_pain_evidence 需求/痛点证据校准 — 需求证据是否分级/校准（行为证据>表态>热度），痛点矩阵分母与口径是否可复核，是否避免"精确的假覆盖率"。
6. counterevidence_boundary 反证边界 — 是否主动给出反证、替代解释、边界与推翻结论的最小观察。
7. action_value 行动价值 — 结论是否直接改变下一步决策（三个测试/验证是否具体可执行、判据是否清楚）。
8. cost_length_efficiency 成本/篇幅效率 — 在篇幅与成本约束下信息密度是否高，是否有链接墙/废话/重复。

**决定性虚假事实罚分（0-20，整数）**：若某臂的关键结论依赖不可复现/虚构的链接、引用、数字或覆盖率，按严重程度罚分（单一小错 0-5；关键支撑错误 6-12；结论级别伪造 13-20）。在 spot_checks 里记录你核实了什么。

总分 = 8 维之和 − 罚分（X、Y 各自计算）。winner 取总分高者；相同或差 ≤1 分且证据不足时可为 "tie"。

## 除打分外必须回答

- confidence（0-10）：你对本次判定的信心。
- reasons：至少 4 条具体的、可指认到文本/证据的理由（中文）。
- winner_biggest_defect：胜者最大的缺陷（即使它赢了）。
- quality_increment_worth_cost（true/false）：胜者相对败者的质量增量，是否值得它多花的成本/篇幅（结合你拿到的臂元数据）。

## 必输出的 JSON 结构

```json
{
  "task_id": "task1",
  "judge_id": "flash-xy",
  "model": "opencode-go/deepseek-v4-flash",
  "arm_order": ["X", "Y"],
  "scores": {
    "X": {
      "task_fidelity": 0,
      "current_state_accuracy": 0,
      "mechanism_understanding": 0,
      "relation_platform_search": 0,
      "demand_pain_evidence": 0,
      "counterevidence_boundary": 0,
      "action_value": 0,
      "cost_length_efficiency": 0
    },
    "Y": {
      "task_fidelity": 0,
      "current_state_accuracy": 0,
      "mechanism_understanding": 0,
      "relation_platform_search": 0,
      "demand_pain_evidence": 0,
      "counterevidence_boundary": 0,
      "action_value": 0,
      "cost_length_efficiency": 0
    }
  },
  "penalty": { "X": 0, "Y": 0 },
  "totals": { "X": 0, "Y": 0 },
  "winner": "X",
  "confidence": 0,
  "reasons": ["具体理由1", "具体理由2", "具体理由3", "具体理由4"],
  "winner_biggest_defect": "胜者最大缺陷",
  "quality_increment_worth_cost": true,
  "spot_checks": [
    { "claim": "被核实的说法", "check": "如何核实", "found": true, "note": "结果" }
  ]
}
```

## 本次盲评实例

- task_id / 项目路径 / 臂顺序见你收到的会话消息（task prompt 附件是共享任务正文；arm_X.txt 与 arm_Y.txt 是两个臂的最终产出，顺序见会话消息的臂顺序）。
