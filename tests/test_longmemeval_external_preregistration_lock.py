import tempfile
import unittest
from pathlib import Path

from cq.eval.external.longmemeval import preregistration_lock as lock


class FairStreamExternalizationLockTests(unittest.TestCase):
    def test_committed_preregistration_lock_validates(self) -> None:
        observed = lock.validate_fair_stream_externalization_lock()
        self.assertEqual(
            observed,
            "0edf74633d8129a9b043dffce0eb76aa46356fcadf2ea2dc5628a039a81c2c56",
        )

    def test_temp_preregistration_lock_recomputes_from_protocol_block(self) -> None:
        body = """# temp

fair_stream_externalization_lock_sha256: {sha}

outside text does not affect the lock

<!-- FAIR_STREAM_EXTERNALIZATION_PROTOCOL_START -->
locked line
<!-- FAIR_STREAM_EXTERNALIZATION_PROTOCOL_END -->
"""
        sha = lock.compute_fair_stream_externalization_lock_sha256(body.format(sha="0" * 64))
        text = body.format(sha=sha)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "registration.md"
            path.write_text(text, encoding="utf-8")
            self.assertEqual(lock.validate_fair_stream_externalization_lock(path), sha)

    def test_lock_mismatch_raises(self) -> None:
        text = """fair_stream_externalization_lock_sha256: {}

<!-- FAIR_STREAM_EXTERNALIZATION_PROTOCOL_START -->
locked line
<!-- FAIR_STREAM_EXTERNALIZATION_PROTOCOL_END -->
""".format("0" * 64)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "registration.md"
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(lock.FairStreamExternalizationLockError):
                lock.validate_fair_stream_externalization_lock(path)


if __name__ == "__main__":
    unittest.main()

