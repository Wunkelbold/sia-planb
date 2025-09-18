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
from globals import *
from flask import flash, url_for, redirect, jsonify
from icalendar import Calendar, Event
import secrets
import base64

def format_datetime(dt):
    return dt.strftime('%Y-%m-%d %H:%M') if dt else None

def format_datetime_hr(dt):
    local_tz = ZoneInfo("Europe/Berlin")
    locale.setlocale(locale.LC_ALL, 'de_DE.utf8')
    return dt.replace(tzinfo=local_tz).strftime('%a, %d/%m/%y %H:%M') if dt else None

def format_endtime(dt):
    return dt.strftime('%H:%M') if dt else None

def event_append(task_count,shift_filled_count,events,event,duty_count,shift_count,individuals_count,personal_count, registrationManager, show_register_button,personal_registration,registration_count):
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
        "individuals_count": individuals_count,
        "personal_count": personal_count,
        "registrationManager": registrationManager,
        "show_register_button": show_register_button,
        "personal_registration":personal_registration,
        "registration_count":registration_count,
        "shift_filled_count":shift_filled_count,
        "task_count":task_count
    })
    return events

def ensure_user_calendar_url(user):
    """Generate a calendar URL for user if they don't have one"""
    if not user.calendar_url:
        # Generate a random 32-character URL-safe string
        random_bytes = secrets.token_bytes(24)  # 24 bytes = 32 chars in base64
        calendar_url = base64.urlsafe_b64encode(random_bytes).decode('ascii').rstrip('=')
        user.calendar_url = calendar_url
        db.session.commit()
    return user.calendar_url



def getAllEvents() -> list[Tables.Event]:
    td12 = timedelta(hours=12)
    today = datetime.now(timezone.utc)
    today -= td12
    event_list = Tables.Event.query.filter(Tables.Event.date >= today).order_by(Tables.Event.date.asc()).all()
    event_data = []
    for event in event_list:
        duty_count = db.session.query(Tables.Duty).join(Tables.Shift).filter(Tables.Shift.event == event.id).count()
        shift_filled_count = (
            db.session.query(func.count(func.distinct(Tables.Shift.id)))
            .join(Tables.Duty)
            .filter(Tables.Shift.event == event.id)
            .scalar()
        )
        shift_count = Tables.Shift.query.filter_by(event=event.id).count()
        registrationManager = Tables.RegisterManager.query.filter_by(eventFK=event.id).all()

        #Logik, ob dem User der Anmeldebutton angezeigt wird oder nicht.
        show_register_button = False
        if current_user.is_authenticated:
            for rm_vis in registrationManager:
                if rm_vis.visibility == "private" and hasPermissions("events.private"):
                    show_register_button = True
                if rm_vis.visibility == "member" and hasPermissions("events.member"):
                    show_register_button = True
                if rm_vis.visibility == "student" and hasPermissions("events.student"):
                    show_register_button = True
                if rm_vis.visibility == "public":
                    show_register_button = True

            personal_count = (
                db.session.query(func.count(Tables.Duty.id))
                .join(Tables.Shift)
                .filter(Tables.Shift.event == event.id)
                .filter(Tables.Duty.user == current_user.id)
                .scalar()
            )

            personal_registration = (
                db.session.query(func.count(Tables.Registration.id))
                .join(Tables.RegisterManager)
                .filter(Tables.RegisterManager.eventFK == event.id)
                .filter(Tables.Registration.userFK == current_user.id)
                .scalar()
            )
            
            individuals_count = (
                db.session.query(func.count(func.distinct(Tables.Duty.user)))
                .join(Tables.Shift)
                .filter(Tables.Shift.event == event.id)
                .scalar()
            )

        else:
            personal_count = 0
            individuals_count = 0
            personal_registration = 0
        
        registration_count = (
            db.session.query(func.count(func.distinct(Tables.Registration.userFK)))
            .join(Tables.RegisterManager)
            .filter(Tables.RegisterManager.eventFK == event.id)
            .scalar()
        )
        task_count = Tables.Task.query.filter_by(eventFK=event.id).count()

        if event.visibility=="public": 
            event_append(task_count,shift_filled_count,event_data,event,duty_count,shift_count,individuals_count,personal_count,registrationManager,show_register_button,personal_registration,registration_count)
        if event.visibility=="member" and hasPermissions("events.member"):
            event_append(task_count,shift_filled_count,event_data,event,duty_count,shift_count,individuals_count,personal_count,registrationManager,show_register_button,personal_registration,registration_count)
        if event.visibility=="private" and hasPermissions("events.private"):
            event_append(task_count,shift_filled_count,event_data,event,duty_count,shift_count,individuals_count,personal_count,registrationManager,show_register_button,personal_registration,registration_count)
        if event.visibility=="student" and hasPermissions("events.student"):
            event_append(task_count,shift_filled_count,event_data,event,duty_count,shift_count,individuals_count,personal_count,registrationManager,show_register_button,personal_registration,registration_count)


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
    if current_user.is_authenticated:
        ensure_user_calendar_url(current_user)
    return render_template('events.html', title='Sia-PlanB.de', events=getAllEvents(), hasPermissions=hasPermissions)

