from globals import *
from flask import flash, url_for, redirect, jsonify,request
from datetime import datetime
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
        user.role = form.role.data
        user.last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
@require_permissions("/api/user/get/scanner/")
def get_user_scanner():
    uid = request.json.get("uid")
    if not uid:
        return jsonify({"error": "No UID received"})

    user = db.session.query(Tables.User).filter_by(uid=uid).first()
    if user:
        registrations = Tables.Registration.query.filter_by(userFK=user.id).all()
        registrationList = []
        for rm in registrations:
            rm_dict = rm.getDict()
            rm_dict["price"] = rm.RegisterManager.price
            registrationList.append(rm_dict)
        return jsonify(registrationList)
    else:
        return jsonify({"error": "User not found"}), 404
    

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
            db.session.delete(user)
            db.session.commit()
        return redirect(url_for('admin'))
    else:
        return redirect(url_for('admin'))