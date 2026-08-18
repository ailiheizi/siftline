# Siftline architecture

## Goal

Siftline ships two pieces with a strict boundary:

- **siftline-research skill** (the *research brain*, in `skills/siftline-research/`)
  is responsible for understanding a seed, expanding relations, judging
  evidence, and deciding when to stop. It is the default calling skill for the
  CLI.
- **siftline CLI** (the *search sensor*) is responsible for one thing only:
  **turning a well-formed provider request into a stable, verifiable, machine-
  readable result** without doing LLM reasoning, ranking, or conclusions.

## High-level shape

```
 seed (article/project/claim/observation)
        │
        ▼
┌────────────────── siftline-research skill (research brain) ──────────────────┐
│  Inspect seed → idea fingerprint                                              │
│  Expand relation branches      references/relation-types.md                   │
│  Route branch → platform       references/platform-routing.md                 │
│  Build query lattice           references/query-patterns.md                   │
│  Discover artifacts            references/artifact-discovery.md               │
│  Evaluate evidence → frontier report                                         │
└───────┬──────────────────────────────────────────────────────────────────────┘
        │  1 request: provider/operation/query/params
        ▼
┌─────────────────────── siftline (CLI) ───────────────────────┐
│  cli.py        argument parsing, output rendering, exit codes │
│  config.py     TOML config + env resolution                   │
│  storage.py    SQLite cache + machine research ledger         │
│  doctor.py     doctor / providers diagnostics                 │
│  canonical.py  URL canonicalization (github forms, http)      │
│  dedup.py      cross-item dedup (URL / raw fingerprint)       │
│  http.py       httpx transport, timeouts, retries, classify   │
│  providers/    1 class per provider (github, hn, exa,         │
│                tavily, openai_web)                            │
└───────────────────────────────┬───────────────────────────────┘
                                │  stable JSON envelope (schema_version=1)
                                ▼
                      back to the research skill
                      (snowball new vocabulary, deepen/abandon branches,
                       then write the frontier report)
```

The skill never talks to a provider directly and the CLI never makes research
decisions. All state crosses the boundary as the stable JSON envelope.

## Skill/CLI boundary and data flow

| Concern | siftline-research skill | siftline CLI |
| --- | --- | --- |
| Reads seed material and builds the idea fingerprint | yes | no |
| Selects relation types and priority | yes | no |
| Routes each branch to a platform and vocabulary | yes | no |
| Builds and adapts the query lattice | yes | no |
| Judges evidence, demand, and pain coverage | yes | no |
| Decides when to stop searching | yes | no |
| Runs a single provider request and returns normalized JSON | no | yes |
| Caches, dedups, canonicalizes, logs, classifies errors | no | yes |
| Ranks or synthesizes conclusions | no | no |

Data flow per branch:

1. The skill picks the smallest mode (quick lookup / audit / discovery) and a
   budget, and gives the whole research run **one stable `--query-id`**.
2. It emits one request per query: `provider`, `operation`, `query`, `params`,
   reusing that stable `--query-id` for correlation.
3. The CLI executes the request (cache-first), canonicalizes and dedups items,
   and returns the envelope; it never invents results and reports transport vs
   vocabulary failures separately. Every invocation is also recorded in the
   machine research ledger with a stable outcome and a factual
   `provider_called` flag.
4. The skill reads `siftline ledger --query-id <id>` for machine-factual
   operation/provider-call counts instead of asking the LLM to remember them,
   extracts new vocabulary, actors, and references from each envelope, updates
   its frontier, deepens promising branches, and stops when searches repeat
   known mechanisms or the budget is exhausted.
5. The skill writes the report with real URLs and explicit evidence states
   (`observed now`, `documented`, `inferred`, `unverified`). Its **finalization
   reserve** freezes the frontier at 75% of the external operation budget and
   allows remaining operations only to verify decisive facts already used in the
   conclusion; if constrained, it returns a partial but reliable answer rather
   than none.

## The envelope (Result)

Every operation returns the same pydantic model:

- `schema_version` — bump when breaking contract changes.
- `query_id` — caller-supplied or UUID; used for log correlation, not caching.
- `provider`, `operation`, `query`, `params` — the exact request, so the caller
  can reproduce it.
- `meta` — provider-level extras (e.g. `nbHits`, model, usage).
- `retrieved_at`, `items`, `errors`, `provenance`.

Items are normalized: canonical `url`, `title`, `snippet`, `published_at`,
`source`, structured `extra`, and provider `raw`. Dedup uses the canonical URL
(case/fragment-insensitive) and falls back to a raw-payload fingerprint.

## Providers

### BaseProvider pipeline (`providers/base.py`)

Each provider implements only `_execute(...) -> Result`. `run()` wraps it with:

1. cache lookup (key = hash of provider/operation/query/params),
2. execute (catching `ProviderHTTPError` into `errors`),
3. canonicalize + dedup items,
4. cache store **only when no hard errors**,
5. classify the run into a stable ledger `outcome` and append it to the machine
   ledger. A cached hit is `cache_hit` (`provider_called=false`); a local
   preflight rejection (missing credentials, unsupported operation, unavailable
   transport) is `validation_failed` (`provider_called=false`); a successful
   external call with a usable, warnings-only result is `provider_succeeded`
   (`provider_called=true`); a parse/normalization failure after a real transport
   call — including a payload with an invalid collection shape and a returned
   result that carries a hard downstream consistency error such as the GitHub
   `empty_result` guard — is `postprocess_failed` (`provider_called=true`); any
   other failed external attempt (remote auth, timeout, rate limit, not found,
   transport, HTTP) is `provider_failed` (`provider_called=true`).

