from datetime import date, datetime, timedelta
from decimal import Decimal
from fnmatch import fnmatch
from uuid import UUID
import re

from flask import current_app, jsonify, redirect, request
from flask_login import current_user
from sqlalchemy import or_
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from database import Tables, db
from globals import app, local_tz
from permissions import hasPermissions
from Sections.FinanceAllocations import (
    allocate_existing_credit_to_charge,
    allocate_unallocated_credit_to_charges,
    allocation_amounts_for_charges,
    allocation_amounts_for_payments,
    charge_payment_state,
    payment_allocation_rows,
    reconcile_charge_amount,
    release_charge_allocations,
    release_payment_allocations,
    sync_charge_payment_state,
    unallocated_payment_cents,
)
from Sections.FinanceMatching import suggest_charge_match
from Sections.FinanceRules import (
    FEE_CATEGORY_LABELS,
    PDF_ANNUAL_RATE_DEFAULTS,
    calendar_year_amount_from_monthly_rates,
    normalize_fee_category,
    next_student_billing_cycle_year,
    student_first_billing_period,
    student_first_payable_month,
)
from Sections.RegistrationService import set_finance_charge_status, set_registration_paid


ALL_FEE_CATEGORIES = {"full", "reduced", "student", "training", "exempt", "special"}
REQUESTABLE_FEE_CATEGORIES = {"full", "reduced", "student", "training", "exempt", "special"}
RATE_FEE_CATEGORIES = {"full", "reduced", "student", "training", "exempt"}


def finance_response(payload, status=200, cache="private, no-store"):
    response = jsonify(payload)
    response.headers["Cache-Control"] = cache
    return response, status


def finance_access_denied():
    if not current_user.is_authenticated:
        return finance_response({"error": "authentication_required"}, 401)
    if not hasPermissions("finance.manage"):
        return finance_response({"error": "permission_denied"}, 403)
    return None


def parse_date(value, field, errors, required=False):
    if value in (None, ""):
        if required:
            errors[field] = "Dieses Datum wird benötigt."
        return None
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        errors[field] = "Bitte gib ein gültiges Datum an."
        return None


def parse_datetime(value, field, errors):
    if value in (None, ""):
        return datetime.now()
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        errors[field] = "Bitte gib ein gültiges Datum und eine Uhrzeit an."
        return None
    if parsed.tzinfo:
        parsed = parsed.astimezone(local_tz).replace(tzinfo=None)
    return parsed


def as_datetime(value):
    return value.replace(tzinfo=local_tz).isoformat(timespec="minutes") if value else None


def current_membership(user_id):
    return Tables.Membership.query.filter_by(user_id=user_id).first()


def user_membership_ids(user_id):
    return [row[0] for row in db.session.query(Tables.Membership.id).filter_by(user_id=user_id).all()]


def user_finance_filter(model, user_id, membership_ids=None):
    membership_ids = membership_ids if membership_ids is not None else user_membership_ids(user_id)
    clauses = [model.user_id == user_id]
    if membership_ids:
        clauses.append(model.membership_id.in_(membership_ids))
    return or_(*clauses)


def user_balance(user_id):
    membership_ids = user_membership_ids(user_id)
    charges = (
        db.session.query(db.func.coalesce(db.func.sum(Tables.FinanceCharge.amount_cents), 0))
        .filter(user_finance_filter(Tables.FinanceCharge, user_id, membership_ids))
        .filter(Tables.FinanceCharge.status != "cancelled")
        .scalar()
    ) or 0
    payments = (
        db.session.query(db.func.coalesce(db.func.sum(Tables.FinancePayment.amount_cents), 0))
        .filter(user_finance_filter(Tables.FinancePayment, user_id, membership_ids))
        .filter(Tables.FinancePayment.voided_at.is_(None))
        .scalar()
    ) or 0
    return int(charges) - int(payments)


def user_charges(user_id):
    membership_ids = user_membership_ids(user_id)
    return Tables.FinanceCharge.query.filter(user_finance_filter(Tables.FinanceCharge, user_id, membership_ids))


def user_payments(user_id):
    membership_ids = user_membership_ids(user_id)
    return Tables.FinancePayment.query.filter(user_finance_filter(Tables.FinancePayment, user_id, membership_ids))


def payment_charge_match_suggestion(user_id, payment_amount_cents):
    charges = user_charges(user_id).filter(
        Tables.FinanceCharge.amount_cents > 0,
        Tables.FinanceCharge.status.notin_(["cancelled", "waived"]),
    ).all()
    charges = [
        charge for charge in charges
        if charge.kind != "event_ticket"
        or (charge.registration and not charge.registration.cancelled_at)
    ]
    allocation_totals = allocation_amounts_for_charges([charge.id for charge in charges])
    candidates = []
    for charge in charges:
        state = charge_payment_state(charge, allocation_totals.get(charge.id, 0))
        if state["status"] in {"open", "partially_paid"} and state["remaining_cents"] > 0:
            charge.match_remaining_cents = state["remaining_cents"]
            charge.match_status = state["status"]
            candidates.append(charge)
    available_amount_cents = unallocated_payment_cents(user_id)
    suggestion = suggest_charge_match(candidates, available_amount_cents)
    return {
        "payment_amount_cents": int(payment_amount_cents),
        "available_amount_cents": available_amount_cents,
        "total_cents": suggestion["total_cents"],
        "remainder_cents": suggestion["remainder_cents"],
        "all_open_charges": suggestion["all_open_charges"],
        "charges": serialize_charges(suggestion["charges"]),
    }


def member_balance(membership_id):
    membership = Tables.Membership.query.filter_by(id=membership_id).first()
    return user_balance(membership.user_id) if membership else 0


def serialize_charge(charge, settlement=None):
    registration = charge.registration if charge.registration_id else None
    manager = registration.RegisterManager if registration else None
    event = Tables.Event.query.filter_by(id=manager.eventFK).first() if manager else None
    settlement = settlement or charge_payment_state(charge)
    return {
        "uid": str(charge.uid),
        "kind": charge.kind,
        "name": charge.name_snapshot,
        "registration_id": charge.registration_id,
        "registration_name": manager.name if manager else None,
        "event_name": event.name if event else None,
        "event_date": as_datetime(event.date) if event else None,
        "fee_category": normalize_fee_category(charge.fee_category_snapshot),
        "cycle_year": charge.cycle_year,
        "quantity": charge.quantity,
        "unit_price_cents": charge.unit_price_cents,
        "amount_cents": charge.amount_cents,
        "due_date": charge.due_date.isoformat() if charge.due_date else None,
        "status": settlement["status"],
        "allocated_cents": settlement["allocated_cents"],
        "remaining_cents": settlement["remaining_cents"],
        "legacy_paid_override": bool(charge.legacy_paid_override),
        "created_at": as_datetime(charge.created_at),
        "status_at": as_datetime(charge.status_at),
        "status_note": charge.status_note or "",
    }


def serialize_charges(charges):
    charges = list(charges)
    allocations = allocation_amounts_for_charges([charge.id for charge in charges])
    return [
        serialize_charge(charge, charge_payment_state(charge, allocations.get(charge.id, 0)))
        for charge in charges
    ]


def serialize_charge_adjustments(user_id):
    charges = user_charges(user_id).all()
    charge_by_id = {charge.id: charge for charge in charges}
    if not charge_by_id:
        return []
    history = Tables.FinanceChargeAdjustmentHistory.query.filter(
        Tables.FinanceChargeAdjustmentHistory.charge_id.in_(charge_by_id),
    ).order_by(
        Tables.FinanceChargeAdjustmentHistory.changed_at.desc(),
        Tables.FinanceChargeAdjustmentHistory.id.desc(),
    ).all()
    actors = {
        user.id: user.username
        for user in Tables.User.query.filter(
            Tables.User.id.in_([event.changed_by for event in history if event.changed_by]),
        ).all()
    } if any(event.changed_by for event in history) else {}
    return [
        {
            "id": event.id,
            "charge_uid": str(charge_by_id[event.charge_id].uid),
            "charge_name": event.to_name,
            "cycle_year": event.cycle_year,
            "from_amount_cents": event.from_amount_cents,
            "to_amount_cents": event.to_amount_cents,
            "from_fee_category": normalize_fee_category(event.from_fee_category),
            "to_fee_category": normalize_fee_category(event.to_fee_category),
            "from_due_date": event.from_due_date.isoformat() if event.from_due_date else None,
            "to_due_date": event.to_due_date.isoformat() if event.to_due_date else None,
            "changed_by_username": actors.get(event.changed_by, "Verwaltung"),
            "changed_at": as_datetime(event.changed_at),
            "source": event.source,
            "note": event.note or "",
        }
        for event in history
    ]


def serialize_payment(payment):
    allocations = payment_allocation_rows(payment)
    allocated_cents = sum(item["active_allocated_cents"] for item in allocations)
    return {
        "uid": str(payment.uid),
        "amount_cents": payment.amount_cents,
        "method": payment.method,
        "reference": payment.reference or "",
        "note": payment.note or "",
        "received_at": as_datetime(payment.received_at),
        "voided_at": as_datetime(payment.voided_at),
        "void_reason": payment.void_reason or "",
        "allocated_cents": allocated_cents,
        "unallocated_cents": 0 if payment.voided_at else max(0, payment.amount_cents - allocated_cents),
        "allocations": allocations,
    }


def serialize_membership_history(event):
    actor = Tables.User.query.filter_by(id=event.changed_by).first() if event.changed_by else None
    return {
        "id": event.id,
        "changed_at": as_datetime(event.changed_at),
        "changed_by": event.changed_by,
        "changed_by_username": actor.username if actor else "Verwaltung",
        "from_status": event.from_status,
        "to_status": event.to_status,
        "from_fee_category": normalize_fee_category(event.from_fee_category),
        "to_fee_category": normalize_fee_category(event.to_fee_category),
        "from_member_since": event.from_member_since.isoformat() if event.from_member_since else None,
        "to_member_since": event.to_member_since.isoformat() if event.to_member_since else None,
        "from_special_rate_cents": event.from_special_rate_cents,
        "to_special_rate_cents": event.to_special_rate_cents,
        "note": event.note or "",
    }


def serialize_tally_item(item):
    return {
        "id": item.id,
        "uid": str(item.uid),
        "name": item.name,
        "price_cents": item.price_cents,
        "is_active": item.is_active,
    }


def serialize_membership(membership, include_balance=True):
    user = membership.user_obj
    payload = {
        "uid": str(membership.uid),
        "user_uid": str(user.uid) if user else None,
        "username": user.username if user else "Gelöschtes Konto",
        "role": user.role if user else "",
        "surname": (user.surname or "") if user else "",
        "lastname": (user.lastname or "") if user else "",
        "email": (user.email or "") if user else "",
        "email_confirmed": bool(user.email_confirmed) if user else False,
        "hs_email": (user.hs_email or "") if user else "",
        "hs_email_confirmed": bool(user.hs_email_confirmed) if user else False,
        "status": membership.status,
        "fee_category": normalize_fee_category(membership.fee_category),
        "member_since": membership.member_since.isoformat() if membership.member_since else None,
        "ended_at": membership.ended_at.isoformat() if membership.ended_at else None,
        "special_rate_cents": membership.special_rate_cents,
        "special_rate_valid_until": membership.special_rate_valid_until.isoformat() if membership.special_rate_valid_until else None,
    }
    if include_balance:
        payload["balance_cents"] = member_balance(membership.id)
    return payload


