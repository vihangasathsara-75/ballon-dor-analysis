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

The default analysis uses a **real compiled extract** of player-season statistics, narrowed to the **top 15 finishers in each award year** (2016–2019 and 2021–2024: 120 rows). Every one of those 120 rows is an exact `year` + player-name match to the voting table. The merged dataset is therefore all real (`is_synthetic` is False). Year-standardised voting columns (`points_share`, `points_year_z`, `points_year_minmax`) are computed on this top-15 set.

### Source and licensing

The extract is taken from the public project [kxnoun/ballondor-predictor](https://github.com/kxnoun/ballondor-predictor), file `data/final_combined_stats.csv` ([raw URL](https://raw.githubusercontent.com/kxnoun/ballondor-predictor/main/data/final_combined_stats.csv)).

That repository **states no license** and **does not name the original statistics source**. Column names and the `W-D-L` `Result` field resemble FBref (Opta), but that origin is not confirmed here. Treat the file as a third-party compilation, not as an official FBref or Transfermarkt dump.

### How the file is obtained

`src/download_performance_data.py` downloads the CSV at runtime, keeps only the analysis years, and writes `data/external/player_performance.csv`. That folder is gitignored; **do not commit the CSV**. `src/data_loading.py` uses this path by default and will run the download if the file is missing.

`Min` is parsed from a comma-thousands string into numeric minutes. `Result` (`W-D-L`) is parsed into `wins`, `draws`, and `losses`; appearances are the sum of those three.

### Missing metrics

Where a metric is clearly unavailable, placeholder zeros are treated as missing (`NaN`), not as true zeros. In this extract, `xG`, `xAG`, `SCA`, and `GCA` are 0.0 for every top-15 player in **2016 and 2017**, so those four metrics are recoded to missing for those two years. From 2018 they have genuine variation and zeros are left as recorded (for example a goalkeeper with no expected goals).

The extract has no playing-position column, so positions in the merged table come only from the Wikipedia voting table; many top-15 rows therefore have `position` missing.

The extract does **not** lack `Sh`, `SoT`, `Int`, or `Tkl` in 2016–2017: those columns contain real-looking non-zero values for outfield players and are kept. Goalkeeper-only fields (`SoTA`, `GA`, `Saves`, `Save%`, `CS`) are populated for goalkeepers and are missing for outfield players, as expected.

`src/collect_player_performance.py` remains the planned collector for official FBref (Opta) tables. On 23 November 2026 those pages returned HTTP 403, so this project does not yet have a first-party official extract.

### SYNTHETIC sample (tests only)

The labelled SYNTHETIC sample is **no longer the default**. It is kept only so the pipeline can be tested without the download:

- `data/sample/synthetic_player_season_stats.csv` — 240 nominee rows. The filename, `data_label`, and `source` all say SYNTHETIC.
- Rebuild it with `python src/generate_sample_data.py` (fixed seed 42).
- Point the loader at it with `--performance-path` or `PERFORMANCE_PATH`. Do not mix these simulated figures into the voting file or present them as real statistics.

## Licensing note

Voting ranks and points originate with France Football. The structured tables in this repository were collected from Wikipedia and should be treated as a CC BY-SA reuse of that structured copy, with links back to the Wikipedia year pages and, where checked, to the official announcements used for validation.

The player-performance extract is downloaded from [kxnoun/ballondor-predictor](https://github.com/kxnoun/ballondor-predictor), which states no license. It is not committed in this repository.
