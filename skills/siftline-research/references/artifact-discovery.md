# Artifact Discovery

Use this reference when the user wants to find or compare open-source projects, Skills, libraries, research agents, tools, or a vaguely remembered artifact. The goal is high recall before selective verification, without degrading into a large unranked list.

## Separate Recall from Verification

Run two distinct passes:

1. **Candidate recall** — collect a bounded pool from multiple discovery channels. Record why each candidate surfaced; do not yet claim that it works or fits.
2. **Candidate verification** — read primary artifacts for the few candidates most likely to change the decision. Reject or downgrade candidates that cannot be reproduced.

A polished analysis of four candidates is still weak if the most relevant candidate was never surfaced.

## Build a Discovery Lattice

Use at least two channels for a landscape task and three when the remembered name or category is uncertain:

| Channel | What it finds | Typical route |
| --- | --- | --- |
| job and mechanism vocabulary | same problem under different names | repository and Web search using the seed fingerprint |
| ecosystem-native signatures | artifacts that generic Web search misses | filename/path search such as `SKILL.md`, package manifests, topics, registries, and known directories |
| curated collections | category vocabulary and small projects | awesome lists, marketplaces, newsletters, maintainers' lists |
| origin and citation graph | predecessors and descendants | README citations, papers, forks, dependencies, releases, and linked projects |
| maintainer social graph | projects selected by people with relevant taste | stars, follows, contributions, organizations, and collaborators |
| regional vocabulary | projects discussed outside English search results | native-language terms, communities, and local directories |

Use the maintainer social graph only as a discovery sensor. A star or follow is an edge, not a quality judgment. Start from at most two strong origins and one hop; expand another hop only when it produces distinct high-value candidates within budget.

## Search Ecosystem-Native Artifacts

For GitHub and Skill discovery, combine repository search with file and structure signatures. Useful patterns include:

- the job or mechanism plus `skill`, `agent`, `workflow`, `research`, `discovery`, or ecosystem name;
- exact filenames and likely paths: `SKILL.md`, `.codex-plugin/plugin.json`, `agents/`, `skills/`, `README.md`;
- topics, package metadata, dependency names, citations, forks, and author organizations;
- known Skill directories or marketplace indexes, followed by the original repository;
- a strong origin's starred repositories, follows, contributions, and README links.

Do not count a search-result snippet, directory entry, or generated summary as verification. Resolve the original repository and primary file.

Prefer structured access over scraping repository pages. For GitHub, use repository/code search and the REST or GraphQL API first; use the contents API or raw files for primary artifacts; fall back to a read-only shallow clone when raw delivery fails. Record transport failure separately from an empty search result.

If an exact category query yields fewer than three relevant candidates, assume vocabulary may be wrong. Pivot from category nouns to behavior phrases found in repository descriptions and user jobs, for example:

- `finds and validates open-source GitHub repos for your project`;
- `analyze any GitHub project agent skill`;
- `graph-based discovery of open-source projects`;
- `repository recommendation skill license activity`;
- the desired output such as `top repositories quickstart`, `project landscape`, or `structured repository analysis`.

Before claiming reasonable landscape coverage, obtain candidates from both a mechanism/job query and an ecosystem-native or graph/directory channel. If one channel is unavailable, make that missing recall path explicit.

## Disambiguate Fuzzy Memories

Turn an incomplete clue into separate hypotheses before searching:

- **name hypothesis** — product, repository, acronym, translation, pun, or visual motif;
- **author hypothesis** — handle, display name, avatar, organization, or social post;
- **function hypothesis** — what the artifact actually did;
- **association hypothesis** — two memories may have been combined.

Search and label these hypotheses independently. A lexical match is not an identity match; a functional analogue is not proof that it is the remembered artifact. Report the best confirmed match, the best functional match, and unresolved identity evidence separately.

## Maintain a Candidate Ledger

Keep a lightweight internal ledger during research:

`candidate -> discovery channel -> relation to seed -> seen/verified/rejected/unresolved -> primary URL -> artifact type -> license evidence -> adoption signal -> decisive note`

Use it to deduplicate candidates and preserve promising unexplored leads. Keep rejection reasons short: wrong job, only lexical similarity, unavailable primary artifact, stale/inapplicable implementation, license mismatch, or no decision impact.

## Verify Before Recommending

For shortlisted repositories, verify the smallest applicable primary set:

- repository existence and canonical URL;
- actual artifact type: Skill, prompt package, framework, service, or ordinary application;
- original `SKILL.md`, README, manifest, or key implementation file;
- root or applicable subdirectory license and any split-license caveat;
- current maintenance or release state only when it affects adoption;
- mechanism claimed by the documentation versus mechanism visible in files;
- relationship bridge, borrowable design, and boundary.

Treat popularity separately:

- **mechanism relevance** — does it solve the same job or implement a useful component?
- **implementation evidence** — is the mechanism visible and reproducible?
- **adoption signal** — stars, users, releases, contributors, or downstream use.

A zero-star repository may contain a useful mechanism but has no community validation. A high-star repository may be irrelevant or unproven for the seed.

## Stop and Report Coverage Honestly

Stop recall when new channels repeat the same candidates or vocabulary, then spend remaining budget on primary-source verification. In the final report state:

- channels and representative queries used;
- verified, rejected, and unresolved high-impact candidates;
- unavailable channels such as private communities, X search, image/avatar search, or authenticated APIs;
- why the retained candidates change the decision;
- why “not found” remains bounded by the searched channels.

Prefer three to eight verified candidates over a long list. Preserve unresolved leads only when another check could materially change the recommendation.