def serialize_finance_user(user):
    membership = current_membership(user.id)
    role = Tables.Role.query.filter_by(name=user.role).first()
    permission_grants = (list(role.permissions or []) if role else []) + list(user.permissions or [])
    return {
        "uid": str(user.uid),
        "username": user.username,
        "surname": user.surname or "",
        "lastname": user.lastname or "",
        "role": user.role,
        "email": user.email or "",
        "email_confirmed": bool(user.email_confirmed),
        "hs_email": user.hs_email or "",
        "hs_email_confirmed": bool(user.hs_email_confirmed),
        "membership_uid": str(membership.uid) if membership else None,
        "membership_status": membership.status if membership else None,
        "fee_category": normalize_fee_category(membership.fee_category) if membership else None,
        "balance_cents": user_balance(user.id),
        "can_use_tally": any(fnmatch("finance.tally.use", grant) for grant in permission_grants),
    }


def student_verification_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="sia-planb-student-cycle-v1")


def finance_settings():
    settings = Tables.FinanceSettings.query.filter_by(id=1).first()
    if settings:
        return settings
    settings = Tables.FinanceSettings(id=1, payment_instructions="")
    db.session.add(settings)
    db.session.flush()
    return settings


@app.route("/api/v1/me/finances", methods=["GET"])
def api_my_finances():
    if not current_user.is_authenticated:
        return finance_response({"error": "authentication_required"}, 401)
    membership = current_membership(current_user.id)
    pending_request = (
        Tables.MembershipRequest.query
        .filter_by(user_id=current_user.id, status="pending")
        .order_by(Tables.MembershipRequest.submitted_at.desc())
        .first()
    )
    can_use_tally = hasPermissions("finance.tally.use")
    products = (
        Tables.TallyItem.query.filter_by(is_active=True)
        .filter(Tables.TallyItem.price_cents.isnot(None))
        .order_by(Tables.TallyItem.name.asc()).all()
        if can_use_tally else []
    )
    membership_ids = user_membership_ids(current_user.id)
    payload = {
        "membership": serialize_membership(membership) if membership else None,
        "pending_request": ({
            "uid": str(pending_request.uid),
            "request_type": pending_request.request_type,
            "requested_category": pending_request.requested_category,
            "submitted_at": as_datetime(pending_request.submitted_at),
        } if pending_request else None),
        "cycle_year": student_verification_cycle_year(membership) if membership else next_student_billing_cycle_year(),
        "can_use_tally": can_use_tally,
        "products": [serialize_tally_item(item) for item in products],
        "charges": serialize_charges(
            Tables.FinanceCharge.query.filter(user_finance_filter(Tables.FinanceCharge, current_user.id, membership_ids))
            .order_by(Tables.FinanceCharge.created_at.desc(), Tables.FinanceCharge.id.desc()).all()
        ),
        "payments": [
            serialize_payment(payment)
            for payment in Tables.FinancePayment.query.filter(user_finance_filter(Tables.FinancePayment, current_user.id, membership_ids))
            .order_by(Tables.FinancePayment.received_at.desc(), Tables.FinancePayment.id.desc()).all()
        ],
        "charge_adjustments": serialize_charge_adjustments(current_user.id),
        "balance_cents": user_balance(current_user.id),
        "unallocated_credit_cents": unallocated_payment_cents(current_user.id),
        "allocation_suggestion": payment_charge_match_suggestion(current_user.id, 0),
        "payment_instructions": finance_settings().payment_instructions,
    }
    if membership:
        verification = Tables.MembershipStudentVerification.query.filter_by(
            membership_id=membership.id,
            cycle_year=payload["cycle_year"],
        ).first()
        payload["student_verification"] = {
            "required": membership.fee_category == "student",
            "verified": bool(
                verification
                and verification.verified_at
                and membership.user_obj
                and verification.email_snapshot.lower() == (membership.user_obj.hs_email or "").lower()
            ),
            "email": membership.user_obj.hs_email or "" if membership.user_obj else "",
            "verified_at": as_datetime(verification.verified_at) if verification else None,
        }
    return finance_response(payload)


@app.route("/api/v1/me/membership-requests", methods=["POST"])
def api_create_membership_request():
    if not current_user.is_authenticated:
        return finance_response({"error": "authentication_required"}, 401)
    payload = request.get_json(silent=True) or {}
    membership = current_membership(current_user.id)
    request_type = str(payload.get("request_type") or ("category" if membership and membership.status == "active" else "join"))
    category = str(payload.get("requested_category") or "")
    note = str(payload.get("note") or "").strip()
    errors = {}
    if request_type not in {"join", "category"}:
        errors["request_type"] = "Ungültige Art der Anfrage."
    if category not in REQUESTABLE_FEE_CATEGORIES:
        errors["requested_category"] = "Bitte wähle eine gültige Mitgliedskategorie."
    if request_type == "join" and membership and membership.status == "active":
        errors["request_type"] = "Du hast bereits eine aktive Mitgliedschaft."
    if request_type == "category" and (not membership or membership.status != "active"):
        errors["request_type"] = "Für einen Kategorienwechsel benötigst du eine aktive Mitgliedschaft."
    if category == "special" and not note:
        errors["note"] = "Bitte beschreibe kurz, warum du einen Sonderbeitrag beantragst."
    if category == "student" and not current_user.hs_email:
        errors["hs_email"] = "Bitte hinterlege zuerst deine Hochschul-E-Mail-Adresse im Profil."
    pending = Tables.MembershipRequest.query.filter_by(user_id=current_user.id, status="pending").first()
    if pending:
        errors["request"] = "Du hast bereits eine offene Mitgliedschaftsanfrage."
    if errors:
        return finance_response({"success": False, "errors": errors}, 400)
    membership_request = Tables.MembershipRequest(
        user_id=current_user.id,
        request_type=request_type,
        requested_category=category,
        request_note=note,
    )
    db.session.add(membership_request)
    db.session.commit()
    return finance_response({"success": True, "uid": str(membership_request.uid)}, 201)


@app.route("/api/v1/me/finance/purchases", methods=["POST"])
def api_create_tally_purchase():
    if not current_user.is_authenticated:
        return finance_response({"error": "authentication_required"}, 401)
    if not hasPermissions("finance.tally.use"):
        return finance_response({"error": "tally_member_role_required"}, 403)
    payload = request.get_json(silent=True) or {}
    try:
        item_id = int(payload.get("item_id"))
        quantity = int(payload.get("quantity", 1))
    except (TypeError, ValueError):
        return finance_response({"success": False, "errors": {"item": "Bitte wähle ein gültiges Getränk."}}, 400)
    item = Tables.TallyItem.query.filter_by(id=item_id, is_active=True).first()
    if not item or item.price_cents is None or item.price_cents <= 0:
        return finance_response({"error": "tally_item_unavailable"}, 404)
    if quantity < 1 or quantity > 20:
        return finance_response({"success": False, "errors": {"quantity": "Die Menge muss zwischen 1 und 20 liegen."}}, 400)
    charge = Tables.FinanceCharge(
        user_id=current_user.id,
        tally_item_id=item.id,
        kind="drink",
        name_snapshot=item.name,
        quantity=quantity,
        unit_price_cents=item.price_cents,
        amount_cents=item.price_cents * quantity,
        status="open",
        created_by=current_user.id,
    )
    db.session.add(charge)
    db.session.flush()
    allocate_existing_credit_to_charge(
        charge,
        changed_by=current_user.id,
        source="new_tally_charge",
        note="Vorhandenes Kontoguthaben wurde dem neuen Tally-Eintrag zugeordnet.",
    )
    db.session.commit()
    return finance_response({"success": True, "charge": serialize_charge(charge), "balance_cents": user_balance(current_user.id)}, 201)


@app.route("/api/v1/me/student-verification", methods=["POST"])
def api_request_student_verification():
    if not current_user.is_authenticated:
        return finance_response({"error": "authentication_required"}, 401)
    membership = current_membership(current_user.id)
    if not membership or membership.status != "active" or membership.fee_category != "student":
        return finance_response({"error": "student_membership_required"}, 403)
    cycle_year = student_verification_cycle_year(membership)
    from Sections.FinanceMailApi import send_single_student_verification

    result, campaign_uid = send_single_student_verification(membership, cycle_year)
    if result == "student_membership_required":
        return finance_response({"error": "student_membership_required"}, 403)
    if result == "missing_email":
        return finance_response({"error": "hs_email_required"}, 409)
    if result == "already_verified":
        return finance_response({"success": True, "already_verified": True})
    if result == "cooldown":
        return finance_response({"error": "verification_cooldown", "retry_after_seconds": 300}, 429)
    if result == "invalid_template":
        return finance_response({"error": "Die gemeinsame E-Mail-Vorlage ist ungültig. Bitte kontaktiere die Verwaltung."}, 409)
    return finance_response({"success": True, "cycle_year": cycle_year, "campaign_uid": campaign_uid}, 202)


@app.route("/api/v1/manage/finance/student-verifications", methods=["POST"])
def api_send_student_verifications():
    denied = finance_access_denied()
    if denied:
        return denied
    return finance_response({
        "error": "Bitte öffne zuerst den gespeicherten Mailentwurf, prüfe die Empfänger:innen und bestätige den Versand.",
    }, 409)


@app.route("/verify_student_membership", methods=["GET"])
def verify_student_membership():
    uid = request.args.get("membership", "")
    cycle_text = request.args.get("cycle", "")
    token = request.args.get("token", "")
    try:
        membership_uid = UUID(uid)
        cycle_year = int(cycle_text)
    except (ValueError, TypeError, AttributeError):
        return redirect("/me/finances?student_verification=invalid")
    try:
        details = student_verification_serializer().loads(token, max_age=365 * 24 * 60 * 60)
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return redirect("/me/finances?student_verification=expired")
    if details.get("membership_uid") != str(membership_uid) or details.get("cycle_year") != cycle_year:
        return redirect("/me/finances?student_verification=invalid")
    membership = Tables.Membership.query.filter_by(uid=membership_uid).with_for_update().first()
    if not membership or membership.status != "active" or membership.fee_category != "student":
        return redirect("/me/finances?student_verification=invalid")
    verification = Tables.MembershipStudentVerification.query.filter_by(
        membership_id=membership.id,
        cycle_year=cycle_year,
    ).with_for_update().first()
    current_email = (membership.user_obj.hs_email or "").strip().lower()
    if not verification or not current_email or current_email != details.get("email") or verification.email_snapshot.lower() != current_email:
        return redirect("/me/finances?student_verification=invalid")
    if not verification.verified_at:
        verification.verified_at = datetime.now()
        entry_date = student_entry_date(membership) or membership.member_since
        first_cycle_year, _, _ = student_first_billing_period(entry_date)
        affected_years = {cycle_year}
        if first_cycle_year == cycle_year and membership.member_since.year < cycle_year:
            affected_years.add(membership.member_since.year)
        for affected_year in affected_years:
            reconcile_membership_year_charge(
                membership,
                "student_verification",
                membership.user_id,
                f"Studentenstatus für Beitragszyklus {cycle_year} bestätigt.",
                cycle_year=affected_year,
            )
        db.session.commit()
    return redirect("/me/finances?student_verification=verified")


