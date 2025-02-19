from globals import *
from flask import request
import subprocess

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

        print(f"Temporary mail user {email} added.")
    except subprocess.CalledProcessError as e:
        print(f"Error generating password hash: {e.stderr}")

def verify_email(current_user):
    domain = request.host_url.rstrip('/')
    if current_user.email and not current_user.email_confirmed:
        current_user.email_confirm_token = secrets.token_hex(16)
        db.session.commit()
        email_msg = Message(
            subject="Email-Verifikation",
            sender=("NoReply","noreply@localtest.me"),
            recipients=[f"{current_user.email}"],
            html = f'<p> Verifiziere deine E-Mail Adresse</p> <a href="{domain}/verify_mail/{current_user.uid}/{current_user.email_confirm_token}">Verfizieren</a>'
        )
        mail.send(email_msg)
    if current_user.hs_email and not current_user.hs_email_confirmed:
        current_user.hs_email_confirm_token = secrets.token_hex(16)
        db.session.commit()
        hs_email_msg = Message(
            subject="Email-Verifikation",
            sender=("NoReply","noreply@localtest.me"),
            recipients=[f"{current_user.hs_email}"],
            html = f'<p> Verifiziere deine E-Mail Adresse</p> <p> Die HS Email solltest du Verifizieren, weil dir sonst Studi-Exklusiven Inhalte nicht angezeigt werden.</p><a href="{domain}/verify_hs_mail/{current_user.uid}/{current_user.email_confirm_token}">Verfizieren</a>'
        )
        mail.send(hs_email_msg)


update_mail_user(app.config["MAIL_USERNAME"], app.config["MAIL_PASSWORD"])