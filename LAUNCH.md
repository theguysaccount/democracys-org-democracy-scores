# Launch and distribution

Live since 2026-11-22 at https://data.democracys.org/ (first at theguysaccount.github.io/democracys-org-democracy-scores/,
which redirects there), beside https://democracys.org/. Machine channels only.

| Channel | How |
|---|---|
| Search | Indexed: the home page ("democracy scores by country open data"), `/embed/` ("democracy score chart embed") and `/reproducibility/`. Country, ranking and data copies are `noindex` and point at democracys.org. |
| Embeds | Every chart links to the full democracys.org profile, so each embed is a referral loop to the live site. |
| IndexNow | Every deploy submits the indexable pages. |
| robots.txt | `data.democracys.org/robots.txt` lists the sitemap, and so does the account root (`theguysaccount.github.io/robots.txt`). |
| GitHub | Public repo with description, topics and README. |

## Domain

`data.democracys.org` since 2026-11-22: one CNAME at Namecheap, added by the domain rollout session. The democracys.org
apex and www records are untouched. The settings, and how to move or roll back, are in OPERATIONS.md ("Custom domain").
