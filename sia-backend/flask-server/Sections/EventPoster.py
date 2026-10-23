"""Validation, storage, and URL helpers for event poster images."""

import os
from io import BytesIO

from flask import current_app, url_for
from PIL import Image, UnidentifiedImageError


MAX_EVENT_POSTER_BYTES = 5 * 1024 * 1024
EVENT_POSTER_MAX_EDGE = 1200
EVENT_POSTER_EXTENSIONS = ("png", "jpg", "jpeg")


def poster_directory():
    return os.path.join(current_app.root_path, "static", "images", "eventposter")


def poster_base_path(event_uid):
    return os.path.join(poster_directory(), os.path.basename(str(event_uid)))


def poster_candidates(event_uid):
    base = poster_base_path(event_uid)
    return [*(f"{base}.{extension}" for extension in EVENT_POSTER_EXTENSIONS), base]


def find_event_poster(event_uid):
    for candidate in poster_candidates(event_uid):
        if os.path.isfile(candidate):
            return candidate
    return None


def event_poster_url(event_uid):
    path = find_event_poster(event_uid)
    if not path:
        return url_for("get_image", filename=str(event_uid))
    try:
        version = os.stat(path).st_mtime_ns
    except OSError:
        version = 0
    return url_for("get_image", filename=str(event_uid), v=version)


def event_poster_mimetype(path):
    try:
        with open(path, "rb") as handle:
            header = handle.read(8)
    except OSError:
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return "image/jpeg"


def remove_event_poster(event_uid):
    for candidate in poster_candidates(event_uid):
        if not os.path.isfile(candidate):
            continue
        try:
            os.remove(candidate)
        except OSError:
            current_app.logger.warning("Could not remove event poster %s", candidate)


def store_event_poster(event_uid, data):
    contents, extension = prepare_event_poster(data)
    target = f"{poster_base_path(event_uid)}.{extension}"
    os.makedirs(os.path.dirname(target), exist_ok=True)
    temporary = f"{target}.tmp"
    try:
        with open(temporary, "wb") as handle:
            handle.write(contents)
        os.replace(temporary, target)
    finally:
        if os.path.isfile(temporary):
            try:
                os.remove(temporary)
            except OSError:
                current_app.logger.warning("Could not remove temporary event poster %s", temporary)

    for candidate in poster_candidates(event_uid):
        if candidate == target or not os.path.isfile(candidate):
            continue
        try:
            os.remove(candidate)
        except OSError:
            current_app.logger.warning("Could not remove old event poster %s", candidate)
    return extension


def prepare_event_poster(data):
    """Validate and downscale an uploaded poster. Returns (bytes, extension)."""
    if not data:
        raise ValueError("Die Datei ist leer.")
    if len(data) > MAX_EVENT_POSTER_BYTES:
        raise ValueError("Das Bild darf höchstens 5 MB groß sein.")
    try:
        probe = Image.open(BytesIO(data))
        probe.verify()
        image = Image.open(BytesIO(data))
        image.load()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as error:
        raise ValueError("Bitte lade ein gültiges Bild (PNG oder JPG) hoch.") from error

    if image.mode in {"P", "LA"} or (image.mode == "RGBA" and image.getextrema()[3][0] < 255):
        image = image.convert("RGBA")
        keep_alpha = True
    else:
        image = image.convert("RGB")
        keep_alpha = False
    if max(image.size) > EVENT_POSTER_MAX_EDGE:
        image.thumbnail((EVENT_POSTER_MAX_EDGE, EVENT_POSTER_MAX_EDGE), Image.LANCZOS)

    buffer = BytesIO()
    if keep_alpha:
        image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue(), "png"
    image.save(buffer, format="JPEG", quality=88, optimize=True)
    return buffer.getvalue(), "jpg"
