import os
import secrets


def _secret(name, fallback_bytes):
    value = os.getenv(name)
    if value:
        return value
    if os.getenv("APP_ENV", "development").strip().lower() in {"prod", "production"}:
        raise RuntimeError(f"{name} must be configured in production")
    return secrets.token_hex(fallback_bytes)


def _database_uri():
    uri = os.getenv("DATABASE_URI")
    if uri and uri.startswith("postgresql://"):
        return uri.replace("postgresql://", "postgresql+psycopg2://", 1)
    return uri


class Config:
    SQLALCHEMY_DATABASE_URI = _database_uri()
    DEBUG = os.getenv("DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}
    SECRET_KEY = _secret("SECRET_KEY", 25)
    MAIL_SERVER = os.getenv("hostname") or os.getenv("HOSTNAME")
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_DEBUG = False
    MAIL_USERNAME = 'noreply@'+os.getenv("HOSTNAME")
    MAIL_PASSWORD = _secret("MAIL_PASSWORD", 10)
    MAIL_DEFAULT_SENDER = 'noreply@' + os.getenv("HOSTNAME")
    MAIL_ACCOUNTS_FILE = "/app/postfix-accounts.cf"

CONFIG_CAPTCHA = {
    'SECRET_CAPTCHA_KEY': _secret("CAPTCHA_SECRET_KEY", 25),
    'CAPTCHA_LENGTH': 6,
    'CAPTCHA_DIGITS': True,
    'EXPIRE_SECONDS': 600,
}
