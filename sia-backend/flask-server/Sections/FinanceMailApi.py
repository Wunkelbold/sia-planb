from collections import defaultdict
from datetime import date, datetime, timedelta
from html import escape
import re
import threading
from urllib.parse import urlencode
from uuid import UUID

from flask import current_app, request
from flask_login import current_user
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from database import Tables, db
from globals import Message, app
from Sections.EmailHandler import frontend_base_url, send_mail
from Sections.FinanceAllocations import allocation_amounts_for_charges, charge_payment_state
from Sections.FinanceApi import (
    as_datetime,
    finance_access_denied,
    finance_response,
    finance_settings,
    format_euros,
    next_student_billing_cycle_year,
    student_verification_serializer,
    user_balance,
    user_charges,
    user_payments,
)


MAIL_KINDS = {"payment_reminder", "student_verification"}
MAIL_PLACEHOLDERS = {
    "payment_reminder": {
        "name", "balance", "account_activity", "payment_instructions", "finance_url",
    },
    "student_verification": {"name", "cycle_year", "verification_link"},
}
MAX_DRAFT_BODY_LENGTH = 12000
MAX_RECIPIENTS_PER_CAMPAIGN = 5000


DEFAULT_MAIL_DRAFTS = {
    "payment_reminder": {
        "subject_template": "Hinweis zu deinem Finanzsaldo",
        "body_template": (
            "Hallo {{name}},\n\n"
            "auf deinem Konto ist aktuell ein offener Finanzsaldo von {{balance}}.\n\n"
            "Buchungen und erfasste Zahlungen:\n{{account_activity}}\n\n"
            "{{payment_instructions}}\n\n"
            "Bitte prüfe den aktuellen Stand in deinem Finanzbereich. Bereits veranlasste Zahlungen "
            "können einige Bankarbeitstage benötigen. Bei Fragen oder Unklarheiten melde dich bitte "
            "bei der Verwaltung.\n\n"
            "{{finance_url}}\n\nDein SIA-Team"
        ),
        "minimum_balance_cents": 0,
        "cycle_year": None,
    },
    "student_verification": {
        "subject_template": "Studentenstatus für den Mitgliedsbeitrag bestätigen",
        "body_template": (
            "Hallo {{name}},\n\n"
            "bitte bestätige deine Hochschul-E-Mail-Adresse für den Mitgliedsbeitragszyklus "
            "{{cycle_year}}.\n\n{{verification_link}}\n\nDein SIA-Team"
        ),
        "minimum_balance_cents": 0,
        "cycle_year": None,
    },
}


def _valid_kind(kind):
    return kind in MAIL_KINDS


def _mail_test_address():
    return (finance_settings().mail_test_email or "").strip()


def _mail_draft_dict(draft):
    actor = Tables.User.query.filter_by(id=draft.updated_by).first() if draft.updated_by else None
    return {
        "kind": draft.kind,
        "subject_template": draft.subject_template,
        "body_template": draft.body_template,
        "minimum_balance_cents": draft.minimum_balance_cents,
        "cycle_year": draft.cycle_year,
        "selected_recipient_keys": draft.selected_recipient_keys,
        "version": draft.version,
        "updated_by_username": actor.username if actor else "",
        "updated_at": as_datetime(draft.updated_at),
    }


def _get_or_create_mail_draft(kind):
    draft = Tables.FinanceMailDraft.query.filter_by(kind=kind).first()
    if draft:
        return draft
    defaults = DEFAULT_MAIL_DRAFTS[kind]
    try:
        with db.session.begin_nested():
            draft = Tables.FinanceMailDraft(
                kind=kind,
                subject_template=defaults["subject_template"],
                body_template=defaults["body_template"],
                minimum_balance_cents=defaults["minimum_balance_cents"],
                cycle_year=next_student_billing_cycle_year() if kind == "student_verification" else None,
            )
            db.session.add(draft)
            db.session.flush()
        return draft
    except IntegrityError:
        draft = Tables.FinanceMailDraft.query.filter_by(kind=kind).first()
        if draft:
            return draft
        raise


def _validate_template(kind, subject, body):
    errors = {}
    subject = str(subject or "").strip()
    body = str(body or "").strip()
    if not subject:
        errors["subject_template"] = "Bitte gib einen Betreff ein."
    elif len(subject) > 255:
        errors["subject_template"] = "Der Betreff darf höchstens 255 Zeichen enthalten."
    elif "\r" in subject or "\n" in subject:
        errors["subject_template"] = "Der Betreff darf keine Zeilenumbrüche enthalten."
    if not body:
        errors["body_template"] = "Bitte gib einen Nachrichtentext ein."
    elif len(body) > MAX_DRAFT_BODY_LENGTH:
        errors["body_template"] = f"Der Nachrichtentext darf höchstens {MAX_DRAFT_BODY_LENGTH} Zeichen enthalten."
    placeholders = set(re.findall(r"{{\s*([a-z_]+)\s*}}", subject + "\n" + body))
    unknown = placeholders - MAIL_PLACEHOLDERS[kind]
    if unknown:
        errors["body_template"] = "Unbekannte Platzhalter: " + ", ".join(sorted(unknown))
    return subject, body, errors


def _normalize_selection(value):
    if value is None:
        return None
    if not isinstance(value, list) or len(value) > MAX_RECIPIENTS_PER_CAMPAIGN:
        raise ValueError("Die Empfängerauswahl ist ungültig.")
    keys = []
    seen = set()
    for item in value:
        item = str(item).strip()
        if not item or len(item) > 100:
            raise ValueError("Die Empfängerauswahl ist ungültig.")
        if item not in seen:
            seen.add(item)
            keys.append(item)
    return keys


