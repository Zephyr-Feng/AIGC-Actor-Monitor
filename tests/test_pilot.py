from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from actor_monitor.pilot import prepare_pilot


class PilotPreparationTests(unittest.TestCase):
    def test_excludes_prior_groups_and_preserves_pair_channel(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            real, fake = root / "real", root / "fake"
            real.mkdir()
            fake.mkdir()
            for name in ("a.jpg", "b.jpg"):
                Image.new("RGB", (16, 12), "white").save(real / name)
                Image.new("RGB", (16, 12), "black").save(fake / name)
            rows = prepare_pilot(real, fake, root / "pilot", {"caption-a"}, n_pairs=1)
            self.assertEqual({row["source_group_id"] for row in rows}, {"caption-b"})
            self.assertEqual({row["label"] for row in rows}, {"real", "fake"})
            self.assertEqual({row["channel"] for row in rows}, {"center-fit-512px-jpeg-q90-444"})
            with self.assertRaisesRegex(ValueError, "only 1 unused"):
                prepare_pilot(real, fake, root / "unused", {"caption-a"}, n_pairs=2)


if __name__ == "__main__":
    unittest.main()
