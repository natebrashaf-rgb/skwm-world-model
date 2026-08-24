import unittest
from pathlib import Path

import task_cd_handover as handover


class StateVectorTests(unittest.TestCase):
    def test_added_keywords_change_rebuilt_state(self):
        baseline = [
            {"year": year, "keywords": ["tourism", "heritage"]}
            for year in range(2016, 2021)
        ]
        augmented = baseline + [
            {"year": 2020, "keywords": ["سياحة", "تراث"]}
        ]

        self.assertNotEqual(
            handover.sha256_json(handover.build_state_vectors(baseline)),
            handover.sha256_json(handover.build_state_vectors(augmented)),
        )

    def test_topic_classifier_uses_canonical_labels(self):
        arabic = handover.classify_topics("سياحة تراث جامعة تاريخ")
        english = handover.classify_topics("tourism heritage university history")

        self.assertEqual(set(arabic), set(english))


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task_c, cls.task_d = handover.run_all(Path("data"), write=False)

    def test_task_c_compares_distinct_state_vectors(self):
        versions = self.task_c["data_version"]
        self.assertNotEqual(
            versions["baseline_state_sha256"],
            versions["augmented_state_sha256"],
        )
        self.assertTrue(self.task_c["conclusions"]["q1_state_vector_changed"])
        self.assertFalse(self.task_c["conclusions"]["q1_top20_membership_changed"])

    def test_c_and_d_share_tourism_count(self):
        self.assertEqual(
            self.task_c["arabic_analysis"]["tourism_related"],
            self.task_d["summary"]["tourism_related"],
        )

    def test_primary_levels_are_exclusive_and_complete(self):
        self.assertEqual(
            sum(self.task_d["primary_level_distribution"].values()),
            self.task_d["summary"]["total_arabic_papers"],
        )

    def test_comparison_has_one_row_per_canonical_topic(self):
        labels = [row["topic"] for row in self.task_d["comparison"]]
        self.assertEqual(labels, list(handover.TOPIC_KEYWORDS))


if __name__ == "__main__":
    unittest.main()
