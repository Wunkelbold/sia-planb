from globals import *
from flask import make_response, Response, flash, render_template, request, send_from_directory, url_for, redirect, jsonify, get_flashed_messages, send_file
from flask_login import login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf.csrf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from http import HTTPStatus
import os
from datetime import datetime, timezone
from functools import wraps
import json
from io import BytesIO

#-----FILES-----
from database import Tables, init_database, init_roles, init_default_role
from forms import Forms
from permissions import *

#-----Load Sections-----

import Sections.EventHandler as _
from Sections.EventHandler import getAllEvents
import Sections.UserManager as _
import Sections.ContactManager as _
import Sections.RegistrationHandler as _
import Sections.TaskManager as _
from Sections.EmailHandler import *

csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Tables.User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for('login'))

def run_migrations():
    with app.app_context():
        print("--- Running migrations... ---")
        migrate(message="Auto migration")  # Equivalent to `flask db migrate`
        upgrade()  # Equivalent to `flask db upgrade`
        print("--- Migrations complete.  ---")

def format_datetime_hr(dt):
    local_tz = ZoneInfo("Europe/Berlin")
    locale.setlocale(locale.LC_ALL, 'de_DE.utf8')
    return dt.replace(tzinfo=local_tz).strftime('%a, %d/%m/%y %H:%M') if dt else None

if os.getenv('RUN_MIGRATIONS')=="true":
    run_migrations()




#-------LOGIN-ROUTES--------
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = Forms.RegisterForm()
    public_roles = Tables.Role.query.filter_by(selectable_on_register="yes").all()
    form.role.choices = [(role.name, role.name) for role in public_roles] #Nur manche Rollen sollen zur Auswahl stehen und choices hat dieses syntax
    if request.method == 'POST':
        c_hash = request.form.get('captcha-hash')
        c_text = request.form.get('captcha-text')
        if SIMPLE_CAPTCHA.verify(c_text, c_hash):
            if form.username.data:
                username = form.username.data.lower()
                existing_user_username = Tables.User.query.filter_by(username=username).first()
                if existing_user_username or not username.isalnum() or form.password.data != form.password_confirm.data:
                    if not username.isalnum():
                        flash('Nur Buchstaben und Zahlen im Benutzernamen', 'error')
                    if existing_user_username:
                        flash('Benutzername bereits vergeben', 'error')
                    #if username in manager.config.get_config("banned_usernames"): #TODO ADD BANNED CHARACTERS
                        #flash('- That username is not allowed. Please choose a different name.', 'error')
                    if form.password.data != form.password_confirm.data:
                        flash('Passwörter stimmen nicht überein', 'error')
                else:
                    if form.validate_on_submit():
                        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
                        if form.role.data in [role.name for role in public_roles]: #ansonsten kann der user "admin" außerhalb der Form pushen und ich ´hab kein bock ein custom form validaotr zu schreiben
                            role = form.role.data
                            if form.role.data == "Student" and form.hs_email.data or form.role.data != "Student" :
                                new_user = Tables.User(
                                    username = username,
                                    password = hashed_password,
                                    register_date = "", 
                                    last_login = "",
                                    surname = form.surname.data,
                                    lastname = form.lastname.data,
                                    email = form.email.data,
                                    hs_email = form.hs_email.data,
                                    street = form.street.data,
                                    street_no = form.street_no.data,
                                    city = form.city.data,
                                    postalcode = form.postalcode.data,
                                    role = role,
                                    permissions = [],
                                    last_updated = ""
                                    )
                                new_user.register_date = now
                                new_user.last_updated = now
                                new_user.last_login = now #TODO ungewöhnlicher Fall aber register != login
                                db.session.add(new_user)
                                db.session.commit()
                                login_user(new_user)
                                try:
                                    verify_email(new_user)
                                except:
                                    flash("Der Maildienst hat gerade keine Lust deine Mail zu verifizieren :(")
                                    app.logger.info('%s failed to verify email', new_user.username)
                            else:
                                flash("Als Student musst du deine HS_Mail angeben!")
                                return redirect(url_for('register'))

                            return redirect(url_for('index'))
                        else:
                            flash('Nice Try!', 'error')
                    else:
                        print(form.errors)  # Debugging: Show validation errors
                        flash('Etwas hat nicht gestimmt:', 'error')
        else:
            flash("Das Captcha ist falsch",'error')
    new_captcha_dict = SIMPLE_CAPTCHA.create()
    messages=form.errors
    return render_template('register.html', form=form, messages=messages, captcha=new_captcha_dict)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = Forms.LoginForm()
    if form.username.data:
        username = form.username.data.lower()
        if form.validate_on_submit():
            user = Tables.User.query.filter_by(username=username).first()
            if user:
                if bcrypt.check_password_hash(user.password, form.password.data):
                    login_user(user)
                    current_user.last_login = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    db.session.commit()
                    return redirect(url_for('index'))
                else:
                    flash('Passwort falsch', 'error')
            else:
                flash(f'Benutzer existiert nicht!', 'error')
        else:
                print(form.errors)  # Debugging: Show validation errors
                flash('Form submission failed. Check your input.', 'error')
        #TODO last_login = datetime.now() 
    return render_template('login.html', form=form)

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


