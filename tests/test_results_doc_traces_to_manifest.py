import json
import re
import unittest
from pathlib import Path


RESULTS_DOC = Path("docs/abstention_quality_results.md")


class ResultsDocTraceTests(unittest.TestCase):
    def test_large_json_sha_rows_match_manifests(self) -> None:
        text = RESULTS_DOC.read_text(encoding="utf-8")
        rows = re.findall(
            r"\| `(?P<split>mixed|heldout)` "
            r"\| `(?P<json_path>data/results/evidence_conflict_spectrum/[^`]+\.json)` "
            r"\| `(?P<bytes>\d+)` "
            r"\| `(?P<sha>[0-9a-f]{64})` \|",
            text,
        )

        self.assertEqual(len(rows), 2)
        for split, json_path, byte_count, sha in rows:
            manifest_path = Path(json_path).with_name(
                "{}_manifest.json".format(Path(json_path).stem)
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            artifact = manifest["artifacts"][0]

            self.assertEqual(manifest["run_name"], Path(json_path).stem)
            self.assertEqual(artifact["path"], json_path)
            self.assertEqual(artifact["bytes"], int(byte_count), msg=split)
            self.assertEqual(artifact["sha256"], sha, msg=split)


if __name__ == "__main__":
    unittest.main()
