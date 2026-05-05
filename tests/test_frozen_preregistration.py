import tempfile
import unittest
from pathlib import Path

from cq.eval.preregistration_lock import (
    PREDICTIONS_BLOCK_END,
    PREDICTIONS_BLOCK_START,
    compute_frozen_eval_lock_sha256,
    validate_frozen_eval_lock,
)
from cq.eval.runner import MECHANISM_DIVERSE_HELDOUT, build_run_artifact
from cq.schemas.memory import jsonable
from cq.simulator.scenario_generator import generate_frozen_mechanism_diverse_scenarios


def _preregistration_text(lock_value: str, predictions_block: str) -> str:
    return (
        "# Test Preregistration\n\n"
        "frozen_eval_lock_sha256: {}\n\n"
        "{}\n"
        "{}"
        "{}\n"
    ).format(lock_value, PREDICTIONS_BLOCK_START, predictions_block, PREDICTIONS_BLOCK_END)


class FrozenPreregistrationTests(unittest.TestCase):
    def test_frozen_contracts_are_serializable_without_policy_execution(self) -> None:
        scenarios = generate_frozen_mechanism_diverse_scenarios()

        self.assertEqual(
            [scenario.template_id for scenario in scenarios],
            [
                "false_corroboration_adversarial_mixed_source",
                "memory_poisoning_scope_laundered",
                "preference_drift_long_horizon_corrections",
            ],
        )
        self.assertEqual({scenario.template_split for scenario in scenarios}, {"frozen"})
        self.assertEqual(len(jsonable(scenarios)), 3)

    def test_runner_refuses_frozen_execution_without_preregistration_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_path = Path(tmpdir) / "missing_preregistration.md"
            with self.assertRaises(ValueError):
                build_run_artifact(
                    3,
                    template_mix="frozen",
                    family=MECHANISM_DIVERSE_HELDOUT,
                    preregistration_path=missing_path,
                )

    def test_verified_lock_rejects_mismatched_hash_and_accepts_matching_hash(self) -> None:
        predictions = "## Predictions\n\n- test prediction\n"
        mismatched = _preregistration_text("0" * 64, predictions)

        with tempfile.TemporaryDirectory() as tmpdir:
            prereg_path = Path(tmpdir) / "preregistration.md"
            prereg_path.write_text(mismatched, encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_frozen_eval_lock(prereg_path)

            actual = compute_frozen_eval_lock_sha256(mismatched)
            prereg_path.write_text(_preregistration_text(actual, predictions), encoding="utf-8")
            validate_frozen_eval_lock(prereg_path)

    def test_repo_preregistration_lock_is_current(self) -> None:
        validate_frozen_eval_lock(Path("docs/preregistration.md"))


if __name__ == "__main__":
    unittest.main()
