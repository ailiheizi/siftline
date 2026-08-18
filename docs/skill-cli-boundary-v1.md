# Skill/CLI 边界收敛规范 v1

> 架构收敛文档，可直接实施。本文只定义架构与契约，不修改任何 Skill、CLI、evaluator 或 README。标题沿用“CLI envelope”，正文区分 **CLI core**（传感器产出并哈希）与 **orchestrator wrapper**（外层包入 run 级状态）。

## 0. 决策（先裁决）

1. **禁止继续 v4 文本堆叠。** 冻结 A/B 数据（evals/micro-ab-2026-08-11/lean-v3-runs/RESULTS.md）显示：lean-v3 28/40，低于 baseline 31/40（-3）。剩余失败全部是散文多次未能强制执行的确定性控制（工具数、raw 序列化、长度、锚点路由、taxonomy 保持），再加一段 SKILL.md 只是重复同样无效干预。
2. **不推广、不安装 v3。** v3 成本 0.958×、非缓存 token 0.926×（达标），但墙钟 1.272× 且质量回退；只有成本达标不能通过门禁。
3. **把确定性控制移到 CLI / 外层 orchestrator 硬执行；Skill 只保留高自由度启发式语义。** 这是本文唯一允许的路线。
4. **v3 关键失败以数据为准**：M1 7>6 tools 且 fenced JSON；M4 8>7 tools、2568>1600 chars、fenced JSON、P4 planned 被错判 absent、只命中 2/8 冻结锚点。这些失败点逐一映射到第 2、3、5、9、10 节的硬执行项。

## 1. 分层与术语

| 层 | 职责 | 状态 |
| --- | --- | --- |
| Skill（siftline-research） | 高自由度启发式语义：决策、判断、停止 | 现有，只做语义，不做运行时控制 |
| CLI（siftline） | 单次传感器调用：一次请求 → 一个 hashed sensor core | 现有，扩展到 sensor core + 哈希 |
| orchestrator（外层，新建） | run 生命周期：wrapper、预算、freeze、并发、校验、强制交付、终态 | 待建，本规范的落地主体 |

- **invocation（调用）**：CLI 一次进程执行，对应一条最小请求与一个 sensor core。
- **run（运行）**：一个研究任务从 seed 到交付的完整生命周期，由一个 orchestrator 驱动，含多次 invocation。
- **claim_id**：一个原子研究声明的稳定标识（由 Skill 生成或 orchestrator 登记）。
- **quote_id**：在已验证 item 内容内定位到一段引文的标识，由 orchestrator evidence registry 生成。

## 2. Skill 职责（高自由度启发式语义，仅此范围）

Skill 负责**不可由确定性机器强制、且需要判断自由度**的部分：

- seed fingerprint（机制抽取、假设、生成性洞察）；
- relation routing（分支选择、平台路由、查询词汇）；
- evidence ladder（需求证据分级、observed/documented/inferred/unverified 判定、counterevidence）；
- stop / reversal judgment（何时停下、什么最小观察会反转结论）。

状态标签限定：`code-verified` 只是 `observed` 的**来源/范围限定**（证据来自直接读源码或跑聚焦命令），不是可被模糊化的新增主状态。主状态仅四个：`observed` / `documented` / `inferred` / `unverified`；`code-verified` 必须伴随其一（如 `observed(code-verified, scope=...)`），不得单独使用，否则视为 `unverified`。

Skill **不负责**（本规范把这些明确移出 Skill 语义范围）：

- 可靠计数与预算（调用数、provider 调用数、预算余量）——预算唯一真源是 orchestrator run journal 注入的 budget_snapshot；Skill 不自行计数、不自报预算；
- 哈希与证据登记——item_fingerprint/content_sha256 由 CLI 产生，quote_id 由 orchestrator evidence registry 生成，Skill 只能引用；
- 序列化（raw JSON、长度上限、schema 校验）——由 CLI/orchestrator 硬执行；
- 进程控制（freeze、timeout、并发上限、强制交付）——由 orchestrator 硬执行。

## 3. 所有权：CLI 产生 core，orchestrator 包 wrapper

