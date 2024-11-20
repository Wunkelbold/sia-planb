from flask import Flask, Blueprint, flash, jsonify, render_template, request, send_from_directory, url_for, redirect
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_user import roles_required
from flask_principal import Permission, RoleNeed, UserNeed
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Table, Column, MetaData, Integer, Computed
from wtforms import StringField, PasswordField, SubmitField, EmailField, IntegerField, SelectField
from wtforms.validators import InputRequired, Length, ValidationError, EqualTo, Email
from http import HTTPStatus
import os
import psycopg2
from datetime import datetime
from functools import wraps



import database

app = Flask(__name__)
app = Flask(__name__, template_folder='static/templates', static_folder='static')
app.config.from_object(__name__)
app.config["SQLALCHEMY_DATABASE_URI"]=os.getenv("DATABASE_URI")
app.config["SECRET_KEY"]=os.getenv("SECRET_KEY")  


db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
csrf = CSRFProtect(app)

#---------DATABASE--------

Database = database.DAO
Database.database_dump()

class Event(db.Model, UserMixin):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    visibility = db.Column(db.String(10))
    place = db.Column(db.String(50))
    author = db.Column(db.String(20), nullable=False)
    created = db.Column(db.TEXT)
    date = db.Column(db.TEXT)
    description = db.Column(db.String(200))
    postername = db.Column(db.String(50))

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    surname = db.Column(db.String(20))
    lastname = db.Column(db.String(20))
    street = db.Column(db.String(25))
    street_no = db.Column(db.String(25))
    password = db.Column(db.String(200))
    email = db.Column(db.String(30))
    city = db.Column(db.String(25))
    postalcode = db.Column(db.String(25))
    register_date = db.Column(db.TEXT)
    last_login = db.Column(db.TEXT)
    role = db.Column(db.Integer)

with app.app_context():
    db.create_all()

# legacy Database.database_init()
Database.database_fill()

#---------PERMISSIONS--------

def role_required(role):
    def decorator(func):
        @wraps(func)
        def decorated_function(*args, **kwargs):
            user = current_user
            if user.role >= role:
                return func(*args, **kwargs)
            else:
                return 'You do not have the required permission', 403
        return decorated_function
    return decorator

#---------LOGIN--------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for('login'))


#---------FORMS--------

class RegisterForm(FlaskForm):
    username = StringField(render_kw={"placeholder": "Benutzername"})
    password = PasswordField(render_kw={"placeholder": "Passwort"})
    password_confirm = PasswordField( render_kw={"placeholder": "Passwörter bestätigen"})
    submit = SubmitField('Register')
    surname = StringField(label="Vorname",render_kw={"placeholder": "Vorname"},default="")
    lastname = StringField(label="Nachname",render_kw={"placeholder": "Nachname"},default="")
    email = EmailField(render_kw={"placeholder": "Email"},default="")
    street = StringField(render_kw={"placeholder": "Straße"},default="")
    street_no = StringField(render_kw={"placeholder": "Nr"},default="")
    city = StringField( render_kw={"placeholder": "Stadt"},default="")
    postalcode = StringField(render_kw={"placeholder": "PLZ"},default="")
    role = SelectField(label="Rolle",choices=[("1", "Gast"),("2", "Student"),("3", "Sia Alumni"),("4", "Mitglied aktiv"),("5", "moderator"),("6", "admin")] ,coerce=str, render_kw={"class": "form-select", "id": "inputRole"})
    #confirm_privacy_policy = SelectField(label="Rolle", choices=[(0, "Gast"), (1, "Student"), (2, "Sia-Mitglied"), (3, "Sia-Alumni")])
    #, EqualTo('password', message='Passwörter nicht gleich')

class LoginForm(FlaskForm):
    username = StringField(render_kw={"placeholder": "Benutzername"})
    password = PasswordField(render_kw={"placeholder": "Passwort"})
    submit = SubmitField('Login')


#---TEST--DATABASE--CONN--
with app.app_context():
    print("DATABASETEST")
    password= bcrypt.generate_password_hash("3dE$N4U$7hfWkG7VK6bEQ*MW9").decode('utf-8')
    user1 = User(username="default",role=7,password=password)
    db.session.add(user1)
    db.session.commit()
    users = User.query.all()
    print(users)


@ app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.username.data:
        username = form.username.data.lower()
        existing_user_username = User.query.filter_by(username=username).first()
        if existing_user_username or not username.isalnum() or form.password.data != form.password_confirm.data:
            if not username.isalnum():
                flash('Nur Buchstaben und Zahlen im Benutzernamen', 'error')
            if existing_user_username:
                flash('Benutzername bereits vergeben', 'error')
            #if username in manager.config.get_config("banned_usernames"):
                #flash('- That username is not allowed. Please choose a different name.', 'error')
            if form.password.data != form.password_confirm.data:
                flash('Passwörter stimmen nicht überein', 'error')
        else:
            if form.validate_on_submit():
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
                new_user = User(username=username, password=hashed_password, register_date="", last_login="",surname=form.surname.data,lastname=form.lastname.data,email=form.email.data,street=form.street.data,street_no=form.street_no.data,city=form.city.data,postalcode=form.postalcode.data,role=form.role.data)
                new_user.register_date = now
                new_user.last_login = now
                db.session.add(new_user)
                db.session.commit()
                return redirect(url_for('login'))
            else:
                print(form.errors)  # Debugging: Show validation errors
                flash('Form submission failed. Check your input.', 'error')
            
    with app.app_context():
        print("ALL USERS")
        users = User.query.all()
        print(users)
    
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.username.data:
        username = form.username.data.lower()
        if form.validate_on_submit():
            user = User.query.filter_by(username=username).first()
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
    return render_template('login.html', form=form)

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


#----------ROUTES---------

@app.route("/admin",methods=['GET'])
@login_required
@role_required(6)
def admin():
    users=Database.get_all_users()
    return render_template('admin.html', title='Sia-PlanB.de', users=users)

@app.route("/eventmanager",methods=['GET'])
@login_required
@role_required(3)
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

@app.route("/contact",methods=['GET'])
def contact():
    return render_template('contact.html', title='Sia-PlanB.de')

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

@app.route("/profile",methods=['GET'])
def profile():
    return render_template('profile.html', title='Sia-PlanB.de')

@app.route("/verein",methods=['GET'])
def verein():
    return render_template('verein.html', title='Verein')

if __name__ == "__main__":
    app.run(host='0.0.0.0',debug=True)