def serialize_membership_request(membership_request):
    user = Tables.User.query.filter_by(id=membership_request.user_id).first()
    return {
        "id": membership_request.id,
        "uid": str(membership_request.uid),
        "user_uid": str(user.uid) if user else None,
        "username": user.username if user else "Gelöschtes Konto",
        "surname": user.surname or "" if user else "",
        "lastname": user.lastname or "" if user else "",
        "email": user.email or "" if user else "",
        "request_type": membership_request.request_type,
        "requested_category": normalize_fee_category(membership_request.requested_category),
        "request_note": membership_request.request_note or "",
        "status": membership_request.status,
        "submitted_at": as_datetime(membership_request.submitted_at),
        "review_note": membership_request.review_note or "",
    }


def admin_membership_overview():
    memberships = Tables.Membership.query.order_by(Tables.Membership.status.asc(), Tables.Membership.member_since.asc()).all()
    member_user_ids = {membership.user_id for membership in memberships}
    requests = Tables.MembershipRequest.query.filter_by(status="pending").order_by(Tables.MembershipRequest.submitted_at.asc()).all()
    return {
        "memberships": [serialize_membership(membership) for membership in memberships],
        "finance_users": [
            serialize_finance_user(user)
            for user in Tables.User.query.order_by(Tables.User.username.asc()).all()
        ],
        "available_users": [
            {
                "uid": str(user.uid),
                "username": user.username,
                "surname": user.surname or "",
                "lastname": user.lastname or "",
                "role": user.role,
            }
            for user in Tables.User.query.order_by(Tables.User.username.asc()).all()
            if user.id not in member_user_ids
        ],
        "requests": [serialize_membership_request(item) for item in requests],
        "products": [serialize_tally_item(item) for item in Tables.TallyItem.query.order_by(Tables.TallyItem.name.asc()).all()],
        "fee_rates": [
            {"category": rate.category, "annual_amount_cents": rate.annual_amount_cents}
            for rate in Tables.MembershipFeeRate.query.order_by(Tables.MembershipFeeRate.category.asc()).all()
        ],
        "payment_instructions": finance_settings().payment_instructions,
        "mail_test_email": finance_settings().mail_test_email,
    }


@app.route("/api/v1/manage/finance", methods=["GET"])
def api_manage_finance():
    denied = finance_access_denied()
    if denied:
        return denied
    return finance_response(admin_membership_overview())


@app.route("/api/v1/manage/finance/memberships", methods=["POST"])
def api_create_finance_membership():
    denied = finance_access_denied()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    user_uid = payload.get("user_uid")
    user = Tables.User.query.filter_by(uid=user_uid).first() if user_uid else None
    if not user:
        return finance_response({"error": "User not found"}, 404)
    if current_membership(user.id):
        return finance_response({"error": "Für dieses Konto existiert bereits eine Beitragsmitgliedschaft."}, 409)
    category = str(payload.get("fee_category") or "student")
    if category not in ALL_FEE_CATEGORIES:
        return finance_response({"success": False, "errors": {"fee_category": "Ungültige Beitragskategorie."}}, 400)
    errors = {}
    member_since = parse_date(payload.get("member_since"), "member_since", errors, required=True)
    special_rate = payload.get("special_rate_cents")
    if category == "special":
        try:
            special_rate = int(special_rate)
            if special_rate < 0:
                raise ValueError()
        except (TypeError, ValueError):
            errors["special_rate_cents"] = "Für einen Sonderbeitrag ist ein gültiger Betrag erforderlich."
    if errors:
        return finance_response({"success": False, "errors": errors}, 400)
    membership = Tables.Membership(
        user_id=user.id,
        status="active",
        fee_category=category,
        member_since=member_since,
        special_rate_cents=special_rate if category == "special" else None,
        created_by=current_user.id,
    )
    db.session.add(membership)
    db.session.flush()
    create_initial_membership_charge(membership, current_user.id)
    db.session.commit()
    return finance_response({"success": True, "membership": serialize_membership(membership)}, 201)


@app.route("/api/v1/manage/finance/memberships/<membership_uid>", methods=["PUT"])
def api_update_finance_membership(membership_uid):
    denied = finance_access_denied()
    if denied:
        return denied
    membership = Tables.Membership.query.filter_by(uid=membership_uid).first()
    if not membership:
        return finance_response({"error": "Mitgliedschaft nicht gefunden."}, 404)
    payload = request.get_json(silent=True) or {}
    errors = {}
    previous = {
        "status": membership.status,
        "fee_category": membership.fee_category,
        "member_since": membership.member_since,
        "special_rate_cents": membership.special_rate_cents,
        "special_rate_valid_until": membership.special_rate_valid_until,
    }
    category = str(payload.get("fee_category", membership.fee_category))
    status = str(payload.get("status", membership.status))
    if category not in ALL_FEE_CATEGORIES:
        errors["fee_category"] = "Ungültige Beitragskategorie."
    if status not in {"active", "ended"}:
        errors["status"] = "Ungültiger Mitgliedschaftsstatus."
    member_since = parse_date(payload.get("member_since", membership.member_since.isoformat()), "member_since", errors, required=True)
    special_rate = payload.get("special_rate_cents", membership.special_rate_cents)
    if category == "special":
        try:
            special_rate = int(special_rate)
            if special_rate < 0:
                raise ValueError()
        except (TypeError, ValueError):
            errors["special_rate_cents"] = "Für einen Sonderbeitrag ist ein gültiger Betrag erforderlich."
        if "special_rate_valid_until" in payload:
            special_rate_valid_until = parse_date(payload.get("special_rate_valid_until"), "special_rate_valid_until", errors)
        else:
            special_rate_valid_until = membership.special_rate_valid_until
    else:
        special_rate_valid_until = None
    if errors:
        return finance_response({"success": False, "errors": errors}, 400)
    fee_fields_changed = any((
        previous["fee_category"] != category,
        previous["member_since"] != member_since,
        previous["special_rate_cents"] != (special_rate if category == "special" else None),
        previous["special_rate_valid_until"] != special_rate_valid_until,
    ))
    if fee_fields_changed and membership_has_cancelled_charge_in_active_run(
        membership,
        {date.today().year, next_student_billing_cycle_year()},
    ):
        return finance_response({
            "error": "Für diese Mitgliedschaft wurde eine Buchung in einem aktiven Beitragslauf storniert. Um sie neu auszustellen, muss der gesamte Beitragslauf ersetzt werden.",
        }, 409)
    membership.fee_category = category
    membership.status = status
    membership.member_since = member_since
    membership.ended_at = date.today() if status == "ended" else None
    membership.special_rate_cents = special_rate if category == "special" else None
    membership.special_rate_valid_until = special_rate_valid_until
    membership.updated_at = datetime.now()
    current = {
        "status": membership.status,
        "fee_category": membership.fee_category,
        "member_since": membership.member_since,
        "special_rate_cents": membership.special_rate_cents,
        "special_rate_valid_until": membership.special_rate_valid_until,
    }
    fee_adjustments = []
    if current != previous:
        note = str(payload.get("note") or "Direkte Änderung durch die Verwaltung.").strip()[:500]
        db.session.add(Tables.MembershipHistory(
            membership_id=membership.id,
            changed_by=current_user.id,
            changed_at=datetime.now(),
            from_status=previous["status"],
            to_status=current["status"],
            from_fee_category=previous["fee_category"],
            to_fee_category=current["fee_category"],
            from_member_since=previous["member_since"],
            to_member_since=current["member_since"],
            from_special_rate_cents=previous["special_rate_cents"],
            to_special_rate_cents=current["special_rate_cents"],
            from_special_rate_valid_until=previous["special_rate_valid_until"],
            to_special_rate_valid_until=current["special_rate_valid_until"],
            note=note or None,
        ))
        db.session.flush()
        if any(previous[key] != current[key] for key in (
            "fee_category",
            "member_since",
            "special_rate_cents",
            "special_rate_valid_until",
        )):
            fee_adjustments = reconcile_membership_fee_changes(
                membership,
                "membership_edit",
                current_user.id,
                note or "Beitragskategorie oder Sonderbeitrag geändert.",
            )
    db.session.commit()
    return finance_response({
        "success": True,
        "membership": serialize_membership(membership),
        "fee_adjustments": fee_adjustments,
    })


@app.route("/api/v1/manage/finance/requests/<int:request_id>/review", methods=["POST"])
def api_review_membership_request(request_id):
    denied = finance_access_denied()
    if denied:
        return denied
    membership_request = Tables.MembershipRequest.query.filter_by(id=request_id, status="pending").first()
    if not membership_request:
        return finance_response({"error": "Offene Anfrage nicht gefunden."}, 404)
    payload = request.get_json(silent=True) or {}
    decision = str(payload.get("decision") or "")
    if decision not in {"approve", "reject"}:
        return finance_response({"success": False, "errors": {"decision": "Bitte wähle genehmigen oder ablehnen."}}, 400)
    note = str(payload.get("note") or "").strip()
    if decision == "reject" and not note:
        return finance_response({"success": False, "errors": {"note": "Bitte gib einen kurzen Grund für die Ablehnung an."}}, 400)

    membership = current_membership(membership_request.user_id)
    membership_existed = membership is not None
    previous_membership = ({
        "status": membership.status,
        "fee_category": membership.fee_category,
        "member_since": membership.member_since,
        "special_rate_cents": membership.special_rate_cents,
        "special_rate_valid_until": membership.special_rate_valid_until,
    } if membership else None)
    fee_adjustments = []
    if decision == "approve":
        category = str(payload.get("fee_category") or membership_request.requested_category)
        if category not in ALL_FEE_CATEGORIES:
            return finance_response({"success": False, "errors": {"fee_category": "Ungültige Beitragskategorie."}}, 400)
        if membership_request.request_type == "category" and membership and membership_has_cancelled_charge_in_active_run(
            membership,
            {date.today().year, next_student_billing_cycle_year()},
        ):
            return finance_response({
                "error": "Für diese Mitgliedschaft wurde eine Buchung in einem aktiven Beitragslauf storniert. Um sie neu auszustellen, muss der gesamte Beitragslauf ersetzt werden.",
            }, 409)
        if membership_request.request_type == "join":
            if membership and membership.status == "active":
                return finance_response({"error": "Für dieses Konto existiert bereits eine Beitragsmitgliedschaft."}, 409)
            member_since = parse_date(payload.get("member_since") or date.today().isoformat(), "member_since", {}, required=True)
            if not member_since:
                return finance_response({"error": "Ungültiges Eintrittsdatum."}, 400)
            if membership:
                membership.status = "active"
                membership.fee_category = category
                membership.member_since = member_since
                membership.ended_at = None
                membership.updated_at = datetime.now()
            else:
                membership = Tables.Membership(
                    user_id=membership_request.user_id,
                    status="active",
                    fee_category=category,
                    member_since=member_since,
                    created_by=current_user.id,
                )
                db.session.add(membership)
        elif not membership:
            return finance_response({"error": "Für diesen Kategorienwechsel gibt es keine aktive Beitragsmitgliedschaft."}, 409)

        if category == "special":
            try:
                special_rate = int(payload.get("special_rate_cents"))
                if special_rate < 0:
                    raise ValueError()
            except (TypeError, ValueError):
                return finance_response({"success": False, "errors": {"special_rate_cents": "Bitte gib den genehmigten Sonderbeitrag in Cent an."}}, 400)
            membership.special_rate_cents = special_rate
            membership.special_rate_valid_until = parse_date(payload.get("special_rate_valid_until"), "special_rate_valid_until", {})
        else:
            membership.special_rate_cents = None
            membership.special_rate_valid_until = None
        membership.fee_category = category
        membership.status = "active"
        membership.updated_at = datetime.now()
        db.session.flush()
        if membership_request.request_type == "join" and (
            not membership_existed or previous_membership["status"] != "active"
        ):
            create_initial_membership_charge(membership, current_user.id)
        elif previous_membership:
            current_membership_state = {
                "status": membership.status,
                "fee_category": membership.fee_category,
                "member_since": membership.member_since,
                "special_rate_cents": membership.special_rate_cents,
                "special_rate_valid_until": membership.special_rate_valid_until,
            }
            if current_membership_state != previous_membership:
                db.session.add(Tables.MembershipHistory(
                    membership_id=membership.id,
                    changed_by=current_user.id,
                    changed_at=datetime.now(),
                    from_status=previous_membership["status"],
                    to_status=current_membership_state["status"],
                    from_fee_category=previous_membership["fee_category"],
                    to_fee_category=current_membership_state["fee_category"],
                    from_member_since=previous_membership["member_since"],
                    to_member_since=current_membership_state["member_since"],
                    from_special_rate_cents=previous_membership["special_rate_cents"],
                    to_special_rate_cents=current_membership_state["special_rate_cents"],
                    from_special_rate_valid_until=previous_membership["special_rate_valid_until"],
                    to_special_rate_valid_until=current_membership_state["special_rate_valid_until"],
                    note=note or "Beitragskategorie oder Sonderbeitrag genehmigt.",
                ))
                db.session.flush()
                fee_adjustments = reconcile_membership_fee_changes(
                    membership,
                    "membership_request_approved",
                    current_user.id,
                    note or "Beitragskategorie oder Sonderbeitrag genehmigt.",
                )

    membership_request.status = "approved" if decision == "approve" else "rejected"
    membership_request.reviewed_by = current_user.id
    membership_request.reviewed_at = datetime.now()
    membership_request.review_note = note
    db.session.commit()
    return finance_response({
        "success": True,
        "membership_request": serialize_membership_request(membership_request),
        "fee_adjustments": fee_adjustments,
    })


