from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID

from flask import jsonify, request, url_for
from flask_login import current_user
from sqlalchemy import or_

from database import Tables, db
from forms import Forms
from Sections.EventHandler import getAllEvents
from Sections.EmailHandler import verify_email
from globals import app, bcrypt, local_tz
from permissions import hasPermissions
from Sections.RegistrationService import cancel_registration, create_event_ticket_charge
from Sections.AssignmentPermissions import can_assign_to, can_view_event
from Sections.EventScheduleRules import shift_event_schedule


def json_response(payload, status=200):
    response = jsonify(payload)
    response.headers["Cache-Control"] = "private, no-store"
    return response, status


def access_denied(permission=None):
    if not current_user.is_authenticated:
        return json_response({"error": "authentication_required"}, 401)
    if permission and not hasPermissions(permission):
        return json_response({"error": "permission_denied"}, 403)
    return None


def local_datetime(value):
    if value is None:
        return None
    if value.tzinfo:
        value = value.astimezone(local_tz).replace(tzinfo=None)
    return value.replace(tzinfo=local_tz).isoformat(timespec="minutes")


def serialize_assigned_user(user):
    return {
        "uid": str(user.uid),
        "username": user.username,
        "surname": user.surname or "",
        "lastname": user.lastname or "",
        "role": user.role,
    }


def user_permission_grants(user):
    role = Tables.Role.query.filter_by(name=user.role).first()
    permissions = list(role.permissions or []) if role else []
    permissions.extend(user.permissions or [])
    return permissions


def user_can_view_event(user, event):
    return can_view_event(user_permission_grants(user), event.visibility)


def parse_datetime(value, field, errors, required=False):
    if value in (None, ""):
        if required:
            errors[field] = "Dieses Datum wird benötigt."
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        errors[field] = "Bitte gib ein gültiges Datum und eine Uhrzeit an."
        return None
    if parsed.tzinfo:
        parsed = parsed.astimezone(local_tz).replace(tzinfo=None)
    return parsed


def serialize_event(event):
    shifts = Tables.Shift.query.filter_by(event=event.id).order_by(Tables.Shift.start.asc()).all()
    registrations = Tables.RegisterManager.query.filter_by(eventFK=event.id).order_by(Tables.RegisterManager.id.asc()).all()
    return {
        "id": event.id,
        "uid": str(event.uid),
        "name": event.name,
        "visibility": event.visibility,
        "place": event.place or "",
        "date": local_datetime(event.date),
        "end": local_datetime(event.end),
        "description": event.description or "",
        "poster_url": url_for("get_image", filename=str(event.uid)),
        "task_count": Tables.Task.query.filter_by(eventFK=event.id).count(),
        "shifts": [
            {
                "id": shift.id,
                "type": shift.type or "",
                "start": local_datetime(shift.start),
                "end": local_datetime(shift.end),
                "participants": len(shift.duty_rel),
                "assigned_users": [
                    serialize_assigned_user(duty.user_obj)
                    for duty in shift.duty_rel
                    if duty.user_obj
                ],
            }
            for shift in shifts
        ],
        "registration_options": [
            {
                "id": manager.id,
                "name": manager.name or "",
                "visibility": manager.visibility,
                "accept": manager.accept,
                "deny": manager.deny,
                "start": local_datetime(manager.start),
                "end": local_datetime(manager.end),
                "price": manager.price,
                "participants": [
                    serialize_assigned_user(registration.user_obj)
                    for registration in manager.registration_rel
                    if registration.user_obj and not registration.cancelled_at
                ],
            }
            for manager in registrations
        ],
    }


def event_fields(payload):
    errors = {}
    name = str(payload.get("name") or "").strip()
    visibility = payload.get("visibility")
    place = str(payload.get("place") or "").strip()
    description = str(payload.get("description") or "").strip()
    date = parse_datetime(payload.get("date"), "date", errors, required=True)
    end = parse_datetime(payload.get("end"), "end", errors)

    if not name:
        errors["name"] = "Der Eventname wird benötigt."
    elif len(name) > 50:
        errors["name"] = "Der Eventname darf höchstens 50 Zeichen lang sein."
    if visibility not in {"public", "student", "member", "private"}:
        errors["visibility"] = "Bitte wähle eine gültige Sichtbarkeit."
    if len(place) > 50:
        errors["place"] = "Der Ort darf höchstens 50 Zeichen lang sein."
    if len(description) > 300:
        errors["description"] = "Die Beschreibung darf höchstens 300 Zeichen lang sein."
    if date and end and end <= date:
        errors["end"] = "Das Eventende muss nach dem Start liegen."

    return {
        "name": name,
        "visibility": visibility,
        "place": place,
        "description": description,
        "date": date,
        "end": end,
    }, errors


def shift_fields(payload):
    errors = {}
    shift_type = str(payload.get("type") or "").strip()
    start = parse_datetime(payload.get("start"), "start", errors)
    end = parse_datetime(payload.get("end"), "end", errors)
    if not shift_type:
        errors["type"] = "Die Bezeichnung wird benötigt."
    elif len(shift_type) > 20:
        errors["type"] = "Die Bezeichnung darf höchstens 20 Zeichen lang sein."
    if start and end and end <= start:
        errors["end"] = "Das Schichtende muss nach dem Start liegen."
    return {"type": shift_type, "start": start, "end": end}, errors


