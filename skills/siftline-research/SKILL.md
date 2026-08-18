---
name: siftline-research
description: Seed-driven associative research and channel-specific evidence acquisition. Extract mechanisms and consequential signals, route each question to the right media or source channel, use available channel Skills or configured transports such as Siftline, browser adapters, and RSSHub, and return a concise evidence-backed research frontier. Use for demand, pain, implementation, origin, counterexample, Xiaohongshu, Chinese social-media, forgotten-post, platform-native, and cross-media research requests.
---

# Siftline Research

## Objective

Turn one seed into a useful research frontier. Do not merely retrieve text that sounds similar. Find material that changes the interpretation of the seed, tests demand, exposes hidden relations, or changes the next action.

Treat search engines and platform search as interchangeable sensors. Put the intelligence in deciding what the seed means, which relation to pursue, where evidence is likely to live, and when another search is worth doing.

## Channel Router

Treat a media platform, a native API, an RSSHub route, and a browser adapter as
different acquisition paths. A platform name alone is not a research plan.

- Before the first external operation, create a small channel plan: evidence
  class, channel ID, adapter Skill or reference, transport, query vocabulary,
  expected source URL, and the fallback if that path is unavailable.
- Read [channel-routing.md](references/channel-routing.md) for the common
  adapter contract. Load only the channel reference needed for the current
  branch; do not load every media guide into context.
- If a matching channel Skill is available, use it as the primary adapter and
  pass it the seed fingerprint, one bounded evidence question, the channel
  plan, and the common output contract. If no matching Skill is available, use
  the configured native endpoint, browser adapter, named sensor, or RSSHub
  transport described by the channel reference.
- RSSHub is a transport/aggregation layer, never automatic proof that the
  original platform said something. Preserve both the feed URL and the
  original item URL, and label feed-only observations as discovery or
  aggregated evidence until the original is verified.
- Every completed or failed channel attempt produces a ledger record. If the
  chosen channel is inaccessible, name the missing evidence class and use only
  the declared fallback; never silently turn a generic web result into
  platform-native evidence.
- A final answer must state which channels were actually used, which were
  unavailable, and what each channel can and cannot prove.

## Delivery First (overrides everything)

The user's final deliverable is one complete, evidenced answer — never a skeleton, a plan, a promise, or an empty text. All process rules below serve that deliverable; when they compete with it, the deliverable wins.

- **Final-answer-first.** In a single turn, or whenever time, context, or output budget is constrained, the run MUST end with a real formal answer, not a skeleton or progress note. An incomplete but evidenced answer is strictly preferred over ledger reads, lint passes, more searches, or any process ceremony. If you can only deliver a shortened version, deliver the shortened version — as text, not as a promise to finish later.
- **Synthesis deadline.** From the freeze point onward, stop acquiring. Do not draft the whole answer inside hidden reasoning first — compose the final answer directly in visible text. If output budget is short, write the shortened-but-complete answer immediately instead of waiting for a clean state that may never come. **A turn that ends with reasoning and no text delivers nothing and is a hard failure.**
- **Reasoning is not delivery.** The answer must exist as assistant text. Reasoning blocks are not visible final text and do not count as an answer, a partial answer, or a skeleton.
- **One decisive final text.** The final assistant text is the complete formal answer. When a clean linter `--emit` was reachable within the lint budget (see Final Review), it is the emitted payload byte-for-byte; otherwise the fallback is the manually-verified full text delivered in the same turn. Lint never takes priority over delivery: never delay or drop the final text to earn a lint PASS. Never end the run on a skeleton block, a ledger dump, a lint narration line, or a status sentence.

## Start Gate (mandatory)

When the task supplies a project path and the sensor command contract is already in the Skill or the prompt, phase one is evidence, not environment discovery. Do not inspect cwd, PATH, sensor version, help, providers, auth/status, or the sensor implementation repository — no `pwd`/`ls`/`which`, no version probes, no grepping the Siftline repo, no `--help` chain. Read the known seed files, run the single decisive project-native command, or issue the first external query; then start researching.

Diagnostic verbs a user prompt allows (version, test, build, status, git log) are permissions, not a checklist. Run only a decisive project-native command. Never run a diagnostic already made irrelevant by observed local state: run no git command after an inventory showed no `.git`, and skip VCS checks whenever VCS state cannot change the decision.

Absolute Skill paths are zero-discovery. When the task supplies a Skill path, read `<path>/SKILL.md` directly — never the skill registry, never a listing of `<path>/references` or `<path>/scripts`. Load only the mode-required named references. A marker-only `echo`/`printf`/`true`/comment tool that carries no information is forbidden as a progress signal.

Forbidden preflight (a known failure — it spent the whole local budget and made zero provider calls):
`pwd`/`ls` -> `which siftline`/`siftline version` -> grep the Siftline repo for commands -> `--help` probes -> still no query.
Correct alternative: read the seed files, then go straight to `siftline --query-id <id> github search-repos "<q>" --limit 8`.

## Select the Smallest Mode

Choose a mode before loading references or searching:

- **Quick lookup** — one fact, known artifact, exact repository, or narrow verification. Use direct primary-source lookup, usually one or two queries (default external base **2**), skip the research-frontier workflow.
- **Audit** — current repository state, pain coverage, competitor boundary, or a claim whose local truth matters. Verify authoritative local state first; use two to four external queries (default external base **4**) and retain at most eight decision-changing sources unless the user asks for more.
- **Discovery** — an article, project, observation, or idea should lead to non-obvious related work, demand evidence, origins, implementations, or counterexamples. Use five to eight external queries (default external base **8**) and retain at most twelve decision-changing sources unless the user sets another budget.

For mixed or multiple-seed work, choose the dominant mode and allocate one shared budget. Escalate from Audit to Discovery only when an external relation could change the decision. These bases apply only when the user gives no budget; an explicit user budget always wins.

## Multi-Seed Budget Scaling

When the run has **S seeds sharing one budget**, allocate one shared pool so each seed is not starved and no seed clones the whole template. This is the default for multi-project work; a single-seed run just uses S=1.