@app.route("/events.ics", methods=['GET'])
def events_ical():
    # Get all public events from now onwards
    td12 = timedelta(hours=12)
    today = datetime.now(timezone.utc)
    today -= td12
    public_events = Tables.Event.query.filter(
        Tables.Event.date >= today,
        Tables.Event.visibility == "public"
    ).order_by(Tables.Event.date.asc()).all()

    # Create calendar
    cal = Calendar()
    cal.add('prodid', '-//Sia-PlanB Events//')
    cal.add('version', '2.0')
    cal.add('name', 'Sia-PlanB Public Events')
    cal.add('x-wr-calname', 'Sia-PlanB Public Events')

    for event in public_events:
        ical_event = Event()
        ical_event.add('summary', event.name)
        utc_date = event.date.replace(tzinfo=ZoneInfo("Europe/Berlin")).astimezone(timezone.utc)
        ical_event.add('dtstart', utc_date)
        if event.end:
            ical_event.add('dtend', event.end.replace(tzinfo=ZoneInfo("Europe/Berlin")).astimezone(timezone.utc))
        else:
            # Assume 1 hour duration if no end time specified
            ical_event.add('dtend', utc_date + timedelta(hours=1))
        if event.place:
            ical_event.add('location', event.place)
        if event.description:
            ical_event.add('description', event.description + "\n\n https://sia-planb.de/events")
        else:
            ical_event.add('description', "https://sia-planb.de/events")
        cal.add_component(ical_event)

    # Return as .ics file
    response = Response(cal.to_ical(), mimetype='text/calendar')
    response.headers['Content-Disposition'] = 'attachment; filename=events.ics'
    return response

@app.route("/calendar/<calendar_id>.ics", methods=['GET'])
def user_calendar_ical(calendar_id: str):
    # Find user by calendar URL
    user = Tables.User.query.filter_by(calendar_url=calendar_id).first()
    if not user:
        return Response(status=404)

    # Get user's role permissions
    user_role = Tables.Role.query.filter_by(name=user.role).first()
    if not user_role:
        return Response(status=404)

    user_permissions = set(user_role.permissions) if user_role.permissions else set()

    # Get events based on permissions
    td12 = timedelta(hours=12)
    today = datetime.now(timezone.utc)
    today -= td12

    # Build query based on permissions
    event_query = Tables.Event.query.filter(Tables.Event.date >= today)

    # Include events based on visibility permissions
    visibility_filters = []
    if "events.public" in user_permissions:
        visibility_filters.append(Tables.Event.visibility == "public")
    if "events.member" in user_permissions:
        visibility_filters.append(Tables.Event.visibility == "member")
    if "events.student" in user_permissions:
        visibility_filters.append(Tables.Event.visibility == "student")
    if "events.private" in user_permissions:
        visibility_filters.append(Tables.Event.visibility == "private")

    if visibility_filters:
        from sqlalchemy import or_
        event_query = event_query.filter(or_(*visibility_filters))

    events = event_query.order_by(Tables.Event.date.asc()).all()

    # Create calendar
    cal = Calendar()
    cal.add('prodid', '-//Sia-PlanB Personal Calendar//')
    cal.add('version', '2.0')
    cal.add('name', f'Sia-PlanB Calendar - {user.username}')
    cal.add('x-wr-calname', f'Sia-PlanB Calendar - {user.username}')

    for event in events:
        # Get user's shifts for this event
        user_shifts = (Tables.Shift.query
                      .join(Tables.Duty)
                      .filter(Tables.Shift.event == event.id)
                      .filter(Tables.Duty.user == user.id)
                      .order_by(Tables.Shift.start.asc())
                      .all())

        ical_event = Event()
        ical_event.add('summary', event.name)
        utc_date = event.date.replace(tzinfo=ZoneInfo("Europe/Berlin")).astimezone(timezone.utc)
        ical_event.add('dtstart', utc_date)
        if event.end:
            ical_event.add('dtend', event.end.replace(tzinfo=ZoneInfo("Europe/Berlin")).astimezone(timezone.utc))
        if event.place:
            ical_event.add('location', event.place)

        # Calculate shift availability for the event
        total_shifts = Tables.Shift.query.filter_by(event=event.id).count()
        filled_shifts = (db.session.query(func.count(func.distinct(Tables.Shift.id)))
                        .join(Tables.Duty)
                        .filter(Tables.Shift.event == event.id)
                        .scalar()) or 0

        # Build description with shifts
        description = event.description or ""
        if user_shifts:
            shift_lines = []
            for shift in user_shifts:
                if shift.start:
                    time_str = shift.start.strftime('%H:%M %d.%m')
                    shift_lines.append(f"{shift.type} - {time_str}")
                else:
                    shift_lines.append(f"{shift.type} - Time TBD")
            if shift_lines:
                description += "\n\nDeine Schichten:\n" + "\n".join(shift_lines)

        # Add shift availability info
        if total_shifts > 0:
            description += f"\n\nBelegte Schichten: {filled_shifts}/{total_shifts}"
        description += "\n\n https://sia-planb.de/events"

        if description:
            ical_event.add('description', description)
        ical_event.add('uid', str(event.uid))
        cal.add_component(ical_event)

    # Return as .ics file
    response = Response(cal.to_ical(), mimetype='text/calendar')
    response.headers['Content-Disposition'] = f'attachment; filename={user.username}_calendar.ics'
    return response

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
                    form.file.data.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), current_app.root_path,"static", "images", "eventposter", str(event.uid)))
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
    
@app.route("/delete_event", methods=['POST']) #TODO noch auf API Syntax umbauen
@require_permissions("adminpanel.event.delete")
def delete_event():
    form = Forms.eventDelete() #braucht man keine neue Form dafür
    if form.validate_on_submit():
        uid = form.uid.data
        event = db.session.query(Tables.Event).filter_by(uid=uid).first()
        if event:
            image_path = os.path.join(app.root_path, 'static', 'images', 'eventposter', 'default.jpg',str(event.uid))
            if os.path.exists(image_path):
                os.remove( os.path.join(app.root_path, 'static', 'images', 'eventposter', 'default.jpg',str(event.uid)))
            db.session.delete(event)
            db.session.commit()
        return redirect(url_for('admin'))
    else:
        return redirect(url_for('admin'))
