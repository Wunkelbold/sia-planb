from globals import *
from flask import make_response, Response, flash, render_template, request, send_from_directory, url_for, redirect, jsonify, get_flashed_messages, send_file
from flask_login import login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_sqlalchemy import SQLAlchemy
from http import HTTPStatus
import os
from datetime import datetime, timezone
from functools import wraps
import json
from io import BytesIO
from uuid import UUID
from sqlalchemy import func
from itsdangerous import BadSignature, SignatureExpired

#-----FILES-----
from database import Tables, init_database, init_roles, init_default_role
from forms import Forms
from permissions import *
from Sections.EventPoster import event_poster_mimetype, find_event_poster

#-----Load Sections-----

import Sections.EventHandler as _
from Sections.EventHandler import getAllEvents
import Sections.ManagementApi as _
import Sections.FinanceApi as _
import Sections.FinanceMailApi as _
import Sections.FinanceDemoData as _
import Sections.DrinkMenuApi as _
import Sections.UserManager as _
import Sections.ContactManager as _
import Sections.RegistrationHandler as _
import Sections.TaskManager as _
from Sections.EmailHandler import *

csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Tables.User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for('login'))

def format_datetime_hr(dt):
    local_tz = ZoneInfo("Europe/Berlin")
    locale.setlocale(locale.LC_ALL, 'de_DE.utf8')
    return dt.replace(tzinfo=local_tz).strftime('%a, %d/%m/%y %H:%M') if dt else None




#-------LOGIN-ROUTES--------
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = Forms.RegisterForm()
    public_roles = Tables.Role.query.filter_by(selectable_on_register="yes").all()
    form.role.choices = [(role.name, role.name) for role in public_roles] #Nur manche Rollen sollen zur Auswahl stehen und choices hat dieses syntax
    if request.method == 'POST':
        c_hash = request.form.get('captcha-hash')
        c_text = request.form.get('captcha-text')
        if SIMPLE_CAPTCHA.verify(c_text, c_hash):
            if form.username.data:
                username = form.username.data.lower()
                existing_user_username = Tables.User.query.filter_by(username=username).first()
                if existing_user_username or not username.isalnum() or form.password.data != form.password_confirm.data:
                    if not username.isalnum():
                        flash('Nur Buchstaben und Zahlen im Benutzernamen', 'error')
                    if existing_user_username:
                        flash('Benutzername bereits vergeben', 'error')
                    #if username in manager.config.get_config("banned_usernames"): #TODO ADD BANNED CHARACTERS
                        #flash('- That username is not allowed. Please choose a different name.', 'error')
                    if form.password.data != form.password_confirm.data:
                        flash('Passwörter stimmen nicht überein', 'error')
                else:
                    if form.validate_on_submit():
                        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
                        if form.role.data in [role.name for role in public_roles]: #ansonsten kann der user "admin" außerhalb der Form pushen und ich ´hab kein bock ein custom form validaotr zu schreiben
                            role = form.role.data
                            if form.role.data == "Student" and form.hs_email.data or form.role.data != "Student" :
                                new_user = Tables.User(
                                    username = username,
                                    password = hashed_password,
                                    register_date = "", 
                                    last_login = "",
                                    surname = form.surname.data,
                                    lastname = form.lastname.data,
                                    email = form.email.data,
                                    hs_email = form.hs_email.data,
                                    street = form.street.data,
                                    street_no = form.street_no.data,
                                    city = form.city.data,
                                    postalcode = form.postalcode.data,
                                    role = role,
                                    permissions = [],
                                    last_updated = ""
                                    )
                                new_user.register_date = now
                                new_user.last_updated = now
                                new_user.last_login = now #TODO ungewöhnlicher Fall aber register != login
                                db.session.add(new_user)
                                db.session.commit()
                                # Generate calendar URL for new user
                                from Sections.EventHandler import ensure_user_calendar_url
                                ensure_user_calendar_url(new_user)
                                login_user(new_user)
                                try:
                                    verify_email(new_user)
                                except:
                                    flash("Der Maildienst hat gerade keine Lust deine Mail zu verifizieren :(")
                                    app.logger.info('%s failed to verify email', new_user.username)
                            else:
                                flash("Als Student musst du deine HS_Mail angeben!")
                                return redirect(url_for('register'))

                            return redirect(url_for('index'))
                        else:
                            flash('Nice Try!', 'error')
                    else:
                        print(form.errors)  # Debugging: Show validation errors
                        flash('Etwas hat nicht gestimmt:', 'error')
        else:
            flash("Das Captcha ist falsch",'error')
    new_captcha_dict = SIMPLE_CAPTCHA.create()
    messages=form.errors
    return render_template('register.html', form=form, messages=messages, captcha=new_captcha_dict)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = Forms.LoginForm()
    if form.username.data:
        username = form.username.data.lower()
        if form.validate_on_submit():
            user = Tables.User.query.filter_by(username=username).first()
            if user:
                if bcrypt.check_password_hash(user.password, form.password.data):
                    login_user(user)
                    current_user.last_login = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    db.session.commit()
                    return redirect(url_for('index'))
                else:
                    flash('Passwort falsch', 'error')
            else:
                flash(f'Benutzer existiert nicht!', 'error')
        else:
                print(form.errors)  # Debugging: Show validation errors
                flash('Form submission failed. Check your input.', 'error')
        #TODO last_login = datetime.now() 
    return render_template('login.html', form=form)

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


