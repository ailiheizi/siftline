# Platform Routing

Choose a platform because of the evidence it contains, not because it is fashionable.

| Evidence sought | Prefer | Useful secondary sources | Caveat |
| --- | --- | --- | --- |
| concepts and prior theory | Google Scholar, Semantic Scholar, arXiv, SSRN, citations | expert blogs, books | papers do not prove adoption |
| software implementation | GitHub code, issues, PRs, releases | package registries, Stack Overflow | stars are weak demand evidence |
| game mechanics and player experience | Steam reviews/discussions, itch.io, game forums, Reddit, YouTube/Twitch comments | Discord summaries, wikis, postmortems | distinguish genre fans from target audience |
| emerging practitioner ideas | Hacker News, X, Mastodon, Bluesky, Substack, personal blogs | newsletters, podcasts | high recency but strong selection bias |
| repeated product pain | support forums, GitHub issues, Reddit, Stack Overflow, app reviews | X, HN | complaints alone do not show willingness to switch/pay |
| costly behavior | purchases, wishlists when public, crowdfunding, migrations, forks, mods, custom scripts, job posts | case studies, public metrics | check alternative motives |
| company/product behavior | changelogs, pricing, docs, status pages, job posts, filings | interviews, press | official claims are not independent evidence |
| standards and policy | specifications, RFCs, regulator and court sites | legal commentary, news | preserve jurisdiction and effective date |
| failure and abandonment | negative reviews, postmortems, closed projects, issue history | forums, archived pages | loud failures can be unrepresentative |
| Chinese-language game demand | Steam reviews filtered by Simplified Chinese, TapTap, Bilibili, NGA and game-specific forums | Douban groups, Zhihu, creator communities | distinguish creator amplification from player behavior |
| Chinese developer/product pain | V2EX, GitHub issues, app reviews, product communities | Zhihu, X, newsletters | technical early adopters are not representative of nontechnical buyers |
| Chinese consumer language and remembered lifestyle/product notes | Xiaohongshu native search and original notes | Bilibili, Zhihu, general Web discovery | personalized ranking and creator incentives limit representativeness |

## Routing Rules

- Use general Web search to discover vocabulary and candidate origins.
- Move to the authoritative platform to verify the actual artifact or discussion.
- Use exact platform search for structured behavior: issue state, review text, release history, mods, commits, and replies.
- Use community sources to understand language, motivations, and friction; use behavior or primary records to test consequential demand.
- If a platform is inaccessible, say which evidence class is missing and use `site:` discovery only as a degraded substitute.
- For games, search both mechanic vocabulary and desired experience vocabulary. Players often describe feelings rather than systems.
- For novel products, search the current workaround and failure event; users may never use the proposed category name.
- For bilingual products, translate the underlying job or desired experience rather than only the product category, and compare whether signals differ by language or distribution channel.
- Resolve media-specific acquisition through `channel-routing.md`; RSSHub and browser automation are transports, not evidence channels.

## Useful Native Endpoints

- Steam: use Store Search or app details to resolve an app, then `https://store.steampowered.com/appreviews/<app-id>?json=1` for review evidence. Preserve language, purchase type, date, review counts, and release state.
- Hacker News: use `https://hn.algolia.com/api/v1/search` for reproducible query results, then open the original story or discussion.
- GitHub: use repository code, issues, PRs, releases, and native/API search rather than star counts alone.
- General Web: use it to discover vocabulary and candidate URLs, then fetch the origin.

Treat endpoints as optional shortcuts, not required infrastructure. If an endpoint is unavailable or access-limited, report the missing evidence class instead of fabricating coverage.
