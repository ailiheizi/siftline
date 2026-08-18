# Evidence Integrity Templates

Operational templates for the hard rules. Load this reference before Audit mode or any task with numeric, current-state, or coverage claims. Apply each template while working, not only at final write-up.

The top rule of the Skill — **Delivery First** — overrides everything in this file when they compete: the run must end with a complete, evidenced formal answer as text, never a skeleton, a plan, an empty text, or a promise. Reasoning is not delivery; a turn that ends with reasoning and no text delivers nothing and is a hard failure. See [SKILL.md](../SKILL.md) "Delivery First".

## 1. Query Ledger

Count one external search, fetch, or provider invocation as one operation. Purely local file reads and commands that do not access a network or provider do not count; network access through local CLIs such as siftline, gh, curl, wget, or provider SDKs counts once per invocation. Retained sources are a separate count from operations.

When the siftline CLI is the sensor, do not count provider calls by memory. Give the whole research run **one stable `--query-id`**, run every siftline call for that run under it, then read the counts from the **machine ledger**:

```
siftline --query-id run-2026-08-10-a github search-repos "<q1>" --limit 8
siftline --query-id run-2026-08-10-a hn search "<q2>" --limit 10
siftline ledger --query-id run-2026-08-10-a --limit 100
```

The ledger summary reports `attempts`, `provider_calls` (external calls actually attempted), and per-outcome counts, so provider call counts are machine-factual, not LLM-remembered. Manual ledger remains the fallback for tools other than siftline.

**Serialization.** Every invocation sharing one `--query-id` is serialized — issue one siftline call, complete it, then issue the next — across providers and before the freeze. Never emit a Siftline batch (two or more siftline invocations in one parallel tool call). Concurrent writes to the same ledger can raise SQLite `database is locked`. Failures that reach ledger insertion — auth, validation, network — are logged as one `attempt` each; pre-parser, Typer, and shell-argument failures may never reach insertion and are absent from the machine ledger, so cover them with the §1.3 manual ledger overlay.

```
operations:
  - #04 | platform=github search | query="..." ; 3 results, 1 new
  - #05 | fetch github.com/x/releases | versions table ; scope-check only
total_operations: 5 / 4 budget
overrun_reason: one named unresolved question could change the decision — "is the shortlisted project legally borrowable?" — so one extra fetch read its license file
retained_sources: 6
```

Stop before the mode budget unless one named unresolved question can change the decision. Disclose the actual operation count and any overrun reason.

## 1.1 Sensor Compliance

When the prompt restricts external operations to a named sensor (e.g., "use Siftline only"), that restriction overrides all platform-routing preferences. Verify before and after the run:

```
restriction: "every external operation must use Siftline"
allowed:     siftline --query-id <id> hn/github search ...
forbidden:   direct curl, wget, gh, webfetch, native API/website calls (unless the prompt explicitly permits them)
unavailable: native demand channel not reachable through Siftline => mark "evidence class unavailable (channel X, query Y, date Z)", never bypass
query-id:    first external call uses the stable run --query-id; every siftline call reuses it; a prompt-supplied ID is used exactly
```

## 1.2 Provider Probes Are Permissions, Not a Checklist

Provider names in a prompt (web, Exa, Tavily, Brave, Google, ...) are options, not a mandate to probe each one. Run **one provider-availability/auth probe per evidence class** unless the prompt or config explicitly indicates another provider is configured, or a second provider uniquely changes a decision. After a missing-key validation failure, pivot to a known-working sensor or mark that evidence class unavailable (`evidence class unavailable — channel X, query Y, date Z`); do not serially enumerate optional providers just because their names appear in the prompt. Every auth/validation failure still consumes an `attempt` and advances the freeze counter.

```
invalid: web probe (no key) -> Exa probe (no key) -> Tavily probe (no key): 3 attempts, no evidence
valid:   one probe for the evidence class -> missing key -> pivot to known-working sensor or mark class unavailable
```

## 1.3 Manual Ledger Overlay (Siftline CLI omissions)

The machine ledger can miss invocations that fail before insertion. Keep an **internal integer counter** — `issued_invocations` — and increment it **before** every siftline invocation: malformed, Typer, shell-argument, validation, auth, and other attempts that may fail before ledger insertion — starting at `issued_invocations=1` for the first call. The counter is internal state, not an assistant-visible event: never print a `issued_invocations=N` marker before a call, and a marker-only `echo`/`printf`/`true`/comment tool is forbidden. Every siftline invocation visible in the transcript counts once toward `issued_invocations`.

