from flask_login import current_user, login_required
from globals import app
from flask import Response, json, render_template, jsonify, request, abort
from permissions import require_permissions, hasPermissions
from database import *
from forms import *
from flask import current_app
from datetime import timedelta, timezone, datetime
from decimal import Decimal
from sqlalchemy import func
from zoneinfo import ZoneInfo
from Sections.RegistrationService import cancel_registration, create_event_ticket_charge, set_registration_paid
from Sections.ManagementApi import user_can_view_event

'''
_____            _     _             _   _                                                           
|  __ \          (_)   | |           | | (_)                                                          
| |__) |___  __ _ _ ___| |_ _ __ __ _| |_ _  ___  _ __    _ __ ___   __ _ _ __   __ _  __ _  ___ _ __ 
|  _  // _ \/ _` | / __| __| '__/ _` | __| |/ _ \| '_ \  | '_ ` _ \ / _` | '_ \ / _` |/ _` |/ _ \ '__|
| | \ \  __/ (_| | \__ \ |_| | | (_| | |_| | (_) | | | | | | | | | | (_| | | | | (_| | (_| |  __/ |   
|_|  \_\___|\__, |_|___/\__|_|  \__,_|\__|_|\___/|_| |_| |_| |_| |_|\__,_|_| |_|\__,_|\__, |\___|_|   
            __/ |                                                                     __/ |          
            |___/                                                                     |___/           
'''

@app.route("/api/events/event/<int:eventid>/newRM", methods=['POST'])
@require_permissions("events.newRM")
def apiNewRM(eventid: int):
    def add_rm(form: Forms.newRegistration) -> str:
        new_RM = Tables.RegisterManager(
            eventFK = event.id,
            name = form.RegistrationName.data,
            start = form.RegistrationStart.data ,
            end = form.RegistrationEnd.data,
            visibility = form.RegistrationVisibility.data,
            accept = form.RegistrationAccept.data,
            price = form.RegistrationPrice.data,
            deny = form.RegistrationDeny.data
        )
        db.session.add(new_RM)
        db.session.commit()
        return jsonify({'success': True, 'message' : { "Erfolg":['Neue Registrierungsmöglichkeit angelegt.']}})

    if hasPermissions(f"/api/events/event/{eventid}/newRM"):
        form = Forms.newRegistration()
        event = Tables.Event.query.filter_by(id=eventid).first()
        if form.validate():
            if (form.RegistrationAccept.data == "Zeitraum" and form.RegistrationEnd.data and form.RegistrationName.data):
                return add_rm(form)
            elif form.RegistrationAccept.data == "geöffnet":
                return add_rm(form)
            elif form.RegistrationAccept.data == "geschlossen":
                return add_rm(form)
            else:
                return jsonify({
                            'success': False,
                            'error': {'Form': ["Für 'Zeitraum' musst du Start und Ende angeben."]}
                        })
        else:
            errors=form.errors
            return jsonify({'success': False, 'error' : errors})
    else:
        return jsonify({'success': False, 'error': "Dir fehlt die Berechtigung!"})
    
@app.route("/api/events/event/<int:eventid>/getRM/<int:rmID>", methods=['GET'])
def apiGetRmSingle(eventid: int,rmID: int):
    if hasPermissions(f"/api/events/event/{eventid}/getRM/{rmID}"):
        registerManager = Tables.RegisterManager.query.filter_by(eventFK=eventid,id=rmID).first()
        if registerManager:
            count = (
                db.session.query(func.count(func.distinct(Tables.Registration.userFK)))
                .filter(Tables.Registration.rmFK == rmID)
                .filter(Tables.Registration.cancelled_at.is_(None))
                .scalar()
            )
            register_data = registerManager.getDict()
            register_data["registration_count"] = count
            if registerManager.accept == "Zeitraum":
                register_data["join_button_active"] = check_time_span(registerManager)
            if registerManager.accept == "geschlossen":
                register_data["join_button_active"] = False
            return jsonify(registerManager.getDict())
        return jsonify({'success': False, 'message' : {'Erfolg': ['Keine Registrierungsmöglichkeiten gefunden.']}})
    else:
        return jsonify({'success': False, 'error': {'Fehler': ["Dir fehlt die Berechtigung!"]}})
    
