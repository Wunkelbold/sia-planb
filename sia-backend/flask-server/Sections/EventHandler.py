from globals import app
from flask import render_template, jsonify
from permissions import require_permissions
from database import *

def getAllEvents() -> list[Tables.Event]:
    Tables.Event.query.all()

def getActiveEvents() -> list[Tables.Event]:
    return Tables.Event.query.filter_by(visibility=True).all()

@app.route("/events",methods=['GET'])
def events():
    return render_template('events.html', title='Sia-PlanB.de', events=getActiveEvents())

@app.route("/eventmanager",methods=['GET'])
@require_permissions("eventmanager.show")
def eventmanager():
    return render_template('eventmanager.html', title='Sia-PlanB.de', events=getAllEvents())

@app.route("/api/events/all",methods=['GET'])
@require_permissions("events.all")
def apiGetAllEvents():
    return jsonify(getAllEvents())