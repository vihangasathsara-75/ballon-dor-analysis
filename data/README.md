# Data

This folder holds the project's raw, sample, and processed datasets.

## Voting results: source of record

**France Football is the organiser and the primary source of record** for Ballon d'Or voting results. Official announcements are published on [francefootball.fr](https://www.francefootball.fr/) and, for recent editions, the official [Ballon d'Or](https://ballondor.com/) site. L'Équipe (same publisher group) also carries official ranking write-ups.

**Wikipedia is used only as a convenient structured copy** of those published rankings. The collection script (`src/collect_voting_data.py`) reads the English Wikipedia year pages, which cite France Football. Wikipedia text is licensed under [CC BY-SA](https://en.wikipedia.org/wiki/Wikipedia:Text_of_the_Creative_Commons_Attribution-ShareAlike_4.0_International_License); attribution is given through the `source_url` column on each row.

The 2020 Ballon d'Or was **not awarded** because of the COVID-19 pandemic, so that year is omitted.

## Files in `data/raw`

- `ballon_dor_voting.csv` — men's Ballon d'Or nominees for 2016–2019 and 2021–2024 (30 players per year). Columns include `year`, `rank`, `player`, `nationality`, `club`, `points`, `position` (when the Wikipedia table provides it), `source_url`, and `source`. Rebuild it with `python src/collect_voting_data.py`.
- `podium_reference.csv` — top-three point totals that were actually read from official France Football or Ballon d'Or pages, plus a `status` of `verified` or `unverified`. If an official page could not be reached or did not publish points, the reference value is left blank. No official figure is invented.

## Validation

`python src/validate_voting_data.py` compares the collected top-three points for each year with `podium_reference.csv`.

Results recorded on 23 November 2026 (Asia/Colombo):

- **2016** — verified against the official France Football complete ranking. Points match: Ronaldo 745, Messi 316, Griezmann 198.
- **2017** — verified against official France Football winner, second-place, and third-place articles. Points match: Ronaldo 946, Messi 670, Neymar 361.
- **2018** — unverified. The official France Football final ranking page lists the order (Modrić, Ronaldo, Griezmann) but does not publish point totals.
- **2019** — verified against the official France Football recap. Points match: Messi 686, van Dijk 679, Ronaldo 476.
- **2021** — unverified. The France Football winner URL was reachable but no longer had an article body; L'Équipe ranking articles returned HTTP 403.
- **2022** — unverified. The France Football winner URL was reachable but no longer had an article body.
- **2023** — unverified. The L'Équipe official ranking page returned HTTP 403; the official Ballon d'Or rankings page lists names but not points.
- **2024** — rechecked 23 November 2026. A 2026 official-site article about Harry Kane was withdrawn as a 2024 source (it is not the contemporaneous announcement). The proper official-family ranking with published points is L'Équipe's complete 2024 ranking article (8/12 November 2024), but that page returned HTTP 403 and could not be read. [ballondor.com 2024 rankings](https://ballondor.com/fr/all-rankings?year=2024) list the order of finish but not point totals. All three 2024 podium totals are therefore **unverified**.

Re-run the validator after refreshing the voting file. Any mismatch should be reported rather than silently corrected.

## Player performance data

Real player-season statistics were **not** added in this commit.

`src/collect_player_performance.py` is the planned collector for official performance features. It requests FBref (Opta) "Big 5 European Leagues" standard player-stats tables, with source URLs, for seasons overlapping 2016–2024. Transfermarkt is the planned source for team trophies, but those pages are not scraped by the script yet. On 23 November 2026, FBref returned HTTP 403 for the Big 5 pages (and the site home page), so no official performance file was written. The script does not invent replacement numbers.

Until a complete official extract is available, the pipeline uses a **clearly labelled SYNTHETIC sample**:

- `data/sample/synthetic_player_season_stats.csv` — one row per nominee (240 rows). The filename, `data_label` column, and `source` column all say SYNTHETIC.
- Rebuild it with `python src/generate_sample_data.py` (fixed seed 42).

Identifiers (`year`, `player`, `club`, `nationality`) are copied from the voting table. `position` is copied from Wikipedia when that table listed one, or propagated from another Wikipedia year for the same player; otherwise it is left blank (`position_source` records this). All of `appearances`, `minutes`, `goals`, `assists`, and the trophy flags are simulated. They must not be mixed into the voting file or presented as FBref or Transfermarkt figures.

To replace the sample later, collect official FBref/Transfermarkt (or equivalent) stats into `data/raw/player_performance.csv` with source URLs, then join to the voting table on `year` and `player`. Keep any remaining synthetic rows in `data/sample/` only.

## Licensing note

Voting ranks and points originate with France Football. The structured tables in this repository were collected from Wikipedia and should be treated as a CC BY-SA reuse of that structured copy, with links back to the Wikipedia year pages and, where checked, to the official announcements used for validation.
