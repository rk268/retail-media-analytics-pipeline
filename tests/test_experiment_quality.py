import unittest
from src.experiment_quality import sample_ratio_mismatch


class SampleRatioMismatchTests(unittest.TestCase):
    def test_balanced_allocation(self):
        result = sample_ratio_mismatch(500, 500)
        self.assertEqual(result["chi_square"], 0)
        self.assertEqual(result["p_value"], 1)
        self.assertFalse(result["srm_detected"])

    def test_large_mismatch_detected(self):
        result = sample_ratio_mismatch(700, 300)
        self.assertTrue(result["srm_detected"])
        self.assertLess(result["p_value"], 0.001)

    def test_unbalanced_design_can_be_valid(self):
        result = sample_ratio_mismatch(700, 300, expected_treatment_share=0.7)
        self.assertFalse(result["srm_detected"])

    def test_unbalanced_design_detects_mismatch(self):
        result = sample_ratio_mismatch(500, 500, expected_treatment_share=0.7)
        self.assertTrue(result["srm_detected"])

    def test_small_expected_count_rejected(self):
        with self.assertRaises(ValueError):
            sample_ratio_mismatch(3, 3)

    def test_invalid_inputs(self):
        for t, c, share, alpha in [
            (-1, 20, .5, .001),
            (True, 20, .5, .001),
            (20.0, 20, .5, .001),
            (100, 100, 0, .001),
            (100, 100, 1, .001),
            (100, 100, float("nan"), .001),
            (100, 100, .5, 0),
            (100, 100, .5, 1),
        ]:
            with self.subTest(t=t, c=c, share=share, alpha=alpha):
                with self.assertRaises(ValueError):
                    sample_ratio_mismatch(t, c, share, alpha)


if __name__ == "__main__":
    unittest.main()
