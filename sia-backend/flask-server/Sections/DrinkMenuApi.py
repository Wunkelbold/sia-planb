"""Public drink menu with admin-managed sections, items, images, and a QR code."""

import os
from datetime import datetime
from uuid import UUID

import click
from flask import current_app, jsonify, request
from flask_login import current_user

from database import Tables, db
from globals import app
from permissions import hasPermissions
from Sections.DrinkMenuRules import (
    MAX_DRINK_IMAGE_BYTES,
    parse_menu_item_payload,
    parse_menu_section_payload,
    prepare_drink_image,
)


MENU_MANAGE_PERMISSION = "menu.manage"
DRINK_IMAGE_SUBDIR = ("static", "images", "drinks")
DRINK_IMAGE_URL_PREFIX = "/static/images/drinks/"


def menu_response(payload, status=200, cache="private, no-store"):
    response = jsonify(payload)
    response.headers["Cache-Control"] = cache
    return response, status


def menu_access_denied():
    if not current_user.is_authenticated:
        return menu_response({"error": "authentication_required"}, 401)
    if not hasPermissions(MENU_MANAGE_PERMISSION):
        return menu_response({"error": "permission_denied"}, 403)
    return None


def drink_image_path(item):
    return os.path.join(current_app.root_path, *DRINK_IMAGE_SUBDIR, str(item.uid))


def remove_drink_image_file(item):
    if not item.image_path:
        return
    base = drink_image_path(item)
    for extension in ("png", "jpg", "jpeg", "webp"):
        candidate = f"{base}.{extension}"
        if os.path.exists(candidate):
            try:
                os.remove(candidate)
            except OSError:
                current_app.logger.warning("Could not remove drink image %s", candidate)


def store_drink_image(item, data):
    contents, extension = prepare_drink_image(data)
    remove_drink_image_file(item)
    target = f"{drink_image_path(item)}.{extension}"
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as handle:
        handle.write(contents)
    item.image_path = f"{DRINK_IMAGE_URL_PREFIX}{item.uid}.{extension}"


def serialize_menu_item(item):
    return {
        "uid": str(item.uid),
        "name": item.name,
        "group_label": item.group_label or "",
        "description": item.description or "",
        "volume_label": item.volume_label or "",
        "price_cents": item.price_cents,
        "show_price": item.show_price,
        "image_url": item.image_path or "",
        "sort_order": item.sort_order,
        "is_active": item.is_active,
    }


def serialize_menu_section(section, items):
    return {
        "uid": str(section.uid),
        "title": section.title,
        "subtitle": section.subtitle or "",
        "price_cents": section.price_cents,
        "show_price": section.show_price,
        "sort_order": section.sort_order,
        "is_active": section.is_active,
        "items": [serialize_menu_item(item) for item in items],
    }


def menu_sections_with_items(include_inactive):
    sections_query = Tables.DrinkMenuSection.query
    if not include_inactive:
        sections_query = sections_query.filter_by(is_active=True)
    sections = sections_query.order_by(Tables.DrinkMenuSection.sort_order.asc(), Tables.DrinkMenuSection.id.asc()).all()
    section_ids = [section.id for section in sections]
    items_by_section = {section.id: [] for section in sections}
    if section_ids:
        items_query = Tables.DrinkMenuItem.query.filter(Tables.DrinkMenuItem.section_id.in_(section_ids))
        if not include_inactive:
            items_query = items_query.filter_by(is_active=True)
        items = items_query.order_by(Tables.DrinkMenuItem.sort_order.asc(), Tables.DrinkMenuItem.id.asc()).all()
        for item in items:
            items_by_section[item.section_id].append(item)
    return [(section, items_by_section[section.id]) for section in sections]


def drink_menu_public_url():
    base = os.getenv("FRONTEND_URL", "").rstrip("/") or request.host_url.rstrip("/")
    return f"{base}/getraenkekarte"


