from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__, template_folder='static/templates', static_folder='static')
db = SQLAlchemy()