import unittest

from algorithm.ml_forecast import (
    MIN_ML_HISTORY_DAYS,
    _weekly_origins,
    peramalkan_random_forest,
)


class RandomForestForecastTestCase(unittest.TestCase):
    def test_short_history_returns_explicit_ses_fallback(self):
        result = peramalkan_random_forest([2, 3, 4] * 10, 7)
        self.assertFalse(result['tersedia'])
        self.assertEqual(result['status'], 'histori_ml_terbatas')
        self.assertIn(str(MIN_ML_HISTORY_DAYS), result['alasan'])

    def test_weekly_backtest_folds_are_chronological_and_non_overlapping(self):
        origins = _weekly_origins(120, 7)
        self.assertEqual(len(origins), 7)
        self.assertEqual(origins, sorted(origins))
        self.assertEqual([right - left for left, right in zip(origins, origins[1:])], [7] * 6)
        self.assertLess(origins[-1] + 7, 121)

    def test_constant_history_keeps_ses_when_random_forest_only_ties(self):
        result = peramalkan_random_forest([5] * 120, 7)
        self.assertFalse(result['tersedia'])
        self.assertEqual(result['status'], 'ses_lebih_baik')
        self.assertEqual(result['mape_persen'], 0)
        self.assertEqual(result['mape_ses_persen'], 0)
        self.assertEqual(result['jumlah_data_uji'], 7)

    def test_random_forest_is_selected_when_weekly_lag_pattern_validates_better(self):
        # The weekly level alternates between two stable regimes; lag features
        # can learn the repeated pattern while SES smooths it toward one level.
        series = [5 if (day // 7) % 2 == 0 else 15 for day in range(120)]
        result = peramalkan_random_forest(series, 7)
        self.assertTrue(result['tersedia'])
        self.assertEqual(result['status'], 'random_forest_mengungguli_ses')
        self.assertLess(result['mape_persen'], result['mape_ses_persen'])
        self.assertEqual(result['jumlah_data_uji'], 7)


if __name__ == '__main__':
    unittest.main()