@app.route("/api/v1/manage/finance/products", methods=["POST"])
def api_create_tally_item():
    denied = finance_access_denied()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()
    errors = {}
    if not name or len(name) > 80:
        errors["name"] = "Der Produktname muss 1 bis 80 Zeichen lang sein."
    try:
        price_cents = int(payload.get("price_cents"))
        if price_cents <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        errors["price_cents"] = "Der Preis muss größer als 0 Cent sein."
    if errors:
        return finance_response({"success": False, "errors": errors}, 400)
    if Tables.TallyItem.query.filter_by(name=name).first():
        return finance_response({"error": "Ein Produkt mit diesem Namen existiert bereits."}, 409)
    item = Tables.TallyItem(name=name, price_cents=price_cents, is_active=True, created_by=current_user.id, updated_by=current_user.id)
    db.session.add(item)
    db.session.commit()
    return finance_response({"success": True, "item": serialize_tally_item(item)}, 201)


@app.route("/api/v1/manage/finance/products/<int:item_id>", methods=["PUT", "DELETE"])
def api_update_tally_item(item_id):
    denied = finance_access_denied()
    if denied:
        return denied
    item = Tables.TallyItem.query.filter_by(id=item_id).first()
    if not item:
        return finance_response({"error": "Tally-Produkt nicht gefunden."}, 404)
    if request.method == "DELETE":
        item.is_active = False
        item.updated_by = current_user.id
        item.updated_at = datetime.now()
        db.session.commit()
        return finance_response({"success": True, "item": serialize_tally_item(item)})
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", item.name) or "").strip()
    errors = {}
    if not name or len(name) > 80:
        errors["name"] = "Der Produktname muss 1 bis 80 Zeichen lang sein."
    try:
        price_cents = int(payload.get("price_cents", item.price_cents))
        if price_cents <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        errors["price_cents"] = "Der Preis muss größer als 0 Cent sein."
    duplicate = Tables.TallyItem.query.filter(Tables.TallyItem.name == name, Tables.TallyItem.id != item.id).first()
    if duplicate:
        errors["name"] = "Ein Produkt mit diesem Namen existiert bereits."
    if errors:
        return finance_response({"success": False, "errors": errors}, 400)
    item.name = name
    item.price_cents = price_cents
    item.is_active = bool(payload.get("is_active", item.is_active))
    item.updated_by = current_user.id
    item.updated_at = datetime.now()
    db.session.commit()
    return finance_response({"success": True, "item": serialize_tally_item(item)})


@app.route("/api/v1/manage/finance/rates/<category>", methods=["PUT"])
def api_update_membership_fee_rate(category):
    denied = finance_access_denied()
    if denied:
        return denied
    if category not in RATE_FEE_CATEGORIES:
        return finance_response({"error": "Ungültige Beitragskategorie."}, 404)
    payload = request.get_json(silent=True) or {}
    try:
        amount_cents = int(payload.get("annual_amount_cents"))
        if amount_cents < 0 or (category == "exempt" and amount_cents != 0):
            raise ValueError()
    except (TypeError, ValueError):
        return finance_response({"success": False, "errors": {"annual_amount_cents": "Bitte gib einen gültigen Jahresbeitrag in Cent an."}}, 400)
    rate = Tables.MembershipFeeRate.query.filter_by(category=category).first()
    if not rate:
        rate = Tables.MembershipFeeRate(category=category, annual_amount_cents=amount_cents)
        db.session.add(rate)
    rate.annual_amount_cents = amount_cents
    rate.updated_by = current_user.id
    rate.updated_at = datetime.now()
    db.session.commit()
    return finance_response({"success": True, "rate": {"category": rate.category, "annual_amount_cents": rate.annual_amount_cents}})


