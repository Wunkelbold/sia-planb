import os
import psycopg2
from psycopg2 import sql

def database_init():
    with open(os.getenv('DATABASE_PASSWORD_FILE', '/run/secrets/db-password'), 'r') as file:
        db_password = file.read().strip()

    conn = psycopg2.connect(
        host=os.getenv("DATABASE_HOST", "localhost"),
        port=os.getenv("DATABASE_PORT", "5432"),
        database=os.getenv("DATABASE_NAME", "postgres"),
        user=os.getenv("DATABASE_USER", "postgres"),
        password=db_password
    )

    cur = conn.cursor()

    cur.execute('DROP TABLE IF EXISTS "user";')
    cur.execute('CREATE TABLE "user" (id serial PRIMARY KEY,'
                'username varchar (150) NOT NULL);'
                'username varchar (150) NOT NULL);'
                )

    conn.commit()
    cur.close()
    conn.close()