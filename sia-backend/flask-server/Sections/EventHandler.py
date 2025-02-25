from flask_login import current_user
from globals import app
from flask import Response, json, render_template, jsonify, request
from permissions import require_permissions, hasPermissions
from database import *
from forms import *
from flask import current_app

def event_append(events,event,duty_count,shift_count):
    events.append({
        "id": event.id,
        "name":event.name,
        "uid": event.uid,
        "place":event.place,
        "date":event.date,
        "description":event.description,
        "duty_count": duty_count,
        "shift_count": shift_count
    })
    return events

def getAllEvents() -> list[Tables.Event]:
    event_list = Tables.Event.query.all()  # Fetch all events
    event_data = []
    for event in event_list:
        duty_count = db.session.query(Tables.Duty).join(Tables.Shift).filter(Tables.Shift.event == event.id).count()
        shift_count = Tables.Shift.query.filter_by(event=event.id).count()
        if event.visibility=="public": 
            event_append(event_data,event,duty_count,shift_count)
        if event.visibility=="member" and hasPermissions("events.member"):
            event_append(event_data,event,duty_count,shift_count)
        if event.visibility=="private" and hasPermissions("events.private"):
            event_append(event_data,event,duty_count,shift_count)
    return event_data


@app.route("/events", methods=['GET'])
def events():
    return render_template('events.html', title='Sia-PlanB.de', events=getAllEvents(), hasPermissions=hasPermissions)

@app.route("/eventmanager", methods=['GET'])
@require_permissions("eventmanager.show")
def eventmanager():
    return render_template('eventmanager.html', title='Sia-PlanB.de', events=getAllEvents())

@app.route("/api/events/all", methods=['GET'])
@require_permissions("events.getall")
def apiGetAllEvents():
    return Response([event.toJSON() for event in getAllEvents()])
    
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
            Tables.User.username,
        ).filter(Tables.Event.id == eventid).first()

        if not event:
            return Response(status=404)

        def format_datetime(dt):
            return dt.strftime('%Y-%m-%dT%H:%M') if dt else None

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
            "username": event.username,
        }

        return Response(json.dumps(event_data), mimetype='application/json')
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



