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
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone


def format_datetime(dt):
    return dt.strftime('%d-%m-%Y %H:%M') if dt else None

def format_datetime_hr(dt):
    local_tz = ZoneInfo("Europe/Berlin")
    locale.setlocale(locale.LC_ALL, 'de_DE.utf8')
    return dt.replace(tzinfo=local_tz).strftime('%a, %d/%m/%y %H:%M') if dt else None

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
        author = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        name = db.Column(db.String(50), nullable=False)
        visibility = db.Column(db.String(10))
        place = db.Column(db.String(50))
        created = db.Column(db.DateTime)
        date = db.Column(db.DateTime)
        end = db.Column(db.DateTime)
        description = db.Column(db.String(200))
        postername = db.Column(db.String(50))
        shift_rel = db.relationship("Shift", cascade="all,delete", backref="Event", lazy="joined")

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
        user = db.Column(db.Integer, db.ForeignKey("user.id"))
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
                "eventFK": self.eventFK,
                "users": [registration.user_obj.username for registration in self.registration_rel if registration.user_obj]
            }

    class Registration(db.Model):
        __tablename__ = 'registration'
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        userFK = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"))
        rmFK = db.Column(db.Integer, db.ForeignKey("registermanager.id", ondelete="CASCADE"))
        teamname = db.Column(db.String(30))
        user_obj = db.relationship("User", backref="registration", lazy="joined")
        rm_obj = db.relationship("RegisterManager", back_populates="registration_rel", lazy="joined")

        def getDict(self):
            return {
                "id": self.id,
                "userFK": self.userFK,
                "rmFK": self.rmFK,
                "teamname": self.teamname,
                "users": [registration.user_obj.username for registration in self.registration_rel if registration.user_obj],
                "rm_name": self.rm_obj.name,
            }

    class HowTo(db.Model):
        __tablename__ = 'howto'
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        userFK = db.Column(db.Integer, db.ForeignKey("user.id"))
        header = db.Column(db.TEXT)
        body = db.Column(db.TEXT)
        created = db.Column(db.DateTime)
        last_changed = db.Column(db.DateTime)
        visibility = db.Column(db.String(10))



    
def init_database():
    if os.getenv("DROP_AND_CREATE_DATABASE")=="true": #TODO für dev einmalig mit if os.getenv("DROP_AND_CREATE_DATABASE","true")=="true": ausführen
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
