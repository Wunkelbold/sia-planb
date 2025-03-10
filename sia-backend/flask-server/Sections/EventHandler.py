from flask_login import current_user
from globals import app
from flask import Response, json, render_template, jsonify, request, abort
from permissions import require_permissions, hasPermissions
from database import *
from forms import *
from flask import current_app
from datetime import timedelta, timezone
from sqlalchemy import func


def format_datetime(dt):
    return dt.strftime('%Y-%m-%d %H:%M') if dt else None

def format_datetime_hr(dt):
    return dt.strftime('%d.%m.%Y %H:%M') if dt else None

def format_endtime(dt):
    return dt.strftime('%H:%M') if dt else None

def event_append(events,event,duty_count,shift_count,individuals_count,personal_count):
    events.append({
        "id": event.id,
        "name": event.name,
        "uid": event.uid,
        "place": event.place,
        "visibility": event.visibility,
        "date": format_datetime_hr(event.date),
        "end": format_endtime(event.end),
        "description": event.description,
        "duty_count": duty_count,
        "shift_count": shift_count,
        "tasks": "0",
        "individuals_count":individuals_count,
        "personal_count":personal_count,
    })
    return events

def getAllEvents() -> list[Tables.Event]:
    td12 = timedelta(hours=12)
    today = datetime.now(timezone.utc)
    today -= td12
    event_list = Tables.Event.query.filter(Tables.Event.date >= today).order_by(Tables.Event.date.asc()).all()
    event_data = []
    for event in event_list:
        duty_count = db.session.query(Tables.Duty).join(Tables.Shift).filter(Tables.Shift.event == event.id).count()
        shift_count = Tables.Shift.query.filter_by(event=event.id).count()
        registrationManager = Tables.RegisterManager.query.filter_by(eventFK=event.id).first()

        individuals_count = (
            db.session.query(func.count(func.distinct(Tables.Duty.user)))
            .join(Tables.Shift)
            .filter(Tables.Shift.event == event.id)
            .scalar()
        )
        if current_user.is_authenticated:
            personal_count = (
                db.session.query(func.count(Tables.Duty.id))
                .join(Tables.Shift)
                .filter(Tables.Shift.event == event.id)
                .filter(Tables.Duty.user == current_user.id)
                .scalar()
            )
            registrations = Tables.Registration.query.filter_by(rmFK=registrationManager.rmFK,userFK=current_user.id).first()
        else:
            personal_count=None
            registrations=None

        if event.visibility=="public": 
            event_append(event_data,event,duty_count,shift_count,individuals_count,personal_count,registrationManager,registrations)
        if event.visibility=="member" and hasPermissions("events.member"):
            event_append(event_data,event,duty_count,shift_count,individuals_count,personal_count,registrationManager,registrations)
        if event.visibility=="private" and hasPermissions("events.private"):
            event_append(event_data,event,duty_count,shift_count,individuals_count,personal_count,registrationManager,registrations)
    return event_data


'''
 _____             _            
|  __ \           | |           
| |__) |___  _   _| |_ ___  ___ 
|  _  // _ \| | | | __/ _ \/ __|
| | \ \ (_) | |_| | ||  __/\__ \
|_|  \_\___/ \__,_|\__\___||___/                          
'''


@app.route("/events", methods=['GET'])
def events():
    return render_template('events.html', title='Sia-PlanB.de', events=getAllEvents(), hasPermissions=hasPermissions)

@app.route("/eventmanager", methods=['GET'])
@require_permissions("eventmanager.show")
def eventmanager():
    return render_template('eventmanager.html', title='Sia-PlanB.de', events=getAllEvents())


'''
   _____ _    _ _____ ______ _______ _____ 
  / ____| |  | |_   _|  ____|__   __/ ____|
 | (___ | |__| | | | | |__     | | | (___  
  \___ \|  __  | | | |  __|    | |  \___ \ 
  ____) | |  | |_| |_| |       | |  ____) |
 |_____/|_|  |_|_____|_|       |_| |_____/ 
                                                      
'''
    
# Get shifts of an event
@app.route("/api/events/event/<int:eventid>/getshifts", methods=['GET'])
def apiGetEventShift(eventid: int):
    if hasPermissions(f"/api/events/event/getshifts/{eventid}"):
        shifts = Tables.Shift.query.filter_by(event=eventid).all()
        if shifts:
            return jsonify([shift.getDict() for shift in shifts])
        else:
            return jsonify("")
    else:
        return Response(status=403)

# Add shift to an event
@app.route("/api/events/event/<int:eventid>/addshift", methods=['POST'])
def apiAddEventShift(eventid: int):
    if hasPermissions(f"/api/events/event/addshift/{eventid}"):
        form = Forms.newShiftForm()
        event = Tables.Event.query.filter_by(id=eventid).first_or_404()
        # TODO add input validation
        new_shift = Tables.Shift(
            event = event.id,
            type = form.type.data,
            start = form.start.data ,
            end = form.end.data
        )
        db.session.add(new_shift)
        db.session.commit()
        return jsonify({'success': True})
    else:
        return Response(status=403)
    
