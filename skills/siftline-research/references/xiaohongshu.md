# Xiaohongshu Channel Adapter

Use Xiaohongshu for Chinese consumer vocabulary, firsthand descriptions of
products and places, creator-led practices, and recovering a vaguely remembered
post. Do not treat it as a representative market sample.

## Classify the Request First

- **Recover a forgotten note**: extract every remembered anchor such as object,
  place, creator trait, visual detail, phrase, approximate date, and outcome.
- **Find evaluations or warnings**: search the product/category plus native
  intent words such as `测评`, `避雷`, `踩雷`, `回购`, `空瓶`, and `真实体验`.
- **Find a method or itinerary**: search the user's goal and constraints, not
  only the product category; include `攻略`, `教程`, location, budget, season,
  or audience when known.
- **Assess a trend or demand**: collect repeated independent behavior or
  detailed experience; likes, saves, and note counts remain attention signals.

For forgotten-note recovery, split memory before querying:

- **hard anchors**: exact phrase, named object/place, unusual visual detail,
  creator handle or trait, hashtag, and bounded date;
- **soft anchors**: theme, mood, approximate conclusion, color, style, or broad
  scene;
- **unknowns**: whether the title/author/platform was remembered correctly,
  whether the note was a repost, and which details may belong to another item.

Search hard anchors first. Use soft anchors to rank candidates, never to confirm
identity by themselves.

## Query Lattice

Start specific and relax one anchor at a time:

1. exact phrase, creator name, product alias, place, or hashtag;
2. two distinctive remembered anchors;
3. category plus native intent vocabulary;
4. current workaround, failure event, or desired outcome;
5. a degraded `site:xiaohongshu.com` discovery query only when native access is
   unavailable.

Do not translate an English product phrase literally when Chinese users use a
different category name. Preserve aliases learned from useful notes and use
them for the next bounded query.

## Acquisition Ladder

1. Use a dedicated Xiaohongshu Skill or an authenticated in-app browser session
   when available.
2. Use a configured RSSHub route only after reading `rsshub.md`; treat feed
   items as aggregated evidence until the original note is opened or otherwise
   verified.
3. Use generic web/site search for candidate discovery only. A snippet is not a
   retained final source unless the answer explicitly labels it snippet-only.
4. If access remains blocked, ask for a note URL, screenshot, creator handle, or
   another remembered anchor. Report the channel as unavailable rather than
   converting no results into absence.

## Retained Evidence

Prefer the original note URL and record author, publication time, exact text,
visible media actually inspected, retrieval time, query, and access state.
Separate the author's observation from promotional claims and from commenter
reactions. If only a screenshot or feed excerpt is available, record that
limitation and do not infer omitted context.

Cluster reposts, copied text, the same author's cross-posts, and comments under
one note before judging repetition. Treat distinct accounts as independent only
when they describe their own concrete trigger, workaround, and consequence;
otherwise record `independence=unknown`.

For remembered-note recovery, rank candidates by matched anchors and show why
each candidate fits or conflicts. Do not identify one candidate as the note
unless a distinctive anchor verifies it.

## What This Channel Does Not Prove

- engagement totals do not prove broad or consequential demand;
- repeated reposts may share one origin and are not independent evidence;
- creator sponsorship or affiliate incentives can affect claims;
- personalized ranking prevents a search result set from being treated as a
  stable census;
- inaccessible or zero-result searches do not establish that a note, audience,
  or behavior does not exist.