- **Explicit user budget wins, never scaled.** If the user gives an explicit total external/search/fetch/provider budget `B`, that `B` is the hard shared cap across ALL seeds for the run — never rescale it to `B + (S-1)*2`, never inflate it with a mode default, never exceed it. The freeze point is `ceil(0.75 × B)`: B=8 -> attempt 6, B=12 -> attempt 9.
- **Default external budget (only when no budget is given).** Base by mode: Quick lookup `base=2`, ordinary Audit `base=4`, Discovery `base=8` (coverage Audit uses the Audit base). Scale for seeds: `default_total = min(base + 2*(S-1), 20)` external operations, one shared pool. Example: three projects, no user budget, Discovery base 8 -> `min(8 + (3-1)*2, 20) = 12` external operations, freeze at `ceil(0.75 × 12) = 9`. Never give each seed its own full copy of the budget.
- **Local pre-search cap.** `pre_search = base_pre + (S-1)*2` (Quick/ordinary Audit/Discovery) or `+ (S-1)*3` (coverage Audit). Example: three projects, Discovery base pre-search 6 -> `6 + (3-1)*2 = 10` local acquisitions before the first external query or synthesis.
- **Local total cap.** `total_local = base_total + (S-1)*2` (or `*3` for coverage), capped at **20** total local acquisitions. Example: three projects, Discovery base total 12 -> `12 + 4 = 16`. Example: three projects, coverage base total 16 -> `16 + 6 = 22` capped to 20.
- Record the computed cap in every `LOCAL` line as `LOCAL n/cap (S=<S>)` so the arithmetic is auditable.
- A single seed's minimum authoritative set is at most four acquisitions. Once its core mechanism, implemented-vs-planned split, and up to three decision-changing unknowns are established, stop reading that seed regardless of remaining cap.

## Research Contract

