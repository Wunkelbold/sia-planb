from globals import *
from flask import flash, url_for, redirect, jsonify
from datetime import datetime
#-----FILES-----
from database import Tables
from forms import Forms
from permissions import *



@app.route("/delete_event", methods=['POST']) #TODO noch auf API Syntax umbauen
@require_permissions("adminpanel.event.delete")
def delete_event():
    form = Forms.eventDelete() #braucht man keine neue Form dafür
    if form.validate_on_submit():
        uid = form.uid.data
        event = db.session.query(Tables.Event).filter_by(uid=uid).first()
        if event:
            db.session.delete(event)
            db.session.commit()
        return redirect(url_for('admin'))
    else:
        return redirect(url_for('admin'))