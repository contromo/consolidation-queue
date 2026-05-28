import tempfile
import unittest
from pathlib import Path

from cq.eval import publication_hardening_lock as lock


class PublicationHardeningLockMissingMarkersTests(unittest.TestCase):
    def test_missing_protocol_markers_raise(self) -> None:
        body = (
            "publication_hardening_lock_sha256: "
            + "0" * 64
            + "\n\nno markers at all in this body\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "publication_hardening.md"
            path.write_text(body, encoding="utf-8")
            with self.assertRaises(lock.PublicationHardeningLockError):
                lock.validate_publication_hardening_lock(path)


if __name__ == "__main__":
    unittest.main()