- Enforce **transport/sensor precedence**: user-imposed sensor or tool restrictions override platform-routing preferences. When the prompt requires every external operation to go through a named sensor (e.g., Siftline), ALL external search, fetch, and provider calls must use that sensor. Direct curl/wget/gh/webfetch/native API calls are forbidden unless the prompt explicitly permits them. If a native demand channel cannot be reached through the allowed sensor, mark that evidence class unavailable; never bypass the sensor.
- Match the user's language.
- Work within the requested time, cost, and source budget. If none is given, use the selected mode's limits.
- Inspect primary seed material before searching. For a repository, distinguish implemented behavior from plans, examples, and aspirations.
- Prefer primary sources, firsthand user behavior, original discussions, reviews, issues, data, and project artifacts over listicles and search snippets.
- Preserve real links and identify the source behind a search result. Never invent a link, quote, user demand, or level of coverage.
- State when a platform or search capability is unavailable. Do not turn "not found" into "does not exist."
- Apply a final **absence-language review**: "not found in searched channels" never becomes "nonexistent", "nobody wants it", "no competitor", "real gap", "clear whitespace", "under-occupied niche", "无人做"/"市场空白", or any equivalent ecosystem-wide claim. Every absence statement stays bounded by the channels actually searched, the queries used, and the retrieval date: "no close candidate surfaced in channels X with queries Y on date Z." Keep vocabulary and channel failure live — a non-result in a bounded search never proves an unserved opportunity.
- Do not modify seed projects unless the user separately asks for changes.
- Keep mechanism relevance, implementation quality, adoption, and popularity separate. Stars, likes, and followers can discover candidates but do not prove that a mechanism works or fits the seed, nor do they establish demand strength on their own.
- Treat causal success-attribution claims (free distribution, mobile reach, mods/community, creator amplification, low price, timing) as claims, not observations. Require every causal neighbour-success attribution to carry inline evidence state and source: `documented`/`observed` — source, `inferred`, or `unverified`. If it is not tagged, remove the attribution. Define `observed causal attribution` narrowly: direct primary evidence that explicitly links the factor to adoption or outcome, such as a postmortem, experiment, cohort/conversion analysis, or attributable behavioral data. Feature labels, distribution presence, snippets, popularity, anecdotes, and co-occurrence are not observed causal evidence; mark them `inferred` or `unverified`.
- Enforce the **claim–evidence entailment gate** before any retained source backs a claim (see [evidence-integrity.md](references/evidence-integrity.md) §2.1 and [relation-types.md](references/relation-types.md)). Every retained source carries `source_url`, `exact_observed_content`, `proposed_claim`, `primary_relation`, `entailment=direct|analogue-only|unsupported`, `maximum_allowed_wording`, `does_not_support`. A real URL is not enough: the source's own predicate decides the label — item crafting does not entail support-gem skills, a deletion event does not entail mechanism-tied demand, a feature list does not entail adoption. When the predicate differs, set `analogue-only` and cap wording to analogy/attention, or `unsupported` and drop it. A successful neighbor requires direct adoption/outcome evidence; a postmortem title, feature list, stars, HN points, popularity, and marketing copy do not qualify — under weak evidence say `candidate` or `unverified-adoption neighbor`, never `successful neighbor`.
- Treat current implementation, test, release, and numeric market claims as high-risk facts. Verify them at the point of use instead of trusting stale README text, logs, cached tool output, or an earlier search result. Keep a **high-risk claim ledger**: reopen each exact number, date, status, and current-implementation claim at the point of use and record `claim -> exact source location or command -> observed value -> scope/retrieval date -> observed/documented/inferred/unverified/code-verified`. If docs and runtime disagree, report both.
- Treat "read-only" or "do not modify files" as a ban on intentional source and durable-state changes, not automatically as a ban on diagnostic commands. Unless command execution is explicitly forbidden, run the smallest project-native test, check, status, or build command needed to establish a decisive current fact. Avoid commands likely to rewrite source; disclose ordinary caches or generated artifacts when relevant.
- Keep a running **query ledger**. Count one external search, fetch, or provider invocation as one operation. Purely local file reads and commands that do not access a network or provider do not count; network access through local CLIs such as siftline, gh, curl, wget, or provider SDKs counts once per invocation. Retained sources count separately. When the siftline CLI is the sensor, give the research run **one stable `--query-id`**, run every siftline call for that run under it, and read the operation/provider-call counts from the **machine ledger** (`siftline ledger --query-id <id>`) instead of asking the LLM to remember provider call counts. The first external operation must already use the stable run `--query-id`; every siftline call in the run reuses it, and a query ID supplied in the prompt is used exactly. Siftline calls are **strictly serial** — one invocation completes before the next, across providers and before the freeze; never emit a Siftline batch (two or more siftline invocations in one parallel tool call), and a `database is locked` failure counts as one `attempt`. Manual ledger remains the fallback for other tools. Stop before the mode budget unless one named unresolved question can change the decision. Disclose the actual operation count and any overrun reason.
- Maintain a **manual ledger overlay** for Siftline CLI omissions. Keep an internal integer counter — `issued_invocations` — and increment it **before** every siftline invocation, including malformed, Typer, shell-argument, validation, auth, and other attempts that may fail before ledger insertion. The counter is internal state, not an assistant-visible event: never print a `issued_invocations=N` marker before a call, and a marker-only `echo`/`printf`/`true`/comment tool is forbidden. Every siftline invocation visible in the transcript counts once toward `issued_invocations`, starting at 1 for the first call. At final reconciliation, match transcript invocations to machine-ledger entries: `unledgered_attempts` is the `issued_invocations` count missing from the ledger, and `effective_attempts = machine_attempts + unledgered_attempts`. `effective_attempts` drives freeze, reserve, and budget; the machine ledger stays authoritative for `provider_calls` and outcomes. Final disclosure carries the exact names `issued_invocations`, `machine_attempts`, `unledgered_attempts`, `effective_attempts`, `provider_calls`, and `budget`, each with a numeric value — abbreviations (`machine`, `unledgered`, `effective`, `provider`, a bare `budget` with a renamed sibling field, or renamed fields) are invalid; never claim the machine ledger recorded an omitted failure. When the ledger is unavailable (see Siftline Command Contract), report the literal `machine ledger unreadable (no 'ledger' subcommand in installed siftline)` plus the six numeric fields; the reconciliation reasoning is capped at 600 characters and never triggers a re-search or a new branch. The ledger read is a finalization step, never a mandated interim output: under any delivery risk, skip the read and reconcile manually.
- Enforce a **finalization reserve**. Freeze arithmetic uses `effective_attempts` — the machine-ledger `attempts` total plus `unledgered_attempts`, counted from the internal `issued_invocations` counter so every invocation, including auth/validation and parser failures that never reach the ledger, advances the counter — not only `provider_calls`. At `ceil(0.75 × B)` attempts spent, freeze the research frontier and begin synthesis: for budget 8 the freeze point is attempt 6, for budget 12 attempt 9, and immediately after that attempt the frontier is frozen — if the actual freeze attempt is a parser failure or otherwise absent from the ledger, freeze immediately after it and issue no further new branch. No parallel batch may cross the freeze boundary: before issuing a batch, count every invocation it would add; at 5/8, at most one external invocation may be issued. Reserved attempts may only re-run or narrowly verify an exact decisive claim/candidate already present in the current conclusion / internal decision cache; a known-but-not-yet-used candidate, a new query phrase, or a new platform is still a new branch and is forbidden. **After the freeze there are no mandated interim outputs**: no skeleton refresh, no ledger read, and no other assistant-visible checkpoint is required before synthesis. If a ledger read is cheap and useful, take it as a finalization step; under any delivery risk, skip it and reconcile manually. Proceed directly to synthesis; the synthesis deadline above applies.
- **Provider probes are permissions/options, not a checklist.** One provider-availability/auth probe per evidence class unless the prompt or config explicitly indicates another provider is configured, or a second provider uniquely changes a decision. After a missing-key validation failure, pivot to a known-working sensor or mark that evidence class unavailable; do not serially enumerate optional providers just because their names appear in the prompt. Each auth failure still consumes an attempt and advances the freeze counter.
- Keep an **internal decision cache** — an optional, short working outline (e.g., the emerging conclusion and the few open unknowns) that protects against interruption. It is a fallback only, never the deliverable, and it is NOT a process contract: it is never required to be an assistant-visible event, never requires literal field names (`conclusion`/`uncertainty`/`unknown_1..3` are optional), is not required before a second read, needs no freeze-time refresh, and is not a lint or final-review compliance item. It may live in reasoning rather than visible text. Write or update it only when it helps; a checkpoint must never preempt the final answer. Once the freeze happens or time/context/output budget is constrained, stop checkpointing entirely and compose the formal answer as text (Delivery First).
- Enforce a **local-acquisition guard** parallel to the external ledger. Local file reads and diagnostic commands never count as external provider operations, but each counts toward a pre-search cap that bounds broad local browsing. **Every tool invocation is one acquisition**, not every assistant turn or batch: count actual invocations, including ones issued simultaneously in a single parallel batch. A batch may contain at most one seed-local acquisition — seed inventories and reads must be serialized. `ls`, `glob`, `find`, nested/docs listing, `rg` preview, and full read each count separately; if an exact file is known, read it directly rather than `rg`/preview it and then read it, since those are two acquisitions. After the first authoritative seed file, every additional local read or command must name which of the three-or-fewer unknowns it resolves; otherwise skip it. Initialize `inventory_used=false`: the first `ls`/`glob`/`find`/inventory sets it true, and any second root, docs, nested, recursive, or sibling inventory is immediately forbidden — a root glob plus a docs glob is two inventories even when both happen before the first authoritative read — and zero when known file paths already point at the files. Consecutive evidence-acquisition tool calls are capped per mode and per seed count (see Multi-Seed Budget Scaling and [evidence-integrity.md](references/evidence-integrity.md)); the cap is never reset by switching from repository reads to CLI `--help` or status probes. External Siftline/provider commands never count as LOCAL; the final ledger read, required Skill-reference loads, the temporary draft write, and the final linter invocation are finalization/exempt, not seed evidence acquisition.
- Treat the sensor command contract as zero-discovery. Never inspect the Siftline implementation repository or call `--help`, `providers`, or `auth status` to rediscover commands already stated in the Skill or the prompt.
- For **pain or capability coverage audits**, build a **coverage-source checklist before scoring anything**: enumerate every authoritative denominator source in the seed project, extract every source item, keep source-specific denominators separate, and merge them only through an explicit item mapping. Report omitted, duplicate, planned, and ambiguous items. `coverage_by_source` is the complete authoritative denominator inventory: end the final output with the literal `coverage_by_source:` block — one row per source with reconciled source-specific counts (`implemented + partial + planned + absent + unmapped == total`) or `score=unscorable reason=...`; every authoritative `.md` source explicitly called `omitted`, `unextracted`, or `unscorable` gets its own row using its literal relative path or basename. Do not turn every technical document into a denominator merely because it exists, and avoid a duplicate prose checklist once the final block carries the inventory. An authoritative source never extracted is `score=unscorable`, never silently omitted; no single overall percentage without an explicit compatible item mapping.
- Tag every numeric threshold inline at the point it appears, using only the literal formats `N[quoted threshold — exact file/section]` or `N[proposed test threshold]`, e.g. `8 名[quoted threshold — docs/18 §11]`, `90 秒[proposed test threshold]`, `>=60%[quoted threshold — docs/22 §10]`. Abbreviations such as `[quoted — ...]` are invalid; a tag placed before the number is invalid. Each numeric expression or number word that defines sample composition, duration, repetition, pass/fail, scope, or reversal criteria needs its own immediately following tag. Every sample size, range, duration, percentage, ratio, content scope used as a gate, count-based gate, pass/fail count, retry count, time limit, and reversal condition must carry its own immediately adjacent tag. A sentence-end label cannot cover earlier numerals, and a heading-level blanket label covering a whole section is insufficient and invalid. Inspect Arabic numerals and number words whenever they function as criteria. Exact in-project mechanic thresholds and current numeric facts used decisively need an adjacent exact source/state, not an unlabeled paragraph-level blanket. Never imply that an invented threshold already exists. Run a **threshold inventory** pass over every numeral and number word in the test/decision section before final output; the inventory must report `unlabeled=0`. If uncertain whether a number can be tagged, remove the number rather than ship it untagged.
- Report volatile metrics as snapshots or approximations and preserve retrieval date, endpoint/platform, filters, and scope. Do not compare counts produced by different filters as one metric.
- Before output, reconcile every numerator/denominator, never merge incompatible denominators, and recheck each decisive fact against its cited source.
- Preserve `proves X / does not prove Y` wording, the evidence ladder, counterevidence, real links, and coverage-boundary patterns throughout.
- Before Audit mode, or any task with numeric, current-state, or coverage claims, read [evidence-integrity.md](references/evidence-integrity.md) and apply its operational templates.
- **Length contract.** Record `length_cap_chars=N` (or none) before drafting. A Chinese 字 counts as one Unicode code point, and a prompt saying "about" or "approximately 3000 Chinese characters" still sets N=3000. Allocate a per-section character budget before the first draft, targeting <=92 percent of the cap. Every audit/discovery/coverage final lint invocation passes exactly one of `--max-chars N` or `--no-max-chars` — missing both, or passing both, is a hard failure. Lint is one optional final check, never a delivery gate: run it at most once after the complete answer is drafted; if it returns any error, including `MARGIN_EXCEEDED`, do not edit, rerun, or wait for a PASS — immediately deliver the manually-verified answer. A clean `--emit` may be used as the final payload, but no lint result may delay or suppress delivery.