At final reconciliation, match transcript invocations to machine-ledger entries. `unledgered_attempts` is the `issued_invocations` count missing from the ledger; `effective_attempts = machine_attempts + unledgered_attempts`. `effective_attempts` drives freeze, reserve, and budget; the machine ledger remains authoritative for `provider_calls` and outcomes. If the actual freeze attempt of 8 is a parser failure or otherwise absent from the ledger, freeze immediately after it and issue no further new branch.

```
issued_invocations:    6   (internal counter, transcript-visible invocations)
machine_attempts:      5   (machine ledger)
unledgered_attempts:   1   (issued_invocations missing from the ledger)
effective_attempts:    6   (drives freeze, reserve, budget)
provider_calls:        4   (machine ledger only)
budget:                8
```

Final disclosure must contain the exact names `issued_invocations`, `machine_attempts`, `unledgered_attempts`, `effective_attempts`, `provider_calls`, and `budget`, each with a numeric value; abbreviations (`machine`, `unledgered`, `effective`, `provider`, a bare `budget` with a renamed sibling field, or renamed fields) are invalid. Never claim the machine ledger recorded an omitted failure. The ledger read is a finalization step, never a mandated interim output: under any delivery risk, skip the read and reconcile manually from the transcript.

### 1.3.1 Ledger Failure Fallback (one chance, then permanent)

The ledger read is a finalization step, not a mandated interim output: if time, context, or output budget is at risk, skip the read entirely and reconcile manually from the transcript. When a `siftline ledger` read is attempted and fails, handle it by kind, never by blind retry:

- **Definitive failure** — the error is clearly `No such command 'ledger'`, an unknown option, a version-missing ledger, or any "not installed / does not exist" signal (the known installed-CLI/source drift). On the FIRST such failure, immediately and permanently switch this run to the **manual ledger overlay**; do not retry `siftline ledger` again this run. Every subsequent read is skipped. Disclose the literal `machine ledger unreadable (no 'ledger' subcommand in installed siftline)` plus the six numeric fields reconciled from the transcript; the reconciliation reasoning is capped at 600 characters and never triggers a re-search or a new branch.
- **Transient failure** — `database is locked`, a transport error, or any recoverable condition. Exactly ONE narrow retry is allowed; if it also fails, fall back to the manual overlay for the rest of the run.
- In both cases the failed read consumed an `attempt` and advances the freeze counter; the fallback must not burn more budget.

```
definitive:  siftline ledger --query-id run --limit 100  -> "No such command 'ledger'"
             => switch to manual overlay NOW; no second ledger call
transient:   siftline ledger --query-id run --limit 100  -> "database is locked"
             => allow exactly one narrow retry; then manual overlay if it fails
```

## 2. High-Risk Claim Ledger

Reopen every exact number, date, status, or current-implementation claim at the point of use. Record internally:

```
claim: "supports macOS"
check: issue #214, line 41 | swift build on branch main
observed: "macos" in supported list, build pass | scope: README + CI, retrieved 2026-08-10 | observed
```

Row format: `claim -> exact source location or command -> observed value -> scope/retrieval date -> observed/documented/inferred/unverified/code-verified`. If docs and runtime disagree, report both.

State wording must not overreach the surface exercised: a build observes build/bundle success only, typecheck observes typecheck, and unit tests observe their tested behavior — none observes playability, the actual player loop, browser usability, fun, session shape, or implemented user-facing behavior unless that exact surface was launched and exercised. If the game/product UI was not exercised, every `可玩`/`真正可玩`/`current playable loop` claim stays `documented` or `inferred` regardless of build success. `documented` facts are phrased "documents claim implemented/runnable", not "it is playable/works", unless the relevant surface was actually exercised. A passing unrelated test or an implementation ledger does not observe playability or user-facing behavior, and a passing build can never be the cited basis for `playable observed`.

