from wtforms import StringField, PasswordField, SubmitField, EmailField, IntegerField, SelectField
from wtforms.validators import InputRequired, Length, ValidationError, EqualTo, Email
from flask_wtf import FlaskForm

class Forms:
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
        role = SelectField(label="Rolle",choices=["Gast", "Student", "Sia Alumni", "Mitglied aktiv", "Moderator", "Admin"] ,coerce=str, render_kw={"class": "form-select", "id": "inputRole"})
        #confirm_privacy_policy = SelectField(label="Rolle", choices=[(0, "Gast"), (1, "Student"), (2, "Sia-Mitglied"), (3, "Sia-Alumni")])
        #, EqualTo('password', message='Passwörter nicht gleich')

    class LoginForm(FlaskForm):
        username = StringField(render_kw={"placeholder": "Benutzername"})
        password = PasswordField(render_kw={"placeholder": "Passwort"})
        submit = SubmitField('Login')


    class ChangeData(FlaskForm):
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

