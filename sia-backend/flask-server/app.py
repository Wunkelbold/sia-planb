from globals import *
from flask import Flask, Blueprint, flash, jsonify, render_template, request, send_from_directory, url_for, redirect
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_user import roles_required
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Table, Column, MetaData, Integer, Computed, func
from http import HTTPStatus
import os
import psycopg2
from datetime import datetime
import random
import secrets
from functools import wraps
#-----FILES-----
from config import Config
from database import Tables, DAO
from forms import Forms
from permissions import *

app.config.from_object(Config)
db.init_app(app)
bcrypt = Bcrypt(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Tables.User.query.get(int(user_id))

Database = DAO
with app.app_context():
    DAO.init()

@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for('login'))

#-------LOGIN-ROUTES--------
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = Forms.RegisterForm()
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
                new_Role = Tables.Role(name=form.role.data, permissions=["adminpanel.show"]) # TODO create roles somewhere else
                new_user = Tables.User(
                    username = username,
                    password = hashed_password,
                    register_date = "", 
                    last_login = "",
                    surname = form.surname.data,
                    lastname = form.lastname.data,
                    email = form.email.data,
                    street = form.street.data,
                    street_no = form.street_no.data,
                    city = form.city.data,
                    postalcode = form.postalcode.data,
                    role = new_Role.name,
                    permissions = [],
                    last_updated = ""
                    )
                new_user.register_date = now
                new_user.last_updated = now
                new_user.last_login = now #TODO ungewöhnlicher Fall aber register != login
                db.session.add(new_Role)
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user)
                return redirect(url_for('login'))
            else:
                print(form.errors)  # Debugging: Show validation errors
                flash('Form submission failed. Check your input.', 'error')
    
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = Forms.LoginForm()
    if form.username.data:
        username = form.username.data.lower()
        if form.validate_on_submit():
            user = Tables.User.query.filter_by(username=username).first()
            if user:
                print(f"Username: {user.username}")
                print(f"Role: {user.role}")

                if bcrypt.check_password_hash(user.password, form.password.data):
                    login_user(user)
                    current_user.last_login = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    db.session.commit()
                    return redirect(url_for('index'))
                else:
                    flash('Passwort falsch', 'error')
            else:
                flash(f'Benutzer existiert nicht, <a href="{url_for("register")}">registriere dich zuerst!</a>', 'error')
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

@app.route("/admin",methods=['GET'])
@require_permissions("adminpanel.show")
def admin():
    users=Database.get_all_users()
    contacts = Tables.Contact.query.all()
    return render_template('admin.html', title='Sia-PlanB.de', users=users, contacts=contacts)


@app.route("/eventmanager",methods=['GET'])
@require_permissions("eventmanager.show")
def eventmanager():
    events=Database.get_all_events()
    return render_template('eventmanager.html', title='Sia-PlanB.de',events=events)

@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static/images'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route("/slider/<name>")
def slider(name):
    image_dir = os.path.join(app.root_path, 'static/images/slider/')
    file_path = os.path.join(image_dir, name)
    if not os.path.exists(file_path):
        name = "placeholder.png"  
    return send_from_directory(image_dir, name)

@app.route("/",methods=['GET'])
def index():
    events=Database.get_all_events()
    return render_template('index.html', title='Sia-PlanB.de', events=events)

@app.route("/contact", methods=['GET', 'POST'])
def contact():
    form = Forms.ContactForm()
    if form.is_submitted():
        print("---New Contact Form Submit!---")
        newContact = Tables.Contact(
            category = form.category.data,
            surname = form.surname.data,
            lastname = form.lastname.data,
            email = form.email.data,
            message = form.message.data,
            created = datetime.now()
        )
        db.session.add(newContact)
        db.session.commit()
        flash("Danke für deine Nachricht!")
    if current_user.is_authenticated:
        if current_user.email: form.email.data=current_user.email 
        if current_user.surname: form.surname.data=current_user.surname 
        if current_user.lastname: form.lastname.data=current_user.lastname
    return render_template('contact.html', title='Sia-PlanB.de', form=form)

@app.route("/datenschutz",methods=['GET'])
def datenschutz():
    return render_template('datenschutz.html', title='Sia-PlanB.de')

@app.route("/faq",methods=['GET'])
def faq():
    return render_template('faq.html', title='Sia-PlanB.de')

@app.route("/events",methods=['GET'])
def events():
    events=Database.get_all_events()
    return render_template('events.html', title='Sia-PlanB.de',events=events)

@app.route("/impressum",methods=['GET'])
def impressum():
    return render_template('impressum.html', title='Sia-PlanB.de')


@app.route("/newsletter",methods=['GET'])
def newsletter():
    return render_template('newsletter.html', title='Sia-PlanB.de')

@app.route("/profile",methods=['GET','POST'])
@login_required
def profile():
    form = Forms.ChangeData()
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
        if form.surname.data:
            user.surname = form.surname.data
        if form.lastname.data:
            user.lastname = form.lastname.data
        if form.email.data:
            user.email = form.email.data
        if form.street.data:
            user.street = form.street.data
        if form.street_no.data:
            user.street_no = form.street_no.data
        if form.city.data:
            user.city = form.city.data
        if form.postalcode.data:
            user.postalcode = form.postalcode.data
        user.last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.session.commit()
        flash('Daten geändert', 'info')
    if current_user.is_authenticated: #eigentlich unnötig da Profile nicht sichtbar ist für Anonyme User
        if current_user.username: form.username.data=current_user.username 
        form.password.data=""
        form.password_confirm.data=""
        if current_user.surname: form.surname.data=current_user.surname # Man weiß ja nie und lieber auf Nummer sicher
        if current_user.email: form.email.data=current_user.email  
        if current_user.lastname: form.lastname.data=current_user.lastname
        if current_user.email: form.email.data=current_user.email 
        if current_user.street: form.street.data=current_user.street 
        if current_user.city: form.city.data=current_user.city 
        if current_user.street_no: form.street_no.data=current_user.street_no 
        if current_user.postalcode: form.postalcode.data=current_user.postalcode 
        role=current_user.role if current_user.role else ""
    return render_template('profile.html', title='Sia-PlanB.de',form=form,role=role)

@app.route("/verein",methods=['GET'])
def verein():
    return render_template('verein.html', title='Verein')

if __name__ == "__main__":
    app.run(host='0.0.0.0')