@app.route("/api/events/event/<int:eventid>/getRM", methods=['GET'])
@login_required
def apiGetRmall(eventid: int):
    # Permission will be checked at the end of
    registerManager = Tables.RegisterManager.query.filter_by(eventFK=eventid).all()
    rmList = []
    if registerManager:
        for rm in registerManager:
            count = (
                db.session.query(func.count(func.distinct(Tables.Registration.userFK)))
                .filter(Tables.Registration.rmFK == rm.id)
                .filter(Tables.Registration.cancelled_at.is_(None))
                .scalar()
            )
            rmDict = rm.getDict()
            rmDict["registration_count"] = count
            if rmDict["accept"] == "Zeitraum":
                rmDict["join_button_active"] = check_time_span(rm)
            elif rmDict["accept"] == "geschlossen":
                rmDict["join_button_active"] = False
            else:
                rmDict["join_button_active"] = True 

            if (
                rmDict["visibility"] == "public" or
                (rmDict["visibility"] == "private" and hasPermissions("events.register.private")) or
                (rmDict["visibility"] == "student" and hasPermissions("events.register.student")) or
                (rmDict["visibility"] == "member" and hasPermissions("events.register.member"))
            ):
                rmList.append(rmDict)

        return jsonify(rmList)
    else:
        return jsonify({'success': False, 'error': { "Fehler":["Es gibt keine Registrierungsmöglichkeit für dieses Event."]}})

@app.route("/api/events/event/<int:eventid>/updateRM/<int:rmID>", methods=['POST'])
def apiUpdateRM(eventid: int,rmID: int):
    if hasPermissions("events.rm.update"):
        form = Forms.newRegistration()
        rm=Tables.RegisterManager.query.filter_by(eventFK=eventid,id=rmID).first()
        if form.validate_on_submit() and rm:
            rm.name = form.RegistrationName.data,
            rm.start = form.RegistrationStart.data ,
            rm.end = form.RegistrationEnd.data,
            rm.visibility = form.RegistrationVisibility.data,
            rm.accept = form.RegistrationAccept.data
            rm.deny = form.RegistrationDeny.data
            db.session.commit()
            return jsonify({'success': True, 'message' : { "Erfolg":['Daten angepasst']}})
        else:
            error=form.errors
            return jsonify({'success': False, 'error' : error})
    else:
        return jsonify({'success': False, 'error': { "Fehler":["Dir fehlt die Berechtigung 'events.rm.update'!"]}})

@app.route("/api/events/event/<int:eventid>/deleteRM/<int:rmID>", methods=['POST'])
@require_permissions("events.rm.delete")
def apiDeleteRM(eventid: int,rmID: int):
    if hasPermissions(f"/api/events/event/{eventid}/deleteRM/{rmID}"):
        if Tables.Registration.query.filter_by(rmFK=rmID).count():
            return jsonify({'success': False, 'error': {"Fehler": ["Anmeldemöglichkeiten mit Registrierungshistorie können nicht gelöscht werden. Schließe sie stattdessen."]}}), 409
        Tables.RegisterManager.query.filter_by(eventFK=eventid,id=rmID).delete()
        db.session.commit()
        return jsonify({'success': True, 'message' : { "Erfolg":['Registrierungsmöglichkeit wurde gelöscht']}})
    else:
        return jsonify({'success': False, 'error': { "Fehler":["Dir fehlt die Berechtigung 'events.rm.delete'!"]}})

