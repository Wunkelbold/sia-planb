from wtforms import StringField, PasswordField, SubmitField, EmailField, IntegerField, SelectField, TextAreaField, DateField, HiddenField, DateTimeLocalField, BooleanField
from wtforms.validators import InputRequired, Length, ValidationError, EqualTo, Email, Optional, Regexp, DataRequired, StopValidation
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileSize
# from flask_uploads import UploadSet, IMAGES


class EmailRequiredIf(object):
    def __init__(self, **kwargs):
        self.conditions = kwargs

    def __call__(self, form, field):
        for key, values in self.conditions.items():
            form_field = getattr(form, key)  # Get the related form field

            # Ensure values is iterable (tuple or list)
            if not isinstance(values, (list, tuple)):
                values = [values]

            if form_field.data in values and not field.data:  # If condition matches but field is empty
                raise ValidationError(f"{field.label.text} muss angegeben werden wenn du {', '.join(values)} wählst.")

            if form_field.data in values:
                return  # Validation passed
            
        
class Forms:
    class RegisterForm(FlaskForm):
        username = StringField(
            render_kw={"placeholder": "Benutzername","autocomplete":"username"},
            validators=[
                InputRequired(),
                Length(
                    min=3, 
                    max=20, 
                    message="Benutzername muss 3 bis 20 Zeichen lang sein.")])
        password = PasswordField(
            render_kw={"placeholder": "Passwort","autocomplete":"new-password"}, 
            validators=[
                InputRequired(),
                Length(
                    min=8, 
                    max=30, 
                    message="Das Passwort muss 8 bis 20 Zeichen lang sein."), 
                EqualTo('password_confirm', message='Passwörter sind nicht gleich.')])
        password_confirm = PasswordField(
            render_kw={"placeholder": "Passwörter bestätigen","autocomplete":"new-password"}, 
            validators=[
                InputRequired(),
                Length(
                    min=8, 
                    max=30, 
                    message="Das Passwort muss 8 bis 20 Zeichen lang sein.")])
        submit = SubmitField('Register')
        surname = StringField(
            label="Vorname",
            render_kw={"placeholder": "Vorname"}, 
            default="", 
            validators=[
                Optional(),
                    Length(
                        min=0, 
                        max=20, 
                        message="Dein Vorname darf maximal 20 Zeichen lang sein.")])
        lastname = StringField(
            label="Nachname",
            render_kw={"placeholder": "Nachname"}, 
            default="",
            validators=[
                Optional(),
                Length(
                    min=0, 
                    max=20, 
                    message="Dein Nachname darf maximal 20 Zeichen lang sein.")])
        email = EmailField(
            render_kw={"placeholder":"Ausweich-Email"}, 
            validators=[
                Optional(),
                Length(
                    min=0, 
                    max=30, 
                    message="Die Email darf maximal 30 Zeichen lang sein."),
                Email(message="Deine Email scheint keine Email zu sein.")]) #TODO edge cases überlegen
        hs_email = EmailField(
            render_kw={"placeholder": "Hochschul-Email (Nur als Student)"}, 
            validators=[
                Regexp(
                    ".+@hs-albsig\.de", 
                    message="Deine Email scheint keine HS-Email zu sein XXXXXXXXX@hs-albsig.de."),
                EmailRequiredIf(role=["Student"]),
                Length(
                    min=0, 
                    max=30, 
                    message="Die Email darf maximal 30 Zeichen lang sein."),
                Email(message="Deine Email scheint keine Email zu sein.")]) #TODO edge cases überlegen
        street = StringField(
            render_kw={"placeholder": "Straße"},
            default="", 
            validators=[
                Optional(),
                Length(
                    min=0, 
                    max=25, 
                    message="Der Straßenname darf maximal 25 Zeichen lang sein.")])
        street_no = StringField(
            render_kw={"placeholder": "Nr"},
            default="",
            validators=[
                Optional(),
                Length(
                    min=0, 
                    max=10, 
                    message="Die Straßennummer darf maximal 25 Zeichen lang sein.")])
        city = StringField(
            render_kw={"placeholder": "Stadt"},
            default="",
            validators=[
                Optional(),
                Length(
                    min=0, 
                    max=25, 
                    message="Der Stadtname darf maximal 25 Zeichen lang sein.")])
        postalcode = StringField(
            render_kw={"placeholder": "PLZ"},
            default="",
            validators=[
                Optional(),
                Length(
                    min=5, 
                    max=5, 
                    message="Deine Postleitzahl scheint nicht ins Format zu passen XXXXX."),
                Regexp(
                    r"[0-9]{5}", 
                    message="Deine Postleitzahl muss aus Zahlen bestehen.")])
        role = SelectField(
            label="Rolle",
            choices=[],
            coerce=str,
            render_kw={"id": "inputRole"})
        privacy_policy = BooleanField(
            validators=[
                InputRequired()]
        )

    class LoginForm(FlaskForm):
        username = StringField(
            render_kw={"placeholder": "Benutzername","autocomplete":"username"},
            validators=[
                InputRequired(),
                Length(
                    min=3, 
                    max=20, 
                    message="Benutzername muss 3 bis 20 Zeichen lang sein.")])
        password = PasswordField(
            render_kw={"placeholder": "Passwort","autocomplete":"current-password"},
            validators=[
                InputRequired(),
                Length(
                    min=8, 
                    max=30, 
                    message="Das Passwort muss 8 bis 20 Zeichen lang sein.")])
        submit = SubmitField('Login')

    class ChangeData(FlaskForm):  #TODO validator Fehlen
        username = StringField(
            render_kw={"placeholder": "Benutzername"},
            validators=[
                InputRequired(),
                Length(
                    min=3, 
                    max=20, 
                    message="Benutzername muss 3 bis 20 Zeichen lang sein.")])
        password = PasswordField(
            render_kw={"placeholder": "Passwort"},
            validators=[
                Optional(),
                Length(
                    min=8, 
                    max=30, 
                    message="Das Passwort muss 8 bis 20 Zeichen lang sein."), 
                EqualTo(
                    'password_confirm', 
                    message='Passwörter sind nicht gleich.')])
        password_confirm = PasswordField(
            render_kw={"placeholder": "Passwörter bestätigen"},
            validators=[
                Optional(),
                Length(
                    min=8, 
                    max=30, 
                    message="Das Passwort muss 8 bis 20 Zeichen lang sein."), 
                EqualTo(
                    'password',
                    message='Passwörter sind nicht gleich.')])
        submit = SubmitField('Ändern')
        surname = StringField(
            label="Vorname",
            render_kw={"placeholder": "Vorname"},
            default="",
            validators=[
                Optional(),
                Length(
                    min=0,
                    max=20,
                    message="Dein Vorname darf maximal 20 Zeichen lang sein.")])
        lastname = StringField(
            label="Nachname",
            render_kw={"placeholder": "Nachname"},
            default="",
            validators=[
                Optional(),
                Length(
                    min=0,
                    max=20,
                    message="Dein Nachname darf maximal 20 Zeichen lang sein.")])
        email = EmailField(
            render_kw={"placeholder":"Ausweich-Email"}, 
            validators=[
                Optional(),
                Length(
                    min=0, 
                    max=30, 
                    message="Die Email darf maximal 30 Zeichen lang sein."),
                Email(message="Deine Email scheint keine Email zu sein.")]) #TODO edge cases überlegen
        hs_email = EmailField(
            render_kw={"placeholder": "Hochschul-Email (Nur als Student)"}, 
            validators=[
                EmailRequiredIf(role=["Student"]),
                Optional(),
                Length(
                    min=0, 
                    max=30, 
                    message="Die Email darf maximal 30 Zeichen lang sein."),
                Email(message="Deine Email scheint keine Email zu sein."),
                Regexp(
                    "........@hs-albsig\.de", 
                    message="Deine Email scheint keine HS-Email zu sein XXXXXXXXX@hs-albsig.de.")]) #TODO edge cases überlegen
        street = StringField(
            render_kw={"placeholder": "Straße"},
            default="",
            validators=[
                Optional(),
                Length(
                    min=0,
                    max=25,
                    message="Der Straßenname darf maximal 25 Zeichen lang sein.")])
        street_no = StringField(
            render_kw={"placeholder": "Nr"},
            default="",
            validators=[
                Optional(),
                Length(
                    min=0,
                    max=10,
                    message="Die Straßennummer darf maximal 25 Zeichen lang sein.")])
        city = StringField(
            render_kw={"placeholder": "Stadt"},
            default="",
            validators=[
                Optional(),
                Length(
                    min=0,
                    max=25,
                    message="Der Stadtname darf maximal 25 Zeichen lang sein.")])
        postalcode = StringField(
            render_kw={"placeholder": "PLZ"},
            default="",
            validators=[
                Optional(),
                Length(
                    min=5,
                    max=5,
                    message="Deine Postleitzahl scheint nicht ins Format zu passen XXXXX."),
                Regexp(
                    r"[0-9]{5}",
                    message="Deine Postleitzahl muss aus Zahlen bestehen.")])
        role = SelectField(
            label="Rolle",
            choices=[],
            coerce=str,
            render_kw={"id": "inputRole"})

    class AdminChangeData(FlaskForm):  #TODO validator Fehlen
        username = StringField(
            render_kw={"placeholder": "Benutzername"},
            validators=[
                InputRequired(),
                Length(
                    min=3,
                    max=20,
                    message="Benutzername muss 3 bis 20 Zeichen lang sein.")])
        password = PasswordField(
            render_kw={"placeholder": "Passwort"},
            validators=[
                Optional(),
                Length(
                    min=8, 
                    max=30, 
                    message="Das Passwort muss 8 bis 20 Zeichen lang sein."), 
                EqualTo(
                    'password_confirm', 
                    message='Passwörter sind nicht gleich.')])
        password_confirm = PasswordField(
            render_kw={"placeholder": "Passwörter bestätigen"},
            validators=[
                Optional(),
                Length(
                    min=8, 
                    max=30, 
                    message="Das Passwort muss 8 bis 20 Zeichen lang sein.")])
        submit = SubmitField('Ändern')
        surname = StringField(
            label="Vorname",
            render_kw={"placeholder": "Vorname"}, 
            default="", 
            validators=[
                Optional(),
                Length(
                    min=0, 
                    max=20, 
                    message="Dein Vorname darf maximal 20 Zeichen lang sein.")])
        lastname = StringField(
            label="Nachname",
            render_kw={"placeholder": "Nachname"}, 
            default="",
            validators=[
                Optional(),
                Length(
                    min=0, 
                    max=20, 
                    message="Dein Nachname darf maximal 20 Zeichen lang sein.")])
        email = EmailField(
            render_kw={"placeholder":"Ausweich-Email"}, 
            validators=[
                Optional(),
                Length(
                    min=0, 
                    max=30, 
                    message="Die Email darf maximal 30 Zeichen lang sein."),
                Email(message="Deine Email scheint keine Email zu sein.")]) #TODO edge cases überlegen
        hs_email = EmailField(
            render_kw={"placeholder": "Hochschul-Email (Nur als Student)"}, 
            validators=[
                EmailRequiredIf(role="Student"),
                Length(
                    min=0, 
                    max=30, 
                    message="Die Email darf maximal 30 Zeichen lang sein."),
                Email(message="Deine Email scheint keine Email zu sein."),
                Regexp(
                    ".+@hs-albsig\.de", 
                    message="Deine Email scheint keine HS-Email zu sein XXXXXXXXX@hs-albsig.de.")]) #TODO edge cases überlegen
        street = StringField(
            render_kw={"placeholder": "Straße"},
            default="", 
            validators=[
                Optional(),
                Length(
                    min=0, 
                    max=25, 
                    message="Der Straßenname darf maximal 25 Zeichen lang sein.")])
        street_no = StringField(
            render_kw={"placeholder": "Nr"},
            default="",
            validators=[
                Optional(),
                Length(
                    min=0, 
                    max=10, 
                    message="Die Straßennummer darf maximal 25 Zeichen lang sein.")])
        city = StringField(
            render_kw={"placeholder": "Stadt"},
            default="", 
            validators=[
                Optional(),
                Length(
                    min=0, 
                    max=25, 
                    message="Der Stadtname darf maximal 25 Zeichen lang sein.")])
        postalcode = StringField(
            render_kw={"placeholder": "PLZ"},
            default="",
            validators=[
                Optional(),
                Length(
                    min=5, 
                    max=5, 
                    message="Deine Postleitzahl scheint nicht ins Format zu passen XXXXX."),
                Regexp(
                    r"[0-9]{5}", 
                    message="Deine Postleitzahl muss aus Zahlen bestehen.")])
        role = SelectField(
            label="Rolle",
            choices=[],
            coerce=str, 
            render_kw={ "id": "inputRole"})

    class ContactForm(FlaskForm):
        category = SelectField(
            render_kw={"placeholder": "Art der Anfrage"},
            choices=[('kontakt', 'Kontakt'), ('mieten', 'Location Mieten'), ('feedback', 'Kritik/Lob'), ('events', 'Wünsche für ein Event')], 
            validators=[
                Length(
                    min=1, 
                    max=20)])
        surname = StringField(
            render_kw={"placeholder": "Vorname"}, 
            validators=[
                EmailRequiredIf(category=["kontakt","mieten","events"]),
                Length(
                    min=0, 
                    max=20, 
                    message="Dein Vorname darf maximal 20 Zeichen lang sein.")])
        lastname = StringField(
            render_kw={"placeholder": "Nachname"}, 
            validators=[
                EmailRequiredIf(category=["kontakt","mieten","events"]),
                Length(
                    min=0, 
                    max=20, 
                    message="Dein Nachname darf maximal 20 Zeichen lang sein.")])
        email = StringField(
            render_kw={"placeholder": "Email"}, 
            validators=[
                EmailRequiredIf(category=["kontakt","mieten","events"]),
                Length(
                    min=0, 
                    max=30, 
                    message="Deine Email darf maximal 30 Zeichen lang sein."),
                Email(message="Deine Email scheint keine Email zu sein.")])
        message = TextAreaField(
            render_kw={"placeholder": "Nachricht"},
            validators=[
                InputRequired(),
                Length(
                    min=20,
                    max=500,
                    message="Deine Nachricht muss zwischen 20 und 500 Zeichen lang sein")])
        privacy_policy = BooleanField(
            validators=[
                InputRequired()]
        )
        submit = SubmitField('Senden')
        
    class EventForm(FlaskForm):
        name = StringField(
            render_kw={"placeholder": "Eventname"}, 
            validators=[
                InputRequired(), 
                Length(
                    max=50,
                    message="Beschreibung darf maximal 50 Zeichen lang sein.")])
        visibility = SelectField(
            label="Sichtbarkeit",
            choices=[("public","public"),("member","member"),("private","private")], 
            coerce=str, 
            render_kw={ "id": "visibility"})
        place = StringField(
            render_kw={"placeholder": "Ort"}, 
            validators=[
                Length(
                    min=0, 
                    max=50,
                    message="Beschreibung darf maximal 50 Zeichen lang sein.")])
        date = DateTimeLocalField(
            render_kw={"placeholder": "Start"}, 
            validators=[
                Optional()])
        event_end = DateTimeLocalField(
            render_kw={"placeholder": "Ende"}, 
            validators=[
                Optional()])
        description = TextAreaField(
            render_kw={"placeholder": "Beschreibung"}, 
            validators=[
                Length(
                    min=0, 
                    max=200,
                    message="Beschreibung darf maximal 200 Zeichen lang sein.")])
        file = FileField(
            render_kw={"placeholder": "Datei"}, 
            validators=[
                Optional(), 
                FileAllowed(["png", "jpg", "jpeg"]), 
                FileSize(5 * 1024 * 1024,message="Uploadlimit 5mb und bitte Seitenverhältnis 1:1")])
        submit = SubmitField("Neues Event")

    class contactDelete(FlaskForm):
        uid = HiddenField('UID', validators=[InputRequired()])

    class eventDelete(FlaskForm):
        uid = HiddenField('UID', validators=[InputRequired()])

    class ChangeEventForm(FlaskForm):
        name = StringField(
            render_kw={"placeholder": "Eventname"}, 
            validators=[
                InputRequired(), 
                Length(
                    max=50,
                    message="Beschreibung darf maximal 50 Zeichen lang sein.")])
        visibility = SelectField(
            label="Sichtbarkeit",
            choices=[("public","public"),("member","member"),("private","private")], 
            coerce=str, 
            render_kw={ "id": "visibility"})
        place = StringField(
            render_kw={"placeholder": "Ort"}, 
            validators=[
                Length(
                    min=0, 
                    max=50,
                    message="Beschreibung darf maximal 50 Zeichen lang sein.")])
        date = DateTimeLocalField(
            render_kw={"placeholder": "Start"}, 
            validators=[Optional()])
        event_end = DateTimeLocalField(
            render_kw={"placeholder": "Ende"}, 
            validators=[
                Optional()])
        description = TextAreaField(
            render_kw={"placeholder": "Beschreibung"}, 
            validators=[
                Length(
                    min=0, 
                    max=200,
                    message="Beschreibung darf maximal 200 Zeichen lang sein.")])
        file = FileField(
            render_kw={"placeholder": "Datei"}, 
            validators = [
                Optional(), 
                FileSize(5 * 1024 * 1024,message="Uploadlimit 5mb und bitte Seitenverhältnis 1:1")])
        move_shifts =  BooleanField(default="True")
        submit = SubmitField("Event ändern")

    class newShiftForm(FlaskForm):
        type = StringField(
            render_kw={"placeholder": "Schichtbezeichnung"}, 
            validators=[
                InputRequired(), 
                Length(
                    max=20,
                    message="Beschreibung darf maximal 20 Zeichen lang sein.")])
        start = DateTimeLocalField(
            render_kw={"placeholder": "Start"}, 
            validators=[Optional()])
        end = DateTimeLocalField(
            render_kw={"placeholder": "Ende"}, 
            validators=[Optional()])
        submit = SubmitField("Neue Schicht")

    class newRegistration(FlaskForm):
        RegistrationName = StringField(
            render_kw={"placeholder": "Name der Anmeldung"}, 
            validators=[
                InputRequired(), 
                Length(
                    max=30,
                    message="Name darf maximal 30 Zeichen lang sein.")])
        RegistrationStart = DateTimeLocalField(
            render_kw={"placeholder": "Start"}, 
            validators=[EmailRequiredIf(RegistrationAccept=["Zeitraum"])])
        RegistrationEnd = DateTimeLocalField(
            render_kw={"placeholder": "Ende"}, 
            validators=[EmailRequiredIf(RegistrationAccept=["Zeitraum"])])
        RegistrationVisibility = SelectField(
            validators=[InputRequired()],
            label="Sichtbarkeit",
            choices=[("public","public"),("member","member"),("private","private")], 
            coerce=str, 
            render_kw={ "id": "RegistrationVisibility"})
        RegistrationAccept = SelectField(
            validators=[InputRequired()],
            label="Sichtbarkeit",
            choices=[("Zeitraum","Zeitraum"),("geöffnet","geöffnet"),("geschlossen","geschlossen")], 
            coerce=str, 
            render_kw={ "id": "RegistrationAccept"})
        RegistrationSubmit = SubmitField("Neue Anmeldung")
        



