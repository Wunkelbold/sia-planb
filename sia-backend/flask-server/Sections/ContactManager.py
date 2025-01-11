from globals import *
from flask import url_for, redirect
#-----FILES-----
from database import Tables
from forms import Forms
from permissions import *

@app.route("/delete_contact", methods=['POST'])
@require_permissions("adminpanel.delete.contact")
def delete_contact():
    form = Forms.contactDelete()
    if form.validate_on_submit():
        uid = form.uid.data
        contact = db.session.query(Tables.Contact).filter_by(uid=uid).first()
        if contact:
            db.session.delete(contact)
            db.session.commit()
        return redirect(url_for('admin'))
    else:
        return redirect(url_for('admin'))
    