@app.route("/api/events/event/<int:eventid>/register/<int:rmID>", methods=['POST'])
@login_required
def apiRegisterEvent(eventid: int, rmID: int):   
    registerManager = Tables.RegisterManager.query.filter_by(eventFK=eventid, id=rmID).first()
    if registerManager:
        event = Tables.Event.query.filter_by(id=eventid).first()
        if not event or not user_can_view_event(current_user, event):
            return jsonify({'success': False, 'error': {"Fehler": ["Dieses Event ist für deine Rolle nicht verfügbar."]}}), 403
        vis = registerManager.visibility
        rmID = registerManager.id
        if not registerManager:
                return jsonify({'success': False, 'error': { "Fehler":["Keine Registrierung vorgesehen!"]}}), 404
        existing_registration = Tables.Registration.query.filter_by(
            rmFK=registerManager.id,
            userFK=current_user.id,
            cancelled_at=None,
        ).first()
        if existing_registration:
            return jsonify({'success': False, 'error': { "Fehler":[f"Bereits angemeldet!"]}})
        if registerManager.accept == "Zeitraum":
            if check_time_span(registerManager):
                return check_register_perm(eventid,rmID,vis)
            else:
                return jsonify({'success': False, 'error': { "Fehler":[f"Die Anmeldephase hat noch nicht begonnen oder ist schon vorbei:"]}})
        elif registerManager.accept == "geschlossen":
            return jsonify({'success': False, 'error': { "Fehler":[f"Anmeldungen sind manuell geschlossen."]}})
        elif registerManager.accept == "geöffnet":
            return check_register_perm(eventid,rmID,vis)
    return jsonify({'success': False, 'error': { "Fehler":[f"Die Registrierung konnte nicht gefunden werden :/"]}})
        
def process_registration(eventid,rmID):
    register_manager = Tables.RegisterManager.query.filter_by(eventFK=eventid, id=rmID).first()
    price = Decimal(str(register_manager.price)) if register_manager and register_manager.price is not None else Decimal("0")
    is_free = price <= 0
    new_registration = Tables.Registration(
        rmFK=rmID,
        userFK=current_user.id,
        timestamp=datetime.now(timezone.utc),
        price=price,
        paid=is_free,
        created_by=current_user.id,
    )
    db.session.add(new_registration)
    db.session.flush()
    create_event_ticket_charge(new_registration, current_user.id)
    db.session.commit()
    return jsonify({'success': True, 'message': { "Erfolg":["Du wurdest erfolgreich für das Event angemeldet"]}})

def check_register_perm(eventid: int, rmID: int, vis: str):
    if vis == "member" and hasPermissions("events.register.member"):
        return process_registration(eventid,rmID)
    if vis == "private" and hasPermissions("events.register.private"):
        return process_registration(eventid,rmID)
    if vis == "student" and hasPermissions("events.register.student"):
        return process_registration(eventid,rmID)
    if vis == "public":
        return process_registration(eventid,rmID) 
    return jsonify({'success': False, 'error': { "Fehler":["Dir Fehlt die Berechtigung dich für die Events anzumelden."]}})

def check_time_span(registerManager: Tables.RegisterManager) -> bool:
    inBetween = True
    local_tz = ZoneInfo("Europe/Berlin")
    current_time = datetime.now(timezone.utc)
    if registerManager.start:
        register_start_local = registerManager.start.replace(tzinfo=local_tz)  
        register_start_utc = register_start_local.astimezone(timezone.utc)
        if current_time < register_start_utc:
            inBetween = False
    if registerManager.end:
        register_end_local = registerManager.end.replace(tzinfo=local_tz)  
        register_end_utc = register_end_local.astimezone(timezone.utc)
        if current_time > register_end_utc:
            inBetween = False
    return inBetween

@app.route("/api/events/event/<int:eventid>/unregister/<int:rmID>", methods=['POST'])
@login_required
def apiUnregisterEvent(eventid: int, rmID: int):
    registerManager = Tables.RegisterManager.query.filter_by(eventFK=eventid, id=rmID).first()

    if not registerManager:
        return jsonify({'success': False, 'error': { "Fehler":["Die Abmeldung war nicht möglich, da keine Registrierung (mehr) für das Event existiert!"]}}), 404
    
    if registerManager.deny == "verbieten":
        return jsonify({'success': False, 'error': { "Fehler":["Die Abmeldung war nicht möglich, da sie abgeschlaten ist!"]}}), 404

    existing_registration = Tables.Registration.query.filter_by(
        rmFK=registerManager.id,
        userFK=current_user.id,
        cancelled_at=None,
    ).first()
    if not existing_registration:
        return jsonify({'success': False, 'error': { "Fehler":[f"Du warst nie angemeldet!"]}})
    
    if existing_registration and registerManager.deny == "erlaubt":
        cancel_registration(existing_registration, current_user.id, "Selbst abgemeldet")
        db.session.commit()

    return jsonify({'success': True, 'message': { "Erfolg":["Du wurdest erfolgreich für das Event angemeldet"]}})