@app.route("/api/v1/manage/finance/settings", methods=["PUT"])
def api_update_finance_settings():
    denied = finance_access_denied()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    payment_instructions = str(payload.get("payment_instructions") or "").strip()
    settings = finance_settings()
    mail_test_email = str(payload.get("mail_test_email", settings.mail_test_email) or "").strip()
    if len(payment_instructions) > 2000:
        return finance_response({"success": False, "errors": {"payment_instructions": "Die Zahlungsinformationen dürfen höchstens 2000 Zeichen enthalten."}}, 400)
    if len(mail_test_email) > 255 or (mail_test_email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", mail_test_email)):
        return finance_response({"success": False, "errors": {"mail_test_email": "Bitte gib eine gültige Test-E-Mail-Adresse mit höchstens 255 Zeichen an."}}, 400)
    settings.payment_instructions = payment_instructions
    settings.mail_test_email = mail_test_email
    settings.updated_by = current_user.id
    settings.updated_at = datetime.now()
    db.session.commit()
    return finance_response({
        "success": True,
        "payment_instructions": settings.payment_instructions,
        "mail_test_email": settings.mail_test_email,
    })


def fee_rate(category):
    return Tables.MembershipFeeRate.query.filter_by(category=normalize_fee_category(category)).first()


def student_verified_for_cycle(membership, cycle_year, entry_date=None):
    if not membership or not membership.user_obj:
        return False
    entry_date = entry_date or membership.member_since
    candidate_years = {cycle_year}
    first_year, _, _ = student_first_billing_period(entry_date)
    if cycle_year == entry_date.year and first_year == cycle_year + 1:
        candidate_years.add(first_year)
    current_email = (membership.user_obj.hs_email or "").strip().lower()
    if not current_email:
        return False
    verifications = Tables.MembershipStudentVerification.query.filter(
        Tables.MembershipStudentVerification.membership_id == membership.id,
        Tables.MembershipStudentVerification.cycle_year.in_(candidate_years),
    ).all()
    return any(
        verification.verified_at
        and verification.email_snapshot.lower() == current_email
        for verification in verifications
    )


def student_entry_date(membership):
    """Find the date this membership most recently entered the student category."""
    history = Tables.MembershipHistory.query.filter_by(membership_id=membership.id).order_by(
        Tables.MembershipHistory.changed_at.asc(),
        Tables.MembershipHistory.id.asc(),
    ).all()
    if not history:
        return membership.member_since if normalize_fee_category(membership.fee_category) == "student" else None

    category = normalize_fee_category(history[0].from_fee_category or membership.fee_category)
    entered_at = membership.member_since if category == "student" else None
    for event in history:
        next_category = normalize_fee_category(event.to_fee_category or category)
        if next_category == "student" and category != "student":
            entered_at = event.changed_at.date()
        elif next_category != "student":
            entered_at = None
        category = next_category
    return entered_at if category == "student" else None


def student_verification_cycle_year(membership, today=None):
    today = today or date.today()
    entry_date = student_entry_date(membership) or membership.member_since
    first_cycle_year, _, _ = student_first_billing_period(entry_date)
    if first_cycle_year >= today.year:
        return first_cycle_year
    return next_student_billing_cycle_year(today)


def membership_year_amount_from_history(membership, cycle_year):
    """Compute a calendar-year obligation, splitting annual rates at category changes."""
    year_start = date(cycle_year, 1, 1)
    history = Tables.MembershipHistory.query.filter_by(membership_id=membership.id).order_by(
        Tables.MembershipHistory.changed_at.asc(),
        Tables.MembershipHistory.id.asc(),
    ).all()

    if history:
        first = history[0]
        category = normalize_fee_category(first.from_fee_category or membership.fee_category)
        special_rate = first.from_special_rate_cents
        special_valid_until = first.from_special_rate_valid_until
    else:
        category = normalize_fee_category(membership.fee_category)
        special_rate = membership.special_rate_cents
        special_valid_until = membership.special_rate_valid_until
    student_since = membership.member_since if category == "student" else None

    def apply_history_event(event):
        nonlocal category, special_rate, special_valid_until, student_since
        next_category = normalize_fee_category(event.to_fee_category or category)
        if next_category == "student" and category != "student":
            student_since = event.changed_at.date()
        elif next_category != "student":
            student_since = None
        category = next_category
        special_rate = event.to_special_rate_cents
        special_valid_until = event.to_special_rate_valid_until

    for event in history:
        if event.changed_at.date() >= year_start:
            break
        apply_history_event(event)

    year_events = [event for event in history if event.changed_at.year == cycle_year]
    event_index = 0
    student_verification_cache = {}
    monthly_annual_amounts = []

    for month in range(1, 13):
        while event_index < len(year_events) and year_events[event_index].changed_at.month <= month:
            apply_history_event(year_events[event_index])
            event_index += 1

        effective_category = category
        if effective_category == "special" and special_valid_until and special_valid_until < date(cycle_year, month, 1):
            effective_category = "full"
        if effective_category == "student":
            if student_since not in student_verification_cache:
                student_verification_cache[student_since] = student_verified_for_cycle(
                    membership,
                    cycle_year,
                    student_since,
                )
            if not student_verification_cache[student_since]:
                effective_category = "full"

        if effective_category == "student":
            if not student_since:
                monthly_annual_amounts.append(0)
                continue
            first_payable_month = student_first_payable_month(student_since, cycle_year)
            if first_payable_month is None or month < first_payable_month:
                monthly_annual_amounts.append(0)
                continue
        if effective_category == "special":
            annual_amount = int(special_rate or 0)
        elif effective_category == "exempt":
            annual_amount = 0
        else:
            rate = fee_rate(effective_category)
            annual_amount = int(rate.annual_amount_cents if rate else PDF_ANNUAL_RATE_DEFAULTS.get(effective_category, 0))
        monthly_annual_amounts.append(annual_amount)

    return calendar_year_amount_from_monthly_rates(monthly_annual_amounts)


def membership_charge_due_date(cycle_year, period="march"):
    return date(cycle_year, 9 if period == "september" else 3, 1)


def membership_charge_name(cycle_year, period, category, amount_cents):
    category = normalize_fee_category(category)
    if amount_cents == 0:
        return f"Mitgliedsbeitrag {cycle_year} · beitragsfrei"
    label = FEE_CATEGORY_LABELS.get(category, category)
    if category == "student":
        annual_rate = fee_rate("student")
        annual_amount = annual_rate.annual_amount_cents if annual_rate else PDF_ANNUAL_RATE_DEFAULTS["student"]
        if amount_cents < annual_amount:
            fraction = "3/12" if period == "september" else "9/12"
            return f"Mitgliedsbeitrag {cycle_year} ({label} · {fraction})"
    return f"Mitgliedsbeitrag {cycle_year} ({label})"


def create_membership_charge_record(membership, cycle_year, amount_cents, category, due_date, created_by, note, billing_run=None, period="march"):
    amount_cents = max(0, int(amount_cents))
    charge = Tables.FinanceCharge(
        membership_id=membership.id,
        billing_run_id=billing_run.id if billing_run else None,
        kind="membership",
        name_snapshot=membership_charge_name(cycle_year, period, category, amount_cents),
        fee_category_snapshot=normalize_fee_category(category),
        cycle_year=cycle_year,
        quantity=1,
        unit_price_cents=amount_cents,
        amount_cents=amount_cents,
        due_date=due_date,
        status="waived" if amount_cents == 0 else "open",
        created_by=created_by,
    )
    db.session.add(charge)
    db.session.flush()
    db.session.add(Tables.FinanceChargeStatusHistory(
        charge_id=charge.id,
        from_status=None,
        to_status=charge.status,
        changed_by=created_by,
        note=note,
    ))
    if amount_cents > 0:
        allocate_existing_credit_to_charge(
            charge,
            changed_by=created_by,
            source="new_membership_charge",
            note=f"Vorhandenes Kontoguthaben wurde dem Mitgliedsbeitrag {cycle_year} zugeordnet.",
        )
    return charge


def serialize_billing_run(run):
    charges = Tables.FinanceCharge.query.filter_by(billing_run_id=run.id).all()
    open_run_charges = [charge for charge in charges if charge.status != "cancelled"]
    member_charge_totals = {}
    for charge in open_run_charges:
        member_charge_totals[charge.membership_id] = member_charge_totals.get(charge.membership_id, 0) + charge.amount_cents
    affected_members = []
    for membership_id, run_amount in member_charge_totals.items():
        membership = Tables.Membership.query.filter_by(id=membership_id).first()
        if not membership:
            continue
        current_balance = member_balance(membership.id)
        affected_members.append({
            "membership_uid": str(membership.uid),
            "username": membership.user_obj.username if membership.user_obj else "Gelöschtes Konto",
            "run_amount_cents": run_amount,
            "current_balance_cents": current_balance,
            "balance_after_void_cents": current_balance - run_amount,
        })
    creator = Tables.User.query.filter_by(id=run.created_by).first() if run.created_by else None
    voider = Tables.User.query.filter_by(id=run.voided_by).first() if run.voided_by else None
    return {
        "id": run.id,
        "cycle_year": run.cycle_year,
        "period": run.period,
        "run_number": run.run_number,
        "status": run.status,
        "due_date": run.due_date.isoformat(),
        "created_at": as_datetime(run.created_at),
        "created_by_username": creator.username if creator else "Verwaltung",
        "voided_at": as_datetime(run.voided_at),
        "voided_by_username": voider.username if voider else None,
        "void_reason": run.void_reason or "",
        "charge_count": len(charges),
        "open_charge_count": len(open_run_charges),
        "issued_amount_cents": sum(charge.amount_cents for charge in charges),
        "open_amount_cents": sum(charge.amount_cents for charge in open_run_charges),
        "cancelled_amount_cents": sum(charge.amount_cents for charge in charges if charge.status == "cancelled"),
        "affected_members": affected_members,
    }


def dues_preview_for(membership, cycle_year, period="march"):
    due_date = membership_charge_due_date(cycle_year, period)
    active_run = Tables.FinanceBillingRun.query.filter_by(
        cycle_year=cycle_year,
        period=period,
        status="issued",
    ).first()
    charge_in_active_run = Tables.FinanceCharge.query.filter_by(
        membership_id=membership.id,
        kind="membership",
        cycle_year=cycle_year,
        billing_run_id=active_run.id,
    ).first() if active_run else None
    cancelled_in_active_run = bool(charge_in_active_run and charge_in_active_run.status == "cancelled")
    existing = charge_in_active_run or Tables.FinanceCharge.query.filter(
        Tables.FinanceCharge.membership_id == membership.id,
        Tables.FinanceCharge.kind == "membership",
        Tables.FinanceCharge.cycle_year == cycle_year,
        Tables.FinanceCharge.status != "cancelled",
    ).order_by(Tables.FinanceCharge.created_at.desc()).first()
    existing_run = Tables.FinanceBillingRun.query.filter_by(id=existing.billing_run_id).first() if existing and existing.billing_run_id else None
    category = normalize_fee_category(membership.fee_category)
    entry_date = student_entry_date(membership) or membership.member_since
    verification = Tables.MembershipStudentVerification.query.filter_by(
        membership_id=membership.id,
        cycle_year=cycle_year,
    ).first() if category == "student" else None
    student_verified = student_verified_for_cycle(membership, cycle_year, entry_date) if category == "student" else False
    effective_category = category
    reason = "Jahresbeitrag gemäß Beitragsordnung"

    if category == "special" and membership.special_rate_valid_until and membership.special_rate_valid_until < due_date:
        effective_category = "full"
        reason = "Sonderbeitrag abgelaufen; Vollbetrag"
    elif category == "student" and not student_verified:
        effective_category = "full"
        reason = "Studiennachweis für diesen Beitragszyklus fehlt; Vollbetrag gemäß Beitragsordnung"
    elif category == "student":
        reason = "Jahresbeitrag für verifizierte Studierende"

    first_year, first_period, _ = student_first_billing_period(entry_date)
    if category == "student":
        if period == "september":
            eligible = cycle_year == first_year and first_period == "september"
            if eligible and student_verified:
                reason = "Studentenbeitrag 3/12 nach Ende des Sommersemesters"
            elif eligible:
                reason = "Studiennachweis fehlt; Vollbeitrag nach Ende des Sommersemesters"
            elif first_period == "march" and cycle_year == first_year:
                reason = "Erster Studierendenbeitrag fällt nach dem Wintersemester in den Märzlauf"
            elif cycle_year > first_year:
                reason = "Jahresbeitrag für Studierende wird im Märzlauf abgerechnet"
        else:
            eligible = cycle_year > first_year or (cycle_year == first_year and first_period == "march")
            if cycle_year == first_year and first_period == "september":
                reason = "Erster Studierendenbeitrag fällt nach dem Sommersemester in den Septemberlauf"
            elif student_verified and cycle_year == first_year and first_period == "march":
                reason = "Studentenbeitrag 9/12 nach Ende des Wintersemesters"
            elif student_verified and cycle_year > first_year:
                reason = "Jahresbeitrag für verifizierte Studierende (12/12)"
            elif not student_verified:
                reason = "Studiennachweis fehlt; Vollbeitrag im fälligen Abrechnungszeitraum"
    else:
        eligible = period == "march"
        if period == "september":
            reason = "Jahresbeiträge dieser Kategorie werden im Märzlauf abgerechnet"

    if period not in {"march", "september"}:
        eligible = False
    if due_date < membership.member_since and not existing:
        eligible = False
        if category != "student":
            reason = "Beitritt nach diesem Lauf; Neumitgliedsbeitrag ist innerhalb von sechs Wochen fällig"
    if cancelled_in_active_run:
        eligible = False
        reason = "Buchung in diesem aktiven Lauf storniert; für eine Neuauflage muss der Lauf ersetzt werden."
    elif existing and existing_run and existing_run.period != period:
        existing_period_label = "März" if existing_run.period == "march" else "September"
        reason = f"Bereits im {existing_period_label}-Lauf abgerechnet; dieser Lauf erstellt keine weitere Buchung."
    elif existing and not existing_run:
        reason = "Neumitgliedsbeitrag bereits erstellt; der Zahlungstermin ist innerhalb von sechs Wochen ab Eintritt."

    needs_admin_review = effective_category == "special" and membership.special_rate_cents is None
    amount_cents = (
        None if needs_admin_review
        else existing.amount_cents
        if existing
        else membership_year_amount_from_history(membership, cycle_year)
        if eligible
        else 0
    )
    if needs_admin_review:
        reason = "Für den Sonderbeitrag muss ein Betrag festgelegt werden."
    return {
        "membership": serialize_membership(membership),
        "cycle_year": cycle_year,
        "period": period,
        "due_date": due_date.isoformat(),
        "amount_cents": amount_cents,
        "effective_category": effective_category,
        "reason": reason,
        "needs_admin_review": needs_admin_review,
        "already_billed": bool(existing),
        "existing_status": existing.status if existing else None,
        "existing_amount_cents": existing.amount_cents if existing else None,
        "existing_due_date": existing.due_date.isoformat() if existing and existing.due_date else None,
        "existing_period": existing_run.period if existing_run else None,
        "not_eligible": not eligible,
        "verification_requested_at": as_datetime(verification.requested_at) if verification else None,
        "verification_at": as_datetime(verification.verified_at) if verification else None,
    }


def effective_fee_category_for_cycle(membership, cycle_year, due_date=None):
    category = normalize_fee_category(membership.fee_category)
    due_date = due_date or date(cycle_year, 3, 1)
    if category == "student" and not student_verified_for_cycle(
        membership,
        cycle_year,
        student_entry_date(membership),
    ):
        return "full"
    if category == "special" and membership.special_rate_valid_until and membership.special_rate_valid_until < due_date:
        return "full"
    return category


def create_initial_membership_charge(membership, created_by):
    """Create the six-week initial annual charge for non-student categories.

    Verified students wait for their first post-semester March/September run.
    Until the required proof is verified, the full rate applies under the
    contribution regulations.
    """
    if not membership or membership.status != "active":
        return None
    existing = Tables.FinanceCharge.query.filter(
        Tables.FinanceCharge.membership_id == membership.id,
        Tables.FinanceCharge.kind == "membership",
        Tables.FinanceCharge.cycle_year == membership.member_since.year,
        Tables.FinanceCharge.status != "cancelled",
    ).first()
    if existing:
        return existing
    category = normalize_fee_category(membership.fee_category)
    if category == "student":
        first_cycle_year, _, _ = student_first_billing_period(membership.member_since)
        if student_verified_for_cycle(membership, first_cycle_year, membership.member_since):
            return None
        category = "full"
    if category == "special" and membership.special_rate_cents is None:
        return None
    amount_cents = membership_year_amount_from_history(membership, membership.member_since.year)
    return create_membership_charge_record(
        membership,
        membership.member_since.year,
        amount_cents,
        category,
        membership.member_since + timedelta(days=42),
        created_by,
        "Jahresbeitrag für Neumitglied; zahlbar innerhalb von sechs Wochen.",
        period="march",
    )


def reconcile_membership_year_charge(membership, source, changed_by, note, cycle_year=None):
    """Recalculate the current calendar-year liability after category/proof changes."""
    if not membership or membership.status != "active":
        return False
    cycle_year = cycle_year or date.today().year
    allowed_years = {date.today().year, next_student_billing_cycle_year()}
    if cycle_year not in allowed_years:
        student_date = student_entry_date(membership) or membership.member_since
        first_student_year, _, _ = student_first_billing_period(student_date)
        if not (
            source == "student_verification"
            and cycle_year == membership.member_since.year
            and first_student_year in allowed_years
        ):
            return False
    charge = Tables.FinanceCharge.query.filter(
        Tables.FinanceCharge.membership_id == membership.id,
        Tables.FinanceCharge.kind == "membership",
        Tables.FinanceCharge.cycle_year == cycle_year,
        Tables.FinanceCharge.status != "cancelled",
    ).order_by(Tables.FinanceCharge.created_at.desc(), Tables.FinanceCharge.id.desc()).with_for_update().first()
    active_run = Tables.FinanceBillingRun.query.filter_by(
        cycle_year=cycle_year,
        status="issued",
    ).order_by(Tables.FinanceBillingRun.run_number.desc()).first()
    amount_cents = membership_year_amount_from_history(membership, cycle_year)
    effective_category = effective_fee_category_for_cycle(membership, cycle_year)
    name = membership_charge_name(cycle_year, "march", effective_category, amount_cents)
    entry_date = student_entry_date(membership) or membership.member_since
    first_year, first_period, _ = student_first_billing_period(entry_date)
    updated_due_date = None
    if source == "student_verification" and effective_category == "student" and cycle_year == first_year:
        updated_due_date = membership_charge_due_date(cycle_year, first_period)
    if charge:
        reconcile_args = (
            charge,
            amount_cents,
            effective_category,
            name,
            changed_by,
            source,
            note,
        )
        if updated_due_date is None:
            return reconcile_charge_amount(*reconcile_args)
        return reconcile_charge_amount(*reconcile_args, new_due_date=updated_due_date)
    if amount_cents <= 0:
        return False
    if cycle_year != date.today().year and not active_run:
        return False
    if active_run and Tables.FinanceCharge.query.filter_by(
        membership_id=membership.id,
        billing_run_id=active_run.id,
        cycle_year=cycle_year,
        kind="membership",
        status="cancelled",
    ).first():
        return False

    if effective_category == "student":
        billing_due = active_run.due_date if active_run else membership_charge_due_date(first_year, first_period)
        if not active_run and (cycle_year != first_year or billing_due > date.today()):
            return False
        due_date = billing_due
    else:
        due_date = active_run.due_date if active_run else date.today() + timedelta(days=42)
    create_membership_charge_record(
        membership,
        cycle_year,
        amount_cents,
        effective_category,
        due_date,
        changed_by,
        note,
        billing_run=active_run,
        period=active_run.period if active_run else ("september" if due_date.month == 9 else "march"),
    )
    return True


def membership_has_cancelled_charge_in_active_run(membership, cycle_years):
    cycle_years = sorted(set(cycle_years))
    if not cycle_years:
        return False
    active_run_ids = [row[0] for row in db.session.query(Tables.FinanceBillingRun.id).filter(
        Tables.FinanceBillingRun.cycle_year.in_(cycle_years),
        Tables.FinanceBillingRun.status == "issued",
    ).all()]
    if not active_run_ids:
        return False
    return Tables.FinanceCharge.query.filter(
        Tables.FinanceCharge.membership_id == membership.id,
        Tables.FinanceCharge.kind == "membership",
        Tables.FinanceCharge.billing_run_id.in_(active_run_ids),
        Tables.FinanceCharge.status == "cancelled",
    ).first() is not None


def reconcile_membership_fee_changes(membership, source, changed_by, note):
    """Reconcile this year and an already-issued upcoming cycle without voiding other accounts."""
    current_year = date.today().year
    target_years = {current_year}
    upcoming_year = next_student_billing_cycle_year()
    if upcoming_year != current_year:
        existing_charge = Tables.FinanceCharge.query.filter(
            Tables.FinanceCharge.membership_id == membership.id,
            Tables.FinanceCharge.kind == "membership",
            Tables.FinanceCharge.cycle_year == upcoming_year,
            Tables.FinanceCharge.status != "cancelled",
        ).first()
        active_run = Tables.FinanceBillingRun.query.filter_by(
            cycle_year=upcoming_year,
            status="issued",
        ).first()
        if existing_charge or active_run:
            target_years.add(upcoming_year)
    adjustments = []
    for cycle_year in sorted(target_years):
        before = Tables.FinanceCharge.query.filter(
            Tables.FinanceCharge.membership_id == membership.id,
            Tables.FinanceCharge.kind == "membership",
            Tables.FinanceCharge.cycle_year == cycle_year,
            Tables.FinanceCharge.status != "cancelled",
        ).order_by(Tables.FinanceCharge.created_at.desc(), Tables.FinanceCharge.id.desc()).first()
        before_amount_cents = before.amount_cents if before else 0
        before_fee_category = normalize_fee_category(before.fee_category_snapshot) if before else None
        changed = reconcile_membership_year_charge(
            membership,
            source,
            changed_by,
            note,
            cycle_year=cycle_year,
        )
        if not changed:
            continue
        after = Tables.FinanceCharge.query.filter(
            Tables.FinanceCharge.membership_id == membership.id,
            Tables.FinanceCharge.kind == "membership",
            Tables.FinanceCharge.cycle_year == cycle_year,
            Tables.FinanceCharge.status != "cancelled",
        ).order_by(Tables.FinanceCharge.created_at.desc(), Tables.FinanceCharge.id.desc()).first()
        if after:
            adjustments.append({
                "cycle_year": cycle_year,
                "from_amount_cents": before_amount_cents,
                "to_amount_cents": after.amount_cents,
                "from_fee_category": before_fee_category,
                "to_fee_category": normalize_fee_category(after.fee_category_snapshot),
                "due_date": after.due_date.isoformat() if after.due_date else None,
            })
    return adjustments


@app.route("/api/v1/manage/finance/billing-preview/<int:cycle_year>", methods=["GET"])
def api_finance_billing_preview(cycle_year):
    denied = finance_access_denied()
    if denied:
        return denied
    if cycle_year < 2020 or cycle_year > date.today().year + 5:
        return finance_response({"error": "Ungültiges Beitragsjahr."}, 400)
    period = str(request.args.get("period") or "march")
    if period not in {"march", "september"}:
        return finance_response({"error": "Ungültiger Beitragszeitraum."}, 400)
    runs = Tables.FinanceBillingRun.query.filter_by(cycle_year=cycle_year).order_by(Tables.FinanceBillingRun.run_number.desc()).all()
    active_run = next((run for run in runs if run.status == "issued" and run.period == period), None)
    memberships = Tables.Membership.query.filter_by(status="active").order_by(Tables.Membership.member_since.asc()).all()
    entries = [dues_preview_for(membership, cycle_year, period) for membership in memberships]
    total = sum(entry["amount_cents"] or 0 for entry in entries if not entry["already_billed"] and not entry["not_eligible"])
    return finance_response({
        "cycle_year": cycle_year,
        "period": period,
        "due_date": membership_charge_due_date(cycle_year, period).isoformat(),
        "run_created": active_run is not None,
        "active_run": serialize_billing_run(active_run) if active_run else None,
        "runs": [serialize_billing_run(run) for run in runs],
        "members": entries,
        "total_to_issue_cents": total,
        "charge_count": sum(1 for entry in entries if not entry["already_billed"] and not entry["not_eligible"]),
    })


@app.route("/api/v1/manage/finance/billing-runs", methods=["POST"])
def api_create_finance_billing_run():
    denied = finance_access_denied()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    period = str(payload.get("period") or "march")
    if period not in {"march", "september"}:
        return finance_response({"error": "Ungültiger Beitragszeitraum."}, 400)
    try:
        cycle_year = int(payload.get("cycle_year"))
    except (TypeError, ValueError):
        return finance_response({"error": "Ungültiges Beitragsjahr."}, 400)
    if cycle_year < 2020 or cycle_year > date.today().year + 5:
        return finance_response({"error": "Ungültiges Beitragsjahr."}, 400)
    active_run = Tables.FinanceBillingRun.query.filter_by(cycle_year=cycle_year, period=period, status="issued").first()
    if active_run:
        return finance_response({"error": f"Für dieses Jahr ist bereits Beitragslauf #{active_run.run_number} aktiv."}, 409)
    memberships = Tables.Membership.query.filter_by(status="active").order_by(Tables.Membership.member_since.asc()).all()
    previews = [dues_preview_for(membership, cycle_year, period) for membership in memberships]
    billable = [item for item in previews if not item["already_billed"] and not item["not_eligible"]]
    if not billable:
        return finance_response({"error": "Für dieses Beitragsjahr gibt es keine neuen beitragspflichtigen Mitgliedschaften."}, 409)
    invalid = [item for item in previews if item["needs_admin_review"] and not item["already_billed"] and not item["not_eligible"]]
    if invalid:
        return finance_response({"error": "Bitte lege zuerst alle offenen Sonderbeiträge fest.", "needs_review": invalid}, 409)
    previous_run = Tables.FinanceBillingRun.query.filter_by(cycle_year=cycle_year).order_by(Tables.FinanceBillingRun.run_number.desc()).first()
    run_number = previous_run.run_number + 1 if previous_run else 1
    run = Tables.FinanceBillingRun(
        cycle_year=cycle_year,
        period=period,
        run_number=run_number,
        status="issued",
        due_date=membership_charge_due_date(cycle_year, period),
        created_by=current_user.id,
    )
    db.session.add(run)
    db.session.flush()
    created = []
    for entry in previews:
        membership_data = entry["membership"]
        membership = Tables.Membership.query.filter_by(uid=membership_data["uid"]).first()
        if not membership or entry["already_billed"] or entry["not_eligible"]:
            continue
        amount = int(entry["amount_cents"] or 0)
        charge = Tables.FinanceCharge(
            membership_id=membership.id,
            billing_run_id=run.id,
            kind="membership",
            name_snapshot=membership_charge_name(cycle_year, period, entry["effective_category"], amount),
            fee_category_snapshot=entry["effective_category"],
            cycle_year=cycle_year,
            quantity=1,
            unit_price_cents=amount,
            amount_cents=amount,
            due_date=membership_charge_due_date(cycle_year, period),
            status="waived" if amount == 0 else "open",
            created_by=current_user.id,
        )
        db.session.add(charge)
        db.session.flush()
        db.session.add(Tables.FinanceChargeStatusHistory(
            charge_id=charge.id,
            from_status=None,
            to_status=charge.status,
            changed_by=current_user.id,
            note=entry["reason"],
        ))
        allocate_existing_credit_to_charge(
            charge,
            changed_by=current_user.id,
            source="new_membership_charge",
            note=f"Vorhandenes Kontoguthaben wurde dem Mitgliedsbeitrag {cycle_year} zugeordnet.",
        )
        created.append(charge)
    db.session.commit()
    return finance_response({
        "success": True,
        "cycle_year": cycle_year,
        "period": period,
        "run_number": run.run_number,
        "due_date": run.due_date.isoformat(),
        "created_count": len(created),
        "total_cents": sum(charge.amount_cents for charge in created),
    }, 201)


@app.route("/api/v1/manage/finance/billing-runs/<int:run_id>/void", methods=["POST"])
def api_void_finance_billing_run(run_id):
    denied = finance_access_denied()
    if denied:
        return denied
    run = Tables.FinanceBillingRun.query.filter_by(id=run_id).first()
    if not run:
        return finance_response({"error": "Beitragslauf nicht gefunden."}, 404)
    if run.status != "issued":
        return finance_response({"error": "Dieser Beitragslauf wurde bereits storniert."}, 409)
    void_preview = serialize_billing_run(run)
    payload = request.get_json(silent=True) or {}
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        return finance_response({"success": False, "errors": {"reason": "Bitte gib einen Grund für die Stornierung des Beitragslaufs an."}}, 400)

    changed_at = datetime.now()
    for charge in Tables.FinanceCharge.query.filter_by(billing_run_id=run.id).all():
        if charge.status == "cancelled":
            continue
        release_charge_allocations(
            charge,
            current_user.id,
            source="billing_run_void",
            note=f"Beitragslauf #{run.run_number} storniert: {reason[:400]}",
        )
        previous_status = charge.status
        status_note = f"Beitragslauf #{run.run_number} storniert: {reason[:400]}"
        charge.status = "cancelled"
        charge.status_by = current_user.id
        charge.status_at = changed_at
        charge.status_note = status_note
        db.session.add(Tables.FinanceChargeStatusHistory(
            charge_id=charge.id,
            from_status=previous_status,
            to_status="cancelled",
            changed_by=current_user.id,
            changed_at=changed_at,
            note=status_note,
        ))
    run.status = "voided"
    run.voided_by = current_user.id
    run.voided_at = changed_at
    run.void_reason = reason[:1000]
    db.session.commit()
    return finance_response({
        "success": True,
        "run": serialize_billing_run(run),
        "voided_charge_count": void_preview["open_charge_count"],
        "affected_members": void_preview["affected_members"],
    })


@app.route("/api/v1/manage/finance/memberships/<membership_uid>", methods=["GET"])
def api_manage_finance_member_detail(membership_uid):
    denied = finance_access_denied()
    if denied:
        return denied
    membership = Tables.Membership.query.filter_by(uid=membership_uid).first()
    if not membership:
        return finance_response({"error": "Mitgliedschaft nicht gefunden."}, 404)
    return finance_response({
        "membership": serialize_membership(membership),
        "membership_history": [
            serialize_membership_history(event)
            for event in Tables.MembershipHistory.query.filter_by(membership_id=membership.id).order_by(Tables.MembershipHistory.changed_at.desc()).all()
        ],
        "charges": serialize_charges(
            user_charges(membership.user_id)
            .order_by(Tables.FinanceCharge.created_at.desc(), Tables.FinanceCharge.id.desc()).all()
        ),
        "payments": [
            serialize_payment(payment)
            for payment in user_payments(membership.user_id)
            .order_by(Tables.FinancePayment.received_at.desc(), Tables.FinancePayment.id.desc()).all()
        ],
        "charge_adjustments": serialize_charge_adjustments(membership.user_id),
        "unallocated_credit_cents": unallocated_payment_cents(membership.user_id),
        "allocation_suggestion": payment_charge_match_suggestion(membership.user_id, 0),
        "payment_instructions": finance_settings().payment_instructions,
    })


@app.route("/api/v1/manage/finance/users/<user_uid>", methods=["GET"])
def api_manage_finance_user_detail(user_uid):
    denied = finance_access_denied()
    if denied:
        return denied
    try:
        user_uuid = UUID(str(user_uid))
    except (TypeError, ValueError, AttributeError):
        return finance_response({"error": "Benutzerkonto nicht gefunden."}, 404)
    user = Tables.User.query.filter_by(uid=user_uuid).first()
    if not user:
        return finance_response({"error": "Benutzerkonto nicht gefunden."}, 404)
    membership = current_membership(user.id)
    return finance_response({
        "user": serialize_finance_user(user),
        "membership": serialize_membership(membership) if membership else None,
        "membership_history": [
            serialize_membership_history(event)
            for event in Tables.MembershipHistory.query.filter_by(membership_id=membership.id)
            .order_by(Tables.MembershipHistory.changed_at.desc()).all()
        ] if membership else [],
        "charges": serialize_charges(
            user_charges(user.id).order_by(Tables.FinanceCharge.created_at.desc(), Tables.FinanceCharge.id.desc()).all()
        ),
        "payments": [
            serialize_payment(payment)
            for payment in user_payments(user.id).order_by(Tables.FinancePayment.received_at.desc(), Tables.FinancePayment.id.desc()).all()
        ],
        "balance_cents": user_balance(user.id),
        "unallocated_credit_cents": unallocated_payment_cents(user.id),
        "allocation_suggestion": payment_charge_match_suggestion(user.id, 0),
        "charge_adjustments": serialize_charge_adjustments(user.id),
        "payment_instructions": finance_settings().payment_instructions,
    })


def serialize_event_ticket_finance(registration, manager, event, user):
    charge = registration.finance_charge
    amount_cents = charge.amount_cents if charge else None
    if charge is None and registration.price is not None:
        amount_cents = int((Decimal(str(registration.price)) * 100).quantize(Decimal("1")))
    charge_state = charge_payment_state(charge) if charge else None
    paid = charge_state["status"] == "paid" if charge else bool(registration.paid)
    state = "cancelled" if registration.cancelled_at or (charge and charge_state["status"] == "cancelled") else (charge_state["status"] if charge else ("paid" if paid else "open"))
    allocated_cents = charge_state["allocated_cents"] if charge_state else 0
    remaining_cents = charge_state["remaining_cents"] if charge_state else amount_cents
    creator = Tables.User.query.filter_by(id=registration.created_by).first() if registration.created_by else None
    return {
        "registration_id": registration.id,
        "event_id": event.id,
        "event_name": event.name,
        "event_visibility": event.visibility,
        "event_date": as_datetime(event.date),
        "registration_name": manager.name or "Anmeldung",
        "registration_visibility": manager.visibility,
        "user_uid": str(user.uid),
        "username": user.username,
        "surname": user.surname or "",
        "lastname": user.lastname or "",
        "role": user.role,
        "price_cents": amount_cents,
        "allocated_cents": allocated_cents,
        "remaining_cents": remaining_cents,
        "price_known": amount_cents is not None,
        "paid": paid,
        "ledger_linked": charge is not None,
        "valid": bool(registration.valid),
        "status": state,
        "timestamp": as_datetime(registration.timestamp),
        "created_by_username": creator.username if creator else None,
        "cancelled_at": as_datetime(registration.cancelled_at),
        "cancel_reason": registration.cancel_reason or "",
    }


@app.route("/api/v1/manage/finance/event-tickets", methods=["GET"])
def api_manage_event_tickets():
    denied = finance_access_denied()
    if denied:
        return denied
    query = db.session.query(Tables.Registration, Tables.RegisterManager, Tables.Event, Tables.User)
    query = query.join(Tables.RegisterManager, Tables.Registration.rmFK == Tables.RegisterManager.id)
    query = query.join(Tables.Event, Tables.RegisterManager.eventFK == Tables.Event.id)
    query = query.join(Tables.User, Tables.Registration.userFK == Tables.User.id)
    query = query.filter(
        or_(Tables.Registration.price.is_(None), Tables.Registration.price > 0)
    )
    search = str(request.args.get("q") or "").strip()
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            Tables.User.username.ilike(pattern),
            Tables.User.surname.ilike(pattern),
            Tables.User.lastname.ilike(pattern),
            Tables.Event.name.ilike(pattern),
            Tables.RegisterManager.name.ilike(pattern),
        ))
    status = request.args.get("status")
    if status == "open":
        query = query.filter(Tables.Registration.cancelled_at.is_(None), Tables.Registration.paid.is_(False))
    elif status == "paid":
        query = query.filter(Tables.Registration.cancelled_at.is_(None), Tables.Registration.paid.is_(True))
    elif status == "cancelled":
        query = query.filter(Tables.Registration.cancelled_at.isnot(None))
    elif status == "legacy":
        query = query.filter(
            Tables.Registration.cancelled_at.is_(None),
            Tables.Registration.price.is_(None),
        )
    records = query.order_by(
        Tables.Event.date.desc().nullslast(),
        Tables.Registration.timestamp.desc().nullslast(),
        Tables.Registration.id.desc(),
    ).all()
    tickets = [serialize_event_ticket_finance(*record) for record in records]
    return finance_response({
        "tickets": tickets,
        "open_amount_cents": sum(
            ticket["remaining_cents"] for ticket in tickets
            if ticket["status"] in {"open", "partially_paid"} and ticket["remaining_cents"] is not None and ticket["ledger_linked"]
        ),
        "open_unlinked_count": sum(
            ticket["status"] == "open" and not ticket["ledger_linked"] for ticket in tickets
        ),
    })


