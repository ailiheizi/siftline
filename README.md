# siftline

Siftline is a two-piece product for AI-driven research:

- **siftline-research skill** — the *research brain*. It reads an article,
  project, claim, observation, or design; extracts its generative mechanisms
  and consequential signals; routes multiple relation paths to suitable
  platforms; searches iteratively for origins, analogues, implementations,
  demand evidence, and counterexamples; and returns a concise, evidence-backed
  research frontier. Lives in [`skills/siftline-research/`](skills/siftline-research/).
- **siftline CLI** — the *search sensor*. A thin, scriptable **search/fetch
  sensor CLI** for AI agents, skills, and research pipelines. It turns provider
  query/credentials details into one stable JSON envelope. **It does no LLM
  reasoning, ranking, or conclusion generation inside the CLI** — that stays in
  the calling skill.

The skill decides *what* a seed means, *which* relation to pursue, *where*
evidence is likely to live, and *when* to stop; the CLI executes each search and
returns verifiable, schema-versioned JSON.

Providers:
- **GitHub** — read-only queries through your authenticated `gh` CLI (no token in siftline).
- **Hacker News** — public Algolia API, no key required.
- **Exa** — optional HTTP provider (key from env).
- **Tavily** — optional HTTP provider (key from env).
- **web** — any OpenAI-compatible **Responses `web_search`** endpoint, configurable
  base URL, model, and key env (no vendor hardcoded).

## The research skill

The bundled **siftline-research** skill ([`skills/siftline-research/`](skills/siftline-research/))
contains the research logic: seed fingerprinting, relation branches, platform
routing, query patterns, and artifact discovery. It treats the CLI below as an
interchangeable sensor — GitHub/`gh`, Hacker News, Exa, Tavily, and
OpenAI-compatible `web_search` all feed the same stable JSON envelope.

| | siftline-research skill | siftline CLI |
| --- | --- | --- |
| Role | research brain | search sensor |
| Decides | seed meaning, relations, platforms, queries, evidence judgment, stop condition | nothing (ordering is provider order) |
| Produces | an evidence-backed research frontier with real links and confidence | one stable JSON envelope per query |
| Runs | inside the agent (OpenCode/Codex) | as a subprocess invoked by the skill |

### Loading the repo skill explicitly

OpenCode registers skill directories via `skills.paths` (scanned recursively for
`**/SKILL.md`) — add the repo's `skills/` directory to `opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "skills": { "paths": ["skills"] }
}
```

Restart opencode after changing config. The skill then triggers as
`$siftline-research`.

Codex (and other SKILL.md-based agents) discover skills under
`~/.codex/skills/`. Point the discovery directory at the repo copy with a
symlink, then reference it as `$siftline-research`:

```bash
ln -s "$PWD/skills/siftline-research" ~/.codex/skills/siftline-research
```

### Combining the skill with the CLI

Give the skill a seed and let it drive the CLI as its search sensor:

```text
Use $siftline-research, with the siftline CLI as the search sensor, to
discover open-source analogues of this project and verify demand evidence.
```

In practice the skill runs the CLI per branch, reads the JSON envelopes, and
keeps only decision-changing sources. The whole research run shares one stable
`--query-id`, and provider call counts come from the machine ledger:

```bash
siftline doctor
siftline --query-id run-2026-08-10-a github search-repos "<mechanism> skill agent" --limit 8
siftline --query-id run-2026-08-10-a github readme "<owner/repo>"
siftline --query-id run-2026-08-10-a hn search "<mechanism> community discussion" --limit 10
siftline --query-id run-2026-08-10-a web search "how do people <job> without <proposed solution>" --limit 5
siftline ledger --query-id run-2026-08-10-a
```

See [`docs/architecture.md`](docs/architecture.md) for the Skill/CLI boundary
and data flow.

## Install

Requires Python 3.11+ and `uv`.

```bash
cd siftline
uv sync --dev          # development environment
uv tool install .      # global CLI (optional)
```

After changing anything under `src/`, the global CLI must be reinstalled or it
drifts from the source (`uv tool upgrade` cannot detect a same-version source
edit). Reinstall with `uv tool install --force .` and verify the version:

```bash
uv tool install --force .   # sync the global CLI to this source tree
siftline --version          # must match the version in pyproject.toml
```

Then make a config if you want to change anything:

```bash
cp config.example.toml ~/.config/siftline/config.toml
```

No API keys are needed for `github` (uses your `gh` auth) or `hn`.

## Quick start

```bash
# Environment check
siftline doctor

