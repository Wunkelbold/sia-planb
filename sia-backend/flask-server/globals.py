from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import *
from flask_bcrypt import Bcrypt
from flask_simple_captcha import CAPTCHA
from flask_mail import Mail, Message
app = Flask(__name__, template_folder='static/templates', static_folder='static')
app.config.from_object(Config)

db = SQLAlchemy()
db.init_app(app)
bcrypt = Bcrypt(app)

SIMPLE_CAPTCHA = CAPTCHA(config=CONFIG_CAPTCHA)
app = SIMPLE_CAPTCHA.init_app(app)


app.config['MAIL_SERVER'] = 'mail.localtest.me'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False #weirder Fehler falls True
app.config['MAIL_DEBUG'] = False
app.config['MAIL_USERNAME'] = 'noreply@localtest.me'
app.config['MAIL_PASSWORD'] = 'admin'
app.config['MAIL_DEFAULT_SENDER'] = 'noreply@localtest.me'
mail = Mail(app)