@app.route("/api/events/event/registration/punch/<regID>", methods=['POST'])
@login_required
def apiPunchRM(regID: int):
    if hasPermissions("events.rm.punch"):
        registration = Tables.Registration.query.filter_by(id=regID).filter(Tables.Registration.cancelled_at.is_(None)).first()
        if registration:
            if not registration.valid:
                return jsonify({"success": False, "message": { "Fehler":[f"'{registration.RegisterManager.name}' - Ist schon entwertet!"]}})
            registration.valid = False
            db.session.commit()
            return jsonify({'success': True, "message": { "Erfolg":[f"'{registration.RegisterManager.name}' wurde entwertet!"]}})
        else:
            return jsonify({"success":False, "error": { "Fehler":["Keine Registrierung gefunden!"]}})
    else:
        return jsonify({"success":False, "error": { "Fehler":["Missing Privilige 'events.rm.punch'!"]}})
    
@app.route("/api/events/event/registration/validate/<regID>", methods=['POST'])
@login_required
def apiValidateRM(regID: int):
    if hasPermissions("events.rm.validate"):
        registration = Tables.Registration.query.filter_by(id=regID).filter(Tables.Registration.cancelled_at.is_(None)).first()
        if registration:
            if registration.valid:
                return jsonify({"success":False, "message": { "Fehler":[f"'{registration.RegisterManager.name}' - Ist schon validiert!"]}})
            registration.valid = True
            db.session.commit()
            return jsonify({'success': True, "message": { "Erfolg":[f"'{registration.RegisterManager.name}' wurde validiert!"]}})
        else:
            return jsonify({"success":False, "error":{ "Fehler":["Keine Registrierung gefunden!"]}})
    else:
        return jsonify({"success":False, "error": { "Fehler":["Missing Privilige 'events.rm.validate'!"]}})
    
@app.route("/api/events/event/registration/unpaid/<regID>", methods=['POST'])
@login_required
def apiUnpaidRM(regID: int):
    if hasPermissions("events.rm.unpaid"):
        registration = Tables.Registration.query.filter_by(id=regID).filter(Tables.Registration.cancelled_at.is_(None)).first()
        if registration:
            if not registration.paid:
                return jsonify({"success":False, "message": { "Fehler":[f"'{registration.RegisterManager.name}' - Status ist bereits auf unbezahlt!"]}})
            set_registration_paid(registration, False, current_user.id, "scanner", "Am Scanner als unbezahlt markiert")
            db.session.commit()
            return jsonify({'success': True, "message": { "Erfolg":[f"'{registration.RegisterManager.name}' - Status wurde auf 'unbezahlt' gesetzt!"]}})
        else:
            return jsonify({"success":False, "error": { "Fehler":["Keine Registrierung gefunden!"]}})
    else:
        return jsonify({"success":False, "error": { "Fehler":["Missing Privilige 'events.rm.unpaid'!"]}})

@app.route("/api/events/event/registration/paid/<regID>", methods=['POST'])
@login_required
def apiPaidRM(regID: int):
    if hasPermissions("events.rm.paid"):
        registration = Tables.Registration.query.filter_by(id=regID).filter(Tables.Registration.cancelled_at.is_(None)).first()
        if registration:
            if registration.paid:
                return jsonify({"success":False, "message": { "Fehler":[f"'{registration.RegisterManager.name}' - Status ist bereits auf bezahlt!"]}})
            set_registration_paid(registration, True, current_user.id, "scanner", "Am Scanner als bezahlt markiert")
            db.session.commit()
            return jsonify({'success': True, "message": { "Erfolg":[f"'{registration.RegisterManager.name}' - Status wurde auf 'bezahlt' gesetzt!"]}})
        else:
            return jsonify({"success":False, "error": { "Fehler":["Keine Registrierung gefunden!"]}})
    else:
        return jsonify({"success":False, "error": { "Fehler":["Missing Privilige 'events.rm.paid'!"]}})
    



