"""Fast business-rule tests that do not require a Spark runtime."""

def safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def test_ctr():
    assert safe_ratio(500, 10_000) == 0.05


def test_roas():
    assert safe_ratio(25_000, 5_000) == 5.0


def test_zero_denominator():
    assert safe_ratio(100, 0) == 0.0
