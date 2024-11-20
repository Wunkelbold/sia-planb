import os
import psycopg2
from psycopg2 import OperationalError, DatabaseError, InterfaceError, sql
from flask_login import UserMixin
import logging
from extensions import db

class Tables:
    class Event(db.Model, UserMixin):
        __tablename__ = 'events'
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(50), nullable=False)
        visibility = db.Column(db.String(10))
        place = db.Column(db.String(50))
        author = db.Column(db.String(20), nullable=False)
        created = db.Column(db.TEXT)
        date = db.Column(db.TEXT)
        description = db.Column(db.String(200))
        postername = db.Column(db.String(50))

    class User(db.Model, UserMixin):
        __tablename__ = 'user'
        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String(20), nullable=False, unique=True)
        surname = db.Column(db.String(20))
        lastname = db.Column(db.String(20))
        street = db.Column(db.String(25))
        street_no = db.Column(db.String(25))
        password = db.Column(db.String(200))
        email = db.Column(db.String(30))
        city = db.Column(db.String(25))
        postalcode = db.Column(db.String(25))
        register_date = db.Column(db.TEXT)
        last_login = db.Column(db.TEXT)
        role = db.Column(db.Integer)
        pass

class DAO:
    def init():
        if os.getenv("DROP_DATABASE"):
            db.drop_all()
            print("---DATABASE WAS DROPPED DUE TO COMPOSE SETTING---")
        if os.getenv("CREATE_DATABASE"):
            db.create_all()
            print("---DATABASE WAS CREATED DUE TO COMPOSE SETTING---")

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