from globals import *
from flask import flash, url_for, redirect, jsonify,request
from datetime import datetime
from uuid import UUID
from flask_login import current_user
#-----FILES-----
from database import Tables
from forms import Forms
from permissions import *
from Sections.EmailHandler import verify_email

import json



@app.route("/api/user/update/<uid>", methods=['POST'])
@require_permissions("adminpanel.user.update")
def update_user(uid):
    form = Forms.AdminChangeData()
    roles = Tables.Role.query.all() # sonst geht validate_on_submit nicht durch, TODO eventuell hier auf Rechte prüfen wer welche Rollen setzen kann
    form.role.choices = [(role.name, role.name) for role in roles]
    user = db.session.query(Tables.User).filter_by(uid=uid).first()
    if form.validate_on_submit():
        new_username = form.username.data.lower()
        if user.username != new_username:
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
        user.email = form.email.data
        if user.hs_email != form.hs_email.data:
            user.hs_email_confirmed = False
        user.hs_email = form.hs_email.data
        user.street = form.street.data
        user.street_no = form.street_no.data
        user.city = form.city.data
        user.postalcode = form.postalcode.data
        role_changed = user.role != form.role.data
        user.role = form.role.data
        user.last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if role_changed:
            pending_role_request = Tables.UserRoleRequest.query.filter_by(user_id=user.id, status="pending").first()
            if pending_role_request:
                pending_role_request.status = "withdrawn"
                pending_role_request.reviewed_by = current_user.id
                pending_role_request.reviewed_at = datetime.now()
                pending_role_request.review_note = "Von der Verwaltung direkt geändert."
        db.session.commit()
        if form.verify_mail.data:
            try:
                verify_email(user)
            except:
                app.logger.info('%s failed to verify email by admin', user.username)
        return jsonify({'success': True})  # JSON-Antwort bei Erfolg
    else:
        for field_name, field_errors in form.errors.items():
            print(f"Feld '{field_name}' hat folgende Fehler:")
            for error in field_errors:
                print(f"  - {error}")

    errors = []
    for field, error_list in form.errors.items():
        for error in error_list:
            errors.append(f"{error}")

    return jsonify({'success': False, 'errors': errors})  # JSON-Antwort mit Fehlern


@app.route("/api/user/get/scanner", methods=["POST"])
def get_user_scanner():
    if not current_user.is_authenticated:
        return jsonify({"error": "Bitte melde dich erneut an."}), 401
    if not hasPermissions("scanner.show"):
        return jsonify({"error": "Dir fehlt die Berechtigung für den Scanner."}), 403

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    username = payload.get("username")
    uid = payload.get("uid")
    user = None

    if isinstance(username, str) and username.strip():
        user = db.session.query(Tables.User).filter_by(username=username.strip().lower()).first()
    elif isinstance(uid, str) and uid.strip():
        identifier = uid.strip()
        # Existing check-in QR codes contain UUIDs. Accept usernames in the
        # legacy uid field as well so older scanner clients remain compatible.
        user = db.session.query(Tables.User).filter_by(username=identifier.lower()).first()
        if user is None:
            try:
                user_uid = UUID(identifier)
            except (ValueError, TypeError, AttributeError):
                user_uid = None
            if user_uid is not None:
                user = db.session.query(Tables.User).filter_by(uid=user_uid).first()
    else:
        return jsonify({"error": "Gib einen Benutzernamen ein oder scanne einen Check-in-Code."}), 400

    if user is None:
        return jsonify({"error": "Für diesen Benutzernamen oder Check-in-Code wurde kein Konto gefunden."}), 404

    registrations = Tables.Registration.query.filter_by(userFK=user.id).filter(
        Tables.Registration.cancelled_at.is_(None)
    ).all()
    from Sections.FinanceAllocations import charge_payment_state

    registration_list = []
    for registration in registrations:
        registration_dict = registration.getDict()
        registration_dict["price"] = (
            registration.price if registration.price is not None else registration.RegisterManager.price
        )
        ticket_charge = Tables.FinanceCharge.query.filter_by(registration_id=registration.id).first()
        payment_state = charge_payment_state(ticket_charge) if ticket_charge else {
            "status": "paid" if registration.paid else "open",
            "remaining_cents": None,
        }
        registration_dict["paid"] = payment_state["status"] == "paid"
        registration_dict["payment_status"] = payment_state["status"]
        registration_dict["remaining_cents"] = payment_state["remaining_cents"]
        registration_list.append(registration_dict)
    return jsonify(registration_list)
    

@app.route("/api/user/get/<uid>", methods=["POST"])
@require_permissions("adminpanel.user.get")
def get_user(uid):
    if not uid:
        return jsonify({"error": "UID is missing"}), 400

    user = db.session.query(Tables.User).filter_by(uid=uid).first()
    if user:
        return jsonify({
            "username": user.username,
            "email": user.email,
            "hs_email": user.hs_email,
            "surname": user.surname,
            "lastname": user.lastname,
            "street": user.street,
            "street_no": user.street_no,
            "city": user.city,
            "postalcode": user.postalcode,
            "role": user.role,
            "uid":user.uid,
            "registered":user.register_date,
            "last_login":user.last_login,
            "last_updated":user.last_updated,
            "id":user.id,
        })
    else:
        return jsonify({"error": "User not found"}), 404
    
@app.route("/delete_user", methods=['POST']) #TODO noch auf API Syntax umbauen
@require_permissions("adminpanel.user.delete")
def delete_user():
    form = Forms.contactDelete() #braucht man keine neue Form dafür
    if form.validate_on_submit():
        uid = form.uid.data
        user = db.session.query(Tables.User).filter_by(uid=uid).first()
        if user:
            if Tables.Membership.query.filter_by(user_id=user.id).first():
                flash("Ein Konto mit Finanzhistorie kann nicht gelöscht werden. Beende stattdessen die Mitgliedschaft.", "error")
                return redirect(url_for('admin'))
            if Tables.Registration.query.filter_by(userFK=user.id).first():
                flash("Ein Konto mit Event-Ticket-Historie kann nicht gelöscht werden.", "error")
                return redirect(url_for('admin'))
            db.session.delete(user)
            db.session.commit()
        return redirect(url_for('admin'))
    else:
        return redirect(url_for('admin'))
