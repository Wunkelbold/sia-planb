from globals import *
from permissions import *
from flask import request, flash, url_for, redirect, current_app
from database import Tables
from datetime import datetime, timedelta
from flask_login import login_required, current_user
import flask_mail
import threading
from uuid import UUID
import os
from itsdangerous import URLSafeTimedSerializer

def send_mail(app, email: Message):
    with app.app_context():
        try:
            mail.send(email)
        except Exception as error:
            current_app.logger.exception("Mail submission failed")
            return False, f"{type(error).__name__}: {error}"
    return True, None

def verify_email(current_user):
    domain = frontend_base_url()
    local_tz = ZoneInfo("Europe/Berlin")
    locale.setlocale(locale.LC_ALL, 'de_DE.utf8')
    now = datetime.now()

    timedelta5 = timedelta(minutes=5)
    if current_user.email and not current_user.email_confirmed:
        last_sent = datetime.strptime(current_user.email_cooldown, '%Y-%m-%d %H:%M:%S')
        if now - last_sent > timedelta5: 
            current_user.email_confirm_token = secrets.token_hex(16)
            current_user.email_cooldown = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.session.commit()
            email_msg = Message(
                subject=f"Email-Verifikation für {domain}",
                sender="noreply@"+os.getenv("HOSTNAME"),
                recipients=[f"{current_user.email}"],
                html = f'<p> Hallo {current_user.username}, <br><br> verifiziere jetzt deine E-Mail Adresse bei uns. <br> Erst danach kannst du: <ul><li>Dein Passwort zurücksetzen</li><li>Newsletter erhalten (wenn du möchtest)</li></ul></p> <a href="{domain}/verify_mail/{current_user.uid}/{current_user.email_confirm_token}">Jetzt Verfizieren</a><br><br>Alle deine perösnlichen Daten kannst auf der Profilseite verwalten oder löschen wenn du möchtest.'
            )
            thread = threading.Thread(target=send_mail, args=(current_app._get_current_object(), email_msg))
            thread.start()
            flash(f"Eine Email zur Verifizierung von {current_user.email} wird versendet! {datetime.now().astimezone(local_tz).strftime('%H:%M')}")
        else:
            flash(f"{current_user.email} ist noch nicht bestätigt. Überprüfe bitte deinen Spamordner! Eine neue Verifizierungsmail kannst du um {(last_sent+timedelta5).astimezone(local_tz).strftime('%H:%M')} anfordern.")
            timedelta.min
    if current_user.hs_email and not current_user.hs_email_confirmed:
        last_sent = datetime.strptime(current_user.hs_email_cooldown, '%Y-%m-%d %H:%M:%S')
        if now - last_sent > timedelta5: 
            current_user.hs_email_confirm_token = secrets.token_hex(16)
            current_user.hs_email_cooldown = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.session.commit()
            hs_email_msg = Message(
                subject="Email-Verifikation",
                sender="noreply@"+os.getenv("HOSTNAME"),
                recipients=[f"{current_user.hs_email}"],
                html = f'<p> Hallo {current_user.username}, <br><br> verifiziere jetzt deine E-Mail Adresse bei uns. <br> Erst danach kannst du: <ul><li>Dein Passwort zurücksetzen</li><li>Newsletter erhalten (wenn du möchtest)</li></ul></p> <a href="{domain}/verify_hs_mail/{current_user.uid}/{current_user.hs_email_confirm_token}">Jetzt Verfizieren</a><br><br>Alle deine perösnlichen Daten kannst auf der Profilseite verwalten oder löschen wenn du möchtest.'
            )
            thread = threading.Thread(target=send_mail, args=(current_app._get_current_object(), hs_email_msg))
            thread.start()
            flash(f"Eine Email zur Verifizierung von {current_user.hs_email} wird versendet! {datetime.now().astimezone(local_tz).strftime('%H:%M')}")
        else:
            flash(f"{current_user.hs_email} ist noch nicht bestätigt. Überprüfe bitte deinen Spamordner! Eine neue Verifizierungsmail kannst du um {(last_sent+timedelta5).astimezone(local_tz).strftime('%H:%M')} anfordern.")


def frontend_base_url():
    return os.getenv("FRONTEND_URL", "").rstrip("/") or request.host_url.rstrip("/")


def password_reset_serializer(user):
    account_state = (
        f"{user.password}:{user.email}:{user.email_confirmed}:"
        f"{user.hs_email}:{user.hs_email_confirmed}"
    )
    secret = f"{current_app.config['SECRET_KEY']}:{account_state}"
    return URLSafeTimedSerializer(secret, salt="sia-planb-password-reset-v1")


def create_password_reset_token(user):
    return password_reset_serializer(user).dumps({"uid": str(user.uid)})


def send_password_reset_email(user, recipient):
    domain = frontend_base_url()
    token = create_password_reset_token(user)
    reset_url = f"{domain}/reset-password?uid={user.uid}&token={token}"
    message = Message(
        subject="Passwort zurücksetzen",
        sender="noreply@" + os.getenv("HOSTNAME"),
        recipients=[recipient],
        html=(
            f"<p>Hallo {user.username},</p>"
            "<p>Über diesen Link kannst du innerhalb der nächsten Stunde ein neues Passwort festlegen:</p>"
            f'<p><a href="{reset_url}">Passwort zurücksetzen</a></p>'
            "<p>Wenn du diese Anfrage nicht gestellt hast, kannst du diese Nachricht ignorieren.</p>"
        ),
    )
    thread = threading.Thread(target=send_mail, args=(current_app._get_current_object(), message))
    thread.start()


@app.route("/verify_mail/<uid>/<token>",methods=['GET'])
def verify_mail(uid,token):
    try:
        user_uid = UUID(uid)
    except ValueError:
        return redirect("/me/profile?verification=expired")
    user = Tables.User.query.filter_by(uid=user_uid).first()
    if not user:
        return redirect("/me/profile?verification=expired")
    if user.email_confirmed:
        return redirect("/me/profile?verification=already")
    if not user.email_confirm_token or user.email_confirm_token != token:
        return redirect("/me/profile?verification=invalid")
    user.email_confirmed = True
    db.session.commit()
    return redirect("/me/profile?verification=verified")

@app.route("/verify_hs_mail/<uid>/<token>",methods=['GET'])
def verify_hs_mail(uid,token):
    try:
        user_uid = UUID(uid)
    except ValueError:
        return redirect("/me/profile?verification=expired")
    user = Tables.User.query.filter_by(uid=user_uid).first()
    if not user:
        return redirect("/me/profile?verification=expired")
    if user.hs_email_confirmed:
        return redirect("/me/profile?verification=already")
    if not user.hs_email_confirm_token or user.hs_email_confirm_token != token:
        return redirect("/me/profile?verification=invalid")
    user.hs_email_confirmed = True
    db.session.commit()
    return redirect("/me/profile?verification=verified")

@app.route("/send_verifikation_mail",methods=['GET'])
@login_required
def send_verifikation_mail():
    try:
        verify_email(current_user)
    except Exception as e:
        flash(f"Es gab einen Fehler im Mailserver, versuche es später erneut! {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}")
    return redirect(url_for('profile'))
