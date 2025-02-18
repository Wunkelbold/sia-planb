import os
import secrets

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI")
    DEBUG = os.getenv("DEBUG")
    SECRET_KEY = secrets.token_hex(25)

CONFIG_CAPTCHA = {
    'SECRET_CAPTCHA_KEY': secrets.token_hex(25),
    'CAPTCHA_LENGTH': 6,
    'CAPTCHA_DIGITS': True,
    'EXPIRE_SECONDS': 600,
}