## Siftline Command Contract (zero-discovery)

Use these exact forms; never rediscover them from the Siftline repository, `--help`, or `providers`.

```
siftline --query-id run-2026-08-10-a hn search "<query>" --limit 10
siftline --query-id run-2026-08-10-a github search-repos "<query>" --limit 8
siftline ledger --query-id run-2026-08-10-a --limit 100
```

The ledger reports `attempts` and `provider_calls`; it is the source of truth for provider counts, not the LLM's memory. The ledger is authoritative for `provider_calls` and outcomes; reconcile its `attempts` with the transcript-visible `unledgered_attempts`, and let `effective_attempts` — never machine attempts alone — drive freeze and budget arithmetic. Keep an internal `issued_invocations` counter and increment it before every siftline invocation, starting at 1: a malformed, Typer, shell-argument, validation, auth, or other attempt that never reaches the ledger still counts in `effective_attempts`. The counter is internal only — no assistant-visible `issued_invocations=N` marker and no echo/printf marker; every transcript-visible siftline invocation counts once. Manual ledger is the fallback for non-siftline sensors. Do not chain `--help`/`status` probes or inspect the Siftline repo.

**Ledger failure fallback (one chance, then permanent).** The ledger read is a finalization step, not a mandated interim output: if time, context, or output budget is at risk, skip the read entirely and reconcile manually from the transcript. When a `siftline ledger` read is attempted and fails, handle it by kind, not by blind retry:

- **Definitive failure** — the error is clearly `No such command 'ledger'`, an unknown option, a version-missing ledger, or any "not installed / does not exist" signal (this is the known installed-CLI/source drift). On the FIRST such failure, immediately and permanently switch this run to the **manual ledger overlay**; do not retry `siftline ledger` again this run. Every subsequent read is skipped; the disclosure reports the literal `machine ledger unreadable (no 'ledger' subcommand in installed siftline)` plus the six numeric fields reconciled from the transcript.
- **Transient failure** — `database is locked`, a transport error, or any recoverable condition. Exactly ONE narrow retry is allowed; if it also fails, fall back to the manual overlay for the rest of the run.
- In both cases the failed read still consumed an `attempt` and advances the freeze counter; the fallback must not burn more budget.

## Workflow

### 1. Inspect the Seed

Respect the start gate: when the command contract is supplied, do not inspect cwd, PATH, sensor version, help, providers, auth/status, or the sensor repository. Read the known seed files directly.

Read enough of the supplied article, repository, conversation, or observation to represent it faithfully. For repositories, locate the smallest authoritative set: README, design overview, gameplay/product specification, decisions, roadmap, and current implementation evidence. In Audit mode, establish current state before external research with the single decisive project-native command, not the full test suite.

After the first authoritative seed file, every additional local read or command must name which of the three-or-fewer unknowns it resolves; otherwise skip it. Serialize seed acquisitions — a parallel batch may contain at most one. Initialize `inventory_used=false`; allow at most one directory inventory total across the whole seed, nested directories included — a root listing plus a recursive glob, or a root inventory plus a nested docs listing, is two and is forbidden — and zero when known file paths already point at the files. Once the minimum authoritative seed set establishes the core mechanism, the implemented-vs-planned split, and up to three decision-changing unknowns, stop local browsing — the remaining unknowns belong to external search, not more reads.