#----------ROUTES---------
@app.route("/api/v1/health", methods=["GET"])
def api_health():
    """Minimal health endpoint for the independent static frontend."""
    return jsonify({"status": "ok"})

@app.route("/api/v1/session", methods=["GET"])
def api_session():
    """Expose only the signed-in state needed by the independent frontend."""
    if not current_user.is_authenticated:
        response = jsonify({"authenticated": False, "csrf_token": generate_csrf()})
    else:
        response = jsonify(frontend_session_data())
    response.headers["Cache-Control"] = "private, no-store"
    return response

def frontend_session_data():
    return {
        "authenticated": current_user.is_authenticated,
        "username": current_user.username if current_user.is_authenticated else None,
        "needs_email_confirmation": (
            current_user.is_authenticated
            and bool((current_user.email and not current_user.email_confirmed) or (current_user.hs_email and not current_user.hs_email_confirmed))
        ),
        "can_help": hasPermissions("events.help") if current_user.is_authenticated else False,
        "can_admin_panel": hasPermissions("adminpanel.show") if current_user.is_authenticated else False,
        "can_manage_events": (
            current_user.is_authenticated
            and (hasPermissions("eventmanager.show") or hasPermissions("events.create"))
        ),
        "can_create_events": hasPermissions("events.create") if current_user.is_authenticated else False,
        "can_edit_events": hasPermissions("/api/events/event/update/*") if current_user.is_authenticated else False,
        "can_delete_events": hasPermissions("adminpanel.event.delete") if current_user.is_authenticated else False,
        "can_manage_shifts": hasPermissions("/api/events/event/addshift/*") if current_user.is_authenticated else False,
        "can_manage_registration_options": hasPermissions("events.newRM") if current_user.is_authenticated else False,
        "can_manage_tasks": (
            current_user.is_authenticated
            and (hasPermissions("task.new") or hasPermissions("task.edit") or hasPermissions("task.delete"))
        ),
        "can_scan_tickets": hasPermissions("scanner.show") if current_user.is_authenticated else False,
        "can_manage_users": hasPermissions("adminpanel.user.get") if current_user.is_authenticated else False,
        "can_update_users": hasPermissions("adminpanel.user.update") if current_user.is_authenticated else False,
        "can_delete_users": hasPermissions("adminpanel.user.delete") if current_user.is_authenticated else False,
        "can_manage_contacts": hasPermissions("adminpanel.show") if current_user.is_authenticated else False,
        "can_delete_contacts": hasPermissions("adminpanel.delete.contact") if current_user.is_authenticated else False,
        "can_manage_finances": hasPermissions("finance.manage") if current_user.is_authenticated else False,
        "can_manage_drink_menu": hasPermissions("menu.manage") if current_user.is_authenticated else False,
        "can_use_tally": hasPermissions("finance.tally.use") if current_user.is_authenticated else False,
        "can_validate_tickets": hasPermissions("events.rm.validate") if current_user.is_authenticated else False,
        "can_punch_tickets": hasPermissions("events.rm.punch") if current_user.is_authenticated else False,
        "can_manage_ticket_payment": (
            hasPermissions("events.rm.paid") or hasPermissions("events.rm.unpaid")
        ) if current_user.is_authenticated else False,
        "csrf_token": generate_csrf(),
    }

@app.route("/api/v1/auth/login", methods=["POST"])
def api_auth_login():
    form = Forms.LoginForm()
    if not form.validate_on_submit():
        return jsonify({"success": False, "errors": form.errors}), 400

    username = form.username.data.lower()
    user = Tables.User.query.filter_by(username=username).first()
    if not user or not user.password or not bcrypt.check_password_hash(user.password, form.password.data):
        return jsonify({"success": False, "error": "Benutzername oder Passwort ist falsch."}), 401

    login_user(user)
    user.last_login = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.session.commit()
    response = jsonify({"success": True, "session": frontend_session_data()})
    response.headers["Cache-Control"] = "private, no-store"
    return response

@app.route("/api/v1/auth/password-reset", methods=["POST"])
def api_request_password_reset():
    """Send a reset link only to a matching, confirmed email without revealing account existence."""
    email = request.form.get("email", "").strip().lower()
    if email and len(email) <= 254:
        user = Tables.User.query.filter(
            func.lower(Tables.User.email) == email,
            Tables.User.email_confirmed.is_(True),
        ).first()
        if not user:
            user = Tables.User.query.filter(
                func.lower(Tables.User.hs_email) == email,
                Tables.User.hs_email_confirmed.is_(True),
            ).first()
        if user:
            try:
                from Sections.EmailHandler import send_password_reset_email
                send_password_reset_email(user, email)
            except Exception:
                app.logger.exception("Failed to start password reset email")

    response = jsonify({
        "success": True,
        "message": "Wenn ein Konto mit dieser bestätigten E-Mail-Adresse existiert, erhältst du einen Link zum Zurücksetzen.",
    })
    response.headers["Cache-Control"] = "no-store"
    return response, 202