#----------ROUTES---------
@app.route("/scanner", methods=['GET','POST'])
@require_permissions("scanner.show")
def scanner():
    if hasPermissions("scanner.show"): 
        if request.method == "POST":
            if request.data.userid:
                userid = request.data.userid
                user = Tables.User.query.filter_by(id=userid).first()
                if user:
                    registrations = Tables.Registration.query.filter_by(userFK=user.id).all()
                    if registrations:
                        return render_template('scanner.html', title='Sia-Scanner', registrations=registrations)
                    else:
                       return jsonify({'success': False, 'error': "User ist nirgends angemeldet."}) 
                else:
                   return jsonify({'success': False, 'error': "Kein User zur ID gefunden"}) 
            else:
                return jsonify({'success': False, 'error': "User ID wurde nicht gesendet"})
        return render_template('scanner.html', title='Sia-Scanner')
    else:
        return Response(status=403)

    

@app.route("/tickets", methods=['GET'])
@login_required
def tickets():
    user = Tables.User.query.filter_by(id=current_user.id).first()
    registrations = Tables.Registration.query.filter_by(userFK=current_user.id).all()
    registrationList = []
    if registrations:
        for rm in registrations:
            rm_dict = rm.getDict()
            rm_dict["price"] = rm.RegisterManager.price
            registrationList.append(rm_dict)
    if user:
        user_data = {
            "id": user.id,
            "username": user.username,
            "surname":user.surname ,
            "lastname":user.lastname ,
            "role":user.role ,
            "hs_email_confirmed":user.hs_email_confirmed,
            "uid":str(user.uid),
        }
        json_data = json.dumps(user_data)
        return render_template('tickets.html', title='Tickets', registrations=registrationList, qrcode_string=json_data)
    else:
        flash("Serverfehler")
        return render_template('tickets.html', title='Tickets',messages=get_flashed_messages)


    



