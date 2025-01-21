from flask_login import current_user
from globals import app
from flask import Response, json, render_template, jsonify, request
from permissions import require_permissions, hasPermissions
from database import *

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
@app.route("/api/events/event/<int:eventid>", methods=['GET'])
def apiGetEvent(eventid: int):
    if hasPermissions(f"/api/events/event/{eventid}"):
        event = Tables.Event.query.filter_by(id=eventid).first_or_404()
        return Response(event.Json(), mimetype='application/json')
    else:
        return Response(status=403)