@app.route("/api/v1/auth/password-reset/confirm", methods=["POST"])
def api_confirm_password_reset():
    """Validate a one-hour, password-bound token and replace the account password."""
    uid = request.form.get("uid", "")
    token = request.form.get("token", "")
    password = request.form.get("password", "")
    password_confirm = request.form.get("password_confirm", "")
    errors = {}
    if len(password) < 8 or len(password) > 30:
        errors["password"] = ["Das Passwort muss zwischen 8 und 30 Zeichen lang sein."]
    if password != password_confirm:
        errors["password_confirm"] = ["Die Passwörter stimmen nicht überein."]
    if errors:
        return jsonify({"success": False, "errors": errors}), 400

    try:
        user_uid = UUID(uid)
    except (ValueError, TypeError, AttributeError):
        return jsonify({"success": False, "error": "Der Link ist ungültig oder abgelaufen."}), 400
    user = Tables.User.query.filter_by(uid=user_uid).first()
    if not user:
        return jsonify({"success": False, "error": "Der Link ist ungültig oder abgelaufen."}), 400

    from Sections.EmailHandler import password_reset_serializer
    try:
        payload = password_reset_serializer(user).loads(token, max_age=3600)
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return jsonify({"success": False, "error": "Der Link ist ungültig oder abgelaufen."}), 400
    if payload.get("uid") != str(user.uid):
        return jsonify({"success": False, "error": "Der Link ist ungültig oder abgelaufen."}), 400

    was_current_user = current_user.is_authenticated and current_user.id == user.id
    user.password = bcrypt.generate_password_hash(password).decode("utf-8")
    user.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.session.commit()
    if was_current_user:
        logout_user()
    response = jsonify({"success": True})
    response.headers["Cache-Control"] = "no-store"
    return response

def registration_captcha_payload():
    challenge = SIMPLE_CAPTCHA.create()
    return {
        "image": "data:image/jpeg;base64," + challenge["img"],
        "hash": challenge["hash"],
    }

def registration_setup_payload():
    return {
        "csrf_token": generate_csrf(),
        "roles": [
            role.name
            for role in Tables.Role.query.filter_by(selectable_on_register="yes").all()
        ],
        "captcha": registration_captcha_payload(),
    }

@app.route("/api/v1/auth/register", methods=["GET", "POST"])
def api_auth_register():
    if request.method == "GET":
        response = jsonify(registration_setup_payload())
        response.headers["Cache-Control"] = "no-store"
        return response

    form = Forms.RegisterForm()
    public_roles = Tables.Role.query.filter_by(selectable_on_register="yes").all()
    form.role.choices = [(role.name, role.name) for role in public_roles]

    captcha_text = request.form.get("captcha-text", "")
    captcha_hash = request.form.get("captcha-hash", "")
    if not SIMPLE_CAPTCHA.verify(captcha_text, captcha_hash):
        response = jsonify({
            "success": False,
            "errors": {"captcha": ["Die Sicherheitsabfrage war nicht korrekt. Bitte versuche es erneut."]},
            **registration_setup_payload(),
        })
        response.headers["Cache-Control"] = "no-store"
        return response, 400

    if not form.validate_on_submit():
        response = jsonify({
            "success": False,
            "errors": form.errors,
            **registration_setup_payload(),
        })
        response.headers["Cache-Control"] = "no-store"
        return response, 400

    username = form.username.data.lower()
    if not username.isalnum():
        errors = {"username": ["Der Benutzername darf nur Buchstaben und Zahlen enthalten."]}
    elif Tables.User.query.filter_by(username=username).first():
        errors = {"username": ["Dieser Benutzername ist bereits vergeben."]}
    elif form.role.data not in [role.name for role in public_roles]:
        errors = {"role": ["Bitte wähle eine gültige Rolle."]}
    elif form.role.data == "Student" and not form.hs_email.data:
        errors = {"hs_email": ["Als Student musst du deine Hochschul-E-Mail angeben."]}
    else:
        errors = {}

    if errors:
        response = jsonify({
            "success": False,
            "errors": errors,
            **registration_setup_payload(),
        })
        response.headers["Cache-Control"] = "no-store"
        return response, 400

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = Tables.User(
        username=username,
        password=bcrypt.generate_password_hash(form.password.data).decode("utf-8"),
        register_date=now,
        last_login=now,
        surname=form.surname.data,
        lastname=form.lastname.data,
        email=form.email.data,
        hs_email=form.hs_email.data,
        street=form.street.data,
        street_no=form.street_no.data,
        city=form.city.data,
        postalcode=form.postalcode.data,
        role=form.role.data,
        permissions=[],
        last_updated=now,
    )
    db.session.add(user)
    db.session.commit()

    from Sections.EventHandler import ensure_user_calendar_url
    ensure_user_calendar_url(user)
    login_user(user)
    verification_notice = bool(user.email or user.hs_email)
    try:
        verify_email(user)
    except Exception:
        app.logger.info("%s failed to start email verification", user.username)

    response = jsonify({
        "success": True,
        "session": frontend_session_data(),
        "verification_notice": verification_notice,
    })
    response.headers["Cache-Control"] = "private, no-store"
    return response, 201

