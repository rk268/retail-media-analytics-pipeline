"""Sample-ratio mismatch (SRM) checks for randomized holdout experiments.

SRM validates observed assignment counts against a documented design ratio,
not randomization integrity or the causal validity of an experiment.
"""
from __future__ import annotations
import math
from statistics import NormalDist


def sample_ratio_mismatch(treatment_users: int, control_users: int,
                          expected_treatment_share: float = 0.5,
                          alpha: float = 0.001) -> dict:
    """Two-arm Pearson chi-square SRM check (1 df, normal-tail equivalent).

    For two arms, chi-square = z² and the p-value is 2*SF(|z|).
    Valid for sufficiently large expected counts (at least five per arm).
    """
    if (type(treatment_users) is not int or type(control_users) is not int
            or treatment_users < 0 or control_users < 0):
        raise ValueError("Arm counts must be non-negative integers")
    if not math.isfinite(expected_treatment_share) or not 0 < expected_treatment_share < 1:
        raise ValueError("Expected treatment share must be strictly between zero and one")
    if not math.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError("alpha must be strictly between zero and one")
    total = treatment_users + control_users
    expected_treatment = total * expected_treatment_share
    expected_control = total * (1 - expected_treatment_share)
    if min(expected_treatment, expected_control) < 5:
        raise ValueError("Expected arm counts must each be at least five")
    chi_square = ((treatment_users - expected_treatment) ** 2 / expected_treatment
                  + (control_users - expected_control) ** 2 / expected_control)
    p_value = math.erfc(math.sqrt(chi_square / 2))
    return {
        "treatment_users": treatment_users,
        "control_users": control_users,
        "expected_treatment_share": expected_treatment_share,
        "observed_treatment_share": treatment_users / total,
        "chi_square": chi_square,
        "p_value": p_value,
        "alpha": alpha,
        "srm_detected": p_value < alpha,
        "method": "Pearson chi-square, 1 df, large-sample approximation",
    }