For a multi-seed run, allocate the scaled local budget (see Multi-Seed Budget Scaling) and do not starve any seed: read each seed's minimum authoritative set in turn, then move on.

Separate:

- what exists now;
- what is proposed;
- what is inferred;
- what the user wants externally validated.

**Controlled code/test verification (optional, at most one per seed).** If a decisive current-state claim rests solely on `documented` evidence and could change the decision, and only before the freeze, you may perform at most one targeted verification per seed: read one target source file, or run one already-known focused project-native command — never the full suite, never a browse for a test. It must name the unknown it resolves, counts as one local acquisition, and upgrades the claim to `code-verified` for the exact surface exercised only; a unit-test command verifies its tested behavior, not playability, availability, or UX, and a build/typecheck observes only build/typecheck. If no already-known focused command exists, stay `documented`/`unverified` rather than browsing for a test.

### 2. Build an Idea Fingerprint

Express the seed in mechanisms rather than only nouns. Extract:

- problem or job;
- core mechanism and causal story;
- surprising or generative insight;
- repeated loop or behavior;
- intended outcome and audience;
- assumptions that must be true;
- observable costly signals;
- distinctive terms, entities, authors, citations, and phrases;
- unresolved questions that could change the decision.

For a game, also extract player verbs, fantasy, tension, mastery, progression, session shape, social mode, failure/recovery, content production, and likely friction.

For a product, also extract trigger, current workaround, cost of the pain, alternatives, adoption friction, proposed capability, and residual pain after the capability works.

### 3. Expand Relations, Not Just Keywords

In Discovery mode, read [relation-types.md](references/relation-types.md). In Audit mode, read it only when analogues or causal relationships matter. Generate at most four initial branches; use two or three in Audit mode. Candidate branches include origin, same problem under different vocabulary, same mechanism in another domain, implementation, costly demand evidence, failure mode, counterexample, and useful combination.

When the target is an open-source project, Skill, library, research agent, tool landscape, or vaguely remembered artifact, also read [artifact-discovery.md](references/artifact-discovery.md). Treat candidate recall and candidate verification as separate stages; a strong verifier cannot recover a candidate that the search never surfaced.

Keep conceptual similarity separate from demand validation. An elegant analogue or popular article does not prove that users want the seed product.

### 4. Route Each Branch

Before external searching, read [channel-routing.md](references/channel-routing.md)
and [platform-routing.md](references/platform-routing.md). Select one to three
channel IDs and one transport for each; a channel is the evidence source, while
the transport is how it is reached. For Xiaohongshu work, read
[xiaohongshu.md](references/xiaohongshu.md). When RSSHub is selected as a
transport, read [rsshub.md](references/rsshub.md). For each branch, predict
where the strongest evidence should exist and why. Use platform-native sources
when possible: source code and issues for implementation behavior, reviews and
communities for player experience, papers for mechanisms, and official records
for factual claims. This preference never overrides the transport/sensor
precedence rule: if the prompt restricts external operations to a named sensor,
reach native sources only through that sensor or mark the evidence class
unavailable.

Read [query-patterns.md](references/query-patterns.md) only when generating external queries, and follow its **Platform Grammar** explicitly: on HN Algolia start with an entity or 1–2 distinctive terms (AND-like matching — shorten the query on zero hits, avoid sentence-like queries); on GitHub repo search use compact native vocabulary such as `category + mechanism` (e.g., `rust lsp server`), not prose product descriptions. Generate queries in the vocabulary used by people on that platform. Do not send one generic query to every source. Skip both routing references for a purely local Quick lookup or Audit.

### 5. Search as a Frontier

In Discovery mode, start with three or four high-value branches. In Audit mode, start with one to three external branches only after local verification. Use the single highest-information query for a branch before expanding it. After each useful result:

1. identify what was genuinely new;
2. extract new vocabulary, actors, references, products, failure modes, or communities;
3. update the frontier;
4. deepen promising branches and abandon low-yield branches.

Prefer snowballing from strong sources over producing a large result list. Search for disconfirming evidence before concluding.

Track queries against the budget. Abandon a platform/branch after two consecutive empty or low-information results unless it is the only plausible source of decision-critical evidence. For bilingual or region-specific seeds, reserve at least one branch for the audience's native-language platforms and vocabulary.

**Finalization reserve.** At `ceil(0.75 × B)` external attempts spent (B = explicit user budget, or the scaled default), freeze the research frontier and begin synthesis. From that point the remaining operations may only verify decisive facts already used in the conclusion, never open new branches. If time, context, or tool execution is becoming constrained at any point, stop tool use and return a partial but reliable final answer (Delivery First). An incomplete evidence-backed answer is strictly preferred to no final delivery.

Distinguish a transport failure from a vocabulary failure. If an HTML page, raw endpoint, or search UI times out, switch to a structured API, native CLI, contents endpoint, cached artifact, or read-only shallow clone before treating the branch as empty. If the transport works but results are irrelevant, pivot the query vocabulary or discovery channel instead of repeating synonyms.

### 6. Evaluate the Actual Question

For demand, use an evidence ladder rather than mention counts:

1. repeated payment, migration, retention, return, recommendation, or other consequential action;
2. repeated costly workaround, mod, fork, custom tool, organized play, or sustained community labor;
3. repeated specific problem or desired experience across independent users;
4. explicit feature or genre request;
5. likes, views, stars, follows, generic praise, and trend articles.

Treat lower levels as discovery signals, not proof. Record alternative explanations and sampling bias.

**Demand-strength mapping.** The ladder constrains what each level can support:

- levels 1–2, when repeated across independent users, may support **strong consequential demand**;
- repeated independent level 3 supports **moderate problem/experience demand**;
- level 4 is an explicit request only — support for the ask, not demand at scale;
- level 5 is discovery/attention only.

**Level-2/strong consequential demand requires repeated independent user-side costly actions** (paid-for use, rebuilt scripts, migrated workflows). Maintainer longevity, one mod index, one event, stars/forks, or a single project's maintenance do not qualify.

