import os
import psycopg2
from psycopg2 import sql



class DAO:
    def get_database_password() -> str:
            return os.getenv('DATABASE_PASSWORD')
            
    def get_database_connection():
        conn = psycopg2.connect(
            host=os.getenv("DATABASE_HOST", "localhost"),
            port=os.getenv("DATABASE_PORT", "5432"),
            database=os.getenv("DATABASE_NAME", "postgres"),
            user=os.getenv("DATABASE_USER", "postgres"),
            password=DAO.get_database_password()
        )
        cur = conn.cursor()
        return conn, cur
    

    def database_init():

        conn, cur = DAO.get_database_connection()

        cur.execute('DROP TABLE IF EXISTS "user";')
        cur.execute('DROP TABLE IF EXISTS "events";')
        cur.execute('DROP TABLE IF EXISTS "verteiler";')

        cur.execute('CREATE TABLE IF NOT EXISTS "user"'
                    '(id serial PRIMARY KEY,'
                    'username varchar (25) UNIQUE NOT NULL,'
                    'password VARCHAR(50) NOT NULL,'
                    'email VARCHAR(255) UNIQUE,'
                    'role varchar (40) NOT NULL);'                  
                    )
        
        cur.execute('CREATE TABLE IF NOT EXISTS "events" '
                    '(id serial PRIMARY KEY,'
                    'name varchar (25) NOT NULL,'
                    'visibility varchar (10) NOT NULL,'
                    'place varchar (40) DEFAULT \'Plan B, 72458 Albstadt\','
                    'author varchar (25) NOT NULL,'
                    'created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,'
                    'date TIMESTAMP);'                  
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
            return [] 
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