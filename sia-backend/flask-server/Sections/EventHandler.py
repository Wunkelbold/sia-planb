from flask_login import current_user
from globals import app
from flask import Response, json, render_template, jsonify, request
from permissions import require_permissions, hasPermissions
from database import *
from forms import *
from flask import current_app

def getAllEvents() -> list[Tables.Event]:
    return Tables.Event.query.all()

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
            return Response([shift.toJson() for shift in shifts], mimetype='application/json')
        else:
            return Response(status=404)
    else:
        return Response(status=403)

# Add shift to an event
@app.route("/api/events/event/<int:eventid>/addshift", methods=['POST'])
def apiAddEventShift(eventid: int):
    if hasPermissions(f"/api/events/event/addshift/{eventid}"):
        event = Tables.Event.query.filter_by(id=eventid).first_or_404()

        data = request.json
        # TODO add input validation
        new_shift = Tables.Shift(
            user = current_user.id,
            event = event.id,
            type = data["eventType"],
            start = data["eventStart"],
            end = data["eventEnd"]
        )

        db.session.add(new_shift)
        db.session.commit()
        return Response(status=200)
    else:
        return Response(status=403)
# Add shift to an event
@app.route("/api/events/event/<int:eventid>/delshift", methods=['POST'])
def apiDeleteEventShift(shiftid: int):
    if hasPermissions(f"/api/events/event/delshift/{shiftid}"):
        Tables.Event.query.filter_by(id=shiftid).delete()
        db.session.commit()
        return Response(status=200)
    else:
        return Response(status=403)
    
# Get event information
@app.route("/api/events/event/update/<int:eventid>", methods=['POST'])
def apiUpdateEvent(eventid: int):
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
    errors = []
    for field, error_list in form.errors.items():
        for error in error_list:
            errors.append(f"{error}")

    return jsonify({'success': False, 'errors': errors})  # JSON-Antwort mit Fehlern






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


