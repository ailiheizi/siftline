# RSSHub Transport Adapter

RSSHub is a transport and normalization layer. It can expose a platform feed,
account, search, or topic through RSS/Atom, but it is not the original evidence
source and is not guaranteed to contain full content.

## Preconditions

- Use only a route and instance supplied by the user, local configuration, or a
  verified route catalog. Never invent route syntax, instance availability, or
  authentication state from memory.
- Respect the prompt's transport restrictions. If all external operations must
  use Siftline or another named sensor, access RSSHub only through that sensor
  or mark the transport unavailable.
- Do not place cookies, session tokens, or private query values in a public
  RSSHub instance URL.

## Acquisition Record

For every fetch, retain the configured instance host, route template, resolved
feed URL, target channel, fetch time, HTTP/parser status, cache age when known,
and item count. For each item, retain both the original item URL and the feed
URL, GUID, author, published time, title, available content, and media links.

Use `evidence_state=aggregated` until the original item is verified. If the feed
contains only a title or excerpt, use `snippet-only`. Do not present an RSSHub
timestamp as the original publication time unless the feed explicitly binds it
to the item.

## Failure and Fallback

- A route failure is a transport failure, not evidence that the source channel
  is empty.
- A stale or cached feed must carry its retrieval and publication scope.
- A malformed item is excluded with a ledger error; it is never silently
  repaired into a source claim.
- After one declared fallback transport fails, report the evidence class as
  unavailable and continue synthesis with bounded wording.

RSSHub works well for recurring monitoring and candidate discovery. Native or
original-source verification remains preferable for exact quotations,
authorship, current state, and consequential claims.