def registration_fields(payload):
    errors = {}
    name = str(payload.get("name") or "").strip()
    visibility = payload.get("visibility")
    accept = payload.get("accept")
    deny = payload.get("deny")
    start = parse_datetime(payload.get("start"), "start", errors)
    end = parse_datetime(payload.get("end"), "end", errors)
    raw_price = payload.get("price")
    try:
        price = Decimal(str(raw_price)) if raw_price not in (None, "") else None
        if price is not None and (not price.is_finite() or price < 0):
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        errors["price"] = "Bitte gib einen gültigen, nicht negativen Preis an."
        price = None

    if not name:
        errors["name"] = "Der Name der Anmeldung wird benötigt."
    elif len(name) > 30:
        errors["name"] = "Der Name darf höchstens 30 Zeichen lang sein."
    if visibility not in {"public", "student", "member", "private"}:
        errors["visibility"] = "Bitte wähle eine gültige Sichtbarkeit."
    if accept not in {"geöffnet", "Zeitraum", "geschlossen"}:
        errors["accept"] = "Bitte wähle einen gültigen Anmeldemodus."
    if deny not in {"erlaubt", "verboten"}:
        errors["deny"] = "Bitte wähle einen gültigen Abmeldemodus."
    if accept == "Zeitraum" and not end:
        errors["end"] = "Für einen Anmeldezeitraum wird ein Enddatum benötigt."
    if start and end and end <= start:
        errors["end"] = "Das Anmeldeende muss nach dem Start liegen."

    return {
        "name": name,
        "visibility": visibility,
        "accept": accept,
        "deny": deny,
        "start": start,
        "end": end,
        "price": price,
    }, errors


def task_fields(payload):
    errors = {}
    name = str(payload.get("name") or "").strip()
    description = str(payload.get("description") or "").strip()
    status = payload.get("status")
    priority = payload.get("priority")
    visibility = payload.get("visibility")
    deadline = parse_datetime(payload.get("deadline"), "deadline", errors)
    timeframe_start = parse_datetime(payload.get("timeframe_start"), "timeframe_start", errors)
    timeframe_end = parse_datetime(payload.get("timeframe_end"), "timeframe_end", errors)

    if not name:
        errors["name"] = "Der Name der Vorbereitung wird benötigt."
    elif len(name) > 50:
        errors["name"] = "Der Name der Vorbereitung darf höchstens 50 Zeichen lang sein."
    if len(description) > 500:
        errors["description"] = "Die Beschreibung darf höchstens 500 Zeichen lang sein."
    if status not in {"TakeOverTask", "OnHold", "InProgress", "Ready", "Finished"}:
        errors["status"] = "Bitte wähle einen gültigen Vorbereitungsstatus."
    if priority not in {"niedrig", "mittel", "hoch"}:
        errors["priority"] = "Bitte wähle eine gültige Priorität."
    if visibility not in {"public", "student", "member", "private"}:
        errors["visibility"] = "Bitte wähle eine gültige Sichtbarkeit."
    if timeframe_start and timeframe_end and timeframe_end <= timeframe_start:
        errors["timeframe_end"] = "Das Umsetzungsende muss nach dem Start liegen."

    return {
        "name": name,
        "description": description,
        "status": status,
        "priority": priority,
        "visibility": visibility,
        "deadline": deadline,
        "timeframe_start": timeframe_start,
        "timeframe_end": timeframe_end,
    }, errors


def task_help_permission(visibility):
    if visibility == "public":
        return "events.public"
    return {
        "student": "task.help.student",
        "member": "task.help.member",
        "private": "task.help.private",
    }.get(visibility)


def assignment_actor_denied(kind, event_id):
    if kind == "registration":
        denied = access_denied("events.newRM")
        if denied:
            return denied
        if not hasPermissions(f"/api/events/event/{event_id}/newRM"):
            return json_response({"error": "permission_denied"}, 403)
    elif kind == "shift":
        return access_denied(f"/api/events/event/addshift/{event_id}")
    elif kind == "task":
        return access_denied("task.edit")
    else:
        return json_response({"error": "invalid_assignment_type"}, 400)
    return None


def assignment_target(kind, event_id, target_id):
    if kind == "registration":
        return Tables.RegisterManager.query.filter_by(id=target_id, eventFK=event_id).first()
    if kind == "shift":
        return Tables.Shift.query.filter_by(id=target_id, event=event_id).first()
    if kind == "task":
        return Tables.Task.query.filter_by(id=target_id, eventFK=event_id).first()
    return None


def user_is_eligible_for_assignment(user, event, kind, target):
    return can_assign_to(user_permission_grants(user), event.visibility, kind, getattr(target, "visibility", None))


