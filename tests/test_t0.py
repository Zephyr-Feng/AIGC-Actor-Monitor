from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actor_monitor.t0 import prepare_t0


class T0PreparationTests(unittest.TestCase):
    def test_pairs_share_source_group_and_output_channel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real_dir, fake_dir = root / "real", root / "fake"
            real_dir.mkdir()
            fake_dir.mkdir()
            for name in ("one.jpg", "two.jpg"):
                Image.new("RGB", (80, 60), "white").save(real_dir / name)
                Image.new("RGB", (60, 80), "black").save(fake_dir / name)

            output = root / "t0"
            rows = prepare_t0(real_dir, fake_dir, output, n_pairs=1, seed=7, size=64)
            self.assertEqual(len(rows), 2)
            self.assertEqual({row["label"] for row in rows}, {"real", "fake"})
            self.assertEqual(len({row["source_group_id"] for row in rows}), 1)
            for row in rows:
                with Image.open(row["image_path"]) as image:
                    self.assertEqual(image.size, (64, 64))
                    self.assertEqual(image.format, "JPEG")
            saved = [json.loads(line) for line in (output / "manifest.jsonl").read_text().splitlines()]
            self.assertEqual(saved, rows)


if __name__ == "__main__":
    unittest.main()
