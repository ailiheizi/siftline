# skill-ab-2026-08-10 — siftline-research Skill A/B 评测

可复现的 A/B 评测套件：三个只读研究任务，每个任务两条臂，唯一研究变量是
是否使用 `siftline-research` Skill（baseline 完全不附加、不提及该 Skill；
skill 臂在相同任务正文前只增加 `Use $siftline-research from ...` 一句，并
用 `-f` 附加 `SKILL.md` 与四份 references）。所有 session 都通过本机
`opencode run` 运行，**不修改 `src/`、`tests/`、`skills/` 或任何被检查项目**。

## 方法

1. **生成阶段**（`generate`）：每个任务 × 每条臂一个 fresh opencode session。
   - 全部使用 `--pure --auto --format json`，默认模型 `opencode-go/deepseek-v4-flash`，
     不传 `--continue/--session/--fork`（保证 fresh）。`--pure` 关闭全局
     plugin/Skill/config，确保 baseline 臂不被全局配置污染。
   - 每个 session 运行在 `tempfile.mkdtemp()` 的**中性 cwd**（`--dir`），避免
     项目上下文/配置/已加载 Skill 影响结果。
   - 每个任务的 baseline 与 skill 两臂**相邻**调度；默认 `jobs=2`，避免 provider 过载。
   - 每个 opencode 子进程有可配置超时（`--timeout`，默认 3600 秒；`0` 关闭）。
     超时后优雅终止（SIGTERM→SIGKILL），已到达的原始输出照常写入
     `raw.jsonl`/`stderr.log`，该 run 标记为 failed 且**不写 SUCCESS**，避免
     provider 无限挂起。
   - 保存到 `output/generated/<task>/<condition>/`：`prompt.txt`（实际发送的提示）、
     `attachments/`（skill 条件所附文件副本）、`raw.jsonl`（opencode 原始事件流）、
     `assistant.txt`、`stderr.log`、`meta.json`（session id、wall time、每步
     tokens/cost、合计、tool counts、siftline 调用数、外部操作数、exit code、
     timed_out）。
   - **`assistant.txt` 只取最后一个 `reason=stop` 的 `step_finish.messageID` 对应
     的 text events**（按事件顺序拼接）；中间穿插在 tool 调用前后的进度叙述一律
     排除。没有最终 stop 的 run 没有 assistant 正文。
2. **裁判阶段**（`judge`）：每个任务两次盲评，两次都是 fresh session。
   - 模型各一：fresh DeepSeek V4 Flash（`opencode-go/deepseek-v4-flash`，臂序 X→Y）
     与 Qwen 3.7 Max（`opencode-go/qwen3.7-max`，臂序 Y→X 反序），抵消顺序偏差。
   - 臂以匿名 X/Y 呈现（见 `mapping.json`，此文件**不传给裁判**）。
   - 裁判附件 = 共享任务正文 + 两臂最终产出（按各自顺序）+ 匿名臂元数据。
   - 裁判可只读检查对应本地项目，最多 spot-check 4 个决定性外部事实；**禁止读取**
     映射、Skill、本评测其他产出、昨日评测或 OpenCode 历史。
   - 按 8 个 0-10 维度打分 + 决定性虚假事实罚 0-20，输出严格 JSON
     （每臂分项、罚分、总分、winner、confidence、≥4 条理由、胜者最大缺陷、
     质量增量是否值得成本、spot_checks）。存到 `output/judged/<task>/<judge_id>/`。
3. **汇总阶段**（`summary`）：自动聚合 `summary.json` / `summary.md`，
   **只做结构化聚合，不替代最终人工解释**。
