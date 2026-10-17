"""Synthetic randomized-holdout incrementality analysis.

This educational module does not measure real advertising performance.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def read_cohorts(path: str | Path) -> dict:
    """Validate exactly one aggregated treatment and control row."""
    cohorts = {}
    with open(path, newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {"group", "users", "conversions", "revenue", "spend"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Missing required cohort columns")
        for row in reader:
            group = row["group"].strip().lower()
            if group not in {"treatment", "control"} or group in cohorts:
                raise ValueError("Unexpected or duplicate cohort")
            try:
                users, conversions = int(row["users"]), int(row["conversions"])
                revenue, spend = float(row["revenue"]), float(row["spend"])
            except (TypeError, ValueError) as error:
                raise ValueError("Invalid cohort values") from error
            if users <= 0 or not 0 <= conversions <= users:
                raise ValueError("Invalid conversion counts")
            if not all(math.isfinite(x) and x >= 0 for x in (revenue, spend)):
                raise ValueError("Invalid revenue or spend")
            cohorts[group] = dict(users=users, conversions=conversions,
                                  revenue=revenue, spend=spend)
    if set(cohorts) != {"treatment", "control"}:
        raise ValueError("Treatment and control arms are both required")
    return cohorts


def analyze(cohorts: dict) -> dict:
    """Compute treatment-scaled differences and approximate conversion CI."""
    if set(cohorts) != {"treatment", "control"}:
        raise ValueError("Exactly two arms required")
    t, c = cohorts["treatment"], cohorts["control"]
    for arm in (t, c):
        n, conversions = arm["users"], arm["conversions"]
        if not isinstance(n, int) or not isinstance(conversions, int):
            raise ValueError("Counts must be integers")
        if n <= 0 or not 0 <= conversions <= n:
            raise ValueError("Invalid counts")
        if any(not math.isfinite(arm[k]) or arm[k] < 0 for k in ("revenue", "spend")):
            raise ValueError("Invalid monetary values")
    pt, pc = t["conversions"] / t["users"], c["conversions"] / c["users"]
    difference = pt - pc
    standard_error = math.sqrt(pt * (1 - pt) / t["users"] +
                               pc * (1 - pc) / c["users"])
    conversions = difference * t["users"]
    revenue = (t["revenue"] / t["users"] -
               c["revenue"] / c["users"]) * t["users"]
    spend = t["spend"] - c["spend"]
    return {
        "dataset": "synthetic_randomized_holdout_demo",
        "treatment_users": t["users"],
        "control_users": c["users"],
        "treatment_conversion_rate": pt,
        "control_conversion_rate": pc,
        "absolute_conversion_rate_lift": difference,
        "relative_conversion_rate_lift": difference / pc if pc > 0 else None,
        "conversion_rate_difference_95pct_wald_ci": [
            difference - 1.96 * standard_error,
            difference + 1.96 * standard_error,
        ],
        "incremental_conversions_at_treatment_scale": conversions,
        "incremental_revenue_at_treatment_scale": revenue,
        "incremental_spend": spend,
        "incremental_roas": revenue / spend if spend > 0 else None,
        "cost_per_incremental_conversion": (
            spend / conversions if spend > 0 and conversions > 0 else None
        ),
        "notes": [
            "Synthetic results only; no real advertising performance is claimed.",
            "Causal interpretation requires verified random assignment and no spillover.",
            "Wald CI is only a large-sample approximation for conversion lift.",
            "Revenue and iROAS estimates do not have uncertainty intervals.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/raw/simulated_holdout.csv")
    parser.add_argument("--output", default="data/outputs/incrementality_summary.json")
    args = parser.parse_args()
    result = analyze(read_cohorts(args.input))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n",
                      encoding="utf-8")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
