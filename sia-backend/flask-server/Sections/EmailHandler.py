from globals import *
from flask import request, flash, url_for, redirect, current_app
import subprocess
from database import Tables
from datetime import datetime, timedelta
from flask_login import login_required, current_user
import flask_mail
from smtplib import SMTPAuthenticationError, SMTPServerDisconnected, SMTPException


def update_mail_user(email, password):
    """Removes existing user and adds a new one with a generated password."""
    try:
        # Generate the hashed password using doveadm
        password_hash_cmd = ["doveadm", "pw", "-s", "SHA512-CRYPT", "-p", password]
        hashed_password = subprocess.run(password_hash_cmd, capture_output=True, text=True, check=True).stdout.strip()

        # Read existing users and remove the old entry if it exists
        try:
            with open(app.config["MAIL_ACCOUNTS_FILE"], "r") as file:
                lines = file.readlines()
            updated_lines = [line for line in lines if not line.startswith(f"{email}|")]
        except FileNotFoundError:
            updated_lines = []  # File doesn't exist, create new

        # Add the new user entry
        updated_lines.append(f"{email}|{hashed_password}\n")

        # Write back to the file

        with open(app.config["MAIL_ACCOUNTS_FILE"], "w") as file:
            file.writelines(updated_lines)


        print(f"--- Temporary mail user {email} added. ---")
    except subprocess.CalledProcessError as e:
        print(f"Error generating password hash: {e.stderr}")

def send_mail(email):
    retcode = 0
    try:
        mail.send(email)
    except SMTPAuthenticationError as e:
        retcode = 2
        print(f"SMTP Authentication Error: {e}")
    except SMTPServerDisconnected as e:
        retcode = 3
        print(f"SMTP Server Disconnected: {e}")
    except SMTPException as e:
        retcode = 1
        print(f"General SMTP Exception: {e}")
    if retcode:
        flash("Es gab ein Serverseitiges Problem mit deiner Mail! :(")
        with app.app_context():
            current_app.logger.error(retcode)

def verify_email(current_user):
    domain = request.host_url.rstrip('/')
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
                sender=("NoReply@"+os.getenv("hostname"),"noreply@"+os.getenv("hostname")),
                recipients=[f"{current_user.email}"],
                html = f'<p> Hallo {current_user.username}, <br><br> verifiziere jetzt deine E-Mail Adresse bei uns. <br> Erst danach kannst du: <ul><li>Dein Passwort zurücksetzen</li><li>Newsletter erhalten (wenn du möchtest)</li></ul></p> <a href="{domain}/verify_mail/{current_user.uid}/{current_user.email_confirm_token}">Jetzt Verfizieren</a><br><br>Alle deine perösnlichen Daten kannst auf der Profilseite verwalten oder löschen wenn du möchtest.'
            )
            send_mail(email_msg)
            flash(f"Eine Email zur Verifizierung von {current_user.email} wurde gesendet! {datetime.now().strftime('%H:%M')}")
        else:
            flash(f"{current_user.email} ist noch nicht bestätigt. Überprüfe bitte deinen Spamordner! Eine neue Verifizierungsmail kannst du um {(last_sent+timedelta5).strftime('%H:%M')} anfordern.")
            timedelta.min
    if current_user.hs_email and not current_user.hs_email_confirmed:
        last_sent = datetime.strptime(current_user.hs_email_cooldown, '%Y-%m-%d %H:%M:%S')
        if now - last_sent > timedelta5: 
            current_user.hs_email_confirm_token = secrets.token_hex(16)
            current_user.hs_email_cooldown = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.session.commit()
            hs_email_msg = Message(
                subject="Email-Verifikation",
                sender=("NoReply@"+os.getenv("hostname"),"noreply@"+os.getenv("hostname")),
                recipients=[f"{current_user.hs_email}"],
                html = f'<p> Hallo {current_user.username}, <br><br> verifiziere jetzt deine E-Mail Adresse bei uns. <br> Erst danach kannst du: <ul><li>Dein Passwort zurücksetzen</li><li>Newsletter erhalten (wenn du möchtest)</li></ul></p> <a href="{domain}/verify_hs_mail/{current_user.uid}/{current_user.hs_email_confirm_token}">Jetzt Verfizieren</a><br><br>Alle deine perösnlichen Daten kannst auf der Profilseite verwalten oder löschen wenn du möchtest.'
            )
            send_mail(hs_email_msg)
            flash(f"Eine Email zur Verifizierung von {current_user.hs_email} wurde gesendet! {datetime.now().strftime('%H:%M')}")
        else:
            flash(f"{current_user.hs_email} ist noch nicht bestätigt. Überprüfe bitte deinen Spamordner! Eine neue Verifizierungsmail kannst du um {(last_sent+timedelta5).strftime('%H:%M')} anfordern.")

@app.route("/verify_mail/<uid>/<token>",methods=['GET'])
def verify_mail(uid,token):
    user = Tables.User.query.filter_by(uid=uid).first()
    if user:
        if not user.email_confirmed:
            if user.email_confirm_token == token:
                user.email_confirmed = True
                db.session.commit()
            else:
                return "Token Falsch. Schaue in den Spamordner, der neueste Token ist noch auf dem Weg oder verloren gegangen!"
        else:
            return "Diese E-Mail Adresse ist bereits bestätigt!"
    else:
        return "Link abgelaufen!"
    flash(f"{current_user.email} Erfolgreich Verifiziert!")
    return redirect(url_for('profile'))

@app.route("/verify_hs_mail/<uid>/<token>",methods=['GET'])
def verify_hs_mail(uid,token):
    user = Tables.User.query.filter_by(uid=uid).first()
    if user:
        if not user.hs_email_confirmed:
            if user.hs_email_confirm_token == token:
                user.hs_email_confirmed = True
                db.session.commit()
            else:
                return "Token Falsch. Schaue in den Spamordner, der neueste Token ist noch auf dem Weg oder verloren gegangen!"
        else:
            return "Diese E-Mail Adresse ist bereits bestätigt!"
    else:
        return "Link abgelaufen!"
    flash(f"{current_user.hs_email} Erfolgreich Verifiziert!")
    return redirect(url_for('profile'))


@app.route("/send_verifikation_mail",methods=['GET'])
@login_required
def send_verifikation_mail():
    try:
        verify_email(current_user)
    except Exception as e:
        flash(f"Es gab einen Fehler im Mailserver, versuche es später erneut! {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}")
    return redirect(url_for('profile'))


if os.getenv('UPDATE_MAIL_USER')=="true":
    update_mail_user(app.config["MAIL_USERNAME"], app.config["MAIL_PASSWORD"])