**`code-verified` is a narrow state.** It may label a claim only when the relevant source file was actually read, or the corresponding focused test/command was actually run, in this run. It applies to the exact surface exercised only: a unit-test command verifies its tested behavior, not playability, availability, or UX; a build/typecheck observes only build/typecheck and never upgrades a playability, availability, or UX claim to `code-verified`. A claim upgraded from `documented` to `code-verified` must carry the surface in the same sentence (the command, the test, or the source file path); otherwise the label is `CODE_VERIFIED_SCOPE`-invalid. At most one targeted source read or one focused test per seed, pre-freeze, when a decisive current-state claim rests solely on `documented` evidence and could change the decision.

## 2.1 Claim–Evidence Entailment Gate

Before a retained source backs any claim, fill the gate row and let `entailment` decide the cap on wording:

```
source_url:             literal https://...
exact_observed_content: verbatim snippet or observed fact, not a paraphrase
proposed_claim:         what the source is asked to support
primary_relation:       lexical|problem|mechanism|experience|origin|descendant|component|combination|demand|failure|counterexample|boundary
entailment:             direct | analogue-only | unsupported
maximum_allowed_wording: strongest wording the entailment permits
does_not_support:       what the source must NOT be used to claim
```

A real URL plus a snippet is not sufficient — the source's own predicate decides the label: item crafting does not entail support-gem skills; a character-deletion event does not entail mechanism-tied demand; a feature list does not entail adoption. If the predicate differs, set `analogue-only` (cap wording to analogy/attention) or `unsupported` (drop). "Successful neighbor" requires direct adoption/outcome evidence; a postmortem title, feature list, stars, HN points, popularity, and marketing copy do not qualify — without it, say `analogue`, `candidate`, or `unverified-adoption neighbor`.

## 3. Finalization Reserve

Reserve the last 25 percent of the external operation budget for finalization. The freeze counter is `effective_attempts` — the machine-ledger `attempts` total plus `unledgered_attempts` (see §1.3), counted from the internal `issued_invocations` counter so every invocation, including auth/validation and parser failures that never reach the ledger, advances the counter — not only `provider_calls`. At `ceil(0.75 × B)` attempts spent — for budget 8 the freeze point is attempt 6, for budget 12 attempt 9 — freeze the research frontier and begin synthesis; the frontier is frozen immediately after that attempt — if the actual freeze attempt is a parser failure or otherwise absent from the ledger, freeze immediately after it and issue no further new branch. After the freeze:

- the remaining operations may **only re-run or narrowly verify an exact decisive claim/candidate already present in the current conclusion / internal decision cache**;
- a known-but-not-yet-used candidate, a new query phrase, or a new platform is still a new branch and is **forbidden** — reserved budget never opens a new branch;
- **no parallel batch may cross the freeze boundary**: before issuing a batch, count every invocation it would add; at 5/8, at most one external invocation may be issued;
- opening a new branch after the freeze is a **reserve violation** even if disclosed; the final review must confirm none happened;
- **there are no mandated interim outputs after the freeze**: no skeleton refresh, no ledger read, and no other assistant-visible checkpoint is required before synthesis. If a ledger read is cheap and useful, take it as a finalization step; under any delivery risk, skip it and reconcile manually;
- **synthesis deadline**: immediately after the freeze attempt returns, proceed directly to synthesis — do not draft the whole answer inside hidden reasoning first; compose the final answer in visible text and deliver it in the same turn (see [SKILL.md](../SKILL.md) "Delivery First"). If output budget is short, deliver the shortened-but-complete answer. A turn that ends with reasoning and no text delivers nothing and is a hard failure;
- if time, context, or tool execution is becoming constrained at any point, **stop tool use and return a partial but reliable final answer**; an incomplete evidence-backed answer is strictly preferred to no final delivery.

```
budget: 8 external operations (explicit user budget, never scaled)
freeze_counter: effective_attempts = machine_attempts + unledgered_attempts (internal issued_invocations drives the count), not provider_calls
freeze_point: attempt 6 (ceil(0.75 x 8)); frontier frozen immediately after attempt 6
batch_boundary: at 5/8, at most one external invocation per batch
reserved 7-8: only re-verify #2's decisive star count and #4's license file, both already
              in the current conclusion; the "mobile UX" branch stayed unopened
```
```
verification_only:
  - re-fetch github.com/x/stargazers to confirm count used in the conclusion
deferred:
  - mobile UX branch: frozen; noted in "next three checks", not searched
```

### 3.1 Final Payload

