import os
import secrets

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI")
    DEBUG = os.getenv("DEBUG")
    SECRET_KEY = secrets.token_hex(25)
    MAIL_SERVER = 'mail.localtest.me'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_DEBUG = False
    MAIL_USERNAME = 'noreply@'+os.getenv("HOSTNAME")
    MAIL_PASSWORD = secrets.token_hex(10)
    MAIL_DEFAULT_SENDER = 'noreply@' + os.getenv("HOSTNAME")
    MAIL_ACCOUNTS_FILE = "/app/postfix-accounts.cf"

CONFIG_CAPTCHA = {
    'SECRET_CAPTCHA_KEY': secrets.token_hex(25),
    'CAPTCHA_LENGTH': 6,
    'CAPTCHA_DIGITS': True,
    'EXPIRE_SECONDS': 600,
}