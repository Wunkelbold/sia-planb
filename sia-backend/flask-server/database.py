import os
import psycopg2
from psycopg2 import sql
from psycopg2 import OperationalError, DatabaseError, InterfaceError
import logging

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
    
    def database_dump():
        conn, cur = DAO.get_database_connection()
        cur.execute('DROP TABLE IF EXISTS "user";')
        cur.execute('DROP TABLE IF EXISTS "events";')
        cur.execute('DROP TABLE IF EXISTS "verteiler";')
        conn.commit()
        cur.close()
        conn.close()

    def database_init():

        conn, cur = DAO.get_database_connection()

        cur.execute('CREATE TABLE IF NOT EXISTS "user"'
                    '(id serial PRIMARY KEY,'
                    'username varchar (20) UNIQUE,'
                    'surname VARCHAR(20),'
                    'lastname VARCHAR(50),'
                    'street VARCHAR(25),'
                    'street_no VARCHAR(25),'
                    'password VARCHAR(200),'
                    'email VARCHAR(30) UNIQUE,'
                    'city VARCHAR(25),'
                    'postalcode VARCHAR(10),'
                    'register_date VARCHAR(50),'
                    'last_login VARCHAR(50),'
                    'role varchar (40));'                  
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
        
        
        conn.commit()
        cur.close()
        conn.close()
    def database_fill():
        conn, cur = DAO.get_database_connection()

        cur.execute("INSERT INTO \"events\" (name, visibility, place, author, date, description, postername) VALUES\
            ('Tech Meetup', 'public', 'City Hall, 12345 Metropolis', 'john_doe', '2024-12-01', 'A gathering for tech enthusiasts.', 'kuerbisschnitzen.jpg'),\
            ('Art Exhibition', 'private', 'Art Gallery, 54321 Imaginary', 'jane_smith', '2024-11-30', 'Exclusive display of modern art.', 'kuerbisschnitzen.jpg'),\
            ('Music Festival', 'public', 'Central Park, 67890 Melody', 'alice_jones', '2024-06-15', 'Live music from various artists.', 'kuerbisschnitzen.jpg'),\
            ('Book Launch', 'public', 'Library, 12345 Literature', 'bob_miller', '2024-05-20', 'Launch of the latest bestseller.', 'kuerbisschnitzen.jpg'),\
            ('Startup Pitch', 'private', 'Innovation Hub, 98765 Future', 'carol_wilson', '2024-08-18', 'Pitch ideas to potential investors.', 'kuerbisschnitzen.jpg'),\
            ('Charity Run', 'public', 'Riverside, 45678 Marathon', 'david_brown', '2024-09-25', 'Run for a cause!', 'kuerbisschnitzen.jpg'),\
            ('Cooking Class', 'private', 'Culinary School, 65432 Kitchen', 'eva_clark', '2024-04-10', 'Learn to cook gourmet meals.', 'kuerbisschnitzen.jpg'),\
            ('Film Screening', 'public', 'Cinema, 11122 MovieTown', 'frank_white', '2024-03-12', 'Exclusive preview of a blockbuster.', 'kuerbisschnitzen.jpg'),\
            ('Yoga Retreat', 'public', 'Wellness Center, 22233 Zen', 'grace_hill', '2024-07-05', 'A weekend of relaxation and mindfulness.', 'kuerbisschnitzen.jpg'),\
            ('Hackathon', 'private', 'Tech Park, 33344 CodeBase', 'henry_adams', '2024-10-22', 'Collaborative coding competition.', 'kuerbisschnitzen.jpg'),\
            ('Photography Workshop', 'public', 'Studio, 99988 Shutter', 'ivy_green', '2024-02-15', 'Learn the art of photography.', 'kuerbisschnitzen.jpg'),\
            ('Dance Competition', 'public', 'Auditorium, 88877 Rhythms', 'jack_king', '2024-11-05', 'Showcase your dance moves.', 'kuerbisschnitzen.jpg'),\
            ('Coding Bootcamp', 'private', 'Tech Center, 77766 LearnCode', 'karen_long', '2024-01-10', 'Intensive programming training.', 'kuerbisschnitzen.jpg'),\
            ('Wine Tasting', 'public', 'Vineyard, 55544 Grapes', 'leo_ross', '2024-06-20', 'Taste premium wines.', 'kuerbisschnitzen.jpg'),\
            ('Fashion Show', 'private', 'Runway, 44433 Style', 'mia_wright', '2024-09-01', 'Latest trends in fashion.', 'kuerbisschnitzen.jpg');\
        ")

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