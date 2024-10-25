from flask import Flask, render_template, send_from_directory
import os
import psycopg2
import init_db

app = Flask(__name__)
app = Flask(__name__, template_folder='static/templates')
app.config.from_object(__name__)


#---------DATABASE--------

init_db.database_init()


#----------ROUTES---------
@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static/images'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route("/",methods=['GET'])
def hello_world():
    return render_template('index.html')


if __name__ == "__main__":
    app.run(host='0.0.0.0')