def contact_setup_payload():
    return {
        "csrf_token": generate_csrf(),
        "categories": [
            {"value": "kontakt", "label": "Kontakt"},
            {"value": "mieten", "label": "Location mieten"},
            {"value": "feedback", "label": "Kritik oder Lob"},
            {"value": "events", "label": "Wünsche für ein Event"},
        ],
        "captcha": registration_captcha_payload(),
        "prefill": {
            "surname": current_user.surname or "" if current_user.is_authenticated else "",
            "lastname": current_user.lastname or "" if current_user.is_authenticated else "",
            "email": (
                (current_user.hs_email or current_user.email or "")
                if current_user.is_authenticated
                else ""
            ),
        },
    }

@app.route("/api/v1/contact", methods=["GET", "POST"])
def api_contact():
    if request.method == "GET":
        response = jsonify(contact_setup_payload())
        response.headers["Cache-Control"] = "no-store"
        return response

    form = Forms.ContactForm()
    captcha_text = request.form.get("captcha-text", "")
    captcha_hash = request.form.get("captcha-hash", "")
    if not SIMPLE_CAPTCHA.verify(captcha_text, captcha_hash):
        response = jsonify({
            "success": False,
            "errors": {"captcha": ["Die Sicherheitsabfrage war nicht korrekt. Bitte versuche es erneut."]},
            **contact_setup_payload(),
        })
        response.headers["Cache-Control"] = "no-store"
        return response, 400

    if not form.validate_on_submit():
        response = jsonify({
            "success": False,
            "errors": form.errors,
            **contact_setup_payload(),
        })
        response.headers["Cache-Control"] = "no-store"
        return response, 400

    now = datetime.now()
    contact = Tables.Contact(
        category=form.category.data,
        surname=form.surname.data,
        lastname=form.lastname.data,
        email=form.email.data,
        message=form.message.data,
        created=now.strftime("%Y-%m-%d %H:%M:%S"),
        creation=now,
    )
    db.session.add(contact)
    db.session.commit()
    response = jsonify({"success": True, "message": "Danke für deine Nachricht!"})
    response.headers["Cache-Control"] = "no-store"
    return response, 201

@app.route("/api/v1/me/tickets", methods=["GET"])
def api_my_tickets():
    """Return only the signed-in user's registrations and check-in QR code."""
    if not current_user.is_authenticated:
        return jsonify({"error": "authentication_required"}), 401

    from Sections.FinanceAllocations import charge_payment_state

    user_data = {
        "id": current_user.id,
        "username": current_user.username,
        "surname": current_user.surname,
        "lastname": current_user.lastname,
        "role": current_user.role,
        "hs_email_confirmed": current_user.hs_email_confirmed,
        "uid": str(current_user.uid),
    }
    qr_generator = app.extensions["qrcode"]
    checkin_qr = qr_generator(json.dumps(user_data))

    tickets = []
    registrations = (
        Tables.Registration.query
        .filter_by(userFK=current_user.id)
        .filter(Tables.Registration.cancelled_at.is_(None))
        .order_by(Tables.Registration.timestamp.desc())
        .all()
    )
    for registration in registrations:
        manager = registration.RegisterManager
        event = Tables.Event.query.filter_by(id=manager.eventFK).first()
        if not event:
            continue
        ticket_charge = Tables.FinanceCharge.query.filter_by(registration_id=registration.id).first()
        payment_state = charge_payment_state(ticket_charge) if ticket_charge else {
            "status": "paid" if registration.paid else "open",
            "remaining_cents": None,
        }
        event_date = event.date.replace(tzinfo=local_tz).isoformat(timespec="minutes") if event.date else None
        tickets.append({
            "id": registration.id,
            "registration_name": manager.name,
            "price": registration.price if registration.price is not None else manager.price,
            "paid": payment_state["status"] == "paid",
            "payment_status": payment_state["status"],
            "remaining_cents": payment_state["remaining_cents"],
            "valid": registration.valid,
            "timestamp": registration.timestamp.isoformat(timespec="minutes") if registration.timestamp else None,
            "can_cancel": manager.deny == "erlaubt",
            "event": {
                "id": event.id,
                "name": event.name,
                "date": event_date,
                "place": event.place,
            },
        })

    response = jsonify({"checkin_qr": checkin_qr, "tickets": tickets})
    response.headers["Cache-Control"] = "private, no-store"
    return response

