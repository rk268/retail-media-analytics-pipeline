# Incrementality analysis (synthetic randomized holdout)

This standalone Python exercise models an *assumed randomized* treatment/control experiment with **fabricated aggregate data**. It is separate from the repository's observational cross-channel metrics. No employer or advertiser data is involved, and no real causal effect is claimed.

## Run

From the repository root (Python 3.10+):

```bash
python -m src.incrementality --input data/raw/simulated_holdout.csv --output data/outputs/incrementality_summary.json
python -m unittest discover -s tests -p 'test_incrementality.py' -v
```

## Metrics

For each group, conversion rate = conversions / users. Absolute conversion-rate lift = treatment rate minus control rate. Relative lift divides this difference by the control rate when nonzero. Incremental conversions = absolute lift multiplied by the treated group size. Incremental revenue = (treatment revenue per user minus control revenue per user) times treated users. Incremental spend = treatment spend minus control spend. iROAS = incremental revenue divided by incremental spend when positive.

The 95% interval uses an unpooled normal/Wald approximation for the conversion-rate *difference*, not incremental revenue. It is unsuitable for small/sparse cohorts. Revenue and iROAS are point estimates without confidence intervals.

## Assumptions and caveats

True causal interpretation requires random assignment, comparable observation windows, reliable identity and conversion measurement, and minimal interference/spillover. This program cannot validate these conditions from aggregated input. No source ad-platform export should be treated as a randomized experiment without evidence.

A production framework should use experiment assignment logs, sample-ratio mismatch checks, cluster-aware or robust intervals where required, pre-registration of primary metrics, variance-aware revenue uncertainty, and privacy reviews.
