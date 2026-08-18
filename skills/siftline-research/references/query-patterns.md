# Query Patterns

Generate a small query lattice from the seed fingerprint. Replace brackets with seed-specific language and adapt syntax to the chosen platform.

## Origin and Vocabulary

- `"[distinctive phrase]"`
- `"[mechanism]" history OR origin OR coined`
- `"[claim]" study OR evidence OR experiment`
- `[author/entity] references influences`
- `[formal term] [plain-language symptom]`

## Same Problem, Different Language

- `"[pain symptom]" workaround`
- `"[failure event]" frustrated OR switched OR abandoned`
- `how do people [job] without [proposed solution]`
- `"I built" [workaround] because`
- `"wish there was" [outcome]`

## Mechanism and Cross-Domain Analogy

- `[mechanism] in [adjacent domain]`
- `[observable behavior] as signal of [latent state]`
- `[constraint] reveals [preference/risk/event]`
- `[seed mechanism] alternative terminology`
- `[mechanism A] compared with [mechanism B]`

## Implementation and Descendants

- `[mechanism] open source GitHub`
- `[mechanic] game design postmortem`
- `[feature] implementation issue OR RFC OR architecture`
- `site:github.com [distinctive mechanism]`
- `[project/category] migration case study`

## Demand and Costly Signals

- `"switched to" [alternative] because [pain]`
- `"paid for" [outcome]`
- `"made a mod" [missing mechanic]`
- `"built a script" [repeated job]`
- `[game mechanic] Steam review replayability`
- `[genre combination] demo feedback OR playtest`
- `[product pain] manual process hours`

## Failure, Boundary, and Counterevidence

- `[similar product/game] failed why`
- `[mechanism] limitations OR criticism OR negative results`
- `"stopped playing" [mechanic/genre] because`
- `"uninstalled" [game/product] [friction]`
- `[claim] replication OR counterexample`
- `[successful analogue] depends on [suspected hidden factor]`

## Platform Grammar

- **HN Algolia** matches all terms (AND-like): start with an entity or 1–2 distinctive terms; on zero hits, shorten the query before spending another branch. Avoid sentence-like queries.
- **GitHub repo search** uses compact native vocabulary — `category + mechanism` (e.g., `rust lsp server`) — not prose product descriptions.
- All invocations under one Siftline `--query-id` are serial, never batched.

## Query Progression

1. Start with one exact phrase and one broad mechanism query.
2. Learn the native vocabulary used by the strongest result.
3. Search the newly discovered term on its authoritative platform.
4. Search one demand branch and one failure/counterexample branch.
5. Follow named authors, cited works, projects, games, mods, and communities.
6. For bilingual or regional seeds, repeat the strongest branch using native audience vocabulary, not a literal machine translation.
7. Stop a platform/branch after two consecutive empty or low-information results.
8. Stop repeating synonyms once results share the same sources and mechanisms.

Record representative queries in the report, including failed queries when the missing evidence matters. Search snippets are discovery aids, not final evidence.
