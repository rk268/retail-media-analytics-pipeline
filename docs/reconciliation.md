# Silver-to-Gold reconciliation

The standalone Python helper in src/reconciliation.py checks additive metrics at the same platform, campaign ID and campaign name grain as build_gold. Supply iterables of dictionaries from the same input snapshot and reporting period, with currency already normalized. It reports missing or unexpected campaigns and metric differences; duplicate Gold keys and invalid numeric values raise errors.

Run the synthetic tests from the repository root:

    python -m unittest discover -s tests -p test_reconciliation.py

Counts must match exactly; spend and revenue default to a one-cent absolute tolerance per campaign. Decimal conversion avoids ordinary binary floating-point accumulation for decimal-string inputs, but does not recover precision already lost upstream. Ratios such as ROAS and CTR are not additive and are excluded. Empty inputs match each other; enforce expected volume separately. This in-memory helper is intended for bounded extracts, not distributed Spark datasets, and is not automatically invoked by the orchestrator.