def assigned_user_ids(kind, target):
    if kind == "registration":
        registrations = Tables.Registration.query.filter_by(rmFK=target.id).filter(
            Tables.Registration.cancelled_at.is_(None)
        ).all()
        return {registration.userFK for registration in registrations}
    if kind == "shift":
        return {duty.user for duty in Tables.Duty.query.filter_by(shift=target.id).all()}
    return {assistant.userFK for assistant in Tables.Assistant.query.filter_by(taskFK=target.id).all()}


@app.route(
    "/api/v1/manage/events/<int:event_id>/assignments/<kind>/<int:target_id>/users",
    methods=["GET"],
)
def api_search_assignable_event_users(event_id, kind, target_id):
    denied = assignment_actor_denied(kind, event_id)
    if denied:
        return denied
    event = Tables.Event.query.filter_by(id=event_id).first()
    target = assignment_target(kind, event_id, target_id)
    if not event or not target:
        return json_response({"error": "Assignment target not found"}, 404)
    query = str(request.args.get("q") or "").strip()
    if len(query) < 2:
        return json_response({"users": []})
    pattern = f"%{query}%"
    users = (
        Tables.User.query.filter(or_(
            Tables.User.username.ilike(pattern),
            Tables.User.surname.ilike(pattern),
            Tables.User.lastname.ilike(pattern),
        ))
        .order_by(Tables.User.username.asc())
        .limit(50)
        .all()
    )
    current_ids = assigned_user_ids(kind, target)
    eligible_users = [
        serialize_assigned_user(user)
        for user in users
        if user.id not in current_ids and user_is_eligible_for_assignment(user, event, kind, target)
    ]
    return json_response({"users": eligible_users})


@app.route(
    "/api/v1/manage/events/<int:event_id>/assignments/<kind>/<int:target_id>",
    methods=["POST", "DELETE"],
)
def api_manage_event_assignment(event_id, kind, target_id):
    denied = assignment_actor_denied(kind, event_id)
    if denied:
        return denied
    event = Tables.Event.query.filter_by(id=event_id).first()
    target = assignment_target(kind, event_id, target_id)
    if not event or not target:
        return json_response({"error": "Assignment target not found"}, 404)

    payload = request.get_json(silent=True) or {}
    try:
        user_uid = UUID(str(payload.get("user_uid") or ""))
    except (TypeError, ValueError, AttributeError):
        return json_response({"error": "Bitte wähle ein gültiges Benutzerkonto."}, 400)
    user = Tables.User.query.filter_by(uid=user_uid).first()
    if not user:
        return json_response({"error": "Benutzerkonto nicht gefunden."}, 404)

    if request.method == "POST":
        if not user_is_eligible_for_assignment(user, event, kind, target):
            return json_response({"error": "Das Benutzerkonto hat nicht die erforderliche Berechtigung für diese Anmeldung."}, 403)
        if kind == "registration":
            duplicate = Tables.Registration.query.filter_by(
                rmFK=target.id,
                userFK=user.id,
                cancelled_at=None,
            ).first()
            if duplicate:
                return json_response({"error": "Dieses Konto ist bereits angemeldet."}, 409)
            price = Decimal(str(target.price)) if target.price is not None else Decimal("0")
            is_free = price <= 0
            registration = Tables.Registration(
                rmFK=target.id,
                userFK=user.id,
                timestamp=datetime.now(timezone.utc),
                price=price,
                paid=is_free,
                valid=False,
                created_by=current_user.id,
            )
            db.session.add(registration)
            db.session.flush()
            create_event_ticket_charge(registration, current_user.id)
        elif kind == "shift":
            duplicate = Tables.Duty.query.filter_by(shift=target.id, user=user.id).first()
            if duplicate:
                return json_response({"error": "Dieses Konto ist bereits für die Helferschicht eingetragen."}, 409)
            db.session.add(Tables.Duty(
                shift=target.id,
                user=user.id,
                joined_timestamp=datetime.now(),
                assigned_by=current_user.id,
            ))
        else:
            duplicate = Tables.Assistant.query.filter_by(taskFK=target.id, userFK=user.id).first()
            if duplicate:
                return json_response({"error": "Dieses Konto ist bereits der Vorbereitung zugeordnet."}, 409)
            db.session.add(Tables.Assistant(
                taskFK=target.id,
                userFK=user.id,
                joined_timestamp=datetime.now(),
                assigned_by=current_user.id,
            ))
            if target.status == "TakeOverTask":
                target.status = "InProgress"
        db.session.commit()
        return json_response({"success": True})

    if kind == "registration":
        registration = Tables.Registration.query.filter_by(
            rmFK=target.id,
            userFK=user.id,
            cancelled_at=None,
        ).first()
        reason = str(payload.get("reason") or "").strip()
        if not reason:
            return json_response({"error": "Bitte gib einen Grund für die Abmeldung an."}, 400)
        if not registration:
            return json_response({"error": "Aktive Anmeldung nicht gefunden."}, 404)
        cancel_registration(registration, current_user.id, reason)
    elif kind == "shift":
        duty = Tables.Duty.query.filter_by(shift=target.id, user=user.id).first()
        if not duty:
            return json_response({"error": "Zuordnung nicht gefunden."}, 404)
        db.session.delete(duty)
    else:
        assistant = Tables.Assistant.query.filter_by(taskFK=target.id, userFK=user.id).first()
        if not assistant:
            return json_response({"error": "Zuordnung nicht gefunden."}, 404)
        db.session.delete(assistant)
        db.session.flush()
        if target.status == "InProgress" and Tables.Assistant.query.filter_by(taskFK=target.id).count() == 0:
            target.status = "TakeOverTask"
    db.session.commit()
    return json_response({"success": True})


