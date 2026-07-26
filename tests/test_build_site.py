import tempfile
import unittest
from pathlib import Path

from PIL import Image

import build_site


CONFIG = """[site]
name = Test Photography
photographer_name = Test
category = Photography
tagline = A test portfolio.
location = Jersey City, NJ
email = test@example.com
instagram_username = @test
instagram_url = https://www.instagram.com/test/
[about]
heading = About this photographer
body = First paragraph.

    Second paragraph.
focus = Events
[contact]
heading = Get in touch
intro = Send a message.
"""


class BuildSiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "assets" / "css").mkdir(parents=True)
        (self.root / "assets" / "js").mkdir()
        (self.root / "content").mkdir()
        (self.root / "photos").mkdir()
        (self.root / "assets" / "css" / "styles.css").write_text("", encoding="utf-8")
        (self.root / "assets" / "js" / "main.js").write_text("", encoding="utf-8")
        (self.root / "content" / "site.ini").write_text(CONFIG, encoding="utf-8")
        self.originals = {
            name: getattr(build_site, name)
            for name in ("ROOT", "PHOTO_ROOT", "OUTPUT", "ASSETS", "SETTINGS_FILE")
        }
        build_site.ROOT = self.root
        build_site.PHOTO_ROOT = self.root / "photos"
        build_site.OUTPUT = self.root / "_site"
        build_site.ASSETS = self.root / "assets"
        build_site.SETTINGS_FILE = self.root / "content" / "site.ini"

    def tearDown(self):
        for name, value in self.originals.items():
            setattr(build_site, name, value)
        self.temp.cleanup()

    def image(self, folder, name, size=(120, 80)):
        target = self.root / "photos" / folder
        target.mkdir(exist_ok=True)
        Image.new("RGB", size, "#94745e").save(target / name)

    def test_build_edge_cases_and_relative_navigation(self):
        dated = "2026-08-22--Same Title"
        duplicate = "2025-08-22--Same Title"
        undated = "An Undated Set"
        (self.root / "photos" / "Empty").mkdir()
        (self.root / "photos" / dated / "README.md").parent.mkdir()
        (self.root / "photos" / dated / "README.md").write_text("ignored")
        for name in ("10.jpg", "2.jpg", "1.jpg", "Cover-Main.JPG"):
            self.image(dated, name)
        self.image(duplicate, "one.PNG")
        self.image(undated, "only.WEBP")

        self.assertEqual(build_site.main(), 0)
        output = self.root / "_site"
        self.assertTrue((output / "index.html").is_file())
        self.assertTrue((output / "about" / "index.html").is_file())
        self.assertTrue((output / "contact" / "index.html").is_file())
        self.assertTrue((output / "galleries" / "same-title" / "index.html").is_file())
        self.assertTrue((output / "galleries" / "same-title-2026-08-22" / "index.html").is_file())
        self.assertTrue((output / "galleries" / "an-undated-set" / "index.html").is_file())

        home = (output / "index.html").read_text(encoding="utf-8")
        # Dates control sorting but are not rendered for visitors.
        self.assertLess(home.index("Same Title"), home.index("An Undated Set"))
        self.assertNotIn("<time", home)
        gallery = (output / "galleries" / "same-title-2026-08-22" / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="../../about/"', gallery)
        self.assertIn('src="../../assets/js/main.js"', gallery)
        self.assertNotIn("August 22, 2026", gallery)

        built = build_site.build_gallery(
            self.root / "photos" / dated, "order-check", "Jersey City, NJ"
        )
        self.assertEqual(
            [photo.filename for photo in built.photos],
            ["1.jpg", "2.jpg", "10.jpg", "Cover-Main.JPG"],
        )
        self.assertEqual(build_site.choose_cover(built).filename, "Cover-Main.JPG")


if __name__ == "__main__":
    unittest.main()
