# Sample-ratio mismatch (SRM) diagnostic

The synthetic holdout example in `src/incrementality.py` assumes randomized assignment. `src/experiment_quality.py` adds an **independent**, reproducible diagnostic for one common experiment-integrity failure: unexpected group counts.

An SRM flag does **not** prove how assignment failed; an unflagged SRM does **not** establish randomization, comparable follow-up, absence of spillover, or causal validity.

## Use

```python
from src.experiment_quality import sample_ratio_mismatch
check = sample_ratio_mismatch(700, 300, expected_treatment_share=0.5)
assert check["srm_detected"]
```

The function accepts observed treatment/control user counts, the **pre-specified** allocation share (default 50%), and significance threshold (default 0.001). It computes a two-arm Pearson chi-square statistic with one degree of freedom and its survival probability using `math.erfc`. SRM is flagged only when `p_value < alpha`. At least five expected observations per arm are required for this approximation.

Count *assigned users* at the proper randomization unit, not clicks or conversions. Derive the expected share from the experiment configuration; do not tune it to observed counts. Apply SRM before interpreting any incrementality result. For multi-arm tests, clusters, or time-varying assignment use an appropriately designed diagnostic instead.

Tests use only fabricated group sizes; no real campaign data is included.