Record `length_cap_chars=N` (or none) before drafting — a Chinese 字 counts as one Unicode code point, and a prompt saying "about" or "approximately 3000 Chinese characters" still sets N=3000. Allocate a per-section character budget before the first draft, targeting <=92 percent of the cap. Select the linter profile by mode (audit/discovery/coverage) and emit via `--emit`, passing exactly one of `--max-chars N` or `--no-max-chars` — missing both, or passing both, is a hard failure, and a clean `--emit` is impossible without the explicit choice. When `--max-chars N` is used, the emit additionally passes `--min-margin-pct 8`: a clean emit requires length `<= N × 0.92`, and `MARGIN_EXCEEDED` means trim scope, not shave the cap — this keeps the answer from being pinned to the ceiling. **Lint runs only after the complete answer is drafted as text and only while there is safe margin in the remaining tool/time budget: by default at most one non-emit lint plus one clean `--emit`; if that emit fails, make at most one revision and re-emit once — never iterate for a PASS.** After a clean `--emit` tool result, the next and final assistant text is the emitted stdout **byte-for-byte** — a `Lint passed` narration line, a `Final answer` narration line, a fence, PASS narration, a process note, or any prefix or suffix is a hard failure. Never end on progress prose or ledger output. **When the soft deadline is reached, or remaining tools/time are insufficient for lint+emit, skip the ledger read, lint, and emit entirely and deliver the manually-verified final text in the same turn (Delivery First)** — the final text is never delayed or dropped for a lint PASS.

## 4. Coverage-Source Checklist

For pain or capability coverage audits, build the checklist **before scoring anything**:

1. Enumerate every authoritative denominator source in the seed project: README, design/product specification, JTBD file, roadmap, issue backlog, feature matrix, docs index. A JTBD file is an authoritative source even when the README is not — missing it understates the denominator.
2. Extract every source item from each source, keeping **source-specific denominators separate** (e.g., README claims 10 capabilities, spec claims 7, JTBD lists 4 jobs).
3. Merge denominators **only through an explicit item mapping** (item-to-item identity), never by summing source-specific counts or picking the largest.
4. Report `omitted` (source never enumerated), `duplicate` (same item in multiple sources), `planned` (documented but not implemented), and `ambiguous` (cannot be resolved without another authoritative file).

```
coverage-sources:
  - README.md      -> denominator 10 (capability bullets)
  - SPEC.md        -> denominator 7  (capability bullets)
  - JTBD.md        -> denominator 4  (jobs-to-be-done)
mapping: 3 README items == 2 SPEC items via explicit identity map (merged, not summed)
omitted: none
duplicate: "sync" appears in README + SPEC -> counted once
planned: "mobile widget" (SPEC only)
ambiguous: "custom reports" — README implies full, SPEC lists read-only
```

The scored numerator/denominator must reference this checklist so a reader can see which sources were counted and which were missed.

The final output must end with the literal block — the complete authoritative denominator inventory — one row per source, keeping source denominators separate and reconciling category sums (`implemented + partial + planned + absent + unmapped == total`). The block is the last content: prose after the rows fails. Every authoritative `.md` source explicitly called `omitted`, `unextracted`, or `unscorable` gets its own row using its literal relative path or basename; do not turn every technical document into a denominator merely because it exists, and prefer the block over a duplicate prose checklist. Authoritative sources that were never extracted are `score=unscorable` with a reason, not silently omitted. No single overall percentage unless an explicit compatible item mapping exists:

```
coverage_by_source:
  - source=<name> total=N implemented=N partial=N planned=N absent=N unmapped=N
  - source=<name> score=unscorable reason=<why>
```

## 5. Threshold Provenance

Tag **every** threshold in research output as one of:

- **quoted threshold with source** — `[quoted threshold — exact file/section]`, taken from a project evaluation document or source, with the exact location;
- **proposed test threshold** — `[proposed test threshold]`, created by the agent, never implied to already exist.

Run the **threshold tag check** as part of the final review: if any threshold in the output is not tagged either way, treat it as an unlabeled invented threshold and fix or remove it.

Use only the literal formats `N[quoted threshold — exact file/section]` and `N[proposed test threshold]`, with the tag **immediately after** the numeral or number word: `8 名[quoted threshold — docs/18 §11]`, `90 秒[proposed test threshold]`, `>=60%[quoted threshold — docs/22 §10]`. Abbreviations such as `[quoted — ...]` are invalid, and a tag placed before the number is invalid. Each numeric expression or number word that defines sample composition, duration, repetition, pass/fail, scope, or reversal criteria needs its own immediately following tag.

