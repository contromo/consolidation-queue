import subprocess
import unittest


def is_ignored(path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", path],
        check=False,
    )
    return result.returncode == 0


class GitignoreArtifactPolicyTests(unittest.TestCase):
    def test_large_spectrum_json_is_ignored(self) -> None:
        self.assertTrue(
            is_ignored("data/results/evidence_conflict_spectrum/example_oracle_phase2_5_mixed.json")
        )

    def test_headline_artifacts_are_trackable(self) -> None:
        for path in (
            "data/results/evidence_conflict_spectrum/example_oracle_phase2_5_mixed_metrics.csv",
            "data/results/evidence_conflict_spectrum/example_oracle_phase2_5_mixed_manifest.json",
            "data/results/evidence_conflict_spectrum/example_structure_mixed.json",
            "data/results/evidence_conflict_spectrum/example_nondegeneracy_mixed.json",
            "data/results/abstention/example_abstention.json",
            "data/results/abstention/example_abstention.csv",
        ):
            with self.subTest(path=path):
                self.assertFalse(is_ignored(path))


if __name__ == "__main__":
    unittest.main()
