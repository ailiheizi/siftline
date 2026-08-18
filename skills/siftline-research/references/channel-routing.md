# Channel Routing and Adapter Contract

Use this reference before any external acquisition. A channel is the source
family that can contain the needed evidence. A transport is the mechanism used
to reach it. An adapter is either a dedicated Skill or a reference-backed
procedure that knows the channel's query grammar and failure modes.

## Selection Algorithm

1. Name the exact evidence question and evidence class.
2. Choose the highest-fit channel, not the easiest generic search engine.
3. Resolve an adapter: an available channel Skill first, then the matching
   reference in this Skill.
4. Choose one allowed transport: named sensor, native endpoint, browser, or a
   configured RSSHub route.
5. Declare one fallback before acquisition. A fallback may discover candidates
   but may not silently inherit the primary channel's evidence status.
6. Run channel operations serially and record both success and failure.
7. Normalize retained items to the output contract below.

## Adapter Input Contract

Pass a channel adapter only the context it needs:

```text
seed_fingerprint: mechanism, audience, distinctive terms
evidence_question: one bounded question
evidence_class: origin | implementation | experience | demand | failure | fact
channel_id: stable platform/source identifier
query_vocabulary: native terms and aliases
budget: maximum attempts for this adapter
transport_policy: allowed and forbidden transports
fallback: one declared degraded path
```

## Adapter Output Contract

Return one ledger row per attempt and one record per retained source:

```text
channel_id
adapter_id
transport
query_or_route
status: success | empty | blocked | malformed | unavailable
source_url: original item URL when available
transport_url: feed/API/search URL when different
author
published_at
retrieved_at
exact_observed_content
evidence_class
evidence_state: direct | aggregated | snippet-only | unverified
coverage_limit
```

Never return popularity alone as demand evidence. Never call a feed URL the
original source. Never omit a failed attempt from the channel ledger.

## Initial Registry

| Channel ID | Best for | Primary adapter | Useful transports | Important limit |
| --- | --- | --- | --- | --- |
| `xiaohongshu` | Chinese consumer language, remembered notes, firsthand product/place experience | `xiaohongshu.md` or a dedicated Xiaohongshu Skill | native/browser; configured RSSHub route for discovery | engagement is attention; access and personalization bias are material |
| `github` | implementation, maintenance, issues, releases | existing GitHub routing | named sensor, native/API, browser | stars do not prove fit or demand |
| `hacker-news` | practitioner vocabulary and discussions | existing HN routing | Algolia/native/browser | audience is selective |
| `steam` | game experience and recommendation text | existing Steam routing | appreviews/native/browser | preserve language and purchase filters |
| `v2ex` | Chinese developer/product pain and vocabulary | platform-specific Skill when available | native/browser, RSSHub when configured | not representative of nontechnical users |
| `bilibili` | Chinese creator demonstrations and comments | platform-specific Skill when available | native/browser, RSSHub when configured | creator amplification is not player retention |

RSSHub is not a channel ID. It is a transport that can serve several channels.

## Adding Another Media Adapter

Add a dedicated Skill when the channel needs authentication, browser state,
special parsing, or non-obvious query grammar. Otherwise add one reference file
and one registry row. The adapter must implement the common input/output
contract, state what its evidence can prove, define one bounded fallback, and
avoid duplicating the root research workflow.