@app.route("/api/v1/me/commitments", methods=["GET"])
def api_my_commitments():
    """Return only this user's volunteer shifts and event tasks."""
    if not current_user.is_authenticated:
        return jsonify({"error": "authentication_required"}), 401

    from Sections.ManagementApi import task_help_permission

    def event_summary(event_id):
        event = Tables.Event.query.filter_by(id=event_id).first()
        if not event:
            return None
        return {
            "id": event.id,
            "name": event.name,
            "date": event.date.replace(tzinfo=local_tz).isoformat(timespec="minutes") if event.date else None,
            "place": event.place,
        }

    shifts = []
    for duty in Tables.Duty.query.filter_by(user=current_user.id).all():
        shift = duty.Shift
        event = event_summary(shift.event) if shift else None
        if not shift or not event:
            continue
        shifts.append({
            "id": duty.id,
            "shift_id": shift.id,
            "type": shift.type,
            "start": shift.start.replace(tzinfo=local_tz).isoformat(timespec="minutes") if shift.start else None,
            "end": shift.end.replace(tzinfo=local_tz).isoformat(timespec="minutes") if shift.end else None,
            "can_leave": hasPermissions("events.help"),
            "event": event,
        })

    tasks = []
    for assistant in Tables.Assistant.query.filter_by(userFK=current_user.id).all():
        task = assistant.task
        event = event_summary(task.eventFK) if task else None
        if not task or not event:
            continue
        required_permission = task_help_permission(task.visibility)
        tasks.append({
            "id": assistant.id,
            "task_id": task.id,
            "name": task.name,
            "status": task.status,
            "priority": task.priority,
            "deadline": task.deadline.replace(tzinfo=local_tz).isoformat(timespec="minutes") if task.deadline else None,
            "timeframe_start": task.timeframe_start.replace(tzinfo=local_tz).isoformat(timespec="minutes") if task.timeframe_start else None,
            "timeframe_end": task.timeframe_end.replace(tzinfo=local_tz).isoformat(timespec="minutes") if task.timeframe_end else None,
            "can_leave": bool(required_permission and hasPermissions(required_permission)),
            "event": event,
        })

    response = jsonify({"shifts": shifts, "tasks": tasks})
    response.headers["Cache-Control"] = "private, no-store"
    return response

def profile_api_data(user):
    from Sections.EventHandler import ensure_user_calendar_url

    ensure_user_calendar_url(user)
    selectable_roles = Tables.Role.query.filter_by(selectable_on_register="yes").all()
    role_names = [role.name for role in selectable_roles]
    if user.role and user.role not in role_names:
        role_names.append(user.role)
    return {
        "username": user.username or "",
        "role": user.role or "",
        "roles": role_names,
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
        "personal_calendar_url": url_for(
            "user_calendar_ical",
            calendar_id=user.calendar_url,
        ),
    }

@app.route("/api/v1/me/profile", methods=["GET", "PUT"])
def api_my_profile():
    """Read or update the current user's own profile."""
    if not current_user.is_authenticated:
        return jsonify({"error": "authentication_required"}), 401

    if request.method == "GET":
        response = jsonify(profile_api_data(current_user))
        response.headers["Cache-Control"] = "private, no-store"
        return response

    form = Forms.ChangeData()
    selectable_roles = Tables.Role.query.filter_by(selectable_on_register="yes").all()
    user_role = Tables.Role.query.filter_by(name=current_user.role).first()
    available_roles = list(selectable_roles)
    if user_role and user_role.name not in {role.name for role in available_roles}:
        available_roles.append(user_role)
    form.role.choices = [(role.name, role.name) for role in available_roles]

    if not form.validate_on_submit():
        return jsonify({
            "success": False,
            "errors": {field: errors for field, errors in form.errors.items()},
        }), 400

    new_username = form.username.data.lower()
    if not new_username.isalnum():
        return jsonify({
            "success": False,
            "errors": {"username": ["Der Benutzername darf nur Buchstaben und Zahlen enthalten."]},
        }), 400
    if new_username != current_user.username and Tables.User.query.filter_by(username=new_username).first():
        return jsonify({
            "success": False,
            "errors": {"username": ["Dieser Benutzername ist bereits vergeben."]},
        }), 409

    user = current_user._get_current_object()
    email_changed = user.email != form.email.data
    hs_email_changed = user.hs_email != form.hs_email.data
    role_changed = form.role.data in [role.name for role in available_roles] and form.role.data != user.role
    user.username = new_username
    user.surname = form.surname.data
    user.lastname = form.lastname.data
    user.email = form.email.data
    user.hs_email = form.hs_email.data
    user.street = form.street.data
    user.street_no = form.street_no.data
    user.city = form.city.data
    user.postalcode = form.postalcode.data
    if form.role.data in [role.name for role in available_roles]:
        user.role = form.role.data
    if role_changed:
        pending_role_request = Tables.UserRoleRequest.query.filter_by(user_id=user.id, status="pending").first()
        if pending_role_request:
            pending_role_request.status = "withdrawn"
            pending_role_request.reviewed_at = datetime.now()
            pending_role_request.review_note = "Durch eigene Rollenänderung zurückgezogen."

    if email_changed:
        user.email_confirmed = False
        user.email_cooldown = datetime.min
    if hs_email_changed:
        user.hs_email_confirmed = False
        user.hs_email_cooldown = datetime.min
    if form.password.data:
        user.password = bcrypt.generate_password_hash(form.password.data).decode("utf-8")

    user.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.session.commit()

    verification_warning = False
    if email_changed or hs_email_changed:
        try:
            verify_email(user)
        except Exception:
            verification_warning = True
            app.logger.info("%s failed to verify updated profile email", user.username)

    response = jsonify({
        "success": True,
        "profile": profile_api_data(user),
        "verification_warning": verification_warning,
    })
    response.headers["Cache-Control"] = "private, no-store"
    return response

