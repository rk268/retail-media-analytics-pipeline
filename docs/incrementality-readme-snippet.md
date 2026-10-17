

## Synthetic incrementality example

The independent [randomized-holdout demonstration](docs/incrementality.md) calculates treatment/control conversion-rate lift, incremental conversions, estimated incremental revenue, and iROAS from **fabricated** cohorts, with seven unit tests. It makes no claim of causal lift from observational ad-platform reports.

```bash
python -m src.incrementality --input data/raw/simulated_holdout.csv --output data/outputs/incrementality_summary.json
python -m unittest discover -s tests -p 'test_incrementality.py' -v
```