def serialize_task(task, user_id=None, can_manage=False, include_helpers=False):
    assistants = Tables.Assistant.query.filter_by(taskFK=task.id).all()
    assigned = any(assistant.userFK == user_id for assistant in assistants) if user_id else False
    can_help = bool(user_id and task_help_permission(task.visibility) and hasPermissions(task_help_permission(task.visibility)))
    is_open = task.status in {"TakeOverTask", "InProgress"}
    return {
        "id": task.id,
        "event_id": task.eventFK,
        "name": task.name,
        "description": task.description or "",
        "status": task.status,
        "priority": task.priority,
        "visibility": task.visibility,
        "deadline": local_datetime(task.deadline),
        "timeframe_start": local_datetime(task.timeframe_start),
        "timeframe_end": local_datetime(task.timeframe_end),
        "helper_count": len(assistants),
        "helpers": [
            serialize_assigned_user(assistant.user_obj)
            for assistant in assistants
            if include_helpers and assistant.user_obj
        ],
        "assigned_to_me": assigned,
        "can_join": can_help and is_open and not assigned,
        "can_leave": can_help and assigned,
        "can_manage": can_manage,
    }


def visible_event(event_id):
    return next((event for event in getAllEvents() if event["id"] == event_id), None)


def serialize_admin_user(user):
    return {
        "id": user.id,
        "uid": str(user.uid),
        "username": user.username,
        "role": user.role,
        "surname": user.surname or "",
        "lastname": user.lastname or "",
        "email": user.email or "",
        "email_confirmed": user.email_confirmed,
        "hs_email": user.hs_email or "",
        "hs_email_confirmed": user.hs_email_confirmed,
        "street": user.street or "",
        "street_no": user.street_no or "",
        "city": user.city or "",
        "postalcode": user.postalcode or "",
        "register_date": user.register_date,
        "last_login": user.last_login,
        "last_updated": user.last_updated,
    }


@app.route("/api/v1/manage/users", methods=["GET"])
def api_manage_users():
    denied = access_denied("adminpanel.user.get")
    if denied:
        return denied
    roles = [role.name for role in Tables.Role.query.order_by(Tables.Role.name.asc()).all()]
    users = Tables.User.query.order_by(Tables.User.last_login.desc()).all()
    return json_response({
        "roles": roles,
        "users": [serialize_admin_user(user) for user in users],
    })


@app.route("/api/v1/manage/users/<user_uid>", methods=["PUT", "DELETE"])
def api_manage_user(user_uid: str):
    permission = "adminpanel.user.update" if request.method == "PUT" else "adminpanel.user.delete"
    denied = access_denied(permission)
    if denied:
        return denied
    user = Tables.User.query.filter_by(uid=user_uid).first()
    if not user:
        return json_response({"error": "User not found"}, 404)

    if request.method == "DELETE":
        if user.id == current_user.id:
            return json_response({"error": "Du kannst dein eigenes Konto nicht über die Nutzerverwaltung löschen."}, 409)
        if Tables.Membership.query.filter_by(user_id=user.id).first():
            return json_response({"error": "Ein Konto mit Finanzhistorie kann nicht gelöscht werden. Beende stattdessen die Mitgliedschaft."}, 409)
        if Tables.Registration.query.filter_by(userFK=user.id).first():
            return json_response({"error": "Ein Konto mit Event-Ticket-Historie kann nicht gelöscht werden."}, 409)
        db.session.delete(user)
        db.session.commit()
        return json_response({"success": True})

    form = Forms.AdminChangeData()
    roles = Tables.Role.query.all()
    form.role.choices = [(role.name, role.name) for role in roles]
    if not form.validate_on_submit():
        return json_response({"success": False, "errors": form.errors}, 400)

    username = form.username.data.lower()
    if not username.isalnum():
        return json_response({"success": False, "errors": {"username": ["Der Benutzername darf nur Buchstaben und Zahlen enthalten."]}}, 400)
    if username != user.username and Tables.User.query.filter_by(username=username).first():
        return json_response({"success": False, "errors": {"username": ["Dieser Benutzername ist bereits vergeben."]}}, 409)

    email_changed = user.email != form.email.data
    hs_email_changed = user.hs_email != form.hs_email.data
    role_changed = user.role != form.role.data
    user.username = username
    user.surname = form.surname.data
    user.lastname = form.lastname.data
    user.email = form.email.data
    user.hs_email = form.hs_email.data
    user.street = form.street.data
    user.street_no = form.street_no.data
    user.city = form.city.data
    user.postalcode = form.postalcode.data
    user.role = form.role.data
    user.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if email_changed:
        user.email_confirmed = False
        user.email_cooldown = datetime.min
    if hs_email_changed:
        user.hs_email_confirmed = False
        user.hs_email_cooldown = datetime.min
    if form.password.data:
        user.password = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
    if role_changed:
        pending_role_request = Tables.UserRoleRequest.query.filter_by(user_id=user.id, status="pending").first()
        if pending_role_request:
            pending_role_request.status = "withdrawn"
            pending_role_request.reviewed_by = current_user.id
            pending_role_request.reviewed_at = datetime.now()
            pending_role_request.review_note = "Von der Verwaltung direkt geändert."

    db.session.commit()
    verification_warning = False
    if form.verify_mail.data:
        try:
            verify_email(user)
        except Exception:
            verification_warning = True
            app.logger.info("%s failed to verify email from admin panel", user.username)
    return json_response({
        "success": True,
        "user": serialize_admin_user(user),
        "verification_warning": verification_warning,
    })