A single source cannot prove repetition; "repeated" means multiple independent instances, not multiple quotes from one thread or one campaign. Never call stars, HN points, likes, upvotes, review totals/ratings, sales ranks, concurrent counts, or popularity strong demand. Review totals, ratings, sales ranks, concurrent player counts, stars, likes, HN points, zero-hit results, and popularity support attention/discovery only — never attach large, small, real, validated, or market-size demand language to them, even with the word "attention" nearby. One small or large analogue cannot cap or size demand for the seed combination. Mechanism existence plus popularity does not validate demand for that mechanism without mechanism-tied consequential behavior. Zero results on HN or any single channel cannot establish audience composition, an absent audience, or that users "are not programmers". Every demand conclusion states what it proves and what it does not prove.

**Level-5 claim verbs.** From level-5 (attention) evidence alone, allowed wording: `获得注意`, `存在可见讨论`, `用于发现候选`, `attention/discovery signal`. Forbidden wording from level-5 alone: `证明需求`, `有真实受众`, `有吸引力`, `证明诉求`, `loop/循环成立`, `validated`, `规模大/小`, `市场大/小`, or any synonym. A game's documented feature set may show that mechanisms coexist, but its popularity metric cannot show that the coexistence caused demand — keep mechanism-existence evidence and demand evidence in separate clauses and separate states. If the conclusion caps evidence at level 5, every table cell and neighbouring paragraph stays at attention/discovery wording. When the whole evidence base is level-5 or attention-only, prohibit mechanism-appeal `medium/high`, mainstream-adoption, competitive-baseline, ecosystem-real-pain, players-obsessed, and successful-neighbor language; use bounded candidates and single-user wording instead.

**Platform-substitution rule.** Prefer native demand channels: for games, Steam reviews/discussions, actual play/wishlist/purchase/retention data, and relevant player communities; for products, paid usage, churn, app-store metrics, and sustained community labor. When those channels are unavailable, HN/GitHub may still discover vocabulary and candidates, but they are not equivalent demand validation. Cap the demand conclusion accordingly and state the missing evidence class explicitly.

For pain coverage, build a matrix:

`pain -> external evidence -> project capability -> implemented/planned/partial/absent -> residual pain -> adoption risk`

Do not count a feature as solving a pain merely because the documentation names it. Before scoring, run the **coverage-source checklist** (see [evidence-integrity.md](references/evidence-integrity.md)): enumerate every authoritative denominator source in the seed (README, design spec, JTBD file, roadmap, issues), extract every source item, keep each source's denominator separate, and merge only through an explicit item mapping; report omitted, duplicate, planned, and ambiguous items.

For games, distinguish curiosity, stated willingness to play, demo engagement, purchase/wishlist behavior, repeated play, retention, recommendation, modding, and community creation.

### 7. Challenge the Emerging Story

Test at least two competing explanations. Check:

- whether sources are independent or repeating one origin;
- whether successful analogues rely on another mechanic, license, audience, or distribution channel;
- whether complaints come from the target audience;
- whether the seed solves the painful job or only one visible symptom;
- whether absence of evidence is caused by poor platform access or weak query vocabulary;
- whether novelty makes the idea interesting but difficult to explain or sell.

Before synthesis, state the strongest evidence against the leading interpretation and the smallest observation that would reverse the recommendation. For validation-oriented Discovery work, maintain one explicit counterevidence branch instead of postponing all skepticism until writing.

### 8. Pass the Evidence Integrity Gate

Before writing the conclusion, apply the templates in [evidence-integrity.md](references/evidence-integrity.md), including the **coverage-source checklist** for pain or capability audits and the **finalization-reserve** rule:

- Tie every decisive local-state claim to a current authoritative file or a project-native command. If reporting a test result, record the exact command, exit status, and final pass/fail summary. Every decisive local-state sentence or bullet must carry an adjacent exact file/section or file:line, or the exact command that produced it; a bare large filename is insufficient, and a section-wide or paragraph-wide state label cannot cover unrelated details. Claims verified by reading the relevant source or running the corresponding focused test may be labeled `code-verified` — for the exact surface exercised only; a build/typecheck observes only build/typecheck and never infers playability, availability, or UX.
- If a prompt says "read-only," do not use that wording as a reason to skip a decisive diagnostic command. If the command is unsafe, expensive, or explicitly forbidden, label the state `documented` or `unverified` instead of presenting it as observed now.
- Never turn one transient or concurrent test failure into project status. Re-run the focused failing suite once and compare it with the latest implementation-status source; if they disagree, report the disagreement instead of choosing a convenient version.
- A passing command observes only its own surface: a build observes build/bundle success, typecheck observes typecheck, and a unit test observes its tested behavior. None of them observes playability, the actual player loop, browser usability, fun, session shape, or implemented user-facing behavior unless that exact surface was launched and exercised. If the game/product UI was not exercised, every `可玩`/`真正可玩`/`current playable loop` claim remains `documented` or `inferred`, regardless of build success. It does not make README-described gameplay, browser usability, player experience, or release claims `observed`; those remain `documented` unless directly exercised in the relevant surface. Use wording such as "documents claim implemented/runnable" unless the relevant surface was actually exercised — a passing unrelated test or an implementation ledger does not observe playability.
- Preserve the scope of external numbers: platform, endpoint, language, region, filter, purchase type, release state, and retrieval date when relevant. Do not compare counts produced by different filters as if they were the same metric.
- Spot-check every source that materially changes the recommendation. Remove or downgrade any claim whose link, quote, count, or relation cannot be reproduced.
- For code or Skill borrowing, verify the applicable license from the repository's actual license file or metadata. Keep README license claims, repository metadata, and a legally applicable license file as distinct evidence when they disagree.
- Avoid temporal or exclusivity superlatives such as "first," "only," "dominant," or "no competitor" unless a primary source or bounded comparison directly verifies them.
- Include a literal, directly usable `https://` (never `http://`) URL beside every external candidate or source actually used to support a claim; a name, bare domain, or path alone is insufficient, and search-result snippets and aggregator labels are not final citations. Evidence imported from a local project's prior research document is either described only as `project-documented prior claim — exact local file/section` or carries both that local source and the original external URL; without the original URL it is not retained external evidence. No external candidate may appear from model memory: it must be in the current run's retained-source ledger, or clearly attributed as a project-documented prior claim with its exact local source and URL. For decisive local claims, give an exact file/section or file:line, or the exact command that produced the fact; a bare large filename is insufficient.
- Run a **cross-section consistency check**: the strongest wording anywhere in the answer controls compliance. A bounded conclusion cannot be followed later by stronger demand, audience, causal, validation, or absence claims in the findings; downgrade the later wording to match the bounded conclusion.
- Keep observation separate from interpretation: `observed now`, `documented`, `inferred`, `unverified`, and `code-verified` are different states.