@app.route("/api/v1/me/verification", methods=["POST"])
def api_request_email_verification():
    """Request new verification links for the current user's unconfirmed email addresses."""
    if not current_user.is_authenticated:
        return jsonify({"error": "authentication_required"}), 401
    has_unconfirmed_email = bool(current_user.email and not current_user.email_confirmed)
    has_unconfirmed_hs_email = bool(current_user.hs_email and not current_user.hs_email_confirmed)
    if not has_unconfirmed_email and not has_unconfirmed_hs_email:
        return jsonify({"error": "no_unconfirmed_email"}), 409

    try:
        from Sections.EmailHandler import verify_email
        verify_email(current_user._get_current_object())
    except Exception:
        app.logger.exception("%s failed to request email verification", current_user.username)
        return jsonify({"error": "verification_unavailable"}), 503

    response = jsonify({"success": True})
    response.headers["Cache-Control"] = "private, no-store"
    return response, 202

@app.route("/scanner", methods=['GET','POST'])
@require_permissions("scanner.show")
def scanner():
    if hasPermissions("scanner.show"): 
        if request.method == "POST":
            if request.data.userid:
                userid = request.data.userid
                user = Tables.User.query.filter_by(id=userid).first()
                if user:
                    registrations = Tables.Registration.query.filter_by(userFK=user.id).all()
                    if registrations:
                        return render_template('scanner.html', title='Sia-Scanner', registrations=registrations)
                    else:
                       return jsonify({'success': False, 'error': "User ist nirgends angemeldet."}) 
                else:
                   return jsonify({'success': False, 'error': "Kein User zur ID gefunden"}) 
            else:
                return jsonify({'success': False, 'error': "User ID wurde nicht gesendet"})
        return render_template('scanner.html', title='Sia-Scanner')
    else:
        return Response(status=403)

    

@app.route("/tickets", methods=['GET'])
@login_required
def tickets():
    user = Tables.User.query.filter_by(id=current_user.id).first()
    registrations = Tables.Registration.query.filter_by(userFK=current_user.id).all()
    registrationList = []
    if registrations:
        for rm in registrations:
            rm_dict = rm.getDict()
            rm_dict["price"] = rm.RegisterManager.price
            registrationList.append(rm_dict)
    if user:
        user_data = {
            "id": user.id,
            "username": user.username,
            "surname":user.surname ,
            "lastname":user.lastname ,
            "role":user.role ,
            "hs_email_confirmed":user.hs_email_confirmed,
            "uid":str(user.uid),
        }
        json_data = json.dumps(user_data)
        return render_template('tickets.html', title='Tickets', registrations=registrationList, qrcode_string=json_data)
    else:
        flash("Serverfehler")
        return render_template('tickets.html', title='Tickets',messages=get_flashed_messages)


    



