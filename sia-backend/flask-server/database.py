import os
import psycopg2
from psycopg2 import sql
from psycopg2 import OperationalError, DatabaseError, InterfaceError
import logging



class DAO:
    def get_database_password() -> str:
            return os.getenv('DATABASE_PASSWORD')
            
    def get_database_connection():
        conn = None
        cur = None
        try:
            conn = psycopg2.connect(
                host=os.getenv("DATABASE_HOST", "localhost"),
                port=os.getenv("DATABASE_PORT", "5432"),
                database=os.getenv("DATABASE_NAME", "postgres"),
                user=os.getenv("DATABASE_USER", "postgres"),
                password=DAO.get_database_password()
            )
            
            cur = conn.cursor()
            return conn, cur

        except OperationalError as e:
            logging.error("OperationalError: Could not connect to the database. Check your connection parameters.")
            logging.exception(e)  # Log the exception details
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
    

    def database_init():

        conn, cur = DAO.get_database_connection()

        #cur.execute('DROP TABLE IF EXISTS "user";')
        #cur.execute('DROP TABLE IF EXISTS "events";')
        #cur.execute('DROP TABLE IF EXISTS "verteiler";')

        cur.execute('CREATE TABLE IF NOT EXISTS "user"'
                    '(id serial PRIMARY KEY,'
                    'username varchar (25) UNIQUE NOT NULL,'
                    'password VARCHAR(50) NOT NULL,'
                    'email VARCHAR(255) UNIQUE,'
                    'role varchar (40) NOT NULL);'                  
                    )
        
        cur.execute('CREATE TABLE IF NOT EXISTS "events" '
                    '(id serial PRIMARY KEY,'
                    'name varchar (25) NOT NULL DEFAULT \'Eventname\','
                    'visibility varchar (10) NOT NULL DEFAULT \'public\','
                    'place varchar (40) DEFAULT \'Plan B, 72458 Albstadt\','
                    'author varchar (25) NOT NULL DEFAULT \'Admin\','
                    'created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,'
                    'date TIMESTAMP NOT NULL DEFAULT TO_DATE(\'01/01/1990\',\'DD/MM/YYYY\'),'
                    'description varchar (200) NOT NULL DEFAULT \'Eventbeschreibung\','
                    'postername varchar (25) DEFAULT \'kuerbisschnitzen.jpg\');'                  
                    )
        
        cur.execute('CREATE TABLE IF NOT EXISTS "verteiler"'
                    '(id serial PRIMARY KEY,'
                    'name varchar (25) NOT NULL,'
                    'email VARCHAR(255) NOT NULL);'                 
                    )

        conn.commit()
        cur.close()
        conn.close()

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