def serialize_user_role_request(role_request):
    user = role_request.user_obj
    return {
        "id": role_request.id,
        "uid": str(role_request.uid),
        "user_uid": str(user.uid) if user else None,
        "username": user.username if user else "Gelöschtes Konto",
        "surname": (user.surname or "") if user else "",
        "lastname": (user.lastname or "") if user else "",
        "current_role": role_request.from_role,
        "requested_role": role_request.requested_role,
        "request_note": role_request.request_note,
        "status": role_request.status,
        "submitted_at": local_datetime(role_request.submitted_at),
        "reviewed_at": local_datetime(role_request.reviewed_at),
        "review_note": role_request.review_note or "",
    }


@app.route("/api/v1/me/role-requests", methods=["GET", "POST"])
def api_my_role_requests():
    if not current_user.is_authenticated:
        return json_response({"error": "authentication_required"}, 401)
    if request.method == "GET":
        pending = Tables.UserRoleRequest.query.filter_by(user_id=current_user.id, status="pending").order_by(
            Tables.UserRoleRequest.submitted_at.desc()
        ).first()
        return json_response({
            "requestable_roles": [
                role.name for role in Tables.Role.query.filter_by(requestable_on_change=True).order_by(Tables.Role.name.asc()).all()
                if role.name != current_user.role
            ],
            "pending_request": serialize_user_role_request(pending) if pending else None,
        })

    payload = request.get_json(silent=True) or {}
    requested_role_name = str(payload.get("requested_role") or "")
    note = str(payload.get("note") or "").strip()
    if not current_user.role:
        return json_response({"error": "Für dein Konto ist keine aktuelle Rolle gesetzt."}, 409)
    requested_role = Tables.Role.query.filter_by(name=requested_role_name, requestable_on_change=True).first()
    if not requested_role:
        return json_response({"success": False, "errors": {"requested_role": "Diese Rolle kann nicht beantragt werden."}}, 400)
    if requested_role.name == current_user.role:
        return json_response({"success": False, "errors": {"requested_role": "Du hast diese Rolle bereits."}}, 400)
    if not note:
        return json_response({"success": False, "errors": {"note": "Bitte erläutere kurz deinen Rollenwunsch."}}, 400)
    pending = Tables.UserRoleRequest.query.filter_by(user_id=current_user.id, status="pending").first()
    if pending:
        return json_response({"error": "Du hast bereits einen offenen Rollenänderungsantrag."}, 409)

    role_request = Tables.UserRoleRequest(
        user_id=current_user.id,
        from_role=current_user.role,
        requested_role=requested_role.name,
        request_note=note[:1000],
    )
    db.session.add(role_request)
    db.session.commit()
    return json_response({"success": True, "request": serialize_user_role_request(role_request)}, 201)


@app.route("/api/v1/manage/role-requests", methods=["GET"])
def api_manage_role_requests():
    denied = access_denied("adminpanel.user.update")
    if denied:
        return denied
    requests = Tables.UserRoleRequest.query.filter_by(status="pending").order_by(
        Tables.UserRoleRequest.submitted_at.asc()
    ).all()
    return json_response({"requests": [serialize_user_role_request(role_request) for role_request in requests]})


@app.route("/api/v1/manage/role-requests/<int:request_id>/review", methods=["POST"])
def api_review_role_request(request_id):
    denied = access_denied("adminpanel.user.update")
    if denied:
        return denied
    role_request = Tables.UserRoleRequest.query.filter_by(id=request_id, status="pending").first()
    if not role_request:
        return json_response({"error": "Offenen Rollenänderungsantrag nicht gefunden."}, 404)
    payload = request.get_json(silent=True) or {}
    decision = str(payload.get("decision") or "")
    if decision not in {"approve", "reject"}:
        return json_response({"success": False, "errors": {"decision": "Bitte wähle genehmigen oder ablehnen."}}, 400)
    note = str(payload.get("note") or "").strip()
    if decision == "reject" and not note:
        return json_response({"success": False, "errors": {"note": "Bitte gib einen kurzen Grund für die Ablehnung an."}}, 400)

    user = role_request.user_obj
    # Keep already-submitted requests reviewable when the self-service policy changes.
    target_role = Tables.Role.query.filter_by(name=role_request.requested_role).first()
    if not user or user.role != role_request.from_role:
        return json_response({"error": "Die aktuelle Benutzerrolle hat sich seit dem Antrag geändert."}, 409)
    if decision == "approve":
        if not target_role:
            return json_response({"error": "Die beantragte Rolle ist nicht mehr freigegeben."}, 409)
        user.role = target_role.name
        user.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    role_request.status = "approved" if decision == "approve" else "rejected"
    role_request.reviewed_by = current_user.id
    role_request.reviewed_at = datetime.now()
    role_request.review_note = note[:1000] or None
    db.session.commit()
    return json_response({"success": True, "request": serialize_user_role_request(role_request)})