@app.route("/admin", methods=['GET', 'POST'])
@require_permissions("adminpanel.show")
def admin():
    submitted=False
    form = Forms.EventForm()

    if form.is_submitted():
        if not hasPermissions("events.create"):
            return Response(status=403)
        
        if not form.validate():
            return make_response(form.errors, 400)
        
        submitted=True
        newEvent = Tables.Event(
            name = form.name.data,
            visibility = form.visibility.data,
            place = form.place.data,
            author = current_user.id,
            created = datetime.now(),
            date = form.date.data,
            end = form.event_end.data,
            description = form.description.data #,
            #postername = current_user.username
        )
        db.session.add(newEvent)
        db.session.commit()

        # TODO add check if file is actually an image 
        if form.file.data:
            form.file.data.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "images", "eventposter", str(newEvent.uid)))

    users = Tables.User.query.order_by(Tables.User.last_login.desc()).all()
    contacts = Tables.Contact.query.order_by(Tables.Contact.created.desc()).all() 
    contacts = [contact.getDict() for contact in contacts]
    timedelta12 = timedelta(days=1)
    today = datetime.now(timezone.utc)
    today -= timedelta12
    all_flag = request.args.get('all')
    if all_flag:
        eventlist = Tables.Event.query.order_by(Tables.Event.date.asc()).all()
    else:
        eventlist = Tables.Event.query.filter(Tables.Event.date >= today).order_by(Tables.Event.date.asc()).all()

    events = []

    def format_datetime(dt):
        return dt.strftime('%Y-%m-%d %H:%M') if dt else None
    
    for event in eventlist:
        authorname = (
            Tables.Event.query
            .join(Tables.User, Tables.Event.author == Tables.User.id) 
            .filter(Tables.Event.id == event.id)  
            .with_entities(Tables.User.username) 
            .scalar()
        )
        shift_filled_count = (
            db.session.query(func.count(func.distinct(Tables.Shift.id)))
            .join(Tables.Duty)
            .filter(Tables.Shift.event == event.id)
            .scalar()
        )
        individuals_count = (
            db.session.query(func.count(func.distinct(Tables.Duty.user)))
            .join(Tables.Shift)
            .filter(Tables.Shift.event == event.id)
            .scalar()
        )
        registration_count = (
            db.session.query(func.count(func.distinct(Tables.Registration.userFK)))
            .join(Tables.RegisterManager)
            .filter(Tables.RegisterManager.eventFK == event.id)
            .scalar()
        )
        duty_count = db.session.query(Tables.Duty).join(Tables.Shift).filter(Tables.Shift.event == event.id).count()
        shift_count = Tables.Shift.query.filter_by(event=event.id).count()
        task_count = Tables.Task.query.filter_by(eventFK=event.id).count()   
        rm_count = Tables.RegisterManager.query.filter_by(id=event.id).count()      
        events.append({
            "id": event.id,
            "name":event.name,
            "uid": event.uid,
            "username":authorname,
            "visibility":event.visibility,
            "place":event.place,
            "created":event.created,
            "date":format_datetime_hr(event.date),
            "end":format_datetime_hr(event.end),
            "description":event.description,
            "duty_count": duty_count,
            "shift_count": shift_count,
            "shift_filled_count":shift_filled_count,
            "task_count":task_count,
            "individuals_count":individuals_count,
            "rm_count":rm_count
        })
    
    '''
    events = Tables.Event.query.join(Tables.User, Tables.Event.author == Tables.User.id) \
        .with_entities(Tables.Event.id, Tables.Event.uid, Tables.Event.name, Tables.Event.visibility, Tables.Event.description, Tables.Event.place, Tables.Event.created, Tables.Event.date, Tables.User.username) \
        .order_by(Tables.Event.created.desc()).all()
    '''
    roles = Tables.Role.query.all()
    form_edit_user=Forms.AdminChangeData()
    form_edit_user.role.choices = [(role.name, role.name) for role in roles] 
    return render_template('admin.html', title='Sia-PlanB.de', events=events, users=users, contacts=contacts, submitted=submitted, form=Forms.EventForm(), form_edit_user=form_edit_user, form_edit_event=Forms.ChangeEventForm(), form_new_shift=Forms.newShiftForm(), form_new_registration=Forms.newRegistration(),form_new_task=Forms.newTask() )


@app.route("/slider/<name>")
def slider(name):
    image_dir = os.path.join(app.root_path, 'static/images/slider/')
    file_path = os.path.join(image_dir, name)
    if not os.path.exists(file_path):
        name = "placeholder.png"  
    return send_from_directory(image_dir, name)

@app.route("/",methods=['GET'])
def index():
    events=getAllEvents()
    return render_template('index.html', title='Sia-PlanB.de', events=events)

@app.route("/contact", methods=['GET', 'POST'])
def contact():
    form = Forms.ContactForm()
    if form.validate_on_submit():
        c_hash = request.form.get('captcha-hash')
        c_text = request.form.get('captcha-text')
        if SIMPLE_CAPTCHA.verify(c_text, c_hash):
            newContact = Tables.Contact(
                category = form.category.data,
                surname = form.surname.data,
                lastname = form.lastname.data,
                email = form.email.data,
                message = form.message.data,
                created = datetime.now(),
                creation = datetime.now()
            )
            db.session.add(newContact)
            db.session.commit()
            flash("Danke für deine Nachricht!")
        else:
            flash("Captcha Falsch!",'error')


    if current_user.is_authenticated:
        if current_user.email: form.email.data=current_user.email
        if current_user.hs_email: form.email.data=current_user.hs_email #Prefer HS_Mail
        if current_user.surname: form.surname.data=current_user.surname 
        if current_user.lastname: form.lastname.data=current_user.lastname
        if current_user.hs_email: form.email.data=current_user.hs_email
    messages=form.errors
    new_captcha_dict = SIMPLE_CAPTCHA.create()
    return render_template('contact.html', title='Sia-PlanB.de', form=form, messages=messages, captcha=new_captcha_dict)
        