# GitHub: search repos, read metadata/readme/license/tree, list social graph
siftline github search-repos "siftline in:name language:python" --limit 5
siftline github repo "claude-ai/claude-code"
siftline github readme "claude-ai/claude-code"
siftline github license "claude-ai/claude-code"
siftline github tree "claude-ai/claude-code" --branch main --limit 100
siftline github starred "torvalds" --limit 20
siftline github repos "torvalds" --limit 20

# Hacker News (no key)
siftline hn search "llm agents" --limit 10
siftline hn item 37551237

# Keyed providers
siftline exa search "zero-shot text classification" --limit 5
siftline tavily search "retrieval augmented generation" --limit 5

# OpenAI-compatible Responses web_search
siftline web search "latest state of open source siftline skills" --limit 5

# Cache and machine research ledger
siftline cache info
siftline cache log              # backward-compatible raw history
siftline cache clear --yes
siftline ledger                 # machine research ledger: summary + entries
siftline ledger --query-id run-2026-08-10-a --limit 100
```

## Output contract

Default output is a single JSON document on stdout (add `--format jsonl` for one
envelope per line, or `--format table` for humans). Every envelope is stable and
schema-versioned:

```json
{
  "schema_version": "1",
  "query_id": "…",
  "provider": "github",
  "operation": "search_repos",
  "query": "…",
  "params": {"limit": 5},
  "meta": {},
  "retrieved_at": "2026-08-09T12:34:56Z",
  "items": [
    {
      "id": "…",
      "url": "https://github.com/owner/repo",
      "title": "owner/repo",
      "snippet": "…",
      "published_at": "…",
      "source": "owner/repo",
      "extra": {"stars": 42, "forks": 3, "language": "Python", "license": "MIT"},
      "raw": {…}
    }
  ],
  "errors": [],
  "provenance": {
    "transport": "gh_cli",
    "source": "https://api.github.com/search/repositories",
    "cache": "miss",
    "elapsed_ms": 512,
    "canonical_url": null,
    "engine": "github_search"
  }
}
```

`query_id` defaults to a fresh UUID; pass `--query-id` to correlate runs with the
machine research ledger.

### Machine research ledger

Every executed query is appended to the same SQLite DB as a ledger row with a
stable `outcome` and a factual `provider_called` flag. `siftline ledger` returns
one structured object: a summary plus newest-first entries.

```json
{
  "summary": {
    "attempts": 3,
    "provider_calls": 1,
    "unknown_provider_call_states": 0,
    "cache_hits": 1,
    "validation_failures": 1,
    "provider_successes": 1,
    "postprocess_failures": 0,
    "provider_failures": 0,
    "internal_failures": 0,
    "unclassified": 0
  },
  "entries": [
    {
      "query_id": "run-1",
      "provider": "hn",
      "operation": "search",
      "query": "my tool",
      "params": {"limit": 10},
      "cache": "miss",
      "outcome": "provider_succeeded",
      "provider_called": true,
      "elapsed_ms": 7,
      "item_count": 1,
      "error_count": 0,
      "error_codes": []
    }
  ]
}
```

`--query-id` is optional for recent history and filters entries when given; it is
the correlation key the `siftline-research` skill uses to read machine-factual
provider call counts for a run instead of counting them by hand.

### Outcome semantics

| outcome | meaning | `provider_called` |
| --- | --- | --- |
| `validation_failed` | request rejected locally before any provider/transport call (missing credentials, unsupported operation, unavailable local transport, explicit validation) | false |
| `cache_hit` | result served from the local cache | false |
| `provider_succeeded` | external provider or transport was called and the normalized result is usable (no hard downstream consistency errors) | true |
| `postprocess_failed` | provider/transport returned, but decode/parse/normalization or downstream consistency failed | true |
| `provider_failed` | external provider/transport call was attempted and failed (remote auth, timeout, rate limit, not found, transport, HTTP) | true |
| `internal_failed` | unexpected CLI failure; `provider_called` is **false** when provider construction itself failed before any provider existed, or **null** when an unexpected exception escaped an existing provider's `run()` and the CLI cannot know whether an external call occurred | false or null |
| `unknown` | pre-v4.1 row migrated from the old query log | null |

`provider_calls` in the summary is the count of entries with
`provider_called: true`, so it is factual by construction: local preflight
failures never inflate it. Entries whose provider-call state is genuinely
unknown — `provider_called: null` (legacy rows, or an unexpected exception
escaping an existing provider's `run()`) — are counted in
`unknown_provider_call_states` instead of being described as either called or
not called. Migrated legacy rows surface as `outcome: unknown`,
`provider_called: null`, and count toward `unclassified` instead of fabricating
an exact call count.

### Framework-validation boundary

Explicit command validation (for example a malformed `owner/repo`) is recorded in
the ledger as `validation_failed` **without** contacting GitHub. Framework-level
usage errors that happen before a truthful request event can be formed — such as
an unknown subcommand, a bad `--format`, or a missing argument — remain ordinary
CLI usage errors (exit code 2) and are not written to the ledger.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success (may include warnings in `errors`). |
| `2` | Failure: requested operation produced no items and at least one hard error — or a CLI usage error. |
| `3` | Partial: some items plus at least one hard error (multi-provider style calls). |

### Error classification

`errors[]` entries carry `code`, `retryable`, and `status_code`:

| code | meaning | retryable |
| --- | --- | --- |
| `auth` | missing key / 401 / 403 | no |
| `not_available` | transport tool missing (e.g. `gh` not installed) | no |
| `not_found` | 404 | no |
| `parse` | provider returned non-JSON or an unexpected, non-normalizable response shape | no |
| `usage` | unsupported operation / bad arguments | no |
| `rate_limit` | 429 / rate limited | yes |
| `transport` | network failure | yes |
| `timeout` | request timed out | yes |
| `http` | other HTTP status | varies |
| `internal` | unexpected exception in the CLI | no |

## Configuration

TOML file at `~/.config/siftline/config.toml`, or anywhere via `--config PATH` or
`$SIFTLINE_CONFIG`. See [config.example.toml](config.example.toml). API keys are
read **only from environment variables** — never from the config file:

| Provider | Primary env | Fallback |
| --- | --- | --- |
| Exa | `SIFTLINE_EXA_API_KEY` | `EXA_API_KEY` |
| Tavily | `SIFTLINE_TAVILY_API_KEY` | `TAVILY_API_KEY` |
| web (OpenAI-compatible) | `SIFTLINE_OPENAI_API_KEY` | `OPENAI_API_KEY` |
| GitHub | none (uses `gh` auth) | — |

`doctor` reports which keys are present (masked) and whether `gh` is installed and
authenticated.

## Behavior guarantees

- **URL canonicalization + dedup** — item URLs are canonicalized; duplicates (case,
  trailing slash, `.git`) collapse, first occurrence wins.
- **SQLite cache + TTL** — responses are cached keyed by `provider|operation|query|params`
  (not `query_id`), so re-running the same query is a cache hit and reproducible.
  Errors are never cached. `--no-cache` and `--ttl` override per run.
- **Reproducible query log / machine ledger** — every executed query (hit or miss)
  is appended to the same SQLite DB with query id, exact params, cache state,
  elapsed ms, item/error counts, a stable `outcome`, the factual
  `provider_called` flag, and error codes. `siftline cache log` is the raw
  backward-compatible history; `siftline ledger` adds the structured summary for
  machine consumption.
- **Timeouts and error classification** — all HTTP calls have configurable timeouts
  and retries; transport vs vocabulary failures are kept distinct in `errors`.
- **No secrets in the repo** — only env var names are referenced.

## Design

The CLI is a thin transport layer on purpose; the research intelligence lives in
the bundled `siftline-research` skill (see [The research skill](#the-research-skill)).
See [docs/architecture.md](docs/architecture.md).

## Known limitations

- **GitHub code search** relies on GitHub's search index, which is frequently
  degraded (HTTP 503 / timed-out results / `total_count > 0` with zero items).
  Siftline reports these honestly: transient failures are `retryable`, and a
  provider-reported non-zero total with zero items is flagged as an
  `empty_result` error instead of being mistaken for a vocabulary miss.
- **License detection** is GitHub's own: repos whose license is not in GitHub's
  detected set (e.g. proprietary or custom license files) return `not_found`
  from `github license`. Inspect the repo metadata or `github tree`/`readme`
  instead.
- The CLI performs no ranking or synthesis; result ordering is whatever the
  provider returns.

## Development

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/siftline
uv run pytest -m "not live"          # offline unit tests (no network)
uv run pytest -m live                # read-only live smoke tests (needs network + gh)
```

## License

MIT. See [LICENSE](LICENSE).
