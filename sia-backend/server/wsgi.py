from flask import Flask, render_template, send_from_directory
import os
import psycopg2


import database

app = Flask(__name__)
app = Flask(__name__, template_folder='static/templates', static_folder='static')
app.config.from_object(__name__)


#---------DATABASE--------

Database = database.DAO
Database.database_init()



#----------ROUTES---------
@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static/images'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')



@app.route("/",methods=['GET'])
def hello_world():
    events=Database.get_all_events_for_diplay()
    return render_template('index.html',title='Home',events=events)


if __name__ == "__main__":
    app.run(host='0.0.0.0')