def drink_menu_qr_data_url():
    generator = current_app.extensions.get("qrcode")
    if not generator:
        return ""
    try:
        return generator(drink_menu_public_url())
    except Exception:  # pragma: no cover - QR generation must never break the menu
        current_app.logger.exception("Could not generate the drink menu QR code")
        return ""


def menu_updated_at(sections_with_items):
    stamps = [section.updated_at for section, _ in sections_with_items if section.updated_at]
    for _, items in sections_with_items:
        stamps.extend(item.updated_at for item in items if item.updated_at)
    return max(stamps) if stamps else None


@app.route("/api/v1/drink-menu", methods=["GET"])
def api_public_drink_menu():
    """Return the public drink menu with the live QR code for sharing."""
    sections_with_items = menu_sections_with_items(include_inactive=False)
    updated_at = menu_updated_at(sections_with_items)
    return menu_response({
        "sections": [
            serialize_menu_section(section, items)
            for section, items in sections_with_items
            if items
        ],
        "updated_at": updated_at.isoformat(timespec="minutes") if updated_at else None,
        "qr_data_url": drink_menu_qr_data_url(),
        "menu_url": drink_menu_public_url(),
    }, cache="public, max-age=60")


@app.route("/api/v1/manage/drink-menu", methods=["GET"])
def api_manage_drink_menu():
    denied = menu_access_denied()
    if denied:
        return denied
    sections_with_items = menu_sections_with_items(include_inactive=True)
    return menu_response({
        "sections": [serialize_menu_section(section, items) for section, items in sections_with_items],
        "menu_url": drink_menu_public_url(),
    })