@app.route("/api/v1/manage/finance/event-tickets/status", methods=["PUT"])
def api_update_event_ticket_status():
    denied = finance_access_denied()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    paid = payload.get("paid")
    if not isinstance(paid, bool):
        return finance_response({"error": "Bitte wähle einen gültigen Zahlungsstatus."}, 400)
    raw_ids = payload.get("registration_ids")
    if not isinstance(raw_ids, list) or not raw_ids or len(raw_ids) > 500:
        return finance_response({"error": "Wähle zwischen 1 und 500 Tickets aus."}, 400)
    try:
        registration_ids = list(dict.fromkeys(int(value) for value in raw_ids))
    except (TypeError, ValueError):
        return finance_response({"error": "Die Ticket-Auswahl ist ungültig."}, 400)
    registrations = Tables.Registration.query.filter(Tables.Registration.id.in_(registration_ids)).all()
    if len(registrations) != len(registration_ids):
        return finance_response({"error": "Mindestens ein ausgewähltes Ticket wurde nicht gefunden."}, 404)
    if any(registration.cancelled_at for registration in registrations):
        return finance_response({"error": "Stornierte Tickets können nicht als bezahlt markiert werden."}, 409)
    note = str(payload.get("note") or ("Als bezahlt markiert" if paid else "Wieder als offen markiert")).strip()[:500]
    changed_count = 0
    for registration in registrations:
        changed_count += set_registration_paid(registration, paid, current_user.id, "finance", note)
    db.session.commit()
    return finance_response({"success": True, "updated_count": changed_count})