def _confirmed_reminder_email(user):
    if user.email and user.email_confirmed:
        return user.email.strip(), "email"
    if user.hs_email and user.hs_email_confirmed:
        return user.hs_email.strip(), "hs_email"
    return "", ""


def _display_name(user):
    return " ".join(part for part in (user.surname, user.lastname) if part).strip() or user.username


def _finance_balances_for_users(users):
    user_ids = [user.id for user in users]
    if not user_ids:
        return {}
    membership_rows = db.session.query(
        Tables.Membership.id,
        Tables.Membership.user_id,
    ).filter(Tables.Membership.user_id.in_(user_ids)).all()
    membership_owners = {membership_id: user_id for membership_id, user_id in membership_rows}
    membership_ids = list(membership_owners)
    totals = {user_id: 0 for user_id in user_ids}

    for model, open_filter in (
        (Tables.FinanceCharge, Tables.FinanceCharge.status != "cancelled"),
        (Tables.FinancePayment, Tables.FinancePayment.voided_at.is_(None)),
    ):
        owner_filters = [model.user_id.in_(user_ids)]
        if membership_ids:
            owner_filters.append(model.membership_id.in_(membership_ids))
        rows = db.session.query(
            model.user_id,
            model.membership_id,
            db.func.coalesce(db.func.sum(model.amount_cents), 0),
        ).filter(
            or_(*owner_filters),
            open_filter,
        ).group_by(model.user_id, model.membership_id).all()
        sign = 1 if model is Tables.FinanceCharge else -1
        for record_user_id, membership_id, amount_cents in rows:
            amount_cents = int(amount_cents or 0) * sign
            if record_user_id in totals:
                totals[record_user_id] += amount_cents
            membership_owner_id = membership_owners.get(membership_id)
            if membership_owner_id in totals and membership_owner_id != record_user_id:
                totals[membership_owner_id] += amount_cents
    return totals


def _selected_by_draft(draft, key, default_selected, selection_set=None, scope_user_uid=None, user_uid=None):
    if scope_user_uid:
        return str(scope_user_uid) == str(user_uid) and default_selected
    if draft.selected_recipient_keys is None:
        return default_selected
    return key in (selection_set or set())


def build_mail_preview(kind, draft, scope_user_uid=None):
    if kind == "payment_reminder":
        users_query = Tables.User.query.order_by(Tables.User.surname.asc(), Tables.User.lastname.asc(), Tables.User.username.asc())
        if scope_user_uid:
            try:
                scope_uuid = UUID(str(scope_user_uid))
            except (TypeError, ValueError, AttributeError):
                return None, "Benutzerkonto nicht gefunden."
            scope_user = Tables.User.query.filter_by(uid=scope_uuid).first()
            if not scope_user:
                return None, "Benutzerkonto nicht gefunden."
            users_query = users_query.filter(Tables.User.id == scope_user.id)

        users = users_query.all()
        balances = _finance_balances_for_users(users)
        candidates = []
        selection_set = set(draft.selected_recipient_keys or []) if draft.selected_recipient_keys is not None else None
        positive_balance = 0
        no_positive_balance = 0
        below_threshold = 0
        no_confirmed_email = 0
        for user in users:
            balance = balances.get(user.id, 0)
            if balance <= 0:
                no_positive_balance += 1
            else:
                positive_balance += 1
            email, email_source = _confirmed_reminder_email(user)
            reasons = []
            if balance <= 0:
                reasons.append("no_positive_balance")
            elif balance < draft.minimum_balance_cents:
                reasons.append("below_threshold")
                below_threshold += 1
            if balance > 0 and not email:
                reasons.append("no_confirmed_email")
                no_confirmed_email += 1
            can_select = balance > 0 and balance >= draft.minimum_balance_cents and bool(email)
            default_selected = can_select
            key = f"user:{user.uid}"
            selected = _selected_by_draft(
                draft,
                key,
                default_selected,
                selection_set,
                scope_user_uid,
                user.uid,
            ) and can_select
            candidates.append({
                "key": key,
                "user_uid": str(user.uid),
                "membership_uid": None,
                "username": user.username,
                "display_name": _display_name(user),
                "email": email,
                "email_source": email_source,
                "balance_cents": balance,
                "can_select": can_select,
                "default_selected": default_selected,
                "selected": selected,
                "reasons": reasons,
            })
        selected_count = sum(item["selected"] for item in candidates)
        return {
            "kind": kind,
            "draft_version": draft.version,
            "minimum_balance_cents": draft.minimum_balance_cents,
            "selected_recipient_keys": draft.selected_recipient_keys,
            "selection_is_saved": draft.selected_recipient_keys is not None,
            "scope_user_uid": str(scope_user_uid) if scope_user_uid else None,
            "summary": {
                "selected": selected_count,
                "positive_balance": positive_balance,
                "no_positive_balance": no_positive_balance,
                "below_threshold": below_threshold,
                "no_confirmed_email": no_confirmed_email,
            },
            "candidates": candidates,
        }, None

    cycle_year = draft.cycle_year or next_student_billing_cycle_year()
    memberships = Tables.Membership.query.filter_by(
        status="active",
        fee_category="student",
    ).order_by(Tables.Membership.member_since.asc(), Tables.Membership.id.asc()).all()
    membership_ids = [membership.id for membership in memberships]
    verifications = {}
    if membership_ids:
        verifications = {
            verification.membership_id: verification
            for verification in Tables.MembershipStudentVerification.query.filter(
                Tables.MembershipStudentVerification.cycle_year == cycle_year,
                Tables.MembershipStudentVerification.membership_id.in_(membership_ids),
            ).all()
        }
    current_time = datetime.now()
    candidates = []
    selection_set = set(draft.selected_recipient_keys or []) if draft.selected_recipient_keys is not None else None
    counts = {"already_verified": 0, "cooldown": 0, "missing_hs_email": 0}
    for membership in memberships:
        user = membership.user_obj
        if not user:
            continue
        email = (user.hs_email or "").strip()
        email_normalized = email.lower()
        verification = verifications.get(membership.id)
        reasons = []
        if not email:
            reasons.append("missing_hs_email")
            counts["missing_hs_email"] += 1
        if (
            email
            and verification
            and verification.verified_at
            and verification.email_snapshot.lower() == email_normalized
        ):
            reasons.append("already_verified")
            counts["already_verified"] += 1
        if (
            email
            and verification
            and verification.email_snapshot.lower() == email_normalized
            and current_time - verification.requested_at < timedelta(minutes=5)
        ):
            reasons.append("cooldown")
            counts["cooldown"] += 1
        can_select = not reasons
        key = f"membership:{membership.uid}"
        selected = _selected_by_draft(draft, key, can_select, selection_set) and can_select
        candidates.append({
            "key": key,
            "user_uid": str(user.uid),
            "membership_uid": str(membership.uid),
            "username": user.username,
            "display_name": _display_name(user),
            "email": email,
            "email_source": "hs_email" if email else "",
            "balance_cents": None,
            "can_select": can_select,
            "default_selected": can_select,
            "selected": selected,
            "reasons": reasons,
        })
    return {
        "kind": kind,
        "cycle_year": cycle_year,
        "draft_version": draft.version,
        "selected_recipient_keys": draft.selected_recipient_keys,
        "selection_is_saved": draft.selected_recipient_keys is not None,
        "scope_user_uid": None,
        "summary": {
            "selected": sum(item["selected"] for item in candidates),
            "active_students": len(candidates),
            **counts,
        },
        "candidates": candidates,
    }, None


