import json
import os
import subprocess
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import nasa_daily_cosmos as nw


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


class FetchTest(unittest.TestCase):
    def fetch(self, platform, *errors):
        """Run fetch("random") where the first calls raise the given errors; return (result, calls, sleeps)."""
        errors = list(errors)
        calls = []
        def library_random():
            calls.append(1)
            if errors:
                raise errors.pop(0)
            return "entry"
        with mock.patch.object(nw, "library_random", library_random), \
                mock.patch.object(nw, "download", lambda entry: entry), \
                mock.patch.object(nw.sys, "platform", platform), mock.patch("time.sleep") as sleep:
            try:
                result = nw.fetch("random")
            except Exception as e:
                result = e
        return result, len(calls), sleep.call_count

    def test_windows_retries_network_errors(self):
        self.assertEqual(self.fetch("win32", urllib.error.URLError("offline"), TimeoutError()), ("entry", 3, 2))

    def test_windows_gives_up_after_four_tries(self):
        result, calls, _ = self.fetch("win32", *[urllib.error.URLError("offline")] * 4)
        self.assertIsInstance(result, urllib.error.URLError)
        self.assertEqual(calls, 4)

    def test_windows_does_not_retry_http_errors(self):
        result, calls, _ = self.fetch("win32", urllib.error.HTTPError("", 500, "down", None, None))
        self.assertIsInstance(result, urllib.error.HTTPError)
        self.assertEqual(calls, 1)

    def test_linux_tries_once(self):
        result, calls, sleeps = self.fetch("linux", urllib.error.URLError("offline"))
        self.assertIsInstance(result, urllib.error.URLError)
        self.assertEqual((calls, sleeps), (1, 0))


class ThumbnailTest(unittest.TestCase):
    def test_passes_paths_through_environment(self):
        with mock.patch("subprocess.run") as run:
            out = nw.thumbnail(Path("C:/a'; rm x.jpg"))
        env = run.call_args.kwargs["env"]
        self.assertEqual((env["SRC"], env["DST"]), (str(Path("C:/a'; rm x.jpg")), str(out)))
        self.assertNotIn("rm x", run.call_args.args[0][-1])

    def test_returns_none_when_conversion_fails(self):
        for error in (FileNotFoundError(), subprocess.CalledProcessError(1, "powershell"),
                      subprocess.TimeoutExpired("powershell", 30)):
            with mock.patch("subprocess.run", side_effect=error):
                self.assertIsNone(nw.thumbnail(Path("x.jpg")))


if __name__ == "__main__":
    unittest.main()