@app.route("/api/v1/manage/finance/memberships/<membership_uid>/payments", methods=["POST"])
def api_record_finance_payment(membership_uid):
    denied = finance_access_denied()
    if denied:
        return denied
    membership = Tables.Membership.query.filter_by(uid=membership_uid).with_for_update().first()
    if not membership:
        return finance_response({"error": "Mitgliedschaft nicht gefunden."}, 404)
    Tables.User.query.filter_by(id=membership.user_id).with_for_update().first()
    payload = request.get_json(silent=True) or {}
    errors = {}
    try:
        amount_cents = int(payload.get("amount_cents"))
        if amount_cents <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        errors["amount_cents"] = "Der Zahlungsbetrag muss größer als 0 Cent sein."
    method = str(payload.get("method") or "")
    if method not in {"bank_transfer", "cash", "other"}:
        errors["method"] = "Bitte wähle eine gültige Zahlungsart."
    received_at = parse_datetime(payload.get("received_at"), "received_at", errors)
    if errors:
        return finance_response({"success": False, "errors": errors}, 400)
    payment = Tables.FinancePayment(
        membership_id=membership.id,
        user_id=membership.user_id,
        amount_cents=amount_cents,
        method=method,
        reference=str(payload.get("reference") or "").strip()[:120] or None,
        note=str(payload.get("note") or "").strip() or None,
        received_at=received_at,
        recorded_by=current_user.id,
    )
    db.session.add(payment)
    db.session.flush()
    match_suggestion = payment_charge_match_suggestion(membership.user_id, payment.amount_cents)
    db.session.commit()
    return finance_response({
        "success": True,
        "payment": serialize_payment(payment),
        "balance_cents": user_balance(membership.user_id),
        "match_suggestion": match_suggestion,
    }, 201)