def _account_charge_activity(charge, allocated_cents):
    state = charge_payment_state(charge, allocated_cents)
    return {
        "kind": charge.kind,
        "name": charge.name_snapshot,
        "amount_cents": charge.amount_cents,
        "status": state["status"],
        "allocated_cents": state["allocated_cents"],
        "remaining_cents": state["remaining_cents"],
        "created_at": as_datetime(charge.created_at),
        "due_date": charge.due_date.isoformat() if charge.due_date else None,
    }


def _account_activity_snapshot(user_id):
    charges = user_charges(user_id).filter(
        Tables.FinanceCharge.status != "cancelled",
    ).order_by(Tables.FinanceCharge.created_at.desc(), Tables.FinanceCharge.id.desc()).all()
    payments = user_payments(user_id).order_by(
        Tables.FinancePayment.received_at.desc(),
        Tables.FinancePayment.id.desc(),
    ).all()
    allocations = allocation_amounts_for_charges([charge.id for charge in charges])
    return {
        "charges": [
            _account_charge_activity(charge, allocations.get(charge.id, 0))
            for charge in charges[:30]
        ],
        "payments": [
            {
                "amount_cents": payment.amount_cents,
                "method": payment.method,
                "reference": payment.reference or "",
                "received_at": as_datetime(payment.received_at),
                "voided": bool(payment.voided_at),
            }
            for payment in payments[:20]
        ],
        "charges_truncated": len(charges) > 30,
        "payments_truncated": len(payments) > 20,
    }


def _activity_text(activity):
    lines = []
    for charge in activity["charges"]:
        status = {
            "open": "offen markiert",
            "partially_paid": "teilweise bezahlt",
            "paid": "als bezahlt markiert",
            "waived": "beitragsfrei",
            "cancelled": "storniert",
        }.get(charge["status"], charge["status"])
        lines.append(f"• {charge['name']}: {format_euros(charge['amount_cents'])} ({status})")
    for payment in activity["payments"]:
        method = {"bank_transfer": "Überweisung", "cash": "Barzahlung", "other": "Zahlung"}.get(payment["method"], "Zahlung")
        if payment["voided"]:
            method += " (storniert)"
        lines.append(f"• {method}: − {format_euros(payment['amount_cents'])}")
    if activity["charges_truncated"] or activity["payments_truncated"]:
        lines.append("Weitere Kontobewegungen findest du in deinem Finanzbereich.")
    return "\n".join(lines) or "Keine Kontobewegungen hinterlegt."


def _render_subject(template, values):
    return re.sub(
        r"{{\s*([a-z_]+)\s*}}",
        lambda match: str(values.get(match.group(1), match.group(0))).replace("\r", " ").replace("\n", " "),
        template,
    )


def _render_body(kind, template, values, verification_url=None):
    link_markup = ""
    if verification_url:
        safe_url = escape(verification_url, quote=True)
        link_markup = f'<a href="{safe_url}">Studentenstatus bestätigen</a>'
    pieces = []
    link_inserted = False
    for part in re.split(r"({{\s*[a-z_]+\s*}})", template):
        match = re.fullmatch(r"{{\s*([a-z_]+)\s*}}", part)
        if not match:
            pieces.append(escape(part).replace("\n", "<br>\n"))
            continue
        key = match.group(1)
        if key == "verification_link" and kind == "student_verification":
            pieces.append(link_markup)
            link_inserted = True
        else:
            pieces.append(escape(str(values.get(key, ""))).replace("\n", "<br>\n"))
    if kind == "student_verification" and not link_inserted and link_markup:
        pieces.append(f"<p>{link_markup}</p>")
    return "".join(pieces)