# Add shift to an event
@app.route("/api/events/event/delshift/<int:shiftid>", methods=['POST'])
def apiDeleteEventShift(shiftid: int):
    if hasPermissions(f"/api/events/event/delshift/{shiftid}"):
        Tables.Shift.query.filter_by(id=shiftid).delete()
        db.session.commit()
        return jsonify({'success': True})
    else:
        return Response(status=403)
    
@app.route("/api/events/event/joinshift/<shiftid>",methods=['POST'])
def apiJoinShift(shiftid: int):
    if hasPermissions(f"events.help"):
        existing_duty = Tables.Duty.query.filter_by(shift=shiftid,user=current_user.id).first()
        if not existing_duty:
            duty = Tables.Duty()
            duty.shift=shiftid
            duty.user=current_user.id
            duty. user_obj=current_user
            db.session.add(duty)
            db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route("/api/events/event/leaveshift/<shiftid>",methods=['POST'])
def apiLeaveShift(shiftid: int):
    if hasPermissions(f"events.help"):
        duty = Tables.Duty.query.filter_by(shift=shiftid,user=current_user.id).first()
        if duty:
            db.session.delete(duty)
        db.session.commit()
        return jsonify({'success': True})
    

    



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
    if hasPermissions(f"/api/events/event/{eventid}/newRM"):
        form = Forms.newRegistration()
        event = Tables.RegisterManager.query.filter_by(id=eventid).first_or_404()
        if event:
            if form.RegistrationAccept.data == "True":
                vis = True
            else:
                vis = False
            new_RM = Tables.Shift(
                eventFK = event.id,
                name = form.RegistrationName.data,
                start = form.RegistrationStart.data ,
                end = form.RegistrationEnd.data,
                visibility = form.RegistrationVisibility.data,
                accept = vis
            )
            db.session.add(new_RM)
            db.session.commit()
            return jsonify({'success': True, 'message' : 'Neue Registrierungsmöglichkeit angelegt.'})
    else:
        return jsonify({'success': False, 'message': "Dir fehlt die Berechtigung!"})

@app.route("/api/events/event/<int:eventid>/getRM", methods=['POST'])
@require_permissions("events.newRM")
def apiGetRM(eventid: int):
    if hasPermissions(f"/api/events/event/{eventid}/getRM"):
        registerManager = Tables.RegisterManager.query.filter_by(event=eventid).all()
        if registerManager:
            return jsonify([RM.getDict() for RM in registerManager])
        else:
            return jsonify({'success': True, 'message' : 'Alle Registrierungsmöglichkeiten wurden geladen'})
    else:
        return jsonify({'success': False, 'message': "Dir fehlt die Berechtigung!"})

@app.route("/api/events/event/<int:eventid>/updateRM/<int:rmID>", methods=['POST'])
@require_permissions("events.updateRM")
def apiUpdateRM(eventid: int,rmID: int):
    pass

@app.route("/api/events/event/<int:eventid>/deleteRM/<int:rmID>", methods=['POST'])
@require_permissions("events.delRM")
def apiDeleteRM(eventid: int,rmID: int):
    if hasPermissions(f"/api/events/event/{eventid}/deleteRM"):
        Tables.RegisterManager.query.filter_by(event=eventid).delete()
        db.session.commit()
        return jsonify({'success': True, 'message' : 'Registrierungsmöglichkeit wurde gelöscht'})
    else:
        return jsonify({'success': False, 'message': "Dir fehlt die Berechtigung!"})


@app.route("/api/events/event/<int:eventid>/register/<int:rmID>", methods=['POST'])
@require_permissions("events.register")
def apiRegisterEvent(eventid: int, rmID: int):
    
    registerManager = Tables.RegisterManager.query.filter_by(eventFK=eventid, id=rmID).first()

    
    current_time = datetime.now(timezone.utc)
    vis = registerManager.visibility
    rmID = registerManager.rmID
    
    if not registerManager:
        return jsonify({'success': False, 'errors': ["Keine Registrierung vorgesehen!"]}), 404
    
    existing_registration = Tables.Registration.query.filter_by(rmFK=registerManager.rmFK, userFK=current_user.id).first()
    if existing_registration:
        return jsonify({'success': False, 'errors': [f"Bereits angemeldet!"]})
   
    if registerManager.start:
        if current_time < registerManager.start:
            return jsonify({'success': False, 'errors': [f"Anmeldungen sind erst ab {current_time.astimezone().strftime('%d.%m.%y %H:%M')} möglich."]})
        
    if registerManager.end:
        if current_time > registerManager.end:
            return jsonify({'success': False, 'errors': [f"Anmeldungen sind seit {current_time.astimezone().strftime('%d.%m.%y %H:%M')} nicht mehr möglich."]})

    if vis == "public":
        return process_registration(eventid,rmID)
    
    if vis == "member":
        if hasPermissions("events.register.member"):
            return process_registration(eventid,rmID)
        else:
            abort(403, "Nur Mitglieder können sich für dieses Event anmelden!")

    if vis == "private":
        if hasPermissions("events.register.private"):
            return process_registration(eventid,rmID)
        else:
            abort(403, "Dieses Event benötigt 'private' Privilegien für eine Anmeldung.")
    
    return jsonify({'success': False, 'errors': ["Invalid event visibility type."]}), 400