Tag each numeric threshold **inline** at the point it appears, adjacent to the numeral. A single heading-level blanket label (e.g., "all criteria are proposed test thresholds") covering a whole section is insufficient and invalid — every number still needs its own inline tag, and a sentence-end label cannot cover earlier numerals. Inspect Arabic numerals and number words whenever they function as criteria.

The tag requirement covers every sample size, range, duration, percentage, ratio, content scope used as a gate, count-based gate, pass/fail count, retry count, time limit, and reversal condition. Exact in-project mechanic thresholds and current numeric facts used decisively (for example a game's `Heat >= 10` rule or a 2-second protection window) need an adjacent exact source/state, not an unlabeled paragraph-level blanket.

Before final output, run a **threshold inventory**: pass over every numeral and number word in the test/decision section (sample sizes, ranges, durations, percentages, ratios, content-scope gates, count-based gates, pass/fail counts, retry counts, time limits, reversal conditions), confirm each carries an immediately following tag, and report `unlabeled=0`. If uncertain whether a number can be tagged, remove the number rather than ship it untagged.

```
- Quoted: "a candidate passes only with >= 100k stars" => from the project's evaluation document, retrieved 2026-08-10
- Agent-created: "engagement >= 3 messages/week" => label `proposed test threshold`; do not present it as if the source already defined it
- Unlabeled: "must have 5+ contributors" => INVALID; tag as quoted-with-source or `proposed test threshold`
- Inventory miss: "n=12 participants [proposed test threshold], 40 min sessions" => 40 min untagged => INVALID; tag it
- Sentence-end miss: "10 participants, 60%, >=1 retry [proposed test threshold]" => first three numerals untagged => INVALID; tag each
- Mechanic fact miss: "Heat >= 10 triggers overtime; a 2-second protection window follows" => untagged in-project facts => INVALID unless each carries its exact source/state
```

## 6. Absence-Language Review

Run the **absence-language check** as part of the final review. `not found in searched channels` never becomes an ecosystem-wide claim. Allowed bounded forms; forbidden restatements:

```
allowed: "no repo surfaced via GitHub code search (2026-08-10, q='...')"
allowed: "no close candidate surfaced in channels X with queries Y on date Z"
allowed: "none of the 12 retained sources mentions this capability"
forbidden: "nobody wants it"
forbidden: "no competitor exists"
forbidden: "it is nonexistent"
forbidden: "the ecosystem has no equivalent"
forbidden: "real gap"
forbidden: "clear whitespace"
forbidden: "under-occupied niche"
forbidden: "无人做" / "市场空白"
```

Every absence statement stays bounded by the channels actually searched, the vocabulary used, the queries, and the retrieval date. A non-result in a bounded search never proves an unserved opportunity; keep vocabulary and channel failure live.

## 7. Volatile Metrics

Use snapshot or approximate wording. Preserve retrieval date, endpoint/platform, filters, and scope.

```
~1.4k stars (GitHub API, 2026-08-10, all languages, no filter) — snapshot, not a trend
```

## 8. Coverage Reconciliation

Before output, reconcile every numerator/denominator. Never merge incompatible denominators. Recheck each decisive fact against its cited source.

```
covered 12/18 pains -> verify numerator: 12 sources with behavioral evidence;
denominator: 18 pains from seed matrix (compatible). Do not add search-hit totals.
```

## 9. Preserved Patterns

Keep from SKILL.md: `proves X / does not prove Y` wording, the evidence ladder, counterevidence, real usable links, and the coverage-boundary statement. A template row does not replace any of these. Apply the demand-strength mapping and platform-substitution rule from SKILL.md section 6: levels 1–2 (when repeated across independent users) may support strong consequential demand, repeated independent level 3 supports moderate problem/experience demand, level 4 is an explicit request only, level 5 is discovery/attention only; a single source never proves repetition; stars, HN points, likes, and one recommendation are never strong demand. Level-2/strong consequential demand requires **repeated independent user-side costly action** (paid-for use, rebuilt scripts, migrated workflows) — maintainer longevity, one mod index, one unusual event, stars/forks, or a single project's maintenance do not qualify.

**Level-5 attention snapshots.** Review totals, ratings, sales ranks, concurrent counts, stars, likes, HN points, zero-hit results, and popularity are level-5 attention snapshots. Unless tied to mechanism-specific consequential behavior (e.g., a review describing repeated use of the core loop), they cannot support "strong", "broad", "large", "small", "real", "validated", or market-size demand by themselves — even when the word "attention" appears nearby. Zero hits on a channel establish nothing about audience composition, an absent audience, or that users "are not programmers". A single small or large analogue never caps or sizes demand for the seed combination. Mechanism existence plus popularity does not validate demand for that mechanism without mechanism-tied consequential behavior.

**Level-5 claim verbs.** From level-5 (attention) evidence alone, allowed wording: `获得注意`, `存在可见讨论`, `用于发现候选`, `attention/discovery signal`. Forbidden wording from level-5 alone: `证明需求`, `有真实受众`, `有吸引力`, `证明诉求`, `loop/循环成立`, `validated`, `规模大/小`, `市场大/小`, or any synonym. A game's documented feature set may show that mechanisms coexist, but its popularity metric cannot show that the coexistence caused demand — keep mechanism-existence evidence and demand evidence in separate clauses and states. If the conclusion caps evidence at level 5, every table cell and neighbouring paragraph stays at attention/discovery wording. When the whole evidence base is level-5 or attention-only, prohibit mechanism-appeal `medium/high`, mainstream-adoption, competitive-baseline, ecosystem-real-pain, players-obsessed, and successful-neighbor language; use bounded candidates and single-user wording instead.

```
snapshot:   "~4k reviews (Steam app page, 2026-08-10)" => attention/interest only
not proven: "therefore strong demand for the core loop" => INVALID without mechanism-tied behavior
invalid:    "~4k reviews is at most attention, but this is still a major-need market" => INVALID; size language contradicts the bounded label
proof:      "review #1 (link) and review #2 (link) each describe X sessions/week with the core loop" => level-3 evidence
```

**Causal attribution.** Every causal neighbour-success attribution (free distribution, open source, community, scale, multiplayer, mobile reach, creator amplification, low price, timing) must carry inline evidence state and source: `documented`/`observed` — source, `inferred`, or `unverified`. Untagged attributions are removed. Define `observed causal attribution` narrowly: direct primary evidence that explicitly links the factor to adoption or outcome — a postmortem, experiment, cohort/conversion analysis, or attributable behavioral data. Feature labels, distribution presence, snippets, popularity, anecdotes, and co-occurrence are not observed causal evidence; mark them `inferred` or `unverified`. The final review verifies the label is correct, not merely present.

```
attribution: "its success came from being open source" => INVALID untagged
tagged:      "its success is attributed to open source (inferred; no source, retrieved 2026-08-10)"
tagged:      "free distribution drove adoption (observed — official postmortem, retrieved 2026-08-10)"
invalid:     "open source drove adoption (observed — repo shows open-source license)" => INVALID; presence of a license is not observed causal evidence
```

**Citations.** Every retained external source or candidate actually used to support a claim carries a literal, directly usable `https://` (never `http://`) URL beside the claim; a name, bare domain, or path alone is insufficient, and search-result snippets and aggregator labels are not final citations. Evidence imported from a local project's prior research document is either described only as `project-documented prior claim — exact local file/section` or carries both that local source and the original external URL; without the original URL it is not retained external evidence. No external candidate may appear from model memory: it must be in the current run's retained-source ledger or clearly attributed as a project-documented prior claim with its exact local source and URL. Every decisive local claim — especially exact counts and mechanic thresholds — carries an exact file/section or file:line, or the exact command that produced it, adjacent to the claim; a bare large filename is insufficient, and a section-wide or paragraph-wide state label cannot cover unrelated details.

**Cross-section consistency.** The strongest wording anywhere in the answer controls compliance. A bounded conclusion is never followed later by stronger demand, audience, causal, validation, or absence claims in the findings; downgrade the later wording to match the bounded conclusion. Reject: "all evidence is level-5" followed by "proves real audience"; "browser untested/documented" followed by "playable loop observed because the build passed"; "no result in HN/GitHub" followed by audience or market-size inference.

## 10. Local-Acquisition Guard

Local file reads and diagnostic commands never count as external provider operations (ledger unchanged), but they count toward a separate finalization-safety checkpoint. Maintain an explicit running `LOCAL n/cap (S=<S>)` count (n = local acquisitions so far, cap = mode pre-search cap scaled for the seed count) of every actual tool invocation, including invocations issued simultaneously in a single parallel batch — a batch is not one acquisition. The cap bounds consecutive evidence-acquisition tool calls before synthesis; required Skill-reference loads, the final machine-ledger read, the temporary draft write, and the final linter invocation are exempt finalization steps, and external Siftline/provider commands are not LOCAL acquisitions at all — only seed-local evidence acquisition counts: the one allowed inventory, local seed reads, and local diagnostic commands. Absolute Skill paths are zero-discovery: read `<path>/SKILL.md` directly — never the skill registry, never a listing of `<path>/references` or `<path>/scripts` — and load only the mode-required named references. Marker-only `echo`/`printf`/`true`/comment tools that carry no information are forbidden as progress signals. Initialize `inventory_used=false`: the first `ls`/`glob`/`find`/inventory sets it true, and any second root, docs, nested, recursive, or sibling inventory is immediately forbidden — a root glob plus a docs glob is two inventories even when both happen before the first authoritative read. Reaching the cap does **not** reset if you switch from repository reads to CLI `--help` or status probes.

### 10.0 Multi-Seed Cap Scaling

For **S seeds sharing one budget**, scale the local caps before any read: `pre_search = base_pre + (S-1)*2` (Quick/ordinary Audit/Discovery) or `+ (S-1)*3` (coverage Audit); `total_local = base_total + (S-1)*2` (or `*3` for coverage), capped at 20 total local acquisitions. **An explicit user external budget `B` is never scaled** — it is the hard shared cap across all seeds, freeze at `ceil(0.75 × B)`. Only when no budget is given does the default external total scale: `default_total = min(base + 2*(S-1), 20)` with Quick base 2, Audit base 4, Discovery base 8. Never give each seed its own full copy of a budget — one shared pool. A single seed's minimum authoritative set is at most four acquisitions; once its core mechanism, implemented-vs-planned split, and up to three decision-changing unknowns are established, stop reading that seed regardless of remaining cap.

```
explicit budget B=12 (user-given, never scaled): freeze at ceil(0.75*12) = 9
S=3 Discovery default external:  base 8 -> min(8 + (3-1)*2, 20) = 12, freeze at attempt 9
S=3 Discovery pre-search: base 6 -> 6 + 4 = 10
S=3 Discovery total:     base 12 -> 12 + 4 = 16
S=3 coverage total:      base 16 -> 16 + 6 = 22 -> capped at 20
```

```
pre-search caps (before the first external query or synthesis), S=1:
  Quick lookup        4
  ordinary Audit      6
  coverage Audit      8
  Discovery           6
total caps (adds only targeted post-search verification), S=1:
  ordinary Audit     12
  coverage Audit     16
  Discovery          12
exempt: required reference loads, final siftline ledger read
```

```
LOCAL 1/10 (S=3) | read README (seed 1)        -> first authoritative read; read design overview next
LOCAL 2/10 (S=3) | read design overview          -> named unknown resolved
LOCAL 9/10 (S=3) | cap-1 reached                 -> next acquisition = single highest-value external query
LOCAL 10/10 (S=3) | pre-search cap reached       -> no more local reads; run the one decisive external query or synthesize
```

`ls`, `glob`, `find`, nested/docs listing, `rg` preview, and full read each count separately, and seed inventories/reads must be serialized — a parallel batch may contain at most one seed-local acquisition. If an exact file is known, read it directly rather than `rg`/preview it and then read it. A root listing plus a recursive glob is two inventories and violates the one-inventory limit.

```
INVALID batch: [glob **/*.md] + [ls .] issued together -> two acquisitions, and root+recursive glob is two inventories
INVALID pair:  [rg "Heat" src/] then [read src/game.py] on a known path -> two acquisitions; read the known file once
VALID:         [read README] -> [read design/spec.md] (serialized, each resolving a named unknown)
```

Operational rules:

- At cap-1, the next acquisition is the single highest-value external query or synthesis. At the cap, a further local test or read is forbidden. No skeleton requirement applies at any cap.
- A full test suite is forbidden in Discovery mode unless the user explicitly requests that exact suite. If no already-known focused command exists, label runtime state `documented`/`unverified` rather than browsing for a test or running the full suite.

```
pre-search cap reached (ordinary Audit, 6 calls) -> no more local reads:
  - move to the one highest-value unresolved external query, or synthesize
  - targeted post-search verification only within the total cap (12);
    never reopen a local browse
```

### 10.1 Internal Decision Cache (optional; never a ceremony)

Keep an **internal decision cache** — an optional short working outline (e.g., the emerging conclusion and the few open unknowns) that protects against interruption. It is NOT a process contract:

- it is never required to be an assistant-visible event — it may live in reasoning rather than visible text;
- it never requires literal field names (`conclusion`/`uncertainty`/`unknown_1..3` are optional);
- it is not required before the second seed read, at any cap, or at the freeze;
- it needs no freeze-time refresh and no periodic refresh;
- it is not a lint or final-review compliance item.

The cache is a **fallback, not the deliverable**. It must never be the final text, and a checkpoint must never preempt the final answer. Once the freeze happens or time, context, or output budget is constrained, stop checkpointing entirely and compose the complete answer delivered as text in the same turn (see [SKILL.md](../SKILL.md) "Delivery First"). Ending the run on the bare outline is a hard failure.

```
optional cache (may live in reasoning):
  conclusion:  "the seed mechanism is X; strongest supporting relation is Y"
  uncertainty: "whether demand is real — I only have analogue evidence"
  unknown_1:   "one primary user pain report from community Z"
```

### 10.2 Minimum Seed Set

Stop broad local browsing once the minimum authoritative seed set establishes the core mechanism, the implemented-vs-planned split, and up to three decision-changing unknowns. After the first authoritative seed file, every additional local read or command must name which of those unknowns it resolves; otherwise skip it. Initialize `inventory_used=false` and allow at most one directory inventory total across the whole seed, nested directories included — the first `ls`/`glob`/`find`/inventory sets `inventory_used=true`; a second root, docs, nested, recursive, or sibling inventory is immediately forbidden, so a root glob plus a docs glob is two inventories even when both precede the first authoritative read — and zero inventories when known file paths already point at the files. Serialize seed acquisitions: a parallel batch may contain at most one seed-local read or inventory. If an exact file is known, read it directly; an `rg`/preview pass plus the read is two acquisitions.

```
named_unknown_1: "does the roadmap ship the mobile widget in v0.2?" -> read roadmap.md
named_unknown_2: "is 'sync' implemented or only documented?"       -> read IMPLEMENTATION-STATUS.md
unanswered:      "current star count" -> external, not a local read
unresolved_read: "read docs/architecture.md" -> resolves no named unknown -> SKIP
```

### 10.3 Total-Tool Failsafe

There is no periodic-refresh checkpoint. After 8 consecutive acquisition tool calls, evaluate whether the emerging conclusion is still clear; if not, tighten the decision cache (internally, never as a mandated visible block) or synthesize — do not pause to emit a refresh event. Discovery additionally defaults to a hard ceiling of **32 total tool invocations** and **20 minutes wall clock**; an explicit user time budget takes priority. Do not wait for the hard ceiling before writing:

- **Research soft stop** = the earliest of: the freeze attempt (`ceil(0.75 × B)`), **18 total tool invocations**, or roughly **12 minutes** wall clock. At the soft stop, stop all new acquisition immediately and draft the final answer.
- If you cannot reliably read a clock, approximate with tool-count gates: soft stop at the freeze attempt or 18 total tools, hard stop at 32 total tools; drafting starts at the soft stop.

After the total cap or wall-clock budget, stop acquisition and deliver — an incomplete reliable answer is preferable to no answer.

```
total_cap_reached (Discovery: 32 tools / 20 min): stop acquisition and deliver the final text in the same turn
soft_stop (freeze attempt, 18 tools, or ~12 min): stop new acquisition and start drafting now
```

### 10.4 Diagnostic Proportionality

Permission verbs (version, test, build, status, git log) are permissions, not a checklist. Run only the decisive project-native command, and never run a diagnostic that observed local state has already made irrelevant: after an inventory shows no `.git` directory, run no git command; if VCS state cannot change the research decision, skip git entirely. A diagnostic made irrelevant by what you already observed adds an acquisition without adding evidence.

```
invalid: [inventory shows no .git] then [git log] -> redundant diagnostic; skip
valid:   [inventory shows .git] and VCS state can change the decision -> one decisive git status/log command
```