@app.route("/datenschutz",methods=['GET'])
def datenschutz():
    return render_template('datenschutz.html', title='Sia-PlanB.de')

@app.route("/faq",methods=['GET'])
def faq():
    return render_template('under_construction.html', title='Sia-PlanB.de')

@app.route("/impressum",methods=['GET'])
def impressum():
    return render_template('impressum.html', title='Sia-PlanB.de')

@app.route("/newsletter",methods=['GET'])
def newsletter():
    return render_template('under_construction.html', title='Sia-PlanB.de')

@app.route("/profile",methods=['GET','POST'])
@login_required
def profile():
    form = Forms.ChangeData()
    public_roles = Tables.Role.query.filter_by(selectable_on_register="yes").all()
    user_role = Tables.Role.query.filter_by(name=current_user.role).first()
    public_roles.append(user_role)
    form.role.choices = [(role.name, role.name) for role in public_roles]
    user = db.session.query(Tables.User).filter_by(username=current_user.username).first()
    if request.method == "POST" and form.validate_on_submit():
        new_username = form.username.data.lower()
        if current_user.username != new_username:
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
            user.email_cooldown = datetime.min
        user.email = form.email.data
        if user.hs_email != form.hs_email.data:
            user.hs_email_confirmed = False
            user.hs_email_cooldown = datetime.min
        user.hs_email = form.hs_email.data
        user.street = form.street.data
        user.street_no = form.street_no.data
        user.city = form.city.data
        user.postalcode = form.postalcode.data
        if form.role.data in [role.name for role in public_roles]:
            user.role = form.role.data
        user.last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.session.commit()
        flash(f"Deine Daten wurden erfolgreich abgespeichert! {datetime.now().astimezone(local_tz).strftime('%H:%M')}", 'info')
        try:
            verify_email(current_user)
        except:
            flash("Der Maildienst hat gerade keine Lust deine Mail zu verifizieren :(")
            app.logger.info('%s failed to verify email', current_user.username)
    if current_user.is_authenticated: #eigentlich unnötig da Profile nicht sichtbar ist für Anonyme User
        if current_user.username: form.username.data=current_user.username 
        form.password.data=""
        form.password_confirm.data=""
        if current_user.surname: form.surname.data=current_user.surname # Man weiß ja nie und lieber auf Nummer sicher
        if current_user.email: form.email.data=current_user.email  
        if current_user.lastname: form.lastname.data=current_user.lastname
        if current_user.email: form.email.data=current_user.email 
        if current_user.hs_email: form.hs_email.data=current_user.hs_email 
        if current_user.street: form.street.data=current_user.street 
        if current_user.city: form.city.data=current_user.city 
        if current_user.street_no: form.street_no.data=current_user.street_no 
        if current_user.postalcode: form.postalcode.data=current_user.postalcode 
        role=current_user.role if current_user.role else ""
    messages=form.errors
    return render_template('profile.html', title='Sia-PlanB.de', form=form, role=role, messages=messages)

@app.route("/verein",methods=['GET'])
def verein():
    return render_template('verein.html', title='Verein')

@app.route("/location",methods=['GET'])
def location():
    return render_template('location.html', title='Plan B')


@app.route('/static/images/eventposter/<filename>')
def get_image(filename):
    image_path = os.path.join(current_app.root_path, 'static', 'images', 'eventposter', filename)

    if os.path.exists(image_path):
        return send_file(image_path)
    else:
        default_path = os.path.join(current_app.root_path, 'static', 'images', 'eventposter', 'default.jpg')
        return send_file(default_path) 
    
if __name__ == "__main__":
    app.run(host='0.0.0.0')
