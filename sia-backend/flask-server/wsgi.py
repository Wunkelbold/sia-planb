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

@app.route("/slider/<name>")
def slider(name):
    # Define the directory where images are stored
    image_dir = os.path.join(app.root_path, 'static/images/slider/')
    file_path = os.path.join(image_dir, name)

    # Check if the requested file exists
    if not os.path.exists(file_path):
        # Return a default placeholder image if the file is not found
        name = "placeholder.png"  # Ensure you have this placeholder in the static/images directory

    # Serve the requested image or the placeholder
    return send_from_directory(image_dir, name)

@app.route("/",methods=['GET'])
def index():
    events=Database.get_all_events()
    return render_template('index.html', title='Sia-PlanB.de', events=events)

@app.route("/admin",methods=['GET'])
def admin():
    return render_template('admin.html', title='Sia-PlanB.de')

@app.route("/contact",methods=['GET'])
def contact():
    return render_template('contact.html', title='Sia-PlanB.de')

@app.route("/datenschutz",methods=['GET'])
def datenschutz():
    return render_template('datenschutz.html', title='Sia-PlanB.de')

@app.route("/eventmanager",methods=['GET'])
def eventmanager():
    events=Database.get_all_events()
    return render_template('eventmanager.html', title='Sia-PlanB.de',events=events)

@app.route("/faq",methods=['GET'])
def faq():
    return render_template('faq.html', title='Sia-PlanB.de')

@app.route("/impressum",methods=['GET'])
def impressum():
    return render_template('impressum.html', title='Sia-PlanB.de')

@app.route("/login",methods=['GET'])
def login():
    return render_template('login.html', title='Sia-PlanB.de')

@app.route("/newsletter",methods=['GET'])
def newsletter():
    return render_template('newsletter.html', title='Sia-PlanB.de')

@app.route("/register",methods=['GET'])
def register():
    return render_template('register.html', title='Sia-PlanB.de')

@app.route("/profile",methods=['GET'])
def profile():
    return render_template('profile.html', title='Sia-PlanB.de')

if __name__ == "__main__":
    app.run(host='0.0.0.0',debug=True)