- **CLI 产生并哈希 sensor core**：`request`、`items`、`errors`、`provenance`、`cache`、`invocation_outcome`。core 内所有哈希（request/item/content/core_sha256）均由 CLI 按第 5 节产生。
- **orchestrator 校验 core 后包入 wrapper**：`run_id`、`branch_id`、`invocation_id`（request 只能可选回显，binding 以 wrapper 为权威）、可信 `budget_snapshot`、`journal` refs、`terminal`。
- **Skill 不能提交预算**：最小协议提交不含任何预算字段。
- **budget_snapshot 不得由 CLI 或 Skill 自报**：其 `source` 恒为 `orchestrator_run_journal`；CLI 不写预算、不写 wrapper 字段，只产生 core。
- 序列化边界：CLI stdout 只输出 sensor core JSON；orchestrator 校验后输出完整 wrapper envelope。两者都必须是单一 raw JSON（无 fence/前后缀）；禁止 CLI 读取 run 级状态文件。

## 4. 契约命名与迁移（不与 Result.schema_version 冲突）

- 新外层契约显式定名：`contract.id = "siftline.sensor-envelope"`、`contract.version = "1"`（合称 `siftline.sensor-envelope/1`）。
- **不重命名、不挪用当前 `Result.schema_version="1"`**。新旧是两个不同命名空间：旧结构是 sensor result，新结构是 sensor-envelope；不存在从 v1“升级”为别的版本号的静默迁移。
- 迁移期：envelope 可在 `payload.legacy` 字段中**明确保留当前 Result v1 对象**（原样嵌入，供旧消费者兼容），但该字段不参与 core 哈希、不被 orchestrator 当作验证依据。旧消费者读到的是 legacy result；新消费者只认 `siftline.sensor-envelope/1`。
- 实现顺序：CLI 先加 `--contract sensor-envelope` 开关（默认仍输出旧 Result v1）→ orchestrator 只消费 sensor-envelope/1 → 全量切换后 `payload.legacy` 可移除，旧输出由兼容层显式标记 deprecated。

## 5. 哈希规范（CLI core 产生，orchestrator 重算验证）

**canonical 序列化（跨语言）**：RFC 8785 JCS（JCS = JSON Canonicalization Scheme：键按字典序、统一字符串转义、统一数字表示、无空白）+ UTF-8；**所有字符串先做 NFC 归一化**。禁止使用 Python 私有 `json.dumps` 行为作为规范。`null` 字段在 canonical 对象中省略。

- **request_fingerprint** = SHA-256(UTF-8(JCS({provider, operation, query, params})))。
  - `params` 必须是 CLI 应用默认后的**完整规范化参数集**：`limit` 归一化进 params（不单列）；`github tree` 的 branch/recursive、`hn search` 的 tags、`web search` 的 limit 等全部 provider 请求语义都含入。
  - cache_key 可由 request_fingerprint 派生，但**相同 request_fingerprint 不保证 cache hit**：命中还要求 cache 启用、TTL 有效、cache policy 相同（错误永不缓存）。
- **canonical item_fingerprint**（跨 operation 稳定，**不包含 operation**）：
  - 对象 = {namespace: provider, canonicalization_version: "item-1", identity_kind, identity_value}，item_fingerprint = SHA-256(UTF-8(JCS(对象)))。
  - **identity_kind 优先级**：`canonical_url` → `provider_id` → `content_fallback`。
    - `canonical_url`：URL 规范化（规则见下）后的绝对 URL。
    - `provider_id`：provider 原生 id（namespace 作用域内唯一，HN item 与 GitHub id 永不碰撞）。
    - `content_fallback`：仅在 canonical_url 与 provider_id 都缺、且 title/snippet/source 至少一项非空时使用，identity_value = SHA-256(UTF-8(JCS({title, snippet, source})))（null 省略）。若三项也全空，CLI 必须 fail closed：丢弃该 item，记录 `unidentifiable_item` postprocess error，不得生成共享的空对象哈希。
  - **URL 规范化规则**：只小写 scheme 与 host；**路径大小写保持**；去 fragment；去默认端口（http:80、https:443）；去末尾斜杠（根路径 "/" 除外）；去末尾 `.git`（忽略大小写）。