def _mail_values(kind, candidate, draft, activity=None, verification_url=None, test=False):
    if kind == "payment_reminder":
        settings = finance_settings()
        balance = candidate.get("balance_cents") or 0
        activity = activity or {"charges": [], "payments": [], "charges_truncated": False, "payments_truncated": False}
        return {
            "name": candidate.get("display_name") or "Testmitglied",
            "balance": format_euros(balance),
            "account_activity": _activity_text(activity),
            "payment_instructions": settings.payment_instructions or "",
            "finance_url": f"{frontend_base_url()}/me/finances",
        }
    return {
        "name": candidate.get("display_name") or "Testmitglied",
        "cycle_year": str(draft.cycle_year or next_student_billing_cycle_year()),
        "verification_link": "",
    }


def _message_for(kind, draft, candidate, activity=None, verification_url=None, test=False):
    values = _mail_values(kind, candidate, draft, activity, verification_url, test)
    subject = _render_subject(draft.subject_template, values)
    if test:
        subject = f"[TEST] {subject}"
    body = _render_body(kind, draft.body_template, values, verification_url)
    message = Message(
        subject=subject,
        sender=current_app.config.get("MAIL_DEFAULT_SENDER"),
        recipients=[candidate["email"]],
        html=body,
    )
    # Keep the individualized copy for the campaign history, but never persist
    # a live student-verification token in an Admin-visible email log.
    history_body = body
    if kind == "student_verification" and verification_url:
        history_body = body.replace(escape(verification_url, quote=True), "[individueller Bestätigungslink]")
    return message, subject, history_body


def _update_campaign_status(campaign):
    status_counts = dict(db.session.query(
        Tables.FinanceMailRecipient.status,
        db.func.count(Tables.FinanceMailRecipient.id),
    ).filter_by(campaign_id=campaign.id).group_by(Tables.FinanceMailRecipient.status).all())
    if status_counts.get("queued", 0):
        campaign.status = "sending"
        campaign.completed_at = None
    else:
        total = sum(status_counts.values())
        campaign.status = "failed" if total and not status_counts.get("accepted", 0) else "completed"
        campaign.completed_at = datetime.now()


def _deliver_campaign_mail(app_object, recipient_id, message):
    with app_object.app_context():
        recipient = Tables.FinanceMailRecipient.query.filter_by(id=recipient_id).first()
        if not recipient:
            return
        recipient.attempted_at = datetime.now()
        db.session.commit()
    accepted, error_message = send_mail(app_object, message)
    with app_object.app_context():
        recipient = Tables.FinanceMailRecipient.query.filter_by(id=recipient_id).first()
        if not recipient:
            return
        recipient.status = "accepted" if accepted else "failed"
        recipient.error_message = None if accepted else str(error_message or "Versand fehlgeschlagen.")[:1000]
        recipient.completed_at = datetime.now()
        _update_campaign_status(recipient.campaign)
        db.session.commit()


def _queue_campaign_mail(app_object, recipient_id, message):
    try:
        thread = threading.Thread(
            target=_deliver_campaign_mail,
            args=(app_object, recipient_id, message),
            daemon=True,
        )
        thread.start()
    except Exception as error:
        recipient = Tables.FinanceMailRecipient.query.filter_by(id=recipient_id).first()
        if recipient:
            recipient.status = "failed"
            recipient.error_message = f"Versand konnte nicht gestartet werden: {error}"[:1000]
            recipient.completed_at = datetime.now()
            _update_campaign_status(recipient.campaign)
            db.session.commit()


def _recipient_snapshot(candidate, status, reason=None, balance=None, activity=None, message_parts=None):
    subject_snapshot = message_parts[1] if message_parts else None
    body_snapshot = message_parts[2] if message_parts else None
    return Tables.FinanceMailRecipient(
        recipient_key=candidate["key"],
        user_id=candidate.get("user_id"),
        membership_id=candidate.get("membership_id"),
        username_snapshot=candidate.get("username", "")[:80],
        display_name_snapshot=candidate.get("display_name", "")[:160],
        email_snapshot=candidate.get("email") or None,
        balance_snapshot_cents=balance,
        activity_snapshot=activity,
        status=status,
        reason=reason,
        subject_snapshot=subject_snapshot,
        body_snapshot=body_snapshot,
    )


def _campaign_counts(kind, preview, selected_keys):
    selected = set(selected_keys)
    summary = dict(preview["summary"])
    summary["selected"] = len(selected)
    summary["excluded_by_admin"] = sum(
        item["can_select"]
        and item["key"] not in selected
        and "below_threshold" not in item.get("reasons", [])
        for item in preview["candidates"]
    )
    summary["skipped_below_threshold"] = sum(
        "below_threshold" in item.get("reasons", []) and item["key"] not in selected
        for item in preview["candidates"]
    )
    summary["queued"] = len(selected)
    return summary