`ProviderHTTPError` carries a `preflight` flag: local validation raise sites set
it so the ledger never counts a rejected request as a provider call. Errors that
originate inside the transport (including remote auth and HTTP statuses) leave it
false.

### github — `gh_cli` transport

Ships no token. All operations go through `gh api` (auth comes from the user's
`gh` login): `search/repositories`, `search/code`, `repos/{o}/{r}`,
`/readme`, `/license`, `/git/trees/{ref}`, and the user list endpoints
(`starred`, `following`, `followers`, `repos`). Search operations use one page
(`per_page=limit`); user lists paginate only when `limit > 100`. Failures are
classified from gh's stderr (404/401/403/429/5xx).

### hn — public Algolia

`GET /api/v1/search` (no key) and `GET /api/v1/items/{id}`. URL for comment hits
falls back to `https://news.ycombinator.com/item?id=<objectID>`.

### exa / tavily — HTTP with env keys

Keys come from `SIFTLINE_*_API_KEY` (fallback `EXA_API_KEY`/`TAVILY_API_KEY`),
never from config. Missing keys raise `auth` errors that `doctor` surfaces.

### web — OpenAI-compatible Responses web_search

POSTs to `{base_url}/responses` (configurable endpoint/model) with a
`web_search` tool. Results are collected with a **generic payload walker** that
finds any `{url, title}`-shaped object, so the same provider works against any
compatible backend without hardcoding vendor response shapes.

## Caching and machine research ledger

One SQLite file (WAL) holds two tables:

- `cache(key, value, retrieved_at, created_at)` — TTL-checked on read.
- `query_log(...)` — the backward-compatible machine research ledger: the
  original append-only reproducible columns plus `outcome`, `provider_called`,
  and `error_codes`.

Because the cache key excludes `query_id`, replaying an identical query is a hit
and cost-free; `--query-id` only correlates runs. A cached result returned under a
new `--query-id` carries that current id on the returned envelope while the stored
row keeps its original one.

The DB migrates safely: opening an old database adds the three ledger columns via
`ALTER TABLE` (plain `CREATE TABLE IF NOT EXISTS` cannot), leaving existing rows
intact. Pre-migration rows read back as `outcome: unknown`,
`provider_called: null`, `error_codes: null`, and `legacy: true`, and count
toward `unclassified` and `unknown_provider_call_states` in the ledger summary —
the CLI never fabricates exact call counts for rows that predate the ledger or
whose provider-call state is unknowable.

`ledger()` returns `{"summary": ..., "entries": [...]}` for the default JSON
machine contract; `cache log` remains the raw, newest-first history and now
exposes the same added fields. Entry fields include query id, provider, operation,
query, params, cache state, outcome, `provider_called`, elapsed ms, item count,
error count, and error codes.

### Framework-validation boundary

Explicit command validation is logged as `validation_failed` without any external
call — for example `github repo "norepo"` records an owner/repo validation entry
(`provider_called: false`) and never constructs or invokes GitHub. Framework-level
usage errors that occur before a truthful request event can be formed — unknown
subcommand, bad `--format`, missing argument, `--limit` out of range — remain
ordinary CLI usage errors (exit code 2) and are not written to the ledger.

## Failure semantics

- Timeouts/network errors are `retryable`; auth/parse/not-found are not.
- Transport failures and vocabulary failures are separate error codes, so a
  skill can switch channels instead of repeating synonyms.
- `exit_code` is part of the contract: `0` ok, `2` total failure/usage, `3`
  partial (items plus hard errors).
- Unexpected CLI failures are `internal_failed` ledger rows. `provider_called`
  is **false** only when provider construction itself failed before any provider
  existed (no truthful dispatched-request event can be formed). When an
  unexpected exception escapes an existing provider's `run()`, the CLI cannot
  know whether an external call occurred, so the row carries `provider_called:
  null` — an honest unknown provider-call state, never a fabricated false.
- `provider_calls` in the ledger summary counts only `provider_called: true`;
  entries with `provider_called: null` are counted separately as
  `unknown_provider_call_states`.

## Testing strategy

- Unit tests never touch the network: HTTP providers are exercised with
  `httpx.MockTransport`; the GitHub provider with an injected fake subprocess
  runner.
- The `http` module, storage, canonicalization, dedup, config, and CLI contract
  (envelope keys, exit codes, formats) have dedicated tests.
- `tests/test_ledger.py` covers every ledger outcome, summary counts,
  query-id filtering, cache hits under a new query id, explicit validation
  logging, internal failures, and migration from the old query-log schema.
- `tests/test_live_smoke.py` runs **read-only** live queries against Hacker News
  and GitHub, skipped unless `gh` is installed and authenticated (and
  `SIFTLINE_SKIP_LIVE` is unset).

## Non-goals (current MVP)

No server, vector store, web UI, LLM SDK, or X scraping. No in-CLI ranking or
conclusion synthesis. Providers are intentionally replaceable; the CLI performs
no final judgment.