@app.route("/api/v1/manage/finance/users/<user_uid>/payments", methods=["POST"])
def api_record_finance_user_payment(user_uid):
    denied = finance_access_denied()
    if denied:
        return denied
    try:
        user_uuid = UUID(str(user_uid))
    except (TypeError, ValueError, AttributeError):
        return finance_response({"error": "Benutzerkonto nicht gefunden."}, 404)
    user = Tables.User.query.filter_by(uid=user_uuid).with_for_update().first()
    if not user:
        return finance_response({"error": "Benutzerkonto nicht gefunden."}, 404)
    payload = request.get_json(silent=True) or {}
    errors = {}
    try:
        amount_cents = int(payload.get("amount_cents"))
        if amount_cents <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        errors["amount_cents"] = "Der Zahlungsbetrag muss größer als 0 Cent sein."
    method = str(payload.get("method") or "")
    if method not in {"bank_transfer", "cash", "other"}:
        errors["method"] = "Bitte wähle eine gültige Zahlungsart."
    received_at = parse_datetime(payload.get("received_at"), "received_at", errors)
    if errors:
        return finance_response({"success": False, "errors": errors}, 400)
    payment = Tables.FinancePayment(
        user_id=user.id,
        amount_cents=amount_cents,
        method=method,
        reference=str(payload.get("reference") or "").strip()[:120] or None,
        note=str(payload.get("note") or "").strip() or None,
        received_at=received_at,
        recorded_by=current_user.id,
    )
    db.session.add(payment)
    db.session.flush()
    match_suggestion = payment_charge_match_suggestion(user.id, payment.amount_cents)
    db.session.commit()
    return finance_response({
        "success": True,
        "payment": serialize_payment(payment),
        "balance_cents": user_balance(user.id),
        "match_suggestion": match_suggestion,
    }, 201)


@app.route("/api/v1/manage/finance/users/<user_uid>/payments/<payment_uid>/confirm-charges", methods=["POST"])
def api_confirm_payment_charge_suggestion(user_uid, payment_uid):
    return _confirm_finance_allocation_suggestion(user_uid, payment_uid)


@app.route("/api/v1/manage/finance/users/<user_uid>/allocations/confirm", methods=["POST"])
def api_confirm_finance_credit_allocation(user_uid):
    return _confirm_finance_allocation_suggestion(user_uid)


def _confirm_finance_allocation_suggestion(user_uid, payment_uid=None):
    denied = finance_access_denied()
    if denied:
        return denied
    try:
        user_uuid = UUID(str(user_uid))
        payment_uuid = UUID(str(payment_uid)) if payment_uid else None
    except (TypeError, ValueError, AttributeError):
        return finance_response({"error": "Benutzerkonto oder Zahlung nicht gefunden."}, 404)
    user = Tables.User.query.filter_by(uid=user_uuid).with_for_update().first()
    if not user:
        return finance_response({"error": "Benutzerkonto nicht gefunden."}, 404)
    triggering_payment = None
    if payment_uuid:
        triggering_payment = user_payments(user.id).filter_by(uid=payment_uuid).with_for_update().first()
        if not triggering_payment:
            return finance_response({"error": "Zahlung gehört nicht zu diesem Benutzerkonto."}, 404)
        if triggering_payment.voided_at:
            return finance_response({"error": "Eine stornierte Zahlung kann nicht zum Abgleich verwendet werden."}, 409)

    payload = request.get_json(silent=True) or {}
    raw_charge_uids = payload.get("charge_uids")
    if not isinstance(raw_charge_uids, list) or not raw_charge_uids or len(raw_charge_uids) > 10000:
        return finance_response({"error": "Wähle mindestens eine und höchstens 10000 Buchungen aus."}, 400)
    try:
        charge_uuids = list(dict.fromkeys(UUID(str(value)) for value in raw_charge_uids))
    except (TypeError, ValueError, AttributeError):
        return finance_response({"error": "Die Buchungsauswahl ist ungültig."}, 400)

    charges = user_charges(user.id).filter(
        Tables.FinanceCharge.uid.in_(charge_uuids),
    ).with_for_update().all()
    if len(charges) != len(charge_uuids):
        return finance_response({"error": "Mindestens eine Buchung gehört nicht zu diesem Benutzerkonto."}, 404)
    allocation_totals = allocation_amounts_for_charges([charge.id for charge in charges])
    charge_states = {
        charge.id: charge_payment_state(charge, allocation_totals.get(charge.id, 0))
        for charge in charges
    }
    if any(
        state["status"] not in {"open", "partially_paid"} or state["remaining_cents"] <= 0
        for state in charge_states.values()
    ):
        return finance_response({"error": "Mindestens eine ausgewählte Buchung ist nicht mehr offen."}, 409)
    if any(
        charge.kind == "event_ticket"
        and (not charge.registration or charge.registration.cancelled_at)
        for charge in charges
    ):
        return finance_response({"error": "Mindestens ein ausgewähltes Eventticket ist nicht mehr gültig."}, 409)
    total_cents = sum(state["remaining_cents"] for state in charge_states.values())
    available_before = unallocated_payment_cents(user.id)
    if total_cents > available_before:
        return finance_response({"error": "Das noch nicht zugeordnete Kontoguthaben reicht für diese Auswahl nicht aus."}, 409)
    note = (
        f"Vorgeschlagene Zuordnung nach Zahlungseingang {triggering_payment.uid} bestätigt."
        if triggering_payment
        else "Vorgeschlagene Zuordnung aus vorhandenem Kontoguthaben bestätigt."
    )
    try:
        allocation_result = allocate_unallocated_credit_to_charges(
            user.id,
            charges,
            current_user.id,
            source="payment_match",
            note=note,
            require_full=True,
        )
    except ValueError as error:
        return finance_response({"error": str(error)}, 409)
    db.session.commit()
    return finance_response({
        "success": True,
        "confirmed_count": len(charges),
        "total_cents": allocation_result["allocated_cents"],
        "unallocated_credit_cents": allocation_result["available_cents"],
        "balance_cents": user_balance(user.id),
    })


@app.route("/api/v1/manage/finance/payments/<payment_uid>/void", methods=["POST"])
def api_void_finance_payment(payment_uid):
    denied = finance_access_denied()
    if denied:
        return denied
    payment = Tables.FinancePayment.query.filter_by(uid=payment_uid).with_for_update().first()
    if not payment:
        return finance_response({"error": "Zahlung nicht gefunden."}, 404)
    if payment.voided_at:
        return finance_response({"error": "Diese Zahlung wurde bereits storniert."}, 409)
    payload = request.get_json(silent=True) or {}
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        return finance_response({"success": False, "errors": {"reason": "Bitte gib einen Grund für die Stornierung an."}}, 400)
    payment.voided_at = datetime.now()
    payment.voided_by = current_user.id
    payment.void_reason = reason[:1000]
    affected_charges = release_payment_allocations(
        payment,
        current_user.id,
        source="payment_voided",
        note=reason[:1000],
    )
    for charge in affected_charges:
        sync_charge_payment_state(charge, current_user.id, "payment_voided", reason)
    db.session.commit()
    owner_user_id = payment.user_id
    if owner_user_id is None and payment.membership_id:
        membership = Tables.Membership.query.filter_by(id=payment.membership_id).first()
        owner_user_id = membership.user_id if membership else None
    return finance_response({"success": True, "payment": serialize_payment(payment), "balance_cents": user_balance(owner_user_id) if owner_user_id else 0})


@app.route("/api/v1/manage/finance/charges/<charge_uid>/status", methods=["PUT"])
def api_update_finance_charge_status(charge_uid):
    denied = finance_access_denied()
    if denied:
        return denied
    charge = Tables.FinanceCharge.query.filter_by(uid=charge_uid).first()
    if not charge:
        return finance_response({"error": "Buchung nicht gefunden."}, 404)
    payload = request.get_json(silent=True) or {}
    status = str(payload.get("status") or "")
    if status not in {"open", "paid", "cancelled"}:
        return finance_response({"success": False, "errors": {"status": "Ungültiger Status."}}, 400)
    note = str(payload.get("note") or "").strip()
    if status == "cancelled" and not note:
        return finance_response({"success": False, "errors": {"note": "Bitte gib einen Grund für die Stornierung an."}}, 400)
    if charge.kind == "event_ticket" and charge.registration:
        if status == "cancelled":
            cancel_registration(charge.registration, current_user.id, note)
        else:
            set_registration_paid(charge.registration, status == "paid", current_user.id, "finance", note or "Ticketstatus im Finanzkonto geändert")
    else:
        if status == "cancelled":
            release_charge_allocations(charge, current_user.id, source="charge_cancelled", note=note)
            charge.legacy_paid_override = False
            set_finance_charge_status(charge, "cancelled", current_user.id, note)
        elif status == "open" and charge.legacy_paid_override:
            charge.legacy_paid_override = False
            sync_charge_payment_state(charge, current_user.id, "legacy_status_cleared", note or "Alte manuelle Bezahlmarkierung entfernt.")
        else:
            return finance_response({"error": "Der Zahlungsstatus wird aus den Zahlungszuordnungen berechnet. Buche eine Zahlung und gleiche sie mit den offenen Buchungen ab."}, 409)
    db.session.commit()
    owner_user_id = charge.user_id
    if owner_user_id is None and charge.membership_id:
        membership = Tables.Membership.query.filter_by(id=charge.membership_id).first()
        owner_user_id = membership.user_id if membership else None
    return finance_response({"success": True, "charge": serialize_charge(charge), "balance_cents": user_balance(owner_user_id) if owner_user_id else 0})


@app.route("/api/v1/manage/finance/memberships/<membership_uid>/confirm-open-tally", methods=["POST"])
def api_confirm_open_tally(membership_uid):
    denied = finance_access_denied()
    if denied:
        return denied
    return finance_response({"error": "Tally-Buchungen werden über Payment-Zuordnungen abgeglichen. Bitte verbuche eine Zahlung und prüfe den Zuordnungsvorschlag."}, 409)


@app.route("/api/v1/manage/finance/users/<user_uid>/confirm-open-tally", methods=["POST"])
def api_confirm_open_tally_for_user(user_uid):
    denied = finance_access_denied()
    if denied:
        return denied
    return finance_response({"error": "Tally-Buchungen werden über Payment-Zuordnungen abgeglichen. Bitte verbuche eine Zahlung und prüfe den Zuordnungsvorschlag."}, 409)


def format_euros(cents):
    cents = int(cents)
    sign = "−" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100},{cents % 100:02d} €"


@app.route("/api/v1/manage/finance/reminders", methods=["POST"])
def api_send_finance_reminders():
    denied = finance_access_denied()
    if denied:
        return denied
    return finance_response({
        "error": "Bitte öffne zuerst den gespeicherten Mailentwurf, prüfe die Empfänger:innen und bestätige den Versand.",
    }, 409)