def _campaign_summary(campaign, status_counts=None):
    actor = Tables.User.query.filter_by(id=campaign.created_by).first() if campaign.created_by else None
    status_counts = status_counts or {}
    actor_name = actor.username if actor else ("Altbestand · Absender unbekannt" if campaign.source == "legacy" else "")
    return {
        "uid": str(campaign.uid),
        "kind": campaign.kind,
        "source": campaign.source,
        "test_only": campaign.test_only,
        "cycle_year": campaign.cycle_year,
        "minimum_balance_cents": campaign.minimum_balance_cents,
        "subject_template": campaign.subject_template,
        "body_template": campaign.body_template,
        "created_by_username": actor_name,
        "created_at": as_datetime(campaign.created_at),
        "completed_at": as_datetime(campaign.completed_at),
        "status": campaign.status,
        "counts": campaign.counts or {},
        "recipient_status_counts": status_counts,
        "recipient_count": sum(status_counts.values()),
    }


def _recipient_history_dict(recipient):
    user = Tables.User.query.filter_by(id=recipient.user_id).first() if recipient.user_id else None
    return {
        "key": recipient.recipient_key,
        "username": recipient.username_snapshot,
        "display_name": recipient.display_name_snapshot,
        "user_uid": str(user.uid) if user else None,
        "email": recipient.email_snapshot or "",
        "balance_cents": recipient.balance_snapshot_cents,
        "activity": recipient.activity_snapshot or {},
        "status": recipient.status,
        "reason": recipient.reason or "",
        "error_message": recipient.error_message or "",
        "subject": recipient.subject_snapshot or "",
        "body": recipient.body_snapshot or "",
        "attempted_at": as_datetime(recipient.attempted_at),
        "completed_at": as_datetime(recipient.completed_at),
    }


@app.route("/api/v1/manage/finance/mail-drafts/<kind>", methods=["GET", "PUT"])
def api_manage_finance_mail_draft(kind):
    denied = finance_access_denied()
    if denied:
        return denied
    if not _valid_kind(kind):
        return finance_response({"error": "Unbekannter E-Mail-Typ."}, 404)
    draft = _get_or_create_mail_draft(kind)
    if request.method == "GET":
        db.session.commit()
        return finance_response({
            "draft": _mail_draft_dict(draft),
            "mail_test_email": _mail_test_address(),
        })

    payload = request.get_json(silent=True) or {}
    try:
        expected_version = int(payload.get("version"))
    except (TypeError, ValueError):
        return finance_response({"error": "Die Entwurfsversion fehlt."}, 400)
    if expected_version != draft.version:
        return finance_response({"error": "Der gemeinsame Entwurf wurde inzwischen von einer anderen Verwaltung geändert.", "draft": _mail_draft_dict(draft)}, 409)
    subject, body, errors = _validate_template(kind, payload.get("subject_template"), payload.get("body_template"))
    if kind == "payment_reminder":
        try:
            minimum_balance_cents = int(payload.get("minimum_balance_cents", draft.minimum_balance_cents))
            if minimum_balance_cents < 0 or minimum_balance_cents > 100_000_000:
                raise ValueError()
        except (TypeError, ValueError):
            errors["minimum_balance_cents"] = "Der Mindestbetrag muss zwischen 0 € und 1.000.000 € liegen."
    else:
        minimum_balance_cents = 0
    if errors:
        return finance_response({"success": False, "errors": errors}, 400)
    try:
        if "selected_recipient_keys" in payload:
            selection = _normalize_selection(payload["selected_recipient_keys"])
        else:
            selection = draft.selected_recipient_keys
    except ValueError as error:
        return finance_response({"error": str(error)}, 400)

    draft.subject_template = subject
    draft.body_template = body
    draft.minimum_balance_cents = minimum_balance_cents
    if kind == "student_verification":
        try:
            cycle_year = int(payload.get("cycle_year", draft.cycle_year or next_student_billing_cycle_year()))
        except (TypeError, ValueError):
            return finance_response({"error": "Ungültiges Beitragsjahr."}, 400)
        if cycle_year < 2020 or cycle_year > date.today().year + 5:
            return finance_response({"error": "Ungültiges Beitragsjahr."}, 400)
        draft.cycle_year = cycle_year
    draft.selected_recipient_keys = selection
    draft.version += 1
    draft.updated_by = current_user.id
    draft.updated_at = datetime.now()
    db.session.commit()
    return finance_response({"success": True, "draft": _mail_draft_dict(draft)})


@app.route("/api/v1/manage/finance/mail-drafts/<kind>/preview", methods=["POST"])
def api_preview_finance_mail_draft(kind):
    denied = finance_access_denied()
    if denied:
        return denied
    if not _valid_kind(kind):
        return finance_response({"error": "Unbekannter E-Mail-Typ."}, 404)
    draft = _get_or_create_mail_draft(kind)
    payload = request.get_json(silent=True) or {}
    if payload.get("version") is not None and str(payload.get("version")) != str(draft.version):
        return finance_response({"error": "Der gemeinsame Entwurf wurde inzwischen geändert. Lade ihn neu und aktualisiere die Vorschau."}, 409)
    scope_user_uid = payload.get("scope_user_uid")
    preview, error = build_mail_preview(kind, draft, scope_user_uid)
    if error:
        return finance_response({"error": error}, 404)
    subject, body, template_errors = _validate_template(kind, draft.subject_template, draft.body_template)
    if template_errors:
        return finance_response({"success": False, "errors": template_errors}, 400)
    db.session.commit()
    preview["draft"] = _mail_draft_dict(draft)
    preview["mail_test_email"] = _mail_test_address()
    return finance_response(preview)


