import os
import sys
import traceback
from flask import json
import psycopg2
from psycopg2 import OperationalError, DatabaseError, InterfaceError
from flask_login import UserMixin
import logging
from globals import *
import uuid
import secrets
from sqlalchemy.dialects.postgresql import UUID, MONEY
from datetime import datetime, timezone


def format_datetime(dt):
    return dt.strftime('%d-%m-%Y %H:%M') if dt else None

def format_datetime_hr(dt):
    local_tz = ZoneInfo("Europe/Berlin")
    locale.setlocale(locale.LC_ALL, 'de_DE.utf8')
    return dt.replace(tzinfo=local_tz).strftime('%a, %d.%m.%y %H:%M') if dt else None

def format_datetime2(dt):
    return dt.strftime('%Y-%m-%dT%H:%M') if dt else None

class Tables:
    class User(db.Model, UserMixin):
        __tablename__ = 'user'
        id = db.Column(db.Integer, primary_key=True)
        uid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)  # Add UUID
        username = db.Column(db.String(20), nullable=False, unique=True)
        surname = db.Column(db.String(20))
        lastname = db.Column(db.String(20))
        street = db.Column(db.String(25))
        street_no = db.Column(db.String(10))
        password = db.Column(db.String(200))
        email = db.Column(db.String(30))
        email_confirmed = db.Column(db.Boolean, nullable=False, default=False)
        email_confirm_token = db.Column(db.String(64))
        email_cooldown = db.Column(db.TEXT, default=datetime.min)
        hs_email = db.Column(db.String(30))
        hs_email_confirmed = db.Column(db.Boolean, nullable=False, default=False)
        hs_email_confirm_token = db.Column(db.String(64))
        hs_email_cooldown = db.Column(db.TEXT,default=datetime.min)
        city = db.Column(db.String(25))
        postalcode = db.Column(db.String(25))
        register_date = db.Column(db.TEXT)
        last_login = db.Column(db.TEXT)
        role = db.Column(db.TEXT, db.ForeignKey("roles.name"), nullable=False)
        permissions = db.Column(db.ARRAY(db.TEXT), nullable=False)
        last_updated = db.Column(db.TEXT)

    class Role(db.Model):
        __tablename__ = 'roles'
        name = db.Column(db.TEXT, primary_key=True)
        permissions = db.Column(db.ARRAY(db.TEXT), nullable=False)
        selectable_on_register = db.Column(db.String(10))
        
    class Event(db.Model):
        __tablename__ = 'events'
        id = db.Column(db.Integer, primary_key=True)
        uid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)  # Add UUID
        author = db.Column(db.Integer, db.ForeignKey("user.id",ondelete='SET DEFAULT'), nullable=False, default=1)
        name = db.Column(db.String(50), nullable=False)
        visibility = db.Column(db.String(10))
        place = db.Column(db.String(50))
        created = db.Column(db.DateTime)
        date = db.Column(db.DateTime)
        end = db.Column(db.DateTime)
        description = db.Column(db.String(300))
        postername = db.Column(db.String(50))
        shift_rel = db.relationship("Shift", cascade="all,delete", backref="Event", lazy="joined")
        task_rel = db.relationship("Task", cascade="all,delete", backref="Event", lazy="joined")

        def toJSON(self):
            def format_datetime(dt):
                return dt.strftime('%Y-%m-%dT%H:%M') if dt else None
            return json.dumps({
                "id": self.id,
                "author": self.author,
                "uid": self.uid,
                "name": self.name,
                "visibility": self.visibility,
                "place": self.place,
                "created": format_datetime(self.created),
                "date": format_datetime(self.date),
                "description": self.description,
                "postername": self.postername
            })
    
    class Shift(db.Model):
        __tablename__ = 'shifts'
        id = db.Column(db.Integer, primary_key=True)
        event = db.Column(db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
        type = db.Column(db.String(30))
        start = db.Column(db.DateTime)
        end = db.Column(db.DateTime)
        duty_rel = db.relationship("Duty", cascade="all,delete", backref="Shift", lazy="joined")
        
        def getDict(self):
            return {
                "id": self.id,
                "event": self.event,
                "type": self.type,
                "start": format_datetime(self.start),
                "end": format_datetime(self.end),
                "start_hr": format_datetime_hr(self.start),
                "end_hr": format_datetime_hr(self.end),
                "users": [duty.user_obj.username for duty in self.duty_rel if duty.user_obj]
            }
        
    class Duty(db.Model):
        __tablename__ = 'duty'
        id = db.Column(db.Integer, primary_key=True)
        shift = db.Column(db.Integer, db.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False)
        user = db.Column(db.Integer, db.ForeignKey("user.id",ondelete="CASCADE"))
        user_obj = db.relationship("User", backref="duties", lazy="joined")

    class Contact(db.Model):
        __tablename__ = 'contact'
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        uid = db.Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)  # Add UUID
        category = db.Column(db.String(20))
        surname = db.Column(db.String(20))
        lastname = db.Column(db.String(20))
        email = db.Column(db.String(30))
        message = db.Column(db.String(500))
        created = db.Column(db.TEXT)
        creation = db.Column(db.DateTime)
        
        def getDict(self):
            return {
                "id":self.id,
                "uid":self.uid,
                "category": self.category,
                "surname":self.surname,
                "lastname":self.lastname,
                "email":self.email,
                "message":self.message,
                "creation":format_datetime_hr(self.creation)
            }

    class RegisterManager(db.Model):
        __tablename__ = 'registermanager'
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        name = db.Column(db.String(30))
        visibility = db.Column(db.String(10))
        accept = db.Column(db.String(12))
        deny = db.Column(db.String(12))
        start = db.Column(db.DateTime)
        end = db.Column(db.DateTime)
        price = db.Column(Numeric(10, 2))
        eventFK = db.Column(db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"))
        registration_rel = db.relationship("Registration", cascade="all,delete", backref="RegisterManager", lazy="joined")


        def getDict(self):
            return {
                "rmID": self.id,
                "name": self.name,
                "visibility": self.visibility,
                "accept": self.accept,
                "deny":self.deny,
                "start": format_datetime2(self.start),
                "end": format_datetime2(self.end),
                "start_hr": format_datetime_hr(self.start),
                "end_hr": format_datetime_hr(self.end),
                "price": self.price,
                "eventFK": self.eventFK,
                "users": [
                            registration.user_obj.username
                            for registration in sorted(
                                self.registration_rel, key=lambda r: r.timestamp
                            ) if registration.user_obj
                        ]
            }

    class Registration(db.Model):
        __tablename__ = 'registration'
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        timestamp = db.Column(db.DateTime)
        userFK = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"))
        rmFK = db.Column(db.Integer, db.ForeignKey("registermanager.id", ondelete="CASCADE"))
        teamname = db.Column(db.String(30))
        price = db.Column(Numeric(10, 2))
        paid = db.Column(db.Boolean, default=False)
        valid = db.Column(db.Boolean, default=False) # Ticket eingeloest / entwertet
        user_obj = db.relationship("User", backref="registration", lazy="joined")

        def getDict(self):
            return {
                "id": self.id,
                "userFK": self.userFK,
                "userUID": self.user_obj.uid,
                "rmFK": self.rmFK,
                "teamname": self.teamname,
                "users": self.user_obj.username,
                "rm_name": self.RegisterManager.name,
                "price" : self.price,
                "paid": self.paid,
                "valid": self.valid, 
            }
        
    class Task(db.Model):
        __tablename__ = 'task'
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        eventFK = db.Column(db.Integer, db.ForeignKey("events.id",ondelete="CASCADE"))
        authorFK = db.Column(db.Integer, db.ForeignKey("user.id",ondelete='SET DEFAULT'),default=1)
        name = db.Column(db.String(50))
        description = db.Column(db.String(500))
        status = db.Column(db.String(30))
        priority = db.Column(db.String(20))
        visibility = db.Column(db.String(10))
        deadline = db.Column(db.DateTime)
        created = db.Column(db.DateTime)
        timeframe_start = db.Column(db.DateTime)
        timeframe_end = db.Column(db.DateTime) 
        assistant_obj = db.relationship("Assistant", backref="task", lazy="joined")

        def getDict(self):
            return {
                "id": self.id,
                "eventFK": self.eventFK,
                "name": self.name,
                "authorFK": self.authorFK,
                "description": self.description,
                "status": self.status,
                "priority": self.priority,
                "visibility": self.visibility,
                "deadline" : format_datetime2(self.deadline),
                "deadline_hr" : format_datetime_hr(self.deadline),
                "created": format_datetime_hr(self.created),
                "timeframe_start": format_datetime2(self.timeframe_start),
                "timeframe_end": format_datetime2(self.timeframe_end),
                "timeframe_start_hr": format_datetime_hr(self.timeframe_start),
                "timeframe_end_hr": format_datetime_hr(self.timeframe_end),
                "event_name": self.Event.name if self.Event else " - ",
            }

    class Assistant(db.Model): #Helfer die Aufgaben erledigen
        __tablename__ = 'assistant'
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        userFK = db.Column(db.Integer, db.ForeignKey("user.id",ondelete="CASCADE"))
        taskFK = db.Column(db.Integer, db.ForeignKey("task.id",ondelete="CASCADE"))
        joined_timestamp = db.Column(db.DateTime)
        role = db.Column(db.String(30))

    class HowTo(db.Model):
        __tablename__ = 'howto'
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        userFK = db.Column(db.Integer, db.ForeignKey("user.id",ondelete="SET DEFAULT"),default=1)
        header = db.Column(db.TEXT)
        body = db.Column(db.TEXT)
        created = db.Column(db.DateTime)
        last_changed = db.Column(db.DateTime)
        visibility = db.Column(db.String(10))







    
def init_database():
    if os.getenv("DROP_AND_CREATE_DATABASE")=="true":
        db.drop_all()
        db.create_all()
        print("--- DROP_AND_CREATE_DATABASE \t true ---")
        print("--- DROPPING SHOULDNT BE USED ANYMOR ---")
    else:
        print("--- DROP_AND_CREATE_DATABASE \t false ---") 

def init_roles():
    print("--- Initializing roles \t\t ---")
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        roles_path = os.path.join(script_dir, "roles.json")
        with open(roles_path, "r") as f:
            roles = json.load(f)
            for name, perm in roles.get("public").items():
                role = Tables.Role.query.filter_by(name=name).first()
                permissions = perm if perm else []
                if role:
                    role.name=name
                    role.permissions=permissions
                    role.selectable_on_register="yes"
                    print(f"--- role '{name}' already exists, permission update ---")
                else:
                    
                    new_role = Tables.Role(name=name, permissions=permissions, selectable_on_register="yes")
                    db.session.add(new_role)
                    print(f"--- role '{name}' initialized ---")
            
            for name, perm in roles.get("private").items():
                role = Tables.Role.query.filter_by(name=name).first()
                permissions = perm if perm else []
                if role:
                    role.name=name
                    role.permissions=permissions
                    role.selectable_on_register="no"
                    print(f"--- role '{name}' already exists, permission update ---")
                else:
                     
                    new_role = Tables.Role(name=name, permissions=permissions, selectable_on_register="no")
                    db.session.add(new_role)
                    print(f"--- role '{name}' initialized ---")
        db.session.commit()
    except Exception as e:
        print("--- init_roles() ERROR:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

def init_default_role():
    if os.getenv("CREATE_ADMIN")=="true":
        print("--- CREATE_ADMIN \t\t true ---")
        admin_pwd = secrets.token_hex(12)
        hashed_password = bcrypt.generate_password_hash(admin_pwd).decode('utf-8')
        admin_existing = Tables.User.query.filter_by(username="admin").first()
        if admin_existing:
            admin_existing.password = hashed_password
            print(f"--- Admin exists, new password: {admin_pwd} ---")
        else:
            admin = Tables.User(username="admin", password=hashed_password, role="Admin", permissions=[])
            db.session.add(admin)
            print(f"--- Admin generated: admin: {admin_pwd} ---")
        db.session.commit()
    else:
        print("--- CREATE_ADMIN \t\t false ---")


with app.app_context():
    init_database()
    init_roles()
    init_default_role()