4. **重处理阶段**（`reprocess`，可选维护操作）：不重跑模型，从已存在的
   `output/generated/<task>/<condition>/raw.jsonl` 重新按上面的规则提取
   `assistant.txt`，并同步修正 `meta.json` 的 `assistant_chars` 与解析出的统计字段
   （session id、wall time、totals、steps、tool_counts、siftline_calls、
   external_ops、n_events、`assistant_stop_message_id`）。失败的 run（`status !=
   success`）或 raw 里没有最终 `stop` 的 run **安全跳过并明确报告，绝不伪造
   SUCCESS**——若之前误写了 SUCCESS 会被移除，之后 `generate` 会重跑该 run。

匿名映射（skill = X/Y 交替，裁判不知情）：

| 任务 | X | Y |
| --- | --- | --- |
| task1 overclock | skill | baseline |
| task2 worldloom | baseline | skill |
| task3 poiema | skill | baseline |

## 布局

```
evals/skill-ab-2026-08-10/
├── run_ab.py            # 主脚本：generate / judge / reprocess / all / summary
├── rubric.md            # 裁判评分标准 + 必输出 JSON schema
├── mapping.json         # 匿名臂映射（单独保存，不传给裁判）
├── tasks/               # 三个共享任务正文（baseline/skill 共用）
├── tests/               # 最小单测（假 opencode JSONL fixture，不调真实模型）
└── output/              # 运行产物（脚本生成）
    ├── manifest.json
    ├── summary.json / summary.md
    ├── generated/<task>/<condition>/{prompt,raw.jsonl,assistant.txt,meta.json,SUCCESS,...}
    └── judged/<task>/<judge_id>/{...}
```

## 前置条件

- Python 3.11+（脚本只用标准库；仓库 `.venv` 自带 3.13 亦可运行）。
- 本机 `opencode` ≥ 1.18（脚本启动时校验版本）。
- `siftline` CLI 已在 PATH（`which siftline`）；GitHub 走 `gh` 登录态，Hacker News
  无需密钥。Exa/Tavily/web 取决于环境是否有对应 API key（`siftline doctor` 可查）——
  Skill 会如实报告不可用平台，这不影响评测。
- 三个被检查项目存在：`/Users/macos/Documents/game/overclock-protocol`、
  `/Users/macos/Documents/game/worldloom`、`/Users/macos/Documents/other_project/poiema`。

## 运行命令

在仓库根目录（任意 cwd 均可）：

```bash
# 生成：6 个 session（3 任务 × 2 臂，两臂相邻，jobs=2）
.venv/bin/python evals/skill-ab-2026-08-10/run_ab.py generate

# 只跑部分任务 / 单条件；调整超时（秒，0=关闭）
.venv/bin/python evals/skill-ab-2026-08-10/run_ab.py generate --tasks 1 3 --only skill --timeout 900

# 裁判：6 次盲评（3 任务 × 2 模型/臂序）
.venv/bin/python evals/skill-ab-2026-08-10/run_ab.py judge

# 一条命令跑完
.venv/bin/python evals/skill-ab-2026-08-10/run_ab.py all

# 不重跑模型，从已有 raw.jsonl 重新提取 assistant.txt 并修正 meta.json
.venv/bin/python evals/skill-ab-2026-08-10/run_ab.py reprocess

# 只汇总（不跑任何 session）
.venv/bin/python evals/skill-ab-2026-08-10/run_ab.py summary

# 计划模式（只打印会跑什么，不调用模型）
.venv/bin/python evals/skill-ab-2026-08-10/run_ab.py generate --dry-run
```

通用参数：`--tasks 1 2 3`、`--jobs N`（默认 2）、`--force`（忽略 SUCCESS 重跑）、
`--dry-run`、`--opencode <path>`；`generate`/`judge`/`all` 另有 `--timeout`（默认
3600 秒）。生成模型可用 `--model` 覆盖（默认 `opencode-go/deepseek-v4-flash`）；
裁判模型固定在 `JUDGES` 表内不可覆盖。

## 污染控制

