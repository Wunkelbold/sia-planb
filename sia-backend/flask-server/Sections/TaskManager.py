from flask_login import current_user, login_required
from globals import app
from flask import Response, json, render_template, jsonify, request, abort
from permissions import require_permissions, hasPermissions
from database import *
from forms import *
from flask import current_app
from datetime import timedelta, timezone, datetime
from sqlalchemy import func
from zoneinfo import ZoneInfo



@app.route("/api/task/get/single/<int:taskID>", methods=['GET'])
@require_permissions("task.get")
def apiTaskGetSingle(taskID: int):
    Task = Tables.Task.query.filter_by(id=taskID).first()
    if Task:
        return jsonify(Task.getDict())
    else:
        return jsonify({'success': False, 'error': { "Fehler":["Aufgabe konnte nicht geladen werden."]}})


@app.route("/api/task/get/<int:eventID>", methods=['GET'])
@require_permissions("task.get")
def apiTaskGetEvent(eventID: int):
    # Permission will be checked at the end of
    Task = Tables.Task.query.filter_by(eventFK=eventID).all()
    taskList = []
    if Task:
        for t in Task:

            tDict = t.getDict()

            if (
                tDict["visibility"] == "public" or
                (tDict["visibility"] == "private" and hasPermissions("task.help.private")) or
                (tDict["visibility"] == "student" and hasPermissions("task.help.student")) or
                (tDict["visibility"] == "member" and hasPermissions("task.help.member"))
            ):
                taskList.append(tDict)

        return jsonify(taskList)
    else:
        return jsonify({'success': False, 'error': { "Erfolg":["Es gibt keine Aufgaben für dieses Event."]}})

@app.route("/api/task/new/<int:eventID>", methods=['POST'])
@require_permissions("task.new")
def apiTaskNewEvent(eventID: int):
    form = Forms.newTask()
    newTask = Tables.Task(
        eventFK = eventID,
        authorFK = current_user.id,
        name = form.TaskName.data,
        description = form.TaskDescription.data,
        status = form.TaskStatus.data,
        priority = form.TaskPriority.data,
        visibility = form.TaskVisibility.data,
        deadline = form.TaskDeadline.data,
        created = datetime.now(),
        timeframe_start = form.TaskStart.data,
        timeframe_end = form.TaskEnd.data,
    )
    db.session.add(newTask)
    db.session.commit()
    return jsonify({'success': True, 'message' : { "Erfolg":["Neue Aufgabe wurde angelegt."]}})

@app.route("/api/task/new", methods=['POST'])
@require_permissions("task.new")
def apiTaskNew():
    form = Forms.newTask()
    newTask = Tables.Task(
        authorFK = current_user.id,
        name = form.TaskName,
        description = form.TaskDescription,
        status = form.TaskStatus,
        priority = form.TaskPriority,
        visibility = form.TaskVisibility,
        deadline = form.TaskDeadline,
        created = datetime.now(),
        timeframe_start = form.TaskStart,
        timeframe_end = form.TaskEnd,
    )
    db.session.add(newTask)
    db.session.commit()
    return jsonify({'success': True, 'message' : { "Erfolg":['Neue Registrierungsmöglichkeit angelegt.']}})

@app.route("/api/task/delete/<int:taskID>", methods=['POST'])
@require_permissions("task.delete")
def apiTaskDelete(taskID: int):
    if hasPermissions("task.delete"):
        Tables.Task.query.filter_by(id=taskID).delete()
        db.session.commit()
        return jsonify({'success': True, 'message' : { "Erfolg":'Aufgabe wurde gelöscht'}})
    else:
        return jsonify({'success': False, 'error': { "Fehler":"Dir fehlt die Berechtigung 'task.delete'!"}})

@app.route("/api/task/edit/<int:taskID>", methods=['POST'])
@require_permissions("task.edit")
def apiTaskEdit(taskID: int):
    form = Forms.newTask()
    current_task = Tables.Task.query.filter_by(id=taskID).first()
    if form.validate_on_submit() and current_task:
        current_task.name = form.TaskName.data,
        current_task.description = form.TaskDescription.data,
        current_task.status = form.TaskStatus.data,
        current_task.priority = form.TaskPriority.data,
        current_task.visibility = form.TaskVisibility.data,
        current_task.deadline = form.TaskDeadline.data,
        current_task.timeframe_start = form.TaskStart.data,
        current_task.timeframe_end = form.TaskEnd.data,
        db.session.commit()
        return jsonify({'success': True, 'message' : { "Erfolg":['Aufgabe wurde geändert']}})

    else:
        error=form.errors
        return jsonify({'success': False, 'error' : error})
    


@app.route("/api/task/help/<int:userID>", methods=['POST'])
@require_permissions("task.edit")
def apiTaskHelpEdit(userID: int):
    pass

@app.route("/api/task/help", methods=['POST'])
@require_permissions("task.help")
def apiTaskHelp():
    pass

@app.route("/api/task/unhelp/<int:userID>", methods=['POST'])
@require_permissions("task.edit")
def apiTaskUnhelpEdit(userID: int):
    pass

@app.route("/api/task/unhelp", methods=['POST'])
@require_permissions("task.unhelp")
def apiTaskUnhelp():
    pass