from wtforms import StringField, PasswordField, SubmitField, EmailField, IntegerField, SelectField, TextAreaField, DateField
from wtforms.validators import InputRequired, Length, ValidationError, EqualTo, Email, Optional
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
        role = SelectField(label="Rolle",choices=[] ,coerce=str, render_kw={"class": "form-select", "id": "inputRole"})
        #confirm_privacy_policy = SelectField(label="Rolle", choices=[(0, "Gast"), (1, "Student"), (2, "Sia-Mitglied"), (3, "Sia-Alumni")])
        #, EqualTo('password', message='Passwörter nicht gleich')

    class LoginForm(FlaskForm):
        username = StringField(render_kw={"placeholder": "Benutzername"})
        password = PasswordField(render_kw={"placeholder": "Passwort"})
        submit = SubmitField('Login')

    class ChangeData(FlaskForm):  #TODO validator Fehlen
        username = StringField(render_kw={"placeholder": "Benutzername"})
        password = PasswordField(render_kw={"placeholder": "Passwort"})
        password_confirm = PasswordField( render_kw={"placeholder": "Passwörter bestätigen"})
        submit = SubmitField('Ändern')
        surname = StringField(label="Vorname",render_kw={"placeholder": "Vorname"},default="")
        lastname = StringField(label="Nachname",render_kw={"placeholder": "Nachname"},default="")
        email = EmailField(render_kw={"placeholder": "Email"},default="")
        street = StringField(render_kw={"placeholder": "Straße"},default="")
        street_no = StringField(render_kw={"placeholder": "Nr"},default="")
        city = StringField( render_kw={"placeholder": "Stadt"},default="")
        postalcode = StringField(render_kw={"placeholder": "PLZ"},default="")

    class ContactForm(FlaskForm):
        category = SelectField(render_kw={"placeholder": "Art der Anfrage"},choices=[('kontakt', 'Kontakt'), ('mieten', 'Das Plan B Mieten'), ('feedback', 'Kritik/Lob'), ('events', 'Vorschlag für ein Event')])
        surname = StringField(render_kw={"placeholder": "Vorname"})
        lastname = StringField(render_kw={"placeholder": "Nachname"})
        email = StringField(render_kw={"placeholder": "Email"})
        message = TextAreaField(render_kw={"placeholder": "Nachricht"},validators=[Length(max=500)])
        submit = SubmitField('Senden')
        
    class EventForm(FlaskForm):
        name = StringField("Event Name", validators=[InputRequired(), Length(max=50)])
        visibility = StringField("Benötigte Berechtigung", validators=[Length(min=0, max=10)])
        place = StringField("Ort", validators=[Length(min=0, max=50)])
        date = DateField("Event Date", validators=[Optional()])
        description = StringField("Beschreibung", validators=[Length(min=0, max=200)])
        submit = SubmitField("Submit")