@app.route("/admin", methods=['GET', 'POST'])
@require_permissions("adminpanel.show")
def admin():
    submitted=False
    form = Forms.EventForm()

    if form.is_submitted():
        if not hasPermissions("events.create"):
            return Response(status=403)
        
        if not form.validate():
            return make_response(form.errors, 400)
        
        submitted=True
        newEvent = Tables.Event(
            name = form.name.data,
            visibility = form.visibility.data,
            place = form.place.data,
            author = current_user.id,
            created = datetime.now(),
            date = form.date.data,
            end = form.event_end.data,
            description = form.description.data #,
            #postername = current_user.username
        )
        db.session.add(newEvent)
        db.session.commit()

        # TODO add check if file is actually an image 
        if form.file.data:
            form.file.data.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "images", "eventposter", str(newEvent.uid)))

    users = Tables.User.query.order_by(Tables.User.last_login.desc()).all()
    contacts = Tables.Contact.query.order_by(Tables.Contact.created.desc()).all() 
    contacts = [contact.getDict() for contact in contacts]
    timedelta12 = timedelta(days=1)
    today = datetime.now(timezone.utc)
    today -= timedelta12
    all_flag = request.args.get('all')
    if all_flag:
        eventlist = Tables.Event.query.order_by(Tables.Event.date.asc()).all()
    else:
        eventlist = Tables.Event.query.filter(Tables.Event.date >= today).order_by(Tables.Event.date.asc()).all()

    events = []

    def format_datetime(dt):
        return dt.strftime('%Y-%m-%d %H:%M') if dt else None
    
    for event in eventlist:
        authorname = (
            Tables.Event.query
            .join(Tables.User, Tables.Event.author == Tables.User.id) 
            .filter(Tables.Event.id == event.id)  
            .with_entities(Tables.User.username) 
            .scalar()
        )
        shift_filled_count = (
            db.session.query(func.count(func.distinct(Tables.Shift.id)))
            .join(Tables.Duty)
            .filter(Tables.Shift.event == event.id)
            .scalar()
        )
        individuals_count = (
            db.session.query(func.count(func.distinct(Tables.Duty.user)))
            .join(Tables.Shift)
            .filter(Tables.Shift.event == event.id)
            .scalar()
        )
        registration_count = (
            db.session.query(func.count(func.distinct(Tables.Registration.userFK)))
            .join(Tables.RegisterManager)
            .filter(Tables.RegisterManager.eventFK == event.id)
            .scalar()
        )
        duty_count = db.session.query(Tables.Duty).join(Tables.Shift).filter(Tables.Shift.event == event.id).count()
        shift_count = Tables.Shift.query.filter_by(event=event.id).count()
        task_count = Tables.Task.query.filter_by(eventFK=event.id).count()   
        rm_count = Tables.RegisterManager.query.filter_by(eventFK=event.id).count()      
        events.append({
            "id": event.id,
            "name":event.name,
            "uid": event.uid,
            "username":authorname,
            "visibility":event.visibility,
            "place":event.place,
            "created":event.created,
            "date":format_datetime_hr(event.date),
            "end":format_datetime_hr(event.end),
            "description":event.description,
            "duty_count": duty_count,
            "shift_count": shift_count,
            "shift_filled_count":shift_filled_count,
            "task_count":task_count,
            "individuals_count":individuals_count,
            "rm_count":rm_count
        })
    
    '''
    events = Tables.Event.query.join(Tables.User, Tables.Event.author == Tables.User.id) \
        .with_entities(Tables.Event.id, Tables.Event.uid, Tables.Event.name, Tables.Event.visibility, Tables.Event.description, Tables.Event.place, Tables.Event.created, Tables.Event.date, Tables.User.username) \
        .order_by(Tables.Event.created.desc()).all()
    '''
    roles = Tables.Role.query.all()
    form_edit_user = Forms.AdminChangeData()
    tasks = [task.getDict() for task in Tables.Task.query.filter(Tables.Task.deadline >= today).order_by(Tables.Task.deadline.asc()).all()]
    form_edit_user.role.choices = [(role.name, role.name) for role in roles] 
    return render_template('admin.html', title='Sia-PlanB.de', tasks=tasks, events=events, users=users, contacts=contacts, submitted=submitted, form=Forms.EventForm(), form_edit_user=form_edit_user, form_edit_event=Forms.ChangeEventForm(), form_new_shift=Forms.newShiftForm(), form_new_registration=Forms.newRegistration(),form_new_task=Forms.newTask() )


@app.route("/slider/<name>")
def slider(name):
    image_dir = os.path.join(app.root_path, 'static/images/slider/')
    file_path = os.path.join(image_dir, name)
    if not os.path.exists(file_path):
        name = "placeholder.png"  
    return send_from_directory(image_dir, name)

@app.route("/logo.svg")
def bimi_logo():
    logo_dir = os.path.join(app.root_path, "static/images")
    return send_from_directory(logo_dir, "logo.svg", mimetype="image/svg+xml")

@app.route("/",methods=['GET'])
def index():
    events=getAllEvents()
    return render_template('index.html', title='Sia-PlanB.de', events=events)

@app.route("/contact", methods=['GET', 'POST'])
def contact():
    form = Forms.ContactForm()
    if form.validate_on_submit():
        c_hash = request.form.get('captcha-hash')
        c_text = request.form.get('captcha-text')
        if SIMPLE_CAPTCHA.verify(c_text, c_hash):
            newContact = Tables.Contact(
                category = form.category.data,
                surname = form.surname.data,
                lastname = form.lastname.data,
                email = form.email.data,
                message = form.message.data,
                created = datetime.now(),
                creation = datetime.now()
            )
            db.session.add(newContact)
            db.session.commit()
            flash("Danke für deine Nachricht!")
        else:
            flash("Captcha Falsch!",'error')


    if current_user.is_authenticated:
        if current_user.email: form.email.data=current_user.email
        if current_user.hs_email: form.email.data=current_user.hs_email #Prefer HS_Mail
        if current_user.surname: form.surname.data=current_user.surname 
        if current_user.lastname: form.lastname.data=current_user.lastname
        if current_user.hs_email: form.email.data=current_user.hs_email
    messages=form.errors
    new_captcha_dict = SIMPLE_CAPTCHA.create()
    return render_template('contact.html', title='Sia-PlanB.de', form=form, messages=messages, captcha=new_captcha_dict)
        
