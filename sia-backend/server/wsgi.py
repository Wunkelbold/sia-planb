from flask import Flask, render_template, send_from_directory
import os


app = Flask(__name__)
app = Flask(__name__, template_folder='static/templates')
app.config.from_object(__name__)






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