@app.route("/api/v1/manage/contacts", methods=["GET"])
def api_manage_contacts():
    denied = access_denied("adminpanel.show")
    if denied:
        return denied
    contacts = Tables.Contact.query.order_by(Tables.Contact.creation.desc()).all()
    return json_response({"contacts": [contact.getDict() for contact in contacts]})


@app.route("/api/v1/manage/contacts/<contact_uid>", methods=["PUT", "DELETE"])
def api_manage_contact(contact_uid: str):
    denied = access_denied("adminpanel.show" if request.method == "PUT" else "adminpanel.delete.contact")
    if denied:
        return denied
    contact = Tables.Contact.query.filter_by(uid=contact_uid).first()
    if not contact:
        return json_response({"error": "Contact request not found"}, 404)
    if request.method == "PUT":
        payload = request.get_json(silent=True) or {}
        handled = payload.get("handled")
        if not isinstance(handled, bool):
            return json_response({"error": "Ungültiger Bearbeitungsstatus."}, 400)
        contact.handled_at = datetime.now() if handled else None
        contact.handled_by = current_user.id if handled else None
        db.session.commit()
        return json_response({"success": True, "contact": contact.getDict()})
    db.session.delete(contact)
    db.session.commit()
    return json_response({"success": True})


@app.route("/api/v1/manage/events", methods=["GET", "POST"])
def api_manage_events():
    if request.method == "GET":
        denied = access_denied()
        if denied:
            return denied
        if not hasPermissions("eventmanager.show") and not hasPermissions("events.create"):
            return json_response({"error": "permission_denied"}, 403)
        events = Tables.Event.query.order_by(Tables.Event.date.desc().nullslast()).all()
        return json_response({"events": [serialize_event(event) for event in events]})

    denied = access_denied("events.create")
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    fields, errors = event_fields(payload)
    if errors:
        return json_response({"success": False, "errors": errors}, 400)

    event = Tables.Event(
        author=current_user.id,
        created=datetime.now(),
        **fields,
    )
    db.session.add(event)
    db.session.commit()
    return json_response({"success": True, "event": serialize_event(event)}, 201)


@app.route("/api/v1/manage/tasks", methods=["GET"])
def api_manage_tasks():
    """Return a cross-event task overview without exposing user registration data."""
    denied = access_denied("task.get")
    if denied:
        return denied
    task_rows = (
        db.session.query(Tables.Task, Tables.Event)
        .join(Tables.Event, Tables.Task.eventFK == Tables.Event.id)
        .order_by(Tables.Task.deadline.asc().nullslast(), Tables.Task.id.asc())
        .all()
    )
    return json_response({
        "tasks": [
            {
                "id": task.id,
                "event_id": event.id,
                "event_name": event.name,
                "name": task.name,
                "priority": task.priority or "",
                "status": task.status or "",
                "visibility": task.visibility or "",
                "deadline": local_datetime(task.deadline),
                "helper_count": len(task.assistant_obj),
            }
            for task, event in task_rows
        ]
    })


@app.route("/api/v1/manage/events/<int:event_id>", methods=["PUT", "DELETE"])
def api_manage_event(event_id: int):
    if request.method == "PUT":
        denied = access_denied(f"/api/events/event/update/{event_id}")
    else:
        denied = access_denied("adminpanel.event.delete")
    if denied:
        return denied

    event = Tables.Event.query.filter_by(id=event_id).first()
    if not event:
        return json_response({"error": "Event not found"}, 404)
    if request.method == "DELETE":
        registration_count = (
            db.session.query(Tables.Registration.id)
            .join(Tables.RegisterManager, Tables.Registration.rmFK == Tables.RegisterManager.id)
            .filter(Tables.RegisterManager.eventFK == event.id)
            .count()
        )
        if registration_count:
            return json_response({"error": "Events mit Ticketregistrierungen können nicht gelöscht werden. Schließe das Event stattdessen."}, 409)
        task_ids = db.session.query(Tables.Task.id).filter_by(eventFK=event.id)
        Tables.Assistant.query.filter(Tables.Assistant.taskFK.in_(task_ids)).delete(synchronize_session=False)
        db.session.delete(event)
        db.session.commit()
        return json_response({"success": True})

    payload = request.get_json(silent=True) or {}
    fields, errors = event_fields(payload)
    if errors:
        return json_response({"success": False, "errors": errors}, 400)

    previous_date = event.date
    if previous_date and fields["date"] and previous_date != fields["date"] and payload.get("move_shifts", True):
        difference = fields["date"] - previous_date
        shift_event_schedule(
            event,
            difference,
            shifts=Tables.Shift.query.filter_by(event=event.id).all(),
            registration_windows=Tables.RegisterManager.query.filter_by(eventFK=event.id).all(),
            tasks=Tables.Task.query.filter_by(eventFK=event.id).all(),
        )
    for field, value in fields.items():
        setattr(event, field, value)
    db.session.commit()
    return json_response({"success": True, "event": serialize_event(event)})