def _create_campaign(kind, source, draft, creator_id, counts, test_only=False):
    campaign = Tables.FinanceMailCampaign(
        kind=kind,
        source=source,
        cycle_year=draft.cycle_year if kind == "student_verification" else None,
        minimum_balance_cents=draft.minimum_balance_cents if kind == "payment_reminder" else None,
        test_only=test_only,
        subject_template=draft.subject_template,
        body_template=draft.body_template,
        created_by=creator_id,
        status="sending",
        counts=counts,
    )
    db.session.add(campaign)
    db.session.flush()
    return campaign


def _test_sample(kind, preview):
    candidates = preview["candidates"]
    sample = next((candidate for candidate in candidates if candidate["selected"]), None)
    if not sample:
        sample = next((candidate for candidate in candidates if candidate["can_select"]), None)
    if sample:
        return dict(sample)
    return {
        "key": "test:sample",
        "user_uid": None,
        "membership_uid": None,
        "username": "testmitglied",
        "display_name": "Testmitglied",
        "email": "",
        "email_source": "",
        "balance_cents": 2345 if kind == "payment_reminder" else None,
        "can_select": False,
        "default_selected": False,
        "selected": False,
        "reasons": [],
    }


@app.route("/api/v1/manage/finance/mail-drafts/<kind>/test", methods=["POST"])
def api_test_finance_mail_draft(kind):
    denied = finance_access_denied()
    if denied:
        return denied
    if not _valid_kind(kind):
        return finance_response({"error": "Unbekannter E-Mail-Typ."}, 404)
    draft = _get_or_create_mail_draft(kind)
    payload = request.get_json(silent=True) or {}
    if str(payload.get("version")) != str(draft.version):
        return finance_response({"error": "Der gemeinsame Entwurf wurde geändert. Speichere oder lade ihn neu, bevor du testest."}, 409)
    test_email = _mail_test_address()
    if not test_email:
        return finance_response({"error": "Bitte konfiguriere zuerst die Test-E-Mail-Adresse in den Finanzhinweisen."}, 409)
    subject, body, errors = _validate_template(kind, draft.subject_template, draft.body_template)
    if errors:
        return finance_response({"success": False, "errors": errors}, 400)
    preview, error = build_mail_preview(kind, draft)
    if error:
        return finance_response({"error": error}, 400)
    sample = _test_sample(kind, preview)
    sample["email"] = test_email
    sample_user = Tables.User.query.filter_by(uid=UUID(sample["user_uid"])).first() if sample.get("user_uid") else None
    activity = _account_activity_snapshot(sample_user.id) if kind == "payment_reminder" and sample_user else None
    verification_url = "https://example.invalid/student-verification-preview" if kind == "student_verification" else None
    message, rendered_subject, rendered_body = _message_for(
        kind,
        draft,
        sample,
        activity=activity,
        verification_url=verification_url,
        test=True,
    )
    counts = {"selected": 1, "test_only": True}
    campaign = _create_campaign(kind, "test", draft, current_user.id, counts, test_only=True)
    recipient = _recipient_snapshot(
        sample,
        "queued",
        reason="Test-E-Mail; wird ausschließlich an die konfigurierte Testadresse gesendet.",
        balance=sample.get("balance_cents"),
        activity=activity,
        message_parts=(message, rendered_subject, rendered_body),
    )
    recipient.recipient_key = f"test:{campaign.uid}"
    recipient.campaign_id = campaign.id
    recipient.email_snapshot = test_email
    db.session.add(recipient)
    db.session.commit()
    _queue_campaign_mail(current_app._get_current_object(), recipient.id, message)
    return finance_response({"success": True, "campaign_uid": str(campaign.uid), "recipient_email": test_email}, 202)


def _reason_text(candidate, kind):
    labels = {
        "below_threshold": "Saldo unter dem gewählten Mindestbetrag",
        "no_confirmed_email": "Keine bestätigte E-Mail-Adresse",
        "no_positive_balance": "Kein positiver offener Saldo",
        "missing_hs_email": "Keine Hochschul-E-Mail hinterlegt",
        "already_verified": "Für diese Adresse bereits bestätigt",
        "cooldown": "Vor weniger als fünf Minuten bereits angefordert",
    }
    return "; ".join(labels.get(reason, reason) for reason in candidate.get("reasons", []))


def _student_verification_url(membership, cycle_year, email):
    token = student_verification_serializer().dumps({
        "membership_uid": str(membership.uid),
        "cycle_year": cycle_year,
        "email": email.strip().lower(),
    })
    query = urlencode({"membership": str(membership.uid), "cycle": cycle_year, "token": token})
    return f"{frontend_base_url()}/verify_student_membership?{query}"


def _lock_student_verification_memberships(recipient_keys, cycle_year):
    membership_uuids = []
    for key in recipient_keys:
        if not key.startswith("membership:"):
            return "Die Empfängerauswahl für Studentenbestätigungen ist ungültig."
        try:
            membership_uuids.append(UUID(key.removeprefix("membership:")))
        except (TypeError, ValueError, AttributeError):
            return "Die Empfängerauswahl für Studentenbestätigungen ist ungültig."
    memberships = Tables.Membership.query.filter(
        Tables.Membership.uid.in_(membership_uuids),
    ).with_for_update().all()
    if len(memberships) != len(set(membership_uuids)):
        return "Mindestens eine Mitgliedschaft wurde nicht gefunden."
    if memberships:
        db.session.query(Tables.MembershipStudentVerification.id).filter(
            Tables.MembershipStudentVerification.cycle_year == cycle_year,
            Tables.MembershipStudentVerification.membership_id.in_([membership.id for membership in memberships]),
        ).with_for_update().all()
    return None


