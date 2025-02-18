from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import *
from flask_bcrypt import Bcrypt
from flask_simple_captcha import CAPTCHA
app = Flask(__name__, template_folder='static/templates', static_folder='static')
app.config.from_object(Config)

db = SQLAlchemy()
db.init_app(app)
bcrypt = Bcrypt(app)
SIMPLE_CAPTCHA = CAPTCHA(config=CONFIG_CAPTCHA)
app = SIMPLE_CAPTCHA.init_app(app)