@app.route("/api/v1/manage/events/<int:event_id>/shifts", methods=["POST"])
def api_manage_event_shifts(event_id: int):
    denied = access_denied(f"/api/events/event/addshift/{event_id}")
    if denied:
        return denied
    event = Tables.Event.query.filter_by(id=event_id).first()
    if not event:
        return json_response({"error": "Event not found"}, 404)
    fields, errors = shift_fields(request.get_json(silent=True) or {})
    if errors:
        return json_response({"success": False, "errors": errors}, 400)
    shift = Tables.Shift(event=event.id, **fields)
    db.session.add(shift)
    db.session.commit()
    return json_response({"success": True, "event": serialize_event(event)}, 201)


@app.route("/api/v1/manage/events/<int:event_id>/shifts/<int:shift_id>", methods=["PUT", "DELETE"])
def api_manage_event_shift(event_id: int, shift_id: int):
    permission = (
        f"/api/events/event/addshift/{event_id}"
        if request.method == "PUT"
        else f"/api/events/event/delshift/{shift_id}"
    )
    denied = access_denied(permission)
    if denied:
        return denied
    shift = Tables.Shift.query.filter_by(id=shift_id, event=event_id).first()
    if not shift:
        return json_response({"error": "Shift not found"}, 404)
    if request.method == "PUT":
        fields, errors = shift_fields(request.get_json(silent=True) or {})
        if errors:
            return json_response({"success": False, "errors": errors}, 400)
        for field, value in fields.items():
            setattr(shift, field, value)
        db.session.commit()
        event = Tables.Event.query.filter_by(id=event_id).first()
        return json_response({"success": True, "event": serialize_event(event)})
    db.session.delete(shift)
    db.session.commit()
    event = Tables.Event.query.filter_by(id=event_id).first()
    return json_response({"success": True, "event": serialize_event(event)})


@app.route("/api/v1/manage/events/<int:event_id>/registrations", methods=["POST"])
def api_manage_event_registrations(event_id: int):
    denied = access_denied("events.newRM")
    if denied:
        return denied
    if not hasPermissions(f"/api/events/event/{event_id}/newRM"):
        return json_response({"error": "permission_denied"}, 403)
    event = Tables.Event.query.filter_by(id=event_id).first()
    if not event:
        return json_response({"error": "Event not found"}, 404)
    fields, errors = registration_fields(request.get_json(silent=True) or {})
    if errors:
        return json_response({"success": False, "errors": errors}, 400)
    manager = Tables.RegisterManager(eventFK=event.id, **fields)
    db.session.add(manager)
    db.session.commit()
    return json_response({"success": True, "event": serialize_event(event)}, 201)


@app.route("/api/v1/manage/events/<int:event_id>/registrations/<int:manager_id>", methods=["PUT", "DELETE"])
def api_manage_event_registration(event_id: int, manager_id: int):
    denied = access_denied("events.rm.update" if request.method == "PUT" else "events.rm.delete")
    if denied:
        return denied
    dynamic_permission = (
        f"/api/events/event/{event_id}/updateRM/{manager_id}"
        if request.method == "PUT"
        else f"/api/events/event/{event_id}/deleteRM/{manager_id}"
    )
    if not hasPermissions(dynamic_permission):
        return json_response({"error": "permission_denied"}, 403)
    manager = Tables.RegisterManager.query.filter_by(id=manager_id, eventFK=event_id).first()
    if not manager:
        return json_response({"error": "Registration option not found"}, 404)
    if request.method == "PUT":
        fields, errors = registration_fields(request.get_json(silent=True) or {})
        if errors:
            return json_response({"success": False, "errors": errors}, 400)
        for field, value in fields.items():
            setattr(manager, field, value)
        db.session.commit()
        event = Tables.Event.query.filter_by(id=event_id).first()
        return json_response({"success": True, "event": serialize_event(event)})
    if Tables.Registration.query.filter_by(rmFK=manager.id).count():
        return json_response({"error": "Anmeldemöglichkeiten mit Registrierungshistorie können nicht gelöscht werden. Schließe sie stattdessen."}, 409)
    db.session.delete(manager)
    db.session.commit()
    event = Tables.Event.query.filter_by(id=event_id).first()
    return json_response({"success": True, "event": serialize_event(event)})


