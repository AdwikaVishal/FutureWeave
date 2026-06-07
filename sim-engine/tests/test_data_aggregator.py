import unittest

from services.aggregator import _monitor, _score_confidence
from services.common import ProviderResult


class DataAggregatorTests(unittest.TestCase):
    def test_confidence_scores_only_available_datasets(self):
        results = {
            "worldbank": ProviderResult(provider="worldbank", dataset="macro", available=True),
            "salary": ProviderResult(provider="ambitionbox", dataset="salary", available=False, error="blocked"),
            "cost_of_living": ProviderResult(provider="numbeo", dataset="cost_of_living", available=False, error="no key"),
            "job_market": ProviderResult(provider="linkedin", dataset="job_market", available=False, error="no key"),
            "industry": ProviderResult(provider="fred", dataset="industry", available=False, error="no key"),
        }

        confidence, explanation, gaps = _score_confidence(results)

        self.assertEqual(confidence, 20)
        self.assertEqual(len(gaps), 4)
        self.assertTrue(any("Real-time salary data unavailable" in gap.message for gap in gaps))
        self.assertIn("World Bank macro data available = +20", explanation)

    def test_monitoring_tracks_failures_and_cache_hits(self):
        results = {
            "worldbank": ProviderResult(
                provider="worldbank",
                dataset="macro",
                available=True,
                cache_hit=True,
                latency_ms=12.5,
            ),
            "salary": ProviderResult(
                provider="ambitionbox",
                dataset="salary",
                available=False,
                error="timeout",
                latency_ms=1000,
            ),
        }

        monitoring = _monitor(results)

        self.assertEqual(monitoring.cache_hits, 1)
        self.assertEqual(monitoring.cache_misses, 1)
        self.assertEqual(monitoring.api_failures["salary"], "timeout")
        self.assertIn("salary", monitoring.missing_datasets)
        self.assertEqual(monitoring.api_latency_ms["worldbank"], 12.5)


if __name__ == "__main__":
    unittest.main()

