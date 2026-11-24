"""Reconcile additive Silver and Gold campaign metrics without comparing ratios."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation

KEYS = ("platform", "campaign_id", "campaign_name")
METRICS = ("impressions", "clicks", "spend", "conversions", "revenue")


def aggregate(rows, *, unique=False):
    totals = defaultdict(lambda: [Decimal(0)] * len(METRICS))
    for row in rows:
        key = tuple(row[k] for k in KEYS)
        if any(not isinstance(k, str) or not k.strip() for k in key):
            raise ValueError("Invalid campaign key")
        if unique and key in totals:
            raise ValueError(f"Duplicate Gold key: {key}")
        for i, metric in enumerate(METRICS):
            try:
                value = Decimal(str(row[metric]))
            except (InvalidOperation, ValueError) as exc:
                raise ValueError(f"Invalid {metric}") from exc
            if not value.is_finite() or value < 0:
                raise ValueError(f"Invalid {metric}")
            totals[key][i] += value
    return totals


def reconcile(silver, gold, *, money_tolerance="0.01"):
    """Return JSON-ready discrepancies; missing keys fail even for zero totals."""
    tolerance = Decimal(str(money_tolerance))
    if not tolerance.is_finite() or tolerance < 0:
        raise ValueError("Invalid tolerance")
    expected = aggregate(silver)
    actual = aggregate(gold, unique=True)
    issues = []
    for key in sorted(expected.keys() | actual.keys()):
        if key not in expected or key not in actual:
            issues.append({"key": list(key), "issue": "missing_gold" if key not in actual else "unexpected_gold"})
            continue
        for metric, left, right in zip(METRICS, expected[key], actual[key]):
            limit = tolerance if metric in ("spend", "revenue") else Decimal(0)
            if abs(right - left) > limit:
                issues.append({"key": list(key), "metric": metric, "expected": str(left),
                               "actual": str(right), "delta": str(right - left)})
    return {"passed": not issues, "silver_keys": len(expected),
            "gold_keys": len(actual), "issues": issues}
