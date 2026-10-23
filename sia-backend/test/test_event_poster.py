import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "flask-server"))

from flask import Flask
from PIL import Image

from Sections.EventPoster import (
    EVENT_POSTER_MAX_EDGE,
    MAX_EVENT_POSTER_BYTES,
    event_poster_mimetype,
    event_poster_url,
    find_event_poster,
    prepare_event_poster,
    remove_event_poster,
    store_event_poster,
)


class EventPosterTests(unittest.TestCase):
    def test_alpha_png_is_kept_as_png_and_downscaled(self):
        buffer = BytesIO()
        Image.new("RGBA", (1800, 900), (20, 90, 140, 150)).save(buffer, format="PNG")

        contents, extension = prepare_event_poster(buffer.getvalue())

        self.assertEqual("png", extension)
        self.assertEqual(b"\x89PNG\r\n\x1a\n", contents[:8])
        with Image.open(BytesIO(contents)) as image:
            self.assertLessEqual(max(image.size), EVENT_POSTER_MAX_EDGE)

    def test_opaque_image_is_converted_to_jpeg(self):
        buffer = BytesIO()
        Image.new("RGB", (500, 400), (20, 90, 40)).save(buffer, format="PNG")

        contents, extension = prepare_event_poster(buffer.getvalue())

        self.assertEqual("jpg", extension)
        self.assertEqual(b"\xff\xd8", contents[:2])
        with Image.open(BytesIO(contents)) as image:
            self.assertEqual("RGB", image.mode)

    def test_invalid_empty_and_oversized_files_are_rejected(self):
        with self.assertRaises(ValueError):
            prepare_event_poster(b"not an image")
        with self.assertRaises(ValueError):
            prepare_event_poster(b"")
        with self.assertRaises(ValueError):
            prepare_event_poster(b"x" * (MAX_EVENT_POSTER_BYTES + 1))


class EventPosterStorageTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.app = Flask(__name__, root_path=self.tempdir.name)
        self.app.config["SERVER_NAME"] = "example.test"
        self.context = self.app.app_context()
        self.context.push()

        @self.app.route("/static/images/eventposter/<filename>", endpoint="get_image")
        def get_image(filename):
            return filename

    def tearDown(self):
        self.context.pop()
        self.tempdir.cleanup()

    def image_bytes(self):
        buffer = BytesIO()
        Image.new("RGB", (20, 20), (30, 60, 90)).save(buffer, format="PNG")
        return buffer.getvalue()

    def test_store_find_url_and_remove_round_trip(self):
        uid = "12345678-1234-1234-1234-123456789abc"

        store_event_poster(uid, self.image_bytes())

        path = find_event_poster(uid)
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith(".jpg"))
        self.assertEqual("image/jpeg", event_poster_mimetype(path))
        self.assertIn(f"/static/images/eventposter/{uid}?v=", event_poster_url(uid))

        remove_event_poster(uid)
        self.assertIsNone(find_event_poster(uid))

    def test_legacy_file_without_extension_is_found(self):
        uid = "legacy-poster"
        target = Path(self.tempdir.name) / "static" / "images" / "eventposter" / uid
        target.parent.mkdir(parents=True)
        target.write_bytes(self.image_bytes())

        self.assertEqual(str(target), find_event_poster(uid))


if __name__ == "__main__":
    unittest.main()
