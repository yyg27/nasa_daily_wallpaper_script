import json
import os
import tempfile
import time
import unittest
from pathlib import Path

import nasa_wallpaper as nw


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        photos = Path(tmp.name)
        for name, value in {"PHOTOS": photos, "FAVORITES": photos / "favorites",
                            "CURRENT": photos / "current.txt", "LATEST": photos / "latest.txt"}.items():
            old = getattr(nw, name)
            setattr(nw, name, value)
            self.addCleanup(setattr, nw, name, old)
        self.photos = photos

    def picture(self, id, days_old=0, **meta):
        image = self.photos / f"{id}.jpg"
        image.write_bytes(b"jpg")
        entry = {"id": id, "title": id, "explanation": "", "image": "", "link": "https://nasa.gov", **meta}
        image.with_suffix(".json").write_text(json.dumps(entry))
        old = time.time() - days_old * 86400
        for f in (image, image.with_suffix(".json")):
            os.utime(f, (old, old))
        return image


class CleanupTest(Base):
    def test_removes_only_old_unprotected_pictures(self):
        old = self.picture("old", days_old=8)
        new = self.picture("new", days_old=1)
        wallpaper = self.picture("wallpaper", days_old=30)
        latest = self.picture("latest", days_old=30)
        nw.CURRENT.write_text(str(wallpaper))
        nw.LATEST.write_text(str(latest))
        nw.favorite(old)

        nw.cleanup()

        self.assertFalse(old.exists())
        self.assertFalse(old.with_suffix(".json").exists())
        for kept in (new, wallpaper, latest, wallpaper.with_suffix(".json"), nw.CURRENT, nw.LATEST,
                     nw.FAVORITES / "old.jpg", nw.FAVORITES / "old.json"):
            self.assertTrue(kept.exists(), kept)

    def test_missing_folder(self):
        nw.PHOTOS = self.photos / "missing"
        nw.cleanup()


class GalleryTest(Base):
    def test_lists_favorites_newest_first_and_escapes_text(self):
        nw.favorite(self.picture("first", days_old=2, title="Old <one>"))
        nw.favorite(self.picture("second", days_old=1, explanation="Stars & dust", link="javascript:alert(1)"))

        page = (nw.FAVORITES / "index.html").read_text()

        self.assertLess(page.index("second.jpg"), page.index("first.jpg"))
        self.assertIn("Old &lt;one&gt;", page)
        self.assertIn("Stars &amp; dust", page)
        self.assertIn('href="https://nasa.gov"', page)
        self.assertNotIn("javascript:", page)


if __name__ == "__main__":
    unittest.main()
