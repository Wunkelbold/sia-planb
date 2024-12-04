from globals import app
from flask import render_template, jsonify
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
    return jsonify(getAllEvents())

@app.route("/api/events/get/<int:eventid>", methods=['GET'])
def apiGetEvent(eventid: int):
    if hasPermissions(f"/api/events/get/{eventid}"):
        event = Tables.Event.query.filter_by(id=eventid).first_or_404()
        return jsonify(event, mimetype='application/json')
    else:
        return app.login_manager.unauthorized()