def _prepare_selected_recipient(kind, draft, candidate, campaign):
    user = Tables.User.query.filter_by(uid=UUID(candidate["user_uid"])).first()
    if not user:
        return None, None
    activity = _account_activity_snapshot(user.id) if kind == "payment_reminder" else None
    verification_url = None
    membership = None
    if kind == "student_verification":
        membership = Tables.Membership.query.filter_by(uid=UUID(candidate["membership_uid"])).first()
        if not membership:
            return None, None
        verification_url = _student_verification_url(membership, draft.cycle_year, candidate["email"])
        verification = Tables.MembershipStudentVerification.query.filter_by(
            membership_id=membership.id,
            cycle_year=draft.cycle_year,
        ).first()
        if not verification:
            verification = Tables.MembershipStudentVerification(
                membership_id=membership.id,
                cycle_year=draft.cycle_year,
                email_snapshot=candidate["email"].strip().lower(),
                requested_at=datetime.now(),
            )
            db.session.add(verification)
        else:
            verification.email_snapshot = candidate["email"].strip().lower()
            verification.requested_at = datetime.now()
            verification.verified_at = None
    message, rendered_subject, rendered_body = _message_for(
        kind,
        draft,
        candidate,
        activity=activity,
        verification_url=verification_url,
    )
    recipient = _recipient_snapshot(
        candidate,
        "queued",
        balance=candidate.get("balance_cents"),
        activity=activity,
        message_parts=(message, rendered_subject, rendered_body),
    )
    recipient.user_id = user.id
    recipient.membership_id = membership.id if membership else None
    recipient.campaign_id = campaign.id
    db.session.add(recipient)
    if kind == "payment_reminder":
        db.session.add(Tables.FinanceReminder(
            batch_uid=campaign.uid,
            user_id=user.id,
            email_snapshot=candidate["email"],
            balance_snapshot_cents=candidate["balance_cents"],
            sent_by=current_user.id,
        ))
    db.session.flush()
    return recipient, message


@app.route("/api/v1/manage/finance/mail-drafts/<kind>/send", methods=["POST"])
def api_send_finance_mail_draft(kind):
    denied = finance_access_denied()
    if denied:
        return denied
    if not _valid_kind(kind):
        return finance_response({"error": "Unbekannter E-Mail-Typ."}, 404)
    draft = _get_or_create_mail_draft(kind)
    payload = request.get_json(silent=True) or {}
    if str(payload.get("version")) != str(draft.version):
        return finance_response({"error": "Der gemeinsame Entwurf wurde inzwischen geändert. Lade ihn neu und aktualisiere die Vorschau."}, 409)
    raw_selected = payload.get("selected_recipient_keys")
    try:
        selected_keys = _normalize_selection(raw_selected)
    except ValueError as error:
        return finance_response({"error": str(error)}, 400)
    if not selected_keys:
        return finance_response({"error": "Wähle mindestens eine empfangende Person aus."}, 400)
    if len(selected_keys) > MAX_RECIPIENTS_PER_CAMPAIGN:
        return finance_response({"error": f"Eine Kampagne kann höchstens {MAX_RECIPIENTS_PER_CAMPAIGN} Empfänger:innen enthalten."}, 400)
    if kind == "student_verification":
        lock_error = _lock_student_verification_memberships(
            selected_keys,
            draft.cycle_year or next_student_billing_cycle_year(),
        )
        if lock_error:
            return finance_response({"error": lock_error}, 409)
    preview, error = build_mail_preview(kind, draft, payload.get("scope_user_uid"))
    if error:
        return finance_response({"error": error}, 404)
    candidates = {candidate["key"]: candidate for candidate in preview["candidates"]}
    invalid = [
        key for key in selected_keys
        if key not in candidates or not candidates[key]["can_select"]
    ]
    if invalid:
        return finance_response({
            "error": "Die Empfängerauswahl ist nicht mehr aktuell. Aktualisiere die Vorschau und prüfe die Empfänger erneut.",
            "preview": preview,
        }, 409)
    subject, body, errors = _validate_template(kind, draft.subject_template, draft.body_template)
    if errors:
        return finance_response({"success": False, "errors": errors}, 400)
    settings = finance_settings()
    if kind == "payment_reminder" and not settings.payment_instructions.strip():
        return finance_response({"error": "Bitte hinterlege zuerst die Zahlungsinformationen."}, 409)

    selected_set = set(selected_keys)
    expected_selected = {
        candidate["key"] for candidate in preview["candidates"]
        if candidate["selected"]
    }
    if selected_set != expected_selected:
        return finance_response({
            "error": "Die gespeicherte Empfängerauswahl weicht von der Vorschau ab. Speichere den Entwurf und prüfe die Empfänger erneut.",
            "preview": preview,
        }, 409)
    counts = _campaign_counts(kind, preview, selected_keys)
    campaign = _create_campaign(kind, "admin", draft, current_user.id, counts)
    outgoing = []
    for candidate in preview["candidates"]:
        selected = candidate["key"] in selected_set
        if selected:
            recipient, message = _prepare_selected_recipient(kind, draft, candidate, campaign)
            if not recipient:
                db.session.rollback()
                return finance_response({"error": "Mindestens ein Konto hat sich geändert. Aktualisiere die Vorschau."}, 409)
            outgoing.append((recipient, message))
            continue
        reasons = candidate.get("reasons", [])
        if not candidate["can_select"]:
            recipient_status = "skipped"
            reason = _reason_text(candidate, kind) or "Nicht für diese Mail geeignet"
        elif "below_threshold" in reasons:
            recipient_status = "skipped"
            reason = _reason_text(candidate, kind)
        else:
            recipient_status = "excluded"
            reason = "Manuell aus der gespeicherten Empfängerauswahl abgewählt."
        recipient = _recipient_snapshot(
            candidate,
            recipient_status,
            reason=reason,
            balance=candidate.get("balance_cents"),
        )
        if candidate.get("user_uid"):
            user = Tables.User.query.filter_by(uid=UUID(candidate["user_uid"])).first()
            recipient.user_id = user.id if user else None
        if candidate.get("membership_uid"):
            membership = Tables.Membership.query.filter_by(uid=UUID(candidate["membership_uid"])).first()
            recipient.membership_id = membership.id if membership else None
        recipient.campaign_id = campaign.id
        db.session.add(recipient)

    db.session.commit()
    app_object = current_app._get_current_object()
    for recipient, message in outgoing:
        _queue_campaign_mail(app_object, recipient.id, message)
    if not payload.get("scope_user_uid") and draft.selected_recipient_keys is not None:
        draft.selected_recipient_keys = None
        draft.version += 1
        draft.updated_by = current_user.id
        draft.updated_at = datetime.now()
        db.session.commit()
    return finance_response({
        "success": True,
        "campaign_uid": str(campaign.uid),
        "selected": len(outgoing),
        "counts": counts,
    }, 202)