- **content_sha256**（adapter 输出规范化 `content_text`，CLI core 绝不从任意 `raw` 猜正文）：
  - 有 `content_text`：`content_scope = "full_text"`，hash = SHA-256(content_text 的 NFC UTF-8 字节)。
  - 无 `content_text` 但 title/snippet 任一非空：`content_scope = "title_snippet"`，hash = SHA-256(UTF-8(JCS({title, snippet})))（null 省略）。
  - 两者皆空：`content_scope = "metadata_only"`，hash = SHA-256(UTF-8(JCS({canonical_url, id, source})))（null 省略）；**显式声明这不是全文证明**，不构成对正文内容的任何断言。若该对象也为空，沿用上项 fail-closed 规则，不产出 item。
  - 绝不允许 content_sha256 为 null；`content_scope` 在 item 中是 required。
- `core_sha256` = SHA-256(UTF-8(JCS(core 中除 core_sha256 外的全部字段)))。
- 三类哈希均由 CLI core 产生；orchestrator 用同一规则重算并验证，不匹配即拒绝该 envelope。

## 6. Envelope v1 契约（合法 JSON Schema）

结构 = `contract` + `core`（CLI 产出并哈希）+ `wrapper`（orchestrator 包入）+ 顶层 `budget_snapshot` + 顶层 `terminal` + 可选 `payload.legacy`。

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "siftline://schema/sensor-envelope/1",
  "title": "siftline sensor-envelope",
  "type": "object",
  "additionalProperties": false,
  "required": ["contract", "core", "wrapper", "budget_snapshot", "terminal"],
  "properties": {
    "contract": {
      "type": "object",
      "required": ["id", "version"],
      "properties": {
        "id": { "const": "siftline.sensor-envelope" },
        "version": { "const": "1" },
        "target": { "const": "siftline-result/v1" }
      },
      "additionalProperties": false
    },
    "core": {
      "type": "object",
      "required": [
        "request", "items", "errors",
        "provenance", "cache", "invocation_outcome", "core_sha256"
      ],
      "properties": {
        "request": {
          "type": "object",
          "required": ["provider", "operation", "query", "params", "request_fingerprint"],
          "properties": {
            "relation": { "type": ["string", "null"] },
            "platform": { "type": ["string", "null"] },
            "provider": { "type": "string" },
            "operation": { "type": "string" },
            "query": { "type": "string" },
            "params": { "type": "object", "additionalProperties": true },
            "run_id": { "type": ["string", "null"], "description": "可选回显；权威绑定在 wrapper" },
            "branch_id": { "type": ["string", "null"], "description": "可选回显；权威绑定在 wrapper" },
            "invocation_id": { "type": ["string", "null"], "description": "可选回显；权威绑定在 wrapper" },
            "request_fingerprint": { "type": "string", "pattern": "^[0-9a-f]{64}$" }
          },
          "additionalProperties": false
        },
        "items": {
          "type": "array",
          "items": {
            "type": "object",
            "required": [
              "item_fingerprint", "content_sha256", "content_scope",
              "identity_kind", "canonicalization_version"
            ],
            "properties": {
              "item_fingerprint": { "type": "string", "pattern": "^[0-9a-f]{64}$" },
              "identity_kind": {
                "enum": ["canonical_url", "provider_id", "content_fallback"]
              },
              "canonicalization_version": { "const": "item-1" },
              "content_sha256": { "type": "string", "pattern": "^[0-9a-f]{64}$" },
              "content_scope": { "enum": ["full_text", "title_snippet", "metadata_only"] },
              "content_text": { "type": ["string", "null"] },
              "id": { "type": ["string", "null"] },
              "url": { "type": ["string", "null"] },
              "canonical_url": { "type": ["string", "null"] },
              "title": { "type": ["string", "null"] },
              "snippet": { "type": ["string", "null"] },
              "published_at": { "type": ["string", "null"] },
              "source": { "type": ["string", "null"] },
              "extra": { "type": "object", "additionalProperties": true },
              "raw": { "type": "object", "additionalProperties": true }
            },
            "additionalProperties": false
          }
        },
        "errors": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["code", "message"],
            "properties": {
              "code": { "type": "string" },
              "message": { "type": "string" },
              "provider": { "type": "string" },
              "operation": { "type": ["string", "null"] },
              "severity": { "enum": ["error", "warning"] },
              "retryable": { "type": "boolean" },
              "status_code": { "type": ["integer", "null"] },
              "cause": { "type": ["string", "null"] }
            },
            "additionalProperties": false
          }
        },
        "provenance": {
          "type": "object",
          "required": ["transport", "source", "cache", "elapsed_ms"],
          "properties": {
            "transport": { "type": "string" },
            "source": { "type": ["string", "null"] },
            "cache": { "enum": ["hit", "miss", "disabled"] },
            "elapsed_ms": { "type": "integer" },
            "canonical_url": { "type": ["string", "null"] },
            "engine": { "type": ["string", "null"] }
          },
          "additionalProperties": false
        },
        "cache": {
          "type": "object",
          "required": ["cache_key", "state"],
          "properties": {
            "cache_key": { "type": "string" },
            "state": { "enum": ["hit", "miss", "disabled"] },
            "ttl_seconds": { "type": "integer" }
          },
          "additionalProperties": false
        },
        "invocation_outcome": {
          "type": "object",
          "required": ["outcome", "provider_called", "item_count", "error_count", "elapsed_ms"],
          "properties": {
            "outcome": {
              "enum": [
                "validation_failed", "cache_hit", "provider_succeeded",
                "postprocess_failed", "provider_failed", "internal_failed"
              ]
            },
            "provider_called": { "enum": [true, false, null] },
            "item_count": { "type": "integer" },
            "error_count": { "type": "integer" },
            "elapsed_ms": { "type": "integer" }
          },
          "additionalProperties": false
        },
        "core_sha256": { "type": "string", "pattern": "^[0-9a-f]{64}$" }
      },
      "additionalProperties": false
    },
    "wrapper": {
      "type": "object",
      "required": ["run_id", "branch_id", "invocation_id", "journal", "created_at"],
      "properties": {
        "run_id": { "type": "string" },
        "branch_id": { "type": "string" },
        "invocation_id": { "type": "string" },
        "created_at": { "type": "string" },
        "journal": {
          "type": "object",
          "required": ["cli_invocation_row", "run_entry"],
          "properties": {
            "cli_invocation_row": { "$ref": "#/$defs/journal_ref" },
            "run_entry": { "$ref": "#/$defs/journal_ref" }
          },
          "additionalProperties": false
        }
      },
      "additionalProperties": false
    },
    "budget_snapshot": {
      "type": "object",
      "required": ["source", "attempts", "remaining", "provider_calls", "freeze_at", "per_provider"],
      "properties": {
        "source": { "const": "orchestrator_run_journal" },
        "attempts": { "type": "integer" },
        "remaining": { "type": "integer" },
        "provider_calls": { "type": "integer" },
        "freeze_at": { "type": "integer" },
        "per_provider": {
          "type": "object",
          "additionalProperties": {
            "type": "object",
            "required": ["used", "cap"],
            "properties": {
              "used": { "type": "integer" },
              "cap": { "type": "integer" }
            },
            "additionalProperties": false
          }
        }
      },
      "additionalProperties": false
    },
    "terminal": {
      "type": "object",
      "required": ["delivery_state", "stop_reason", "delivered", "output_sha256", "output_chars"],
      "properties": {
        "delivery_state": { "enum": ["complete", "forced_partial", "failed"] },
        "stop_reason": {
          "enum": ["skill_stop", "budget_exhausted", "timed_out", "internal_failed"]
        },
        "delivered": { "type": "boolean" },
        "output_sha256": { "type": ["string", "null"], "pattern": "^[0-9a-f]{64}$" },
        "output_chars": { "type": ["integer", "null"] }
      },
      "additionalProperties": false
    },
    "payload": {
      "type": "object",
      "properties": {
        "legacy": {
          "type": ["object", "null"],
          "description": "迁移期原样嵌入的 current Result v1；不参与 core 哈希，不被 orchestrator 验证"
        }
      },
      "additionalProperties": false
    }
  },
  "$defs": {
    "journal_ref": {
      "type": "object",
      "required": ["journal", "run_id", "entry_id", "sequence", "prev_entry_sha256", "entry_sha256", "appended"],
      "properties": {
        "journal": { "type": "string" },
        "run_id": { "type": "string" },
        "entry_id": { "type": "string" },
        "sequence": { "type": "integer" },
        "prev_entry_sha256": { "type": ["string", "null"] },
        "entry_sha256": { "type": "string", "pattern": "^[0-9a-f]{64}$" },
        "appended": { "type": "boolean" }
      },
      "additionalProperties": false
    }
  }
}
```

## 7. Journal（两个 append-only journal）

- **CLI invocation journal**：每条 CLI row 对应一次 invocation；**orchestrator run journal**：每次 run 级事件一条。两者都 **one-shot 原子追加**：单 writer、单事务（SQLite `BEGIN IMMEDIATE`）/锁，行写入 + fsync 持久化后才返回 `appended=true`；一次调用一条记录，禁止分裂或重复写入。
- 每个 journal ref 至少含：`journal`、`run_id`、`entry_id`、`sequence`、`prev_entry_sha256`、`entry_sha256`、`appended`（entry_sha256 = 该 entry 的 JCS 哈希，形成链）。
- **现有 `siftline cache log` 可 clear、可按需重建，是可变历史，不能作为新的 append-only authority**。新 journal 必须是独立存储面（独立表/文件，无 DELETE/UPDATE 暴露）。
- **预算以 orchestrator run journal 为权威**；CLI invocation row 只做交叉核对（invocation 数、provider_called、outcome）。两者不一致时 orchestrator 报错并拒绝继续。

## 8. Provider adapter 契约

- adapter 接口只含三个方法：`validate(request)`、`execute(request)`、`normalize(payload) -> items`。
- `normalize` 输出规范化 item 与可选 `content_text`：从响应里的稳定内容字段提取（如正文、正文预览），**绝不从任意 `raw` 字段猜正文**；`content_text` 是否提供决定 `content_scope`（第 5 节）。
- adapter 不做任何研究判断：不做相关性评分、不做去重排序决策（去重/URL 规范化由 CLI canonicalization 层做）、不解释结果含义。
- 统一 retry/error/call-state：重试策略、超时、错误分类（`auth/not_available/not_found/parse/usage/rate_limit/transport/timeout/http/internal`）、provider_called 三态（true/false/null）由 CLI 框架统一实现，adapter 不自行吞异常。
- **provider-specific 数据不得进入核心字段**：`id/url/title/snippet/published_at/source` 只能填规范化值；provider 私有字段一律进 `extra.<provider>.…` 与 `raw`（命名空间化，例如 `extra.github.stars`），禁止污染核心字段。

## 9. Skill 最小协议与证据登记

**一次提交只含一次决策**，Skill 提交：

```json
{
  "relation": "implementation",
  "platform": "github",
  "provider": "github",
  "operation": "search_repos",
  "query": "rust lsp server",
  "limit": 8
}
```

约束：

- 提交**不含任何预算字段**（Skill 不自报预算、不自报调用计数）；orchestrator 注入顶层 `budget_snapshot`。
- orchestrator 返回一个合法 envelope（第 6 节）。Skill 无权要求绕过。
- Skill 对每个 envelope 只做四种选择：`retain`（保留某 item 为证据）、`drop`、`next`（发起下一决策提交）、`stop`（结束）。
- 证据引用必须用结构化引用：`claim_id` + `polarity`（支持/反对）+ `item_fingerprint` + `quote_id`。不允许“我记得那个链接”式的无哈希引用。
- **quote_id 由 orchestrator evidence registry 生成**：registry 只在已验证内容（content_sha256 匹配）上，用 item_fingerprint/content_sha256/byte offsets/quote_sha256 登记一段引文；Skill 只能引用已登记 quote_id，**不得发明**。
- Skill 侧手工计数逻辑（manual ledger overlay、issued_invocations）在 orchestrator 提供机器计数后**废弃**：预算与计数唯一真源是 run journal 与 budget_snapshot。

## 10. 失败与终态（两轴 terminal）

两套状态分离：

- **invocation outcome**（core.invocation_outcome，复用现有语义）：`validation_failed` / `cache_hit` / `provider_succeeded` / `postprocess_failed` / `provider_failed` / `internal_failed`，另带 `provider_called` 三态。
- **run terminal**（顶层，两轴避免互斥冲突）：`delivery_state = complete | forced_partial | failed`；`stop_reason = skill_stop | budget_exhausted | timed_out | internal_failed`。题目要求的全部名词完整保留：invocation 六名词在 core；`complete`/`forced_partial` 在 delivery_state，`budget_exhausted`/`timed_out`/`internal_failed` 在 stop_reason。语义矩阵：

| 场景 | delivery_state | stop_reason |
| --- | --- | --- |
| 正常完成 | complete | skill_stop |
| 预算/时间/工具上限强制收敛，已交付部分 | forced_partial | budget_exhausted 或 timed_out |
| 预算/时间截断，未交付 | failed | budget_exhausted 或 timed_out |
| 内部故障，未交付 | failed | internal_failed |

**退出码不能单独代表交付成功。** 现有 0/2/3 只描述单次调用的 items/hard-errors；交付成功必须满足：envelope 通过 schema 校验 且 `terminal.delivered = true` 且 delivery_state ∈ {complete, forced_partial}。orchestrator 判定交付只读 terminal 两轴，不读退出码。

**强制交付（可实施）**：orchestrator 在分配时**预留 synthesis 配额**（在预算/墙钟内显式扣留，不计入可搜索预算）。截止时先触发一次**受限 synthesis**（只用 synthesis 配额）；若模型仍无 final，则从 evidence registry 已登记 retained claims **结构化渲染 deterministic forced_partial**（claim_id / polarity / item_fingerprint / quote_id / 引文文本），禁止空交付、禁止“下次再答”。这直接对应 M4 skill 0/20 的修复：模型不交付由 orchestrator 兜底。

**长度控制**：不截断 JSON 交付物；超限时按优先级（低价值 items 优先）删除后**重验 schema**，而不是截断字符串破坏 schema。

## 11. 分阶段落地

**Phase 1 — contract/journal/hash**
1. envelope Schema（`siftline.sensor-envelope/1`）+ 校验器 + `payload.legacy` 迁移映射（不重命名 schema_version）。
2. 两个 append-only journal（CLI invocation + run）：one-shot 原子追加，单 writer/事务/锁，entry 哈希链。
3. 三类哈希实现（RFC 8785 JCS + NFC；request/item/content），CLI core 产生，orchestrator 验证函数。

**Phase 2 — enforcement**
4. 预算分配与 freeze/timeout（总/分 provider、75% freeze、墙钟与工具硬上限、synthesis 配额预留）。
5. raw JSON 输出、长度上限（优先级删除后重验 schema）、交付物 schema 校验、受限 synthesis + deterministic forced_partial 兜底。

**Phase 3 — adapters/parallelism**
6. adapter 三方法 + `content_text` + 统一 retry/error/call-state。
7. 受并发上限约束的受控并行（不与 freeze 边界冲突）。

**Phase 4 — eval**（truth/key 隔离在此阶段，不在 Phase 2）
8. truth/key OS 隔离与对抗用例（见第 12 节）；三组 fresh paired AB/BA。

## 12. 验收（含对抗用例）

**技术验收（Phase 1–3 完成判定）：**

- **对抗用例使矛盾答案低分**：构造同一候选/同一 claim 的“支持 vs 反对”两份答案（如 M4 P4 planned vs absent），evaluator 依靠 claim_id / item_fingerprint / quote_id / content_sha256 做机器比对而非关键词，矛盾交付必须显著低分。
- **M2 candidate 绑定必须显式成链**：`branch_id -> invocation_id / request_fingerprint -> item_fingerprint -> quote_id`（branch 每次展开得到新 invocation_id 与 request_fingerprint，retained item 得到 item_fingerprint，引文得到 quote_id）。同一 request_fingerprint 重跑或跨 run 复用同一 item_fingerprint 时，矛盾必须可被机器检出（这直接回收 v3 只命中 2/8 锚点、P4 误判的问题）。
- **truth/key 指 evaluator 的 private truth/answer key，不是 provider API key**：truth pack 与判分 key 所在文件对传感器/模型子进程 OS 级不可读（权限 000 / 不同 uid / 剥离 env 的独立用户）；provider credential 只按 provider 最小权限注入（github 走 `gh` auth，其余走各自 env，不混入 truth）。子进程可见性为零，不能靠进程内约定。此验收属于 Phase 4 eval harness。
- **atomic one-shot journal/lock**：并发重复调用不产生分裂或重复记录；单传感器路径上不再出现 `database is locked`。
- **candidate/model/plan hash**：候选代码、模型输出、评估计划在评估前各取哈希并冻结；任一变更即失效需重评估。

**质量门禁（Phase 4 判定）：**

- 每个任务三组 fresh paired replicates，AB/BA 平衡（A=orchestrator 驱动新架构，B=baseline）。
- 通过标准：配对**中位数质量 ≥ baseline**（不许出现 v3 的 -3 回退）、无任务退化超过 2 分、delivery rate 不低于 baseline、token/time/cost ≤ 1.5×。
- **质量至少不低于 baseline 之后才允许测大任务**；在此之前大任务评估只增加花费，不增加信任。

## 13. Definition of Done

- [ ] 冻结 v3 且不安装/不推广 v3 的决定已记录到项目外可见处，且不再新增 SKILL.md 规则文本。
- [ ] envelope 契约 `siftline.sensor-envelope/1` 实现；`payload.legacy` 原样保留 current Result v1，无重命名、无静默升级。
- [ ] request/item/content 三类哈希按 RFC 8785 JCS + NFC 由 CLI core 产生，orchestrator 重算一致；`content_scope`（full_text/title_snippet/metadata_only）required；identity_kind 优先级与 URL 规范化规则落地。
- [ ] 两个 append-only journal one-shot 原子追加通过并发测试；journal ref 含 run_id/entry_id/sequence/prev_entry_sha256/entry_sha256；`cache log` 未充当 authority；预算以 run journal 为权威。
- [ ] wrapper（run_id/branch_id/invocation_id/journal）由 orchestrator 包入；budget_snapshot 顶层 required 且 source=orchestrator_run_journal；Skill 提交不含预算；quote_id 由 evidence registry 生成。
- [ ] 预算、freeze/timeout、raw JSON、长度上限（优先级删除+重验 schema）、schema 校验、synthesis 配额与强制交付、并发上限均为代码强制。
- [ ] adapter 三方法 + content_text 落地；provider-specific 数据全部命名空间化，不进核心字段。
- [ ] 对抗用例：矛盾交付（同一 claim 双极性、planned/absent 翻转）被机器检出并低分；M2 显式链 branch_id→invocation_id/request_fingerprint→item_fingerprint→quote_id 成立。
- [ ] Phase 4：truth/answer key 与 provider credential 分离，truth/key 对传感器/模型子进程 OS 级不可读，有测试证明。
- [ ] 三组 fresh paired AB/BA 通过质量门禁（中位数 ≥ baseline、无退化 > 2 分、delivery 不降、≤ 1.5× 资源），之后才启动大任务评估。
- [ ] 未实现能力（orchestrator、wrapper、sensor-envelope/1、evidence registry、RFC 8785 哈希实现、append-only journal、truth/key OS 隔离、对抗 evaluator）在验收报告中被如实标记为“本规范要求、当前未实现”，不承诺已具备。

## 14. 未实现能力声明

本规范要求的以下能力当前仓库中**不存在**，属待实现项：外层 orchestrator 与 wrapper、`siftline.sensor-envelope/1` 契约与迁移、RFC 8785 JCS/NFC 哈希实现、evidence registry（quote_id）、两类 append-only 原子 journal、truth/key OS 级隔离、对抗 evaluator、synthesis 配额与 deterministic forced_partial。现有能力仅为：`Result`/`Item`/`ErrorItem`/`Provenance`（models.py）、cache + ledger（storage）、provider `run` 管线（providers/base.py）、单次调用 exit code。任何验收报告不得声称上述待实现项已可用。