@app.route("/api/v1/manage/events/<int:event_id>/tasks", methods=["GET", "POST"])
def api_manage_event_tasks(event_id: int):
    if request.method == "GET":
        denied = access_denied("task.get")
    else:
        denied = access_denied("task.new")
    if denied:
        return denied

    event = Tables.Event.query.filter_by(id=event_id).first()
    if not event:
        return json_response({"error": "Event not found"}, 404)

    if request.method == "GET":
        tasks = Tables.Task.query.filter_by(eventFK=event_id).order_by(Tables.Task.deadline.asc().nullslast()).all()
        return json_response({
            "event": {
                "id": event.id,
                "name": event.name,
                "date": local_datetime(event.date),
                "place": event.place,
            },
            "tasks": [
                serialize_task(task, current_user.id, can_manage=True, include_helpers=hasPermissions("task.edit"))
                for task in tasks
            ],
            "can_assign_helpers": hasPermissions("task.edit"),
        })

    fields, errors = task_fields(request.get_json(silent=True) or {})
    if errors:
        return json_response({"success": False, "errors": errors}, 400)
    if fields["deadline"] is None:
        fields["deadline"] = event.date

    task = Tables.Task(
        eventFK=event.id,
        authorFK=current_user.id,
        created=datetime.now(),
        **fields,
    )
    db.session.add(task)
    db.session.commit()
    return json_response({
        "success": True,
        "task": serialize_task(task, current_user.id, can_manage=True, include_helpers=hasPermissions("task.edit")),
    }, 201)


@app.route("/api/v1/manage/events/<int:event_id>/tasks/<int:task_id>", methods=["PUT", "DELETE"])
def api_manage_event_task(event_id: int, task_id: int):
    denied = access_denied("task.edit" if request.method == "PUT" else "task.delete")
    if denied:
        return denied
    task = Tables.Task.query.filter_by(id=task_id, eventFK=event_id).first()
    if not task:
        return json_response({"error": "Task not found"}, 404)

    if request.method == "DELETE":
        Tables.Assistant.query.filter_by(taskFK=task.id).delete(synchronize_session=False)
        db.session.delete(task)
        db.session.commit()
        return json_response({"success": True})

    fields, errors = task_fields(request.get_json(silent=True) or {})
    if errors:
        return json_response({"success": False, "errors": errors}, 400)
    for field, value in fields.items():
        setattr(task, field, value)
    db.session.commit()
    return json_response({
        "success": True,
        "task": serialize_task(task, current_user.id, can_manage=True, include_helpers=hasPermissions("task.edit")),
    })


@app.route("/api/v1/events/<int:event_id>/tasks", methods=["GET"])
def api_event_tasks(event_id: int):
    event = visible_event(event_id)
    if not event:
        return json_response({"error": "Event not found"}, 404)
    event_record = Tables.Event.query.filter_by(id=event_id).first()
    all_tasks = Tables.Task.query.filter_by(eventFK=event_id).order_by(Tables.Task.deadline.asc().nullslast()).all()
    visible_tasks = [
        task for task in all_tasks
        if task.visibility == "public"
        or (task_help_permission(task.visibility) and hasPermissions(task_help_permission(task.visibility)))
    ]
    can_manage = current_user.is_authenticated and (
        hasPermissions("task.new") or hasPermissions("task.edit")
    )
    return json_response({
        "event": {
            "id": event_record.id,
            "name": event_record.name,
            "date": local_datetime(event_record.date),
            "place": event_record.place,
        },
        "tasks": [
            serialize_task(
                task,
                current_user.id if current_user.is_authenticated else None,
                can_manage,
                include_helpers=current_user.is_authenticated and hasPermissions("task.edit"),
            )
            for task in visible_tasks
        ],
        "can_manage": can_manage,
    })


def task_action(task_id: int, joining: bool):
    if not current_user.is_authenticated:
        return json_response({"error": "authentication_required"}, 401)
    task = Tables.Task.query.filter_by(id=task_id).first()
    if not task or not visible_event(task.eventFK):
        return json_response({"error": "Task not found"}, 404)
    required_permission = task_help_permission(task.visibility)
    if not required_permission or not hasPermissions(required_permission):
        return json_response({"error": "permission_denied"}, 403)

    assistant = Tables.Assistant.query.filter_by(taskFK=task.id, userFK=current_user.id).first()
    if joining:
        if task.status not in {"TakeOverTask", "InProgress"}:
            return json_response({"error": "Diese Vorbereitung kann aktuell nicht übernommen werden."}, 409)
        if not assistant:
            db.session.add(Tables.Assistant(
                userFK=current_user.id,
                taskFK=task.id,
                joined_timestamp=datetime.now(),
                assigned_by=current_user.id,
            ))
        if task.status == "TakeOverTask":
            task.status = "InProgress"
    else:
        if not assistant:
            return json_response({"error": "Du bist dieser Vorbereitung nicht zugeordnet."}, 409)
        db.session.delete(assistant)
        db.session.flush()
        remaining = Tables.Assistant.query.filter_by(taskFK=task.id).count()
        if remaining == 0 and task.status == "InProgress":
            task.status = "TakeOverTask"

    db.session.commit()
    return json_response({"success": True, "task": serialize_task(task, current_user.id)})


@app.route("/api/v1/tasks/<int:task_id>/join", methods=["POST"])
def api_join_task(task_id: int):
    return task_action(task_id, joining=True)


@app.route("/api/v1/tasks/<int:task_id>/leave", methods=["POST"])
def api_leave_task(task_id: int):
    return task_action(task_id, joining=False)
