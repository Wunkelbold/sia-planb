from globals import *
from flask import request

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