def send_single_student_verification(membership, cycle_year):
    """Record and queue a self-requested student verification email."""
    membership = Tables.Membership.query.filter_by(id=membership.id).with_for_update().first()
    if not membership or membership.status != "active" or membership.fee_category != "student":
        return "student_membership_required", None
    draft = _get_or_create_mail_draft("student_verification")
    subject, body, errors = _validate_template("student_verification", draft.subject_template, draft.body_template)
    if errors:
        return "invalid_template", None
    user = membership.user_obj
    email = (user.hs_email or "").strip() if user else ""
    if not email:
        return "missing_email", None
    verification = Tables.MembershipStudentVerification.query.filter_by(
        membership_id=membership.id,
        cycle_year=cycle_year,
    ).with_for_update().first()
    if verification and verification.verified_at and verification.email_snapshot.lower() == email.lower():
        return "already_verified", None
    if (
        verification
        and verification.email_snapshot.lower() == email.lower()
        and datetime.now() - verification.requested_at < timedelta(minutes=5)
    ):
        return "cooldown", None
    candidate = {
        "key": f"membership:{membership.uid}",
        "user_uid": str(user.uid),
        "membership_uid": str(membership.uid),
        "username": user.username,
        "display_name": _display_name(user),
        "email": email,
        "balance_cents": None,
    }
    campaign_draft = Tables.FinanceMailDraft(
        kind="student_verification",
        subject_template=subject,
        body_template=body,
        minimum_balance_cents=0,
        cycle_year=cycle_year,
    )
    counts = {"selected": 1, "active_students": 1, "source": "member"}
    campaign = _create_campaign("student_verification", "member", campaign_draft, user.id, counts)
    recipient, message = _prepare_selected_recipient("student_verification", campaign_draft, candidate, campaign)
    db.session.commit()
    _queue_campaign_mail(current_app._get_current_object(), recipient.id, message)
    return "sent", str(campaign.uid)


@app.route("/api/v1/manage/finance/mail-campaigns", methods=["GET"])
def api_list_finance_mail_campaigns():
    denied = finance_access_denied()
    if denied:
        return denied
    kind = request.args.get("kind")
    if kind and not _valid_kind(kind):
        return finance_response({"error": "Unbekannter E-Mail-Typ."}, 400)
    try:
        limit = min(100, max(1, int(request.args.get("limit", "30"))))
    except (TypeError, ValueError):
        limit = 30
    query = Tables.FinanceMailCampaign.query
    if kind:
        query = query.filter_by(kind=kind)
    campaigns = query.order_by(Tables.FinanceMailCampaign.created_at.desc(), Tables.FinanceMailCampaign.id.desc()).limit(limit).all()
    status_counts = defaultdict(dict)
    if campaigns:
        grouped = db.session.query(
            Tables.FinanceMailRecipient.campaign_id,
            Tables.FinanceMailRecipient.status,
            db.func.count(Tables.FinanceMailRecipient.id),
        ).filter(
            Tables.FinanceMailRecipient.campaign_id.in_([campaign.id for campaign in campaigns]),
        ).group_by(
            Tables.FinanceMailRecipient.campaign_id,
            Tables.FinanceMailRecipient.status,
        ).all()
        for campaign_id, status, count in grouped:
            status_counts[campaign_id][status] = int(count)
    return finance_response({
        "campaigns": [_campaign_summary(campaign, status_counts[campaign.id]) for campaign in campaigns],
    })


@app.route("/api/v1/manage/finance/mail-campaigns/<campaign_uid>", methods=["GET"])
def api_get_finance_mail_campaign(campaign_uid):
    denied = finance_access_denied()
    if denied:
        return denied
    try:
        campaign_uuid = UUID(str(campaign_uid))
    except (TypeError, ValueError, AttributeError):
        return finance_response({"error": "Mailkampagne nicht gefunden."}, 404)
    campaign = Tables.FinanceMailCampaign.query.filter_by(uid=campaign_uuid).first()
    if not campaign:
        return finance_response({"error": "Mailkampagne nicht gefunden."}, 404)
    return finance_response({
        "campaign": _campaign_summary(campaign),
        "recipients": [_recipient_history_dict(recipient) for recipient in campaign.recipients],
    })
