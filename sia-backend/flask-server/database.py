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
        description = db.Column(db.String(200))
        postername = db.Column(db.String(50))

        def toJSON(self):
            return json.dumps({
                "id": self.id,
                "author": self.author,
                "name": self.name,
                "visibility": self.visibility,
                "place": self.place,
                "created": self.created,
                "date": self.date,
                "description": self.description,
                "postername": self.postername
            })
    
    class Shift(db.Model):
        __tablename__ = 'shifts'
        id = db.Column(db.Integer, primary_key=True)
        user = db.Column(db.Integer, db.ForeignKey("user.id"))
        event = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
        type = db.Column(db.TEXT, nullable=False)
        start = db.Column(db.DateTime, nullable=False)
        end = db.Column(db.DateTime, nullable=False)
        
        def toJSON(self):
            return json.dumps({
                "id": self.id,
                "user": self.user,
                "event": self.event,
                "type": self.type,
                "start": self.start,
                "end": self.end
            })

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


##LEGACY KANN GELÖSCHT WERDEN
class DAO:
    def get_database_connection():
        conn = None
        cur = None
        try:
            conn = psycopg2.connect(
                host=os.getenv("DATABASE_HOST", "localhost"),
                port=os.getenv("DATABASE_PORT", "5432"),
                database=os.getenv("DATABASE_NAME", "postgres"),
                user=os.getenv("DATABASE_USER", "postgres"),
                password=os.getenv('DATABASE_PASSWORD')
            )
            cur = conn.cursor()
            return conn, cur

        except OperationalError as e:
            logging.error("OperationalError: Could not connect to the database. Check your connection parameters.")
            logging.exception(e) 
            raise  # Re-raise the exception if you want it to propagate up

        except InterfaceError as e:
            logging.error("InterfaceError: Database interface connection issue.")
            logging.exception(e)
            raise

        except DatabaseError as e:
            logging.error("DatabaseError: General database error.")
            logging.exception(e)
            raise

        except Exception as e:
            logging.error("Unexpected error occurred while connecting to the database.")
            logging.exception(e)
            raise

        finally:
            if conn and cur is None:
                # Only close the connection if cursor wasn't created (partial connection issue)
                conn.close()
                logging.info("Closed the database connection due to an error.")
    
    def create_event(name,visibility,place,author,created,date):
        conn, cur = DAO.get_database_connection()
        cur.execute('INSERT INTO events (name,visibility,place,author,created,date) VALUES (?,?,?,?,?,?);',name,visibility,place,author,created,date)
        conn.commit()
        cur.close()
        conn.close()

    def get_all_events():
        conn, cur = DAO.get_database_connection()
        try:
            cur.execute('SELECT * FROM events;')
            result = cur.fetchall()
            return result  
        except Exception as e:
            print(f"An error occurred: {e}")
            return ["Fetch failed"] 
        finally:
            cur.close()
            conn.close()

    def get_all_users():
        conn, cur = DAO.get_database_connection()
        try:
            cur.execute('SELECT * FROM "user";')
            result = cur.fetchall()
            return result  
        except Exception as e:
            print(f"An error occurred: {e}")
            return ["Fetch failed"] 
        finally:
            cur.close()
            conn.close()
        
    def get_all_events_for_diplay():
        conn, cur = DAO.get_database_connection()
        try:
            cur.execute('SELECT name,date,place FROM events where visibility=\'public\';')
            result = cur.fetchall()
            return result
        except Exception as e:
            print(f"An error occurred: {e}")
            return [] 
        finally:
            cur.close()
            conn.close()
            
    def get_all_private_events():
        return None
    
    def get_all_admin_events():
        return None
    
def init_database():
    if os.getenv("DROP_AND_CREATE_DATABASE")=="true": #TODO für dev einmalig mit if os.getenv("DROP_AND_CREATE_DATABASE","true")=="true": ausführen
        db.drop_all()
        db.create_all()
        print("--- DROP_AND_CREATE_DATABASE \t true ---")
    else:
        print("--- DROP_AND _CREATE_DATABASE \t false ---") 

def init_roles():
    if os.getenv("INIT_ROLES")=="true":
        print("--- INIT_ROLES \t\t true ---")
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            roles_path = os.path.join(script_dir, "roles.json")
            with open(roles_path, "r") as f:
                roles = json.load(f)

                for name, perm in roles.get("public").items():
                    if Tables.Role.query.filter_by(name=name).first():
                        print(f"--- role '{name}' already exists and was skipped ---")
                    else:
                        permissions = perm if perm else []
                        new_role = Tables.Role(name=name, permissions=permissions, selectable_on_register="yes")
                        db.session.add(new_role)
                
                for name, perm in roles.get("private").items():
                    if Tables.Role.query.filter_by(name=name).first():
                        print(f"--- role '{name}' already exists and was skipped ---")
                    else:
                        permissions = perm if perm else [] 
                        new_role = Tables.Role(name=name, permissions=permissions, selectable_on_register="no")
                        db.session.add(new_role)

            db.session.commit()
            
            admin_pwd=secrets.token_hex(12)
            hashed_password = bcrypt.generate_password_hash(admin_pwd).decode('utf-8')
            admin = Tables.User(username="admin", password=hashed_password, role="Admin", permissions=[])
            db.session.add(admin)
            db.session.commit()
            print(f"--- Admin generated: admin, {admin_pwd} ---")

            print("--- INIT_ROLES \t\t success ---")
    
        except Exception as e:
            print("--- init_roles() ERROR:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

    else:
        print("--- INIT_ROLES \t false ---")


with app.app_context():
    init_database()
    init_roles()