- **昨日评测隔离**：`run_ab.py` 内置 `FORBIDDEN_DIRS`（`/Users/macos/Documents/temp
  2/siftline-v3-eval-2026-08-09`），所有附件与 session cwd 在提交前经
  `guard_no_forbidden()` 校验，落在该目录下的任何输入都会直接报错，绝不进入生成或
  裁判会话。任务提示也明确要求模型不读取该目录。
- **裁判盲化**：裁判只收到匿名 X/Y 产出与共享任务正文；`mapping.json` 单独保存，
  不在裁判附件内；裁判提示明令禁止读取映射、Skill、本评测其他产出、昨日评测与
  OpenCode 历史。X→Y 与 Y→X 两种臂序各由不同模型执行，抵消顺序偏差。
- **中性 cwd**：每个 session 都在独立 `tempfile` 目录内启动，不带入 siftline 仓库
  的配置/Skill 注册。
- **`--pure`**：所有生成与裁判会话统一加 `--pure`，关闭全局 plugin/Skill/config，
  与中性 cwd 配合，保证 baseline 臂与 skill 臂都在相同的纯净运行时里跑，唯一差异
  仍只是提示词与附件（skill 条件）。
- 裁判可只读检查本地项目并 spot-check ≤4 个决定性外部事实（在 `spot_checks` 里记录）。

## 可中断与续跑

- 每个 run 写完 `raw.jsonl`、`assistant.txt`、`meta.json` 后才写 `SUCCESS` 标记。
- 默认跳过已有 `SUCCESS` 的 run；Ctrl-C 会终止当前正在运行的 session（已写部分保留为
  不完整状态），重跑同一命令即可续跑。`--force` 强制重跑。
- 中途失败（`exit_code != 0`）或**超时**不会写 `SUCCESS`，可重跑；原始输出保留在
  `raw.jsonl`，stderr 在 `stderr.log`，`meta.json` 记录 `timed_out: true`。
- `reprocess` 不重跑模型；对失败或没有最终 `stop` 的 run 会移除可能存在的 SUCCESS
  并明确报告，之后 `generate` 会重跑它们。

## 限制与说明

- **统计力量**：每任务每裁判只有一次判定，N=3 任务 × 2 模型；结果用于发现方向性差异，
  不是显著性检验。
- **盲化并非完美**：匿名臂元数据（成本、siftline 调用数等）可能让裁判推断出哪个臂用了
  Skill；这是对比可测量产出的固有代价，已通过"先产出后标注"的方式尽量降低。
- **assistant 提取**：只取最后一个 `reason=stop` 消息的 text events；若模型输出的最终
  正文横跨多个事件仍会完整拼接，但前置的进度叙述不会混入 `assistant.txt`。没有最终
  stop 的 run 视为不可提取（`reprocess` 跳过并移除 SUCCESS）。
- **外部操作计数是启发式**：`external_ops` 统计 `webfetch` 工具调用与 bash 命令中出现
  `siftline|curl|wget|gh api|webfetch` 的次数，不是 provider 侧精确计数。
- **裁判 JSON 解析**：模型偶尔带 markdown 围栏输出，脚本用 `extract_json_object()`
  提取首个 `{...}`；无法解析时 `answer_parsed=false`，`summary` 会把该裁判标为不可用。
- **Provider 可用性**：GitHub/HN 无密钥依赖；若生成环境缺 Exa/Tavily/web 密钥，Skill
  会报告平台不可用，研究只能走可用的渠道。
- **`summary` 只做聚合**：自动生成的胜负计数仅为展示，最终解释必须由人工结合
  `output/judged` 的 reasons/spot_checks、`output/generated` 的原始正文与成本记录给出。

## 测试与 lint

```bash
# 最小单测（假 JSONL fixture，不调用真实模型）
.venv/bin/python -m pytest evals/skill-ab-2026-08-10/tests/ -q

# ruff 仅检查本评测 Python
.venv/bin/ruff check evals/skill-ab-2026-08-10/
```
