from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

app = Flask(__name__, template_folder='static/templates', static_folder='static')
app.config.from_object(Config)

db = SQLAlchemy()
db.init_app(app)