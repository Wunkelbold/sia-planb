from wtforms import StringField, PasswordField, SubmitField, EmailField, IntegerField, SelectField, TextAreaField, DateField, HiddenField
from wtforms.validators import InputRequired, Length, ValidationError, EqualTo, Email, Optional, Regexp
from flask_wtf import FlaskForm

class Forms:
    class RegisterForm(FlaskForm):
        username = StringField(render_kw={"placeholder": "Benutzername"},validators=[InputRequired(),
                                                                                     Length(min=3, max=20, message="Benutzername muss 3 bis 20 Zeichen lang sein.")])
        password = PasswordField(render_kw={"placeholder": "Passwort"}, validators=[
                                                                                    InputRequired(),
                                                                                    Length(min=8, max=30, message="Das Passwort muss 8 bis 20 Zeichen lang sein."), 
                                                                                    EqualTo('password_confirm', message='Passwörter sind nicht gleich.')])
        password_confirm = PasswordField( render_kw={"placeholder": "Passwörter bestätigen"}, validators=[
                                                                                                        InputRequired(),
                                                                                                        Length(min=8, max=30, message="Das Passwort muss 8 bis 20 Zeichen lang sein."), 
                                                                                                        EqualTo('password', message='Passwörter sind nicht gleich.')])
        submit = SubmitField('Register')
        surname = StringField(label="Vorname",render_kw={"placeholder": "Vorname"}, default="", validators=[Optional(),
                                                                                                            Length(min=0, max=30, message="Dein Vorname darf maximal 20 Zeichen lang sein.")])
        lastname = StringField(label="Nachname",render_kw={"placeholder": "Nachname"}, default="",validators=[Optional(),
                                                                                                              Length(min=0, max=30, message="Dein Nachname darf maximal 20 Zeichen lang sein.")])
        email = EmailField(render_kw={"placeholder": "Hochschul-Email"}, validators=[
                                                                                    InputRequired(),
                                                                                    Length(min=0, max=30, message="Die Email darf maximal 30 Zeichen lang sein."),
                                                                                    Email(message="Deine Email scheint keine Email zu sein."),
                                                                                    Regexp("........@hs-albsig\.de", message="Deine Email scheint keine HS-Email zu sein XXXXXXXXX@hs-albsig.de.")]) #TODO edge cases überlegen
        #TODO alumni email hinzufügen
        street = StringField(render_kw={"placeholder": "Straße"},default="", validators=[Optional(),
                                                                                        Length(min=0, max=25, message="Der Straßenname darf maximal 25 Zeichen lang sein.")])
        street_no = StringField(render_kw={"placeholder": "Nr"},default="",validators=[Optional(),
                                                                                       Length(min=0, max=25, message="Die Straßennummer darf maximal 25 Zeichen lang sein.")])
        city = StringField( render_kw={"placeholder": "Stadt"},default="", validators=[Optional(),
                                                                                        Length(min=0, max=25, message="Der Stadtname darf maximal 25 Zeichen lang sein.")])
        postalcode = StringField(render_kw={"placeholder": "PLZ"},default="",validators=[Optional(),
                                                                                        Optional(),
                                                                                        Length(min=5, max=5, message="Deine Postleitzahl scheint nicht ins Format zu passen XXXXX."),
                                                                                        Regexp(r"[0-9]{5}", message="Deine Postleitzahl muss aus Zahlen bestehen.")])
        role = SelectField(label="Rolle",choices=[] ,coerce=str, render_kw={"class": "form-select", "id": "inputRole"})
        #confirm_privacy_policy = SelectField(label="Rolle", choices=[(0, "Gast"), (1, "Student"), (2, "Sia-Mitglied"), (3, "Sia-Alumni")])
        #, EqualTo('password', message='Passwörter nicht gleich')

    class LoginForm(FlaskForm):
        username = StringField(render_kw={"placeholder": "Benutzername"},validators=[
                                                                                    InputRequired(),
                                                                                    Length(min=3, max=20, message="Benutzername muss 3 bis 20 Zeichen lang sein.")])
        password = PasswordField(render_kw={"placeholder": "Passwort"},validators=[
                                                                                    InputRequired(),
                                                                                    Length(min=8, max=30, message="Das Passwort muss 8 bis 20 Zeichen lang sein.")])
        submit = SubmitField('Login')

    class ChangeData(FlaskForm):  #TODO validator Fehlen
        username = StringField(render_kw={"placeholder": "Benutzername"},validators=[InputRequired(),
                                                                                     Length(min=3, max=20, message="Benutzername muss 3 bis 20 Zeichen lang sein.")])
        password = PasswordField(render_kw={"placeholder": "Passwort"}, validators=[
                                                                                    Optional(),
                                                                                    Length(min=8, max=30, message="Das Passwort muss 8 bis 20 Zeichen lang sein."), 
                                                                                    EqualTo('password_confirm', message='Passwörter sind nicht gleich.')])
        password_confirm = PasswordField( render_kw={"placeholder": "Passwörter bestätigen"}, validators=[
                                                                                                        Optional(),
                                                                                                        Length(min=8, max=30, message="Das Passwort muss 8 bis 20 Zeichen lang sein."), 
                                                                                                        EqualTo('password', message='Passwörter sind nicht gleich.')])
        submit = SubmitField('Ändern')
        surname = StringField(label="Vorname",render_kw={"placeholder": "Vorname"}, default="", validators=[Optional(),
                                                                                                            Length(min=0, max=30, message="Dein Vorname darf maximal 20 Zeichen lang sein.")])
        lastname = StringField(label="Nachname",render_kw={"placeholder": "Nachname"}, default="",validators=[Optional(),
                                                                                                              Length(min=0, max=30, message="Dein Nachname darf maximal 20 Zeichen lang sein.")])
        email = EmailField(render_kw={"placeholder": "Hochschul-Email"}, validators=[
                                                                                    InputRequired(),
                                                                                    Length(min=0, max=30, message="Die Email darf maximal 30 Zeichen lang sein."),
                                                                                    Email(message="Deine Email scheint keine Email zu sein."),
                                                                                    Regexp("........@hs-albsig\.de", message="Deine Email scheint keine HS-Email zu sein XXXXXXXXX@hs-albsig.de.")]) #TODO edge cases überlegen
        street = StringField(render_kw={"placeholder": "Straße"},default="", validators=[Optional(),
                                                                                            Length(min=0, max=25, message="Der Straßenname darf maximal 25 Zeichen lang sein.")])
        street_no = StringField(render_kw={"placeholder": "Nr"},default="",validators=[Optional(),
                                                                                       Length(min=0, max=25, message="Die Straßennummer darf maximal 25 Zeichen lang sein.")])
        city = StringField( render_kw={"placeholder": "Stadt"},default="", validators=[Optional(),
                                                                                        Length(min=0, max=25, message="Der Stadtname darf maximal 25 Zeichen lang sein.")])
        postalcode = StringField(render_kw={"placeholder": "PLZ"},default="",validators=[
                                                                                        Optional(),
                                                                                        Length(min=5, max=5, message="Deine Postleitzahl scheint nicht ins Format zu passen XXXXX."),
                                                                                        Regexp(r"[0-9]{5}", message="Deine Postleitzahl muss aus Zahlen bestehen.")])
        
    class AdminChangeData(FlaskForm):  #TODO validator Fehlen
        username = StringField(render_kw={"placeholder": "Benutzername"},validators=[InputRequired(),
                                                                                     Length(min=3, max=20, message="Benutzername muss 3 bis 20 Zeichen lang sein.")])
        password = PasswordField(render_kw={"placeholder": "Passwort"}, validators=[
                                                                                    Optional(),
                                                                                    Length(min=8, max=30, message="Das Passwort muss 8 bis 20 Zeichen lang sein."), 
                                                                                    EqualTo('password_confirm', message='Passwörter sind nicht gleich.')])
        password_confirm = PasswordField( render_kw={"placeholder": "Passwörter bestätigen"}, validators=[
                                                                                                        Optional(),
                                                                                                        Length(min=8, max=30, message="Das Passwort muss 8 bis 20 Zeichen lang sein.")])
        submit = SubmitField('Ändern')
        surname = StringField(label="Vorname",render_kw={"placeholder": "Vorname"}, default="", validators=[Optional(),
                                                                                                            Length(min=0, max=30, message="Dein Vorname darf maximal 20 Zeichen lang sein.")])
        lastname = StringField(label="Nachname",render_kw={"placeholder": "Nachname"}, default="",validators=[Optional(),
                                                                                                              Length(min=0, max=30, message="Dein Nachname darf maximal 20 Zeichen lang sein.")])
        email = EmailField(render_kw={"placeholder": "Hochschul-Email"}, validators=[
                                                                                    InputRequired(),
                                                                                    Length(min=0, max=30, message="Die Email darf maximal 30 Zeichen lang sein."),
                                                                                    Email(message="Deine Email scheint keine Email zu sein."),
                                                                                    Regexp("........@hs-albsig\.de", message="Deine Email scheint keine HS-Email zu sein XXXXXXXXX@hs-albsig.de.")]) #TODO edge cases überlegen
        street = StringField(render_kw={"placeholder": "Straße"},default="", validators=[Optional(),
                                                                                            Length(min=0, max=25, message="Der Straßenname darf maximal 25 Zeichen lang sein.")])
        street_no = StringField(render_kw={"placeholder": "Nr"},default="",validators=[Optional(),
                                                                                       Length(min=0, max=25, message="Die Straßennummer darf maximal 25 Zeichen lang sein.")])
        city = StringField( render_kw={"placeholder": "Stadt"},default="", validators=[Optional(),
                                                                                        Length(min=0, max=25, message="Der Stadtname darf maximal 25 Zeichen lang sein.")])
        postalcode = StringField(render_kw={"placeholder": "PLZ"},default="",validators=[
                                                                                        Optional(),
                                                                                        Length(min=5, max=5, message="Deine Postleitzahl scheint nicht ins Format zu passen XXXXX."),
                                                                                        Regexp(r"[0-9]{5}", message="Deine Postleitzahl muss aus Zahlen bestehen.")])
        role = SelectField(label="Rolle",choices=[] ,coerce=str, render_kw={"class": "form-select", "id": "inputRole"})

    class ContactForm(FlaskForm):
        category = SelectField(render_kw={"placeholder": "Art der Anfrage"},choices=[('kontakt', 'Kontakt'), ('mieten', 'Location Mieten'), ('feedback', 'Kritik/Lob'), ('events', 'Wünsche für ein Event')], validators=[Length(min=1, max=20)])
        surname = StringField(render_kw={"placeholder": "Vorname"}, validators=[InputRequired(),
                                                                                Length(min=0, max=20, message="Dein Vorname darf maximal 20 Zeichen lang sein.")])
        lastname = StringField(render_kw={"placeholder": "Nachname"}, validators=[InputRequired(),
                                                                                  Length(min=0, max=20, message="Dein Nachname darf maximal 20 Zeichen lang sein.")])
        email = StringField(render_kw={"placeholder": "Email"}, validators=[
                                                                            InputRequired(),
                                                                            Length(min=0, max=30, message="Deine Email darf maximal 30 Zeichen lang sein."),
                                                                            Email(message="Deine Email scheint keine Email zu sein.")])
        message = TextAreaField(render_kw={"placeholder": "Nachricht"},validators=[InputRequired(),
                                                                                   Length(min=20,max=500,message="Deine Nachricht muss zwischen 20 und 500 Zeichen lang sein")])
        submit = SubmitField('Senden')
        
    class EventForm(FlaskForm):
        name = StringField("Event Name", validators=[InputRequired(), Length(max=50)])
        visibility = StringField("Benötigte Berechtigung", validators=[Length(min=0, max=10)])
        place = StringField("Ort", validators=[Length(min=0, max=50)])
        date = DateField("Event Date", validators=[Optional()])
        description = StringField("Beschreibung", validators=[Length(min=0, max=200)])
        submit = SubmitField("Submit")

    class contactDelete(FlaskForm):
        uid = HiddenField('UID', validators=[InputRequired()])



