import os
import secrets

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI")
    DEBUG = os.getenv("DEBUG")
    SECRET_KEY = secrets.token_hex(25)