@app.route("/api/v1/manage/drink-menu/sections", methods=["POST"])
def api_create_drink_menu_section():
    denied = menu_access_denied()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    errors = {}
    values = parse_menu_section_payload(payload, errors)
    if errors:
        return menu_response({"success": False, "errors": errors}, 400)
    section = Tables.DrinkMenuSection(
        **values,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.session.add(section)
    db.session.commit()
    return menu_response({"success": True, "section": serialize_menu_section(section, [])}, 201)


@app.route("/api/v1/manage/drink-menu/sections/<section_uid>", methods=["PUT"])
def api_update_drink_menu_section(section_uid):
    denied = menu_access_denied()
    if denied:
        return denied
    section = find_section(section_uid)
    if not section:
        return menu_response({"error": "Kategorie nicht gefunden."}, 404)
    payload = request.get_json(silent=True) or {}
    errors = {}
    values = parse_menu_section_payload(payload, errors)
    if errors:
        return menu_response({"success": False, "errors": errors}, 400)
    for key, value in values.items():
        setattr(section, key, value)
    section.updated_by = current_user.id
    section.updated_at = datetime.now()
    db.session.commit()
    items = Tables.DrinkMenuItem.query.filter_by(section_id=section.id).order_by(
        Tables.DrinkMenuItem.sort_order.asc(),
        Tables.DrinkMenuItem.id.asc(),
    ).all()
    return menu_response({"success": True, "section": serialize_menu_section(section, items)})


@app.route("/api/v1/manage/drink-menu/sections/<section_uid>", methods=["DELETE"])
def api_deactivate_drink_menu_section(section_uid):
    denied = menu_access_denied()
    if denied:
        return denied
    section = find_section(section_uid)
    if not section:
        return menu_response({"error": "Kategorie nicht gefunden."}, 404)
    section.is_active = False
    section.updated_by = current_user.id
    section.updated_at = datetime.now()
    Tables.DrinkMenuItem.query.filter_by(section_id=section.id).update({
        Tables.DrinkMenuItem.is_active: False,
        Tables.DrinkMenuItem.updated_by: current_user.id,
        Tables.DrinkMenuItem.updated_at: datetime.now(),
    })
    db.session.commit()
    return menu_response({"success": True})


@app.route("/api/v1/manage/drink-menu/items", methods=["POST"])
def api_create_drink_menu_item():
    denied = menu_access_denied()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    errors = {}
    section = find_section(payload.get("section_uid"))
    if not section:
        errors["section_uid"] = "Bitte wähle eine gültige Kategorie."
    values = parse_menu_item_payload(payload, errors, section.id if section else None)
    if errors:
        return menu_response({"success": False, "errors": errors}, 400)
    item = Tables.DrinkMenuItem(
        **values,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.session.add(item)
    db.session.commit()
    return menu_response({"success": True, "item": serialize_menu_item(item)}, 201)


@app.route("/api/v1/manage/drink-menu/items/<item_uid>", methods=["PUT"])
def api_update_drink_menu_item(item_uid):
    denied = menu_access_denied()
    if denied:
        return denied
    item = find_item(item_uid)
    if not item:
        return menu_response({"error": "Artikel nicht gefunden."}, 404)
    payload = request.get_json(silent=True) or {}
    errors = {}
    section = find_section(payload.get("section_uid")) if payload.get("section_uid") else Tables.DrinkMenuSection.query.get(item.section_id)
    if not section:
        errors["section_uid"] = "Bitte wähle eine gültige Kategorie."
    values = parse_menu_item_payload(payload, errors, section.id if section else item.section_id)
    if errors:
        return menu_response({"success": False, "errors": errors}, 400)
    for key, value in values.items():
        setattr(item, key, value)
    item.updated_by = current_user.id
    item.updated_at = datetime.now()
    db.session.commit()
    return menu_response({"success": True, "item": serialize_menu_item(item)})


@app.route("/api/v1/manage/drink-menu/items/<item_uid>", methods=["DELETE"])
def api_deactivate_drink_menu_item(item_uid):
    denied = menu_access_denied()
    if denied:
        return denied
    item = find_item(item_uid)
    if not item:
        return menu_response({"error": "Artikel nicht gefunden."}, 404)
    item.is_active = False
    item.updated_by = current_user.id
    item.updated_at = datetime.now()
    db.session.commit()
    return menu_response({"success": True})


@app.route("/api/v1/manage/drink-menu/items/<item_uid>/image", methods=["POST"])
def api_upload_drink_menu_item_image(item_uid):
    denied = menu_access_denied()
    if denied:
        return denied
    item = find_item(item_uid)
    if not item:
        return menu_response({"error": "Artikel nicht gefunden."}, 404)
    upload = request.files.get("file")
    if not upload:
        return menu_response({"success": False, "errors": {"file": "Bitte wähle eine Bilddatei aus."}}, 400)
    try:
        store_drink_image(item, upload.read(MAX_DRINK_IMAGE_BYTES + 1))
    except ValueError as error:
        return menu_response({"success": False, "errors": {"file": str(error)}}, 400)
    item.updated_by = current_user.id
    item.updated_at = datetime.now()
    db.session.commit()
    return menu_response({"success": True, "item": serialize_menu_item(item)})


@app.route("/api/v1/manage/drink-menu/items/<item_uid>/image", methods=["DELETE"])
def api_remove_drink_menu_item_image(item_uid):
    denied = menu_access_denied()
    if denied:
        return denied
    item = find_item(item_uid)
    if not item:
        return menu_response({"error": "Artikel nicht gefunden."}, 404)
    remove_drink_image_file(item)
    item.image_path = None
    item.updated_by = current_user.id
    item.updated_at = datetime.now()
    db.session.commit()
    return menu_response({"success": True, "item": serialize_menu_item(item)})


def find_section(section_uid):
    try:
        parsed = UUID(str(section_uid))
    except (TypeError, ValueError):
        return None
    return Tables.DrinkMenuSection.query.filter_by(uid=parsed).first()


def find_item(item_uid):
    try:
        parsed = UUID(str(item_uid))
    except (TypeError, ValueError):
        return None
    return Tables.DrinkMenuItem.query.filter_by(uid=parsed).first()


DEFAULT_MENU = [
    {
        "title": "Mix your own Longdrink",
        "subtitle": "5 cl Alkohol deiner Wahl + Alkoholfreies Mischgetränk",
        "price_cents": 500,
        "show_price": True,
        "items": [
            ("Alkohol · 5 cl", ["Tequila", "Vodka", "Dos Mas", "Jägermeister", "Jack Daniels", "Ficken", "Rum", "Malibu"]),
            ("Mischgetränk", ["Orangensaft", "Maracujasaft", "Tonic Water", "Bitter Lemon", "Cola", "Sprite", "Fanta", "Energy"]),
        ],
    },
    {
        "title": "Bier",
        "subtitle": "",
        "price_cents": None,
        "show_price": False,
        "items": [
            (None, [("Hirsch Helles", "0,5 l", 350), ("Hirsch Zwuckl", "0,33 l", 300), ("Radler", "0,33 l", 300), ("Salitos Ice", "0,33 l", 350), ("Desperados", "0,33 l", 350)]),
        ],
    },
    {
        "title": "Alkoholfrei",
        "subtitle": "",
        "price_cents": None,
        "show_price": False,
        "items": [
            (None, [
                ("Fritz Kola", "0,33 l", 250),
                ("Fritz Kola light", "0,33 l", 250),
                ("Effect Energy Açaí", "0,25 l", 250),
                ("Effect Energy", "0,25 l", 250),
                ("Stingel Pfirsich Eistee", "0,33 l", 250),
                ("Stingel Johannisbeere", "0,33 l", 250),
                ("Orangensaft", "0,3 l", 250),
                ("Maracujasaft", "0,3 l", 250),
                ("Mineralwasser", "0,5 l", 150),
            ]),
        ],
    },
    {
        "title": "Shots",
        "subtitle": "je 2 cl",
        "price_cents": None,
        "show_price": False,
        "items": [
            (None, [
                ("Tequila", "", 200),
                ("Vodka", "", 200),
                ("Schüttler", "", 200),
                ("Jägermeister", "", 200),
                ("Dos Mas Kiss", "", 200),
                ("Dos Mas Pink", "", 200),
                ("Dos Mas Max", "", 200),
                ("Ficken", "", 200),
            ]),
        ],
    },
    {
        "title": "Warme Getränke",
        "subtitle": "",
        "price_cents": None,
        "show_price": False,
        "items": [
            (None, [("Kaffee", "", 250), ("Tee", "", 150)]),
        ],
    },
]


@app.cli.command("seed-drink-menu")
def seed_drink_menu():
    """Create the printed Plan B drink menu once, if no sections exist yet."""
    if Tables.DrinkMenuSection.query.first():
        click.echo("Drink menu already exists; nothing was changed.")
        return
    item_count = 0
    for section_index, spec in enumerate(DEFAULT_MENU, start=1):
        section = Tables.DrinkMenuSection(
            title=spec["title"],
            subtitle=spec["subtitle"] or None,
            price_cents=spec["price_cents"],
            show_price=spec["show_price"],
            sort_order=section_index,
            is_active=True,
        )
        db.session.add(section)
        db.session.flush()
        item_order = 0
        for group_label, entries in spec["items"]:
            for entry in entries:
                item_order += 1
                name, volume_label, price_cents = entry if isinstance(entry, tuple) else (entry, "", None)
                db.session.add(Tables.DrinkMenuItem(
                    section_id=section.id,
                    group_label=group_label,
                    name=name,
                    volume_label=volume_label or None,
                    price_cents=price_cents,
                    show_price=price_cents is not None,
                    sort_order=item_order,
                    is_active=True,
                ))
                item_count += 1
    db.session.commit()
    click.echo(f"Created the drink menu with {len(DEFAULT_MENU)} sections and {item_count} items.")
