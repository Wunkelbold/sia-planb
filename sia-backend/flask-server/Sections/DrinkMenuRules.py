"""Pure validation and image helpers for the public drink menu."""

from io import BytesIO

from PIL import Image, UnidentifiedImageError


MAX_PRICE_CENTS = 1_000_000
MAX_SORT_ORDER = 9999
MAX_DRINK_IMAGE_BYTES = 5 * 1024 * 1024
DRINK_IMAGE_MAX_EDGE = 1000


def parse_price_cents(value, field, errors):
    if value in (None, ""):
        return None
    try:
        amount = int(value)
    except (TypeError, ValueError):
        errors[field] = "Bitte gib einen gültigen Preis an."
        return None
    if amount < 0 or amount > MAX_PRICE_CENTS:
        errors[field] = "Der Preis muss zwischen 0 und 10.000 € liegen."
        return None
    return amount


def parse_sort_order(value, field, errors, default=0):
    if value in (None, ""):
        return default
    try:
        order = int(value)
    except (TypeError, ValueError):
        errors[field] = "Bitte gib eine gültige Sortiernummer an."
        return default
    if order < 0 or order > MAX_SORT_ORDER:
        errors[field] = "Die Sortiernummer muss zwischen 0 und 9999 liegen."
        return default
    return order


def parse_text(value, field, errors, max_length, required=False):
    text = str(value or "").strip()
    if required and not text:
        errors[field] = "Dieses Feld wird benötigt."
        return ""
    if len(text) > max_length:
        errors[field] = f"Bitte höchstens {max_length} Zeichen verwenden."
        return ""
    return text


def parse_menu_section_payload(payload, errors):
    return {
        "title": parse_text(payload.get("title"), "title", errors, 80, required=True),
        "subtitle": parse_text(payload.get("subtitle"), "subtitle", errors, 200) or None,
        "price_cents": parse_price_cents(payload.get("price_cents"), "price_cents", errors),
        "show_price": bool(payload.get("show_price", False)),
        "sort_order": parse_sort_order(payload.get("sort_order"), "sort_order", errors),
        "is_active": bool(payload.get("is_active", True)),
    }


def parse_menu_item_payload(payload, errors, section_id):
    return {
        "section_id": section_id,
        "name": parse_text(payload.get("name"), "name", errors, 80, required=True),
        "group_label": parse_text(payload.get("group_label"), "group_label", errors, 80) or None,
        "description": parse_text(payload.get("description"), "description", errors, 200) or None,
        "volume_label": parse_text(payload.get("volume_label"), "volume_label", errors, 40) or None,
        "price_cents": parse_price_cents(payload.get("price_cents"), "price_cents", errors),
        "show_price": bool(payload.get("show_price", True)),
        "sort_order": parse_sort_order(payload.get("sort_order"), "sort_order", errors),
        "is_active": bool(payload.get("is_active", True)),
    }


def prepare_drink_image(data):
    """Validate and downscale an uploaded image. Returns (bytes, extension)."""
    if not data:
        raise ValueError("Die Datei ist leer.")
    if len(data) > MAX_DRINK_IMAGE_BYTES:
        raise ValueError("Das Bild darf höchstens 5 MB groß sein.")
    try:
        probe = Image.open(BytesIO(data))
        probe.verify()
        image = Image.open(BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ValueError("Bitte lade ein gültiges Bild (PNG, JPG oder WebP) hoch.") from error

    if image.mode in {"P", "LA"} or (image.mode == "RGBA" and image.getextrema()[3][0] < 255):
        image = image.convert("RGBA")
        keep_alpha = True
    else:
        image = image.convert("RGB")
        keep_alpha = False
    if max(image.size) > DRINK_IMAGE_MAX_EDGE:
        image.thumbnail((DRINK_IMAGE_MAX_EDGE, DRINK_IMAGE_MAX_EDGE), Image.LANCZOS)

    buffer = BytesIO()
    if keep_alpha:
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue(), "png"
    image.save(buffer, format="JPEG", quality=85, optimize=True)
    return buffer.getvalue(), "jpg"