def process_registration(eventid,rmID):

    new_registration = Tables.Registration(rmFK=rmID, userFK=current_user.id)
    db.session.add(new_registration)
    db.session.commit()

    return jsonify({'success': True, 'message': "Du wurdest erfolgreich für das Event angemeldet"})




@app.route("/api/events/event/<int:eventid>/unregister/<int:rmID>", methods=['POST'])
@require_permissions("events.unregister")
def apiUnregisterEvent(eventid: int, rmID: int):
    registerManager = Tables.RegisterManager.query.filter_by(eventFK=eventid, id=rmID).first()

    if not registerManager:
        return jsonify({'success': False, 'errors': ["Die Abmeldung war nicht möglich, da keine Registrierung (mehr) für das Event existiert!"]}), 404
    
    existing_registration = Tables.Registration.query.filter_by(rmFK=registerManager.rmFK, userFK=current_user.id).first()
    if not existing_registration:
        return jsonify({'success': False, 'errors': [f"Du warst nie angemeldet!"]})
    
    if existing_registration:
        db.session.delete(existing_registration)
        db.session.commit()

    return jsonify({'success': True, 'message': "Du wurdest erfolgreich für das Event angemeldet"})



'''
  ________      ________ _   _ _______ 
 |  ____\ \    / /  ____| \ | |__   __|
 | |__   \ \  / /| |__  |  \| |  | |   
 |  __|   \ \/ / |  __| | . ` |  | |   
 | |____   \  /  | |____| |\  |  | |   
 |______|   \/   |______|_| \_|  |_|   

'''

@app.route("/api/events/all", methods=['GET'])
@require_permissions("events.getall")
def apiGetAllEvents():
    return Response([event.toJSON() for event in getAllEvents()])

# Get event information
@app.route("/api/events/event/update/<int:eventid>", methods=['POST'])
def apiUpdateEvent(eventid: int):
    errors = []
    if hasPermissions(f"/api/events/event/update/{eventid}"):
        form = Forms.ChangeEventForm()
        event = db.session.query(Tables.Event).filter_by(id=eventid).first() #TODO auf GUID umbauen
        if form.validate_on_submit() and event:
            if form.name.data:
                event.name = form.name.data
            if form.visibility.data:
                event.visibility = form.visibility.data
            if form.place.data:
                event.place = form.place.data
            if form.description.data:
                event.description = form.description.data
            with app.app_context():
                if form.file.data:
                    form.file.data.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), current_app.root_path,"static", "images", "eventposter", str(event.id)))
            if form.date.data:
                if event.date != form.date.data and form.move_shifts.data and event.date:
                    difference = form.date.data - event.date
                    if event.end:
                        event.end += difference
                    shifts = Tables.Shift.query.filter_by(event=event.id).all()
                    for shift in shifts:
                        if shift.start:
                            shift.start += difference
                        if shift.end:
                            shift.end += difference
                else:
                    if form.event_end.data:
                        event.end = form.event_end.data
                event.date = form.date.data

            db.session.commit()
            return jsonify({'success': True})
        else:
            for field_name, field_errors in form.errors.items():
                print(f"Feld '{field_name}' hat folgende Fehler:")
                for error in field_errors:
                    print(f"  - {error}")
        for field, error_list in form.errors.items():
            for error in error_list:
                errors.append(f"{error}")
    errors.append("Permission missing")
    return jsonify({'success': False, 'errors': errors})

@app.route("/api/events/event/<int:eventid>", methods=['GET'])
def apiGetEvent(eventid: int):
    if hasPermissions(f"/api/events/event/{eventid}"):
        event = Tables.Event.query.join(
            Tables.User, Tables.Event.author == Tables.User.id
        ).with_entities(
            Tables.Event.id,
            Tables.Event.uid,
            Tables.Event.name,
            Tables.Event.visibility,
            Tables.Event.description,
            Tables.Event.place,
            Tables.Event.created,
            Tables.Event.date,
            Tables.Event.end,
            Tables.User.username,
        ).filter(Tables.Event.id == eventid).first()

        if not event:
            return Response(status=404)



        # Serialize manually
        event_data = {
            "id": event.id,
            "uid": str(event.uid),
            "name": event.name,
            "visibility": event.visibility,
            "description": event.description,
            "place": event.place,
            "created": format_datetime(event.created),
            "date": format_datetime(event.date),
            "end": format_datetime(event.end),
            "username": event.username,
        }

        return Response(json.dumps(event_data), mimetype='application/json')
    else:
        return Response(status=403)



    




