import sys
import unittest
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "flask-server"))

from PIL import Image

from Sections.DrinkMenuRules import (
    DRINK_IMAGE_MAX_EDGE,
    MAX_DRINK_IMAGE_BYTES,
    parse_menu_item_payload,
    parse_menu_section_payload,
    parse_price_cents,
    parse_sort_order,
    parse_text,
    prepare_drink_image,
)


class DrinkMenuParsingTests(unittest.TestCase):
    def test_prices_accept_cents_and_empty_values(self):
        errors = {}
        self.assertIsNone(parse_price_cents(None, "price_cents", errors))
        self.assertIsNone(parse_price_cents("", "price_cents", errors))
        self.assertEqual(250, parse_price_cents("250", "price_cents", errors))
        self.assertEqual(500, parse_price_cents(500, "price_cents", errors))
        self.assertEqual({}, errors)

    def test_prices_reject_invalid_and_extreme_values(self):
        errors = {}
        self.assertIsNone(parse_price_cents(-1, "price_cents", errors))
        self.assertIn("price_cents", errors)
        errors = {}
        self.assertIsNone(parse_price_cents(1_000_001, "price_cents", errors))
        self.assertIn("price_cents", errors)
        errors = {}
        self.assertIsNone(parse_price_cents("abc", "price_cents", errors))
        self.assertIn("price_cents", errors)

    def test_sort_order_defaults_and_bounds(self):
        errors = {}
        self.assertEqual(0, parse_sort_order(None, "sort_order", errors))
        self.assertEqual(7, parse_sort_order("7", "sort_order", errors))
        self.assertEqual(3, parse_sort_order(None, "sort_order", errors, default=3))
        self.assertEqual(0, parse_sort_order(-5, "sort_order", errors))
        self.assertIn("sort_order", errors)

    def test_text_trimming_and_length_limits(self):
        errors = {}
        self.assertEqual("Bier", parse_text("  Bier  ", "title", errors, 80, required=True))
        self.assertEqual("", parse_text("   ", "title", errors, 80, required=True))
        self.assertIn("title", errors)
        errors = {}
        self.assertEqual("", parse_text("x" * 81, "title", errors, 80))
        self.assertIn("title", errors)

    def test_section_payload_defaults(self):
        errors = {}
        values = parse_menu_section_payload({"title": "Shots"}, errors)
        self.assertEqual({}, errors)
        self.assertEqual("Shots", values["title"])
        self.assertIsNone(values["subtitle"])
        self.assertIsNone(values["price_cents"])
        self.assertFalse(values["show_price"])
        self.assertTrue(values["is_active"])
        self.assertEqual(0, values["sort_order"])

    def test_item_payload_keeps_section_and_defaults(self):
        errors = {}
        values = parse_menu_item_payload({"name": "Kaffee", "price_cents": 250}, errors, 12)
        self.assertEqual({}, errors)
        self.assertEqual(12, values["section_id"])
        self.assertEqual("Kaffee", values["name"])
        self.assertEqual(250, values["price_cents"])
        self.assertTrue(values["show_price"])
        self.assertIsNone(values["volume_label"])

    def test_item_payload_requires_a_name(self):
        errors = {}
        values = parse_menu_item_payload({"name": "   "}, errors, 12)
        self.assertIn("name", errors)
        self.assertEqual("", values["name"])


class DrinkMenuImageTests(unittest.TestCase):
    def test_alpha_png_is_downscaled_and_kept_as_png(self):
        buffer = BytesIO()
        Image.new("RGBA", (1600, 900), (200, 40, 40, 160)).save(buffer, format="PNG")
        contents, extension = prepare_drink_image(buffer.getvalue())
        self.assertEqual("png", extension)
        self.assertEqual(b"\x89PNG\r\n\x1a\n", contents[:8])
        with Image.open(BytesIO(contents)) as image:
            self.assertLessEqual(max(image.size), DRINK_IMAGE_MAX_EDGE)

    def test_opaque_image_is_converted_to_jpeg(self):
        buffer = BytesIO()
        Image.new("RGB", (400, 300), (10, 80, 10)).save(buffer, format="PNG")
        contents, extension = prepare_drink_image(buffer.getvalue())
        self.assertEqual("jpg", extension)
        self.assertEqual(b"\xff\xd8", contents[:2])
        with Image.open(BytesIO(contents)) as image:
            self.assertEqual("RGB", image.mode)

    def test_invalid_bytes_are_rejected(self):
        with self.assertRaises(ValueError):
            prepare_drink_image(b"not an image")

    def test_empty_and_oversized_uploads_are_rejected(self):
        with self.assertRaises(ValueError):
            prepare_drink_image(b"")
        with self.assertRaises(ValueError):
            prepare_drink_image(b"x" * (MAX_DRINK_IMAGE_BYTES + 1))


if __name__ == "__main__":
    unittest.main()
