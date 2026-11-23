# External data (not committed)

This folder holds downloaded third-party extracts. The CSV files are gitignored and must not be committed.

## Player performance extract

- **Source project:** [kxnoun/ballondor-predictor](https://github.com/kxnoun/ballondor-predictor)
- **File:** `data/final_combined_stats.csv`
- **Direct URL:** https://raw.githubusercontent.com/kxnoun/ballondor-predictor/main/data/final_combined_stats.csv

That repository states no license and does not name the original statistics source. Column names resemble FBref (Opta), but that is not confirmed.

Download and keep only the analysis years with:

```bash
python src/download_performance_data.py
```

This writes `player_performance.csv` here. `src/data_loading.py` uses that path by default, and will run the download automatically if the file is missing.