### 9. Stop Deliberately

Stop when additional searches mostly repeat known mechanisms, the key decision has enough evidence, or the budget is exhausted. After four explored branches, add another only if it can change the recommendation. Continue only when a remaining question could materially change the decision. Honor the finalization reserve: once `ceil(0.75 × B)` external attempts are spent (B = explicit user budget, or the scaled default), freeze the frontier and synthesize; remaining operations only verify decisive facts already used in the conclusion. The freeze is a stop-acquisition signal, not a checkpointing event — from it, go straight to drafting the final text.

**Local-acquisition caps.** Two tiers bound consecutive evidence-acquisition tool calls; required Skill-reference loads, the final machine-ledger read, the temporary draft write, and the final linter invocation never count; external Siftline/provider commands are not LOCAL acquisitions. Maintain an explicit running `LOCAL n/cap` count of every actual local read and diagnostic command, including invocations issued simultaneously in one batch. Caps scale with seed count (see Multi-Seed Budget Scaling). **Pre-search cap** (before the first external query or synthesis): Quick lookup 4, ordinary Audit 6, coverage Audit 8, Discovery 6 — plus `(S-1)*2` (or `(S-1)*3` for coverage). At cap-1, the next acquisition is the single highest-value external query or synthesis. At the cap, a further local test or read is forbidden. **Total cap** (includes targeted post-search verification): ordinary Audit 12, coverage Audit 16, Discovery 12 — plus the same scaling, capped at 20 — preserved only for targeted verification of decisive facts already used in the conclusion, never to reopen a local browse. Neither cap resets by switching from repository reads to CLI `--help` or status probes. A full test suite is forbidden in Discovery mode unless the user explicitly requests that exact suite; if no already-known focused command exists, label runtime state `documented`/`unverified` rather than browsing for a test or running the full suite.

**Total-tool ceiling (Discovery default).** Discovery defaults to a hard ceiling of **32 total tool invocations** and **20 minutes wall clock**. An explicit user time budget always takes priority over these defaults. Do not wait for the hard ceiling before writing:

- **Research soft stop** = the earliest of: the freeze attempt (`ceil(0.75 × B)`), **18 total tool invocations**, or roughly **12 minutes** wall clock.
- At the soft stop, stop all new acquisition immediately and draft the final answer — do not run one more search "to be safe".
- The hard ceiling (32 tools or 20 minutes) means *no more tools, period*: deliver directly.
- If you cannot reliably read a clock, approximate the deadline with tool-count gates: soft stop at the freeze attempt or 18 total tools, hard stop at 32 total tools; drafting starts at the soft stop.

After the total cap or wall-clock budget, stop acquisition and deliver (Delivery First) — an incomplete reliable answer is preferable to no answer.

### 10. Final Review

Run the **draft lint check** only when the complete answer is already drafted as text AND there is still safe margin in the remaining tool/time budget. Lint always serves delivery, never the reverse. Map the profile to the mode: Quick lookup `basic`, ordinary Audit `audit`, Discovery `discovery`, pain/capability coverage Audit `coverage`. The linter contract is zero-discovery: never list `scripts/` or read/grep the linter merely to learn its checks — execute `python3 scripts/lint_draft.py` directly, and inspect its source only after a real unresolvable invocation failure. Write the draft only to a temporary file outside the seed project, then make at most one invocation with exactly one of `--max-chars <cap>` or `--no-max-chars`. On a clean `--emit`, the next and final assistant text may be the emitted stdout byte-for-byte. On any nonzero result, including `MARGIN_EXCEEDED`, stop linting immediately: do not edit the draft, rerun the linter, read a ledger, or wait for a PASS; deliver the manually-verified final answer in the same turn. If time, context, or output budget is constrained, skip lint entirely and deliver directly.

Run these checks on the draft before output:

- **Threshold tag check** — every numeric threshold carries the literal tag `[quoted threshold — exact file/section]` or `[proposed test threshold]` immediately after its numeral or number word; abbreviations and tags placed before the number are invalid. This covers sample sizes, ranges, durations, percentages, ratios, content-scope gates, count-based gates, pass/fail counts, retry counts, time limits, reversal conditions, and decisive in-project mechanic thresholds. The threshold inventory reports `unlabeled=0`; remove any number that cannot be tagged. A heading blanket label is invalid.
- **Absence-language check** — "not found in searched channels" is never restated as "nonexistent", "nobody wants it", "no competitor", "real gap", "clear whitespace", "under-occupied niche", "无人做"/"市场空白", or any equivalent ecosystem-wide claim. Reword any absence statement so it stays bounded by the channels actually searched, the queries used, and the retrieval date. Zero hits on a channel establish nothing about audience composition or absence of users.
- **Demand-strength check** — stars, HN points, likes, upvotes, review totals/ratings, sales ranks, concurrent counts, zero-hit results, popularity, or a single recommendation are never called strong/broad/large/small/real/validated demand or sized as a market, even with the word "attention" nearby; they are attention/discovery signals only unless tied to mechanism-specific consequential behavior. A single analogue never caps or sizes demand for the seed combination. Each demand conclusion states what it proves and does not prove.
- **Profile/structure check** — when the optional lint check ran, its profile matched the mode and it used exactly one of `--max-chars <cap>` or `--no-max-chars`. A lint failure is reported as a process limitation and never blocks the final answer.
- **Margin check** — treat `MARGIN_EXCEEDED` as a warning to keep the answer concise, not as permission to start an edit/lint loop; deliver the best complete answer already drafted.
- **Bounded-gap check** — every "gap", "whitespace", or "under-occupied" claim is worded as "no close candidate surfaced in channels X with queries Y on date Z", with vocabulary and channel failure kept live.
- **Coverage-denominator check** — a coverage Audit ends with the literal `coverage_by_source:` block with source-specific reconciled counts (`implemented + partial + planned + absent + unmapped == total`) or `score=unscorable reason=...`; the block is the last content — prose after the rows fails; an authoritative source never extracted is `score=unscorable`, never silently omitted; the block is the complete authoritative denominator inventory — every authoritative `.md` source explicitly called `omitted`/`unextracted`/`unscorable` has its own row via its literal relative path or basename, incidental technical documents are not denominators merely because they exist, and no duplicate prose checklist once the block carries the inventory; no single overall percentage without an explicit compatible item mapping.
- **Entailment check** — every retained source backing a claim carried the evidence-integrity §2.1 / relation-types fields (`source_url`, `exact_observed_content`, `proposed_claim`, `primary_relation`, `entailment=direct|analogue-only|unsupported`, `maximum_allowed_wording`, `does_not_support`); no candidate is called a successful neighbor without adoption/outcome evidence; real URLs are not treated as sufficient on their own.
- **Serial-Siftline check** — every siftline call used the one stable run `--query-id`, ran strictly serial across providers and before the freeze, no Siftline batch was emitted, and `database is locked` failures counted as `attempts`; an internal `issued_invocations` counter was incremented before every invocation with no assistant-visible `issued_invocations=N` marker and no echo/printf marker, so every transcript-visible siftline invocation counted exactly once; final disclosure carried the exact names `issued_invocations`, `machine_attempts`, `unledgered_attempts`, `effective_attempts`, `provider_calls`, and `budget` with numeric values — abbreviations invalid. When the ledger was unavailable or skipped under delivery risk, the disclosure carried the literal `machine ledger unreadable (no 'ledger' subcommand in installed siftline)` (or a manual reconciliation note) and no third ledger read occurred.
- **Sensor-compliance check** — if the prompt restricted external operations to a named sensor, every external search/fetch/provider call went through that sensor (or the evidence class was marked unavailable); no direct curl/wget/gh/webfetch/native API bypass.
- **Skill-path check** — when the task supplied a Skill path, `<path>/SKILL.md` was read directly; no skill-registry lookup and no listing of `<path>/references` or `<path>/scripts` occurred, and only mode-required named references were loaded.
- **Local-cap check** — the `LOCAL n/cap (S=<S>)` counts counted every actual invocation including parallel-batch ones; no full test suite ran in Discovery mode without an explicit user request for that exact suite; `inventory_used` started false, the first inventory set it true, and any second root/docs/nested/recursive/sibling inventory was forbidden; finalization tools (final ledger read, Skill-reference loads, temporary draft write, final linter invocation) and external Siftline/provider commands never counted as LOCAL. No skeleton ceremony was performed: no assistant-visible skeleton event, no literal-field requirement, no cap-1 skeleton, no freeze refresh — and the provisional internal outline, if kept, was never the final text.
- **Diagnostic-proportionality check** — no diagnostic ran that observed local state had already made irrelevant (no git command after an inventory showed no `.git`); permission verbs were not treated as a checklist.
- **Attribution check** — every causal neighbour-success attribution carries inline evidence state and source (`documented`/`observed` — source, `inferred`, or `unverified`); untagged attributions are removed. Verify the label is correct, not merely present: `observed` requires direct primary evidence explicitly linking the factor to adoption/outcome; feature labels, distribution presence, snippets, popularity, anecdotes, and co-occurrence stay `inferred` or `unverified`.
- **State-label check** — inspect the evidence-producing command and reject any broader state label: a build observes build/bundle success, typecheck observes typecheck, and unit tests observe their tested behavior; none observes playability, the actual player loop, browser usability, fun, session shape, or implemented user-facing behavior unless that exact surface was launched and exercised. A passing build can never be the cited basis for `playable observed`. README-described gameplay, browser usability, player experience, or release claims are never labeled `observed` on the strength of a passing test suite or an implementation ledger; they are worded "documents claim implemented/runnable" and stay `documented` unless directly exercised in the relevant surface. `code-verified` is used only for claims whose relevant source file was actually read or whose focused test was actually run — a build/typecheck alone never upgrades a claim to `code-verified` for playability, availability, or UX.
- **Delivery check** — the final assistant text was the complete formal answer (the emitted payload, or a manually-verified fallback in the same turn), began with a Markdown heading, was not a skeleton/ledger/lint narration/plan/progress note, and was not empty.

## Output

Quick lookup returns the verified fact, source, and any important scope caveat without the full template.

Audit mode returns a compact report led by current verified state: conclusion; observed/documented/inferred/code-verified split; exact commands and results; pain or capability matrix when relevant; external contradictions or gaps; next checks.

Discovery mode returns a compact, decision-oriented report:

1. **Conclusion** — answer the user's actual question and state confidence.
2. **Seed fingerprint** — explain the core loop/mechanism and the most important assumptions.
3. **Research frontier** — show the important relation branches, chosen platforms, and representative queries.
4. **Findings** — provide real links, relation type, key evidence, and why each source changes understanding.
5. **Demand or pain-coverage matrix** — distinguish strong behavior from weak attention and implemented capability from plans.
6. **Contradictions and gaps** — show counterevidence, alternative explanations, unavailable sources, and unanswered questions.
7. **Next three checks** — recommend only the searches, prototypes, or user tests most likely to change the decision.

Every mode that performs external acquisition also includes a compact channel
coverage statement: channels attempted, transport used, successful source
count, unavailable channels, degraded fallbacks, and the evidence class still
missing. Do not claim a channel was covered because a generic search result
mentioned it.

For project or Skill landscapes, lead the findings with a compact verified-candidate table and state the coverage boundary: discovery channels used, important channels unavailable, and unresolved candidates. Do not turn a bounded search into an ecosystem-wide absence claim.

Avoid a wall of links. A source belongs in the final answer only if its relation to the seed and its information gain are explicit.

For multiple seeds, lead with one comparison table and the resource-allocation or prioritization conclusion, then expand only the evidence, risks, or next checks that differ materially per seed. Do not repeat the complete template for every seed; a shared conclusion plus per-seed deltas is the deliverable.