@app.route("/datenschutz",methods=['GET'])
def datenschutz():
    return render_template('datenschutz.html', title='Sia-PlanB.de')

@app.route("/faq",methods=['GET'])
def faq():
    return render_template('under_construction.html', title='Sia-PlanB.de')

@app.route("/impressum",methods=['GET'])
def impressum():
    return render_template('impressum.html', title='Sia-PlanB.de')

@app.route("/newsletter",methods=['GET'])
def newsletter():
    return render_template('under_construction.html', title='Sia-PlanB.de')

@app.route("/profile",methods=['GET','POST'])
@login_required
def profile():
    # Ensure user has a calendar URL
    from Sections.EventHandler import ensure_user_calendar_url
    ensure_user_calendar_url(current_user)

    form = Forms.ChangeData()
    public_roles = Tables.Role.query.filter_by(selectable_on_register="yes").all()
    user_role = Tables.Role.query.filter_by(name=current_user.role).first()
    public_roles.append(user_role)
    form.role.choices = [(role.name, role.name) for role in public_roles]
    user = db.session.query(Tables.User).filter_by(username=current_user.username).first()
    if request.method == "POST" and form.validate_on_submit():
        new_username = form.username.data.lower()
        if current_user.username != new_username:
            existing_user_username = Tables.User.query.filter_by(username=new_username).first()
            if existing_user_username or not new_username.isalnum():
                if not new_username.isalnum():
                    flash('Nur Buchstaben und Zahlen im Benutzernamen', 'error')
                if existing_user_username:
                    flash('Benutzername bereits vergeben', 'error')
                #if username in manager.config.get_config("banned_usernames"): #TODO ADD BANNED CHARACTERS
                    #flash('- That username is not allowed. Please choose a different name.', 'error')
            else:
                user.username=new_username
        if form.password.data and form.password_confirm.data:
            if form.password.data != form.password_confirm.data:
                flash('Passwörter sind nicht gleich', 'error')
            else:
                hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
                user.password=hashed_password

        user.surname = form.surname.data
        user.lastname = form.lastname.data
        if user.email != form.email.data:
            user.email_confirmed = False
            user.email_cooldown = datetime.min
        user.email = form.email.data
        if user.hs_email != form.hs_email.data:
            user.hs_email_confirmed = False
            user.hs_email_cooldown = datetime.min
        user.hs_email = form.hs_email.data
        user.street = form.street.data
        user.street_no = form.street_no.data
        user.city = form.city.data
        user.postalcode = form.postalcode.data
        role_changed = form.role.data in [role.name for role in public_roles] and form.role.data != user.role
        if form.role.data in [role.name for role in public_roles]:
            user.role = form.role.data
        if role_changed:
            pending_role_request = Tables.UserRoleRequest.query.filter_by(user_id=user.id, status="pending").first()
            if pending_role_request:
                pending_role_request.status = "withdrawn"
                pending_role_request.reviewed_at = datetime.now()
                pending_role_request.review_note = "Durch eigene Rollenänderung zurückgezogen."
        user.last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.session.commit()
        flash(f"Deine Daten wurden erfolgreich abgespeichert! {datetime.now().astimezone(local_tz).strftime('%H:%M')}", 'info')
        try:
            verify_email(current_user)
        except:
            flash("Der Maildienst hat gerade keine Lust deine Mail zu verifizieren :(")
            app.logger.info('%s failed to verify email', current_user.username)
    if current_user.is_authenticated: #eigentlich unnötig da Profile nicht sichtbar ist für Anonyme User
        if current_user.username: form.username.data=current_user.username 
        form.password.data=""
        form.password_confirm.data=""
        if current_user.surname: form.surname.data=current_user.surname # Man weiß ja nie und lieber auf Nummer sicher
        if current_user.email: form.email.data=current_user.email  
        if current_user.lastname: form.lastname.data=current_user.lastname
        if current_user.email: form.email.data=current_user.email 
        if current_user.hs_email: form.hs_email.data=current_user.hs_email 
        if current_user.street: form.street.data=current_user.street 
        if current_user.city: form.city.data=current_user.city 
        if current_user.street_no: form.street_no.data=current_user.street_no 
        if current_user.postalcode: form.postalcode.data=current_user.postalcode 
        role=current_user.role if current_user.role else ""
    messages=form.errors
    return render_template('profile.html', title='Sia-PlanB.de', form=form, role=role, messages=messages, calendar_url=current_user.calendar_url)

@app.route("/verein",methods=['GET'])
def verein():
    return render_template('verein.html', title='Verein')

@app.route("/location",methods=['GET'])
def location():
    return render_template('location.html', title='Plan B')


@app.route('/static/images/eventposter/<filename>')
def get_image(filename):
    image_path = find_event_poster(filename)

    if image_path:
        response = send_file(image_path, mimetype=event_poster_mimetype(image_path), conditional=True)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    default_path = os.path.join(current_app.root_path, 'static', 'images', 'eventposter', 'default.jpg')
    response = send_file(default_path)
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response
    
if __name__ == "__main__":
    app.run(host='0.0.0.0')
