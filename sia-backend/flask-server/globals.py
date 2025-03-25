from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import *
from flask_bcrypt import Bcrypt
from flask_simple_captcha import CAPTCHA
from flask_mail import Mail, Message
from flask_migrate import Migrate, upgrade, migrate
import locale
from zoneinfo import ZoneInfo
from flask_qrcode import QRcode
# [...]


local_tz = ZoneInfo("Europe/Berlin")
locale.setlocale(locale.LC_ALL, 'de_DE.utf8')
from sqlalchemy import func, Numeric

app = Flask(__name__, template_folder='static/templates', static_folder='static')
app.config.from_object(Config)
db = SQLAlchemy()
db.init_app(app)
migrate_tool = Migrate(app, db)
bcrypt = Bcrypt(app)
SIMPLE_CAPTCHA = CAPTCHA(config=CONFIG_CAPTCHA)
app = SIMPLE_CAPTCHA.init_app(app)
mail = Mail(app)
QRcode(app)
