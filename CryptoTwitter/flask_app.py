from flask import Flask, request, url_for
from flask.templating import render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy_utils import database_exists, create_database
from werkzeug.utils import redirect
from threading import Thread
import main
import time

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///following.db'
db = SQLAlchemy(app)

class Following(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.String(100), nullable=False)
    user_last_status = db.Column(db.String(300), nullable=True)
    user_avatar = db.Column(db.String(300), nullable=True)
    user_follows = db.Column(db.String, nullable=True)
    user_follows_ids = db.Column(db.String, nullable=True)
    new_follows = db.Column(db.String, nullable=True)
    follows_date_changes = db.Column(db.String, nullable=True)
    removed_follows = db.Column(db.String, nullable=True)
    unfollows_date_changes = db.Column(db.String, nullable=True)

def init_bot():
    global twt_bot, first_run
    create_db_if_not_exists()
    twt_bot = main.Twt_BOT()
    thread1 = Thread(target=twt_bot.main_loop)
    thread1.start()
    time.sleep(2.5)
    first_run = False

def create_db_if_not_exists():
    engine = create_engine("sqlite:///following.db")
    if not database_exists(engine.url):
        create_database(engine.url)
        db.create_all()

@app.route('/add', methods=['POST'])
def add_user():
    global twt_bot
    form_user = request.form['user_name']
    form_user = form_user.replace('@', '')
    twt_bot.add_user_to_db(form_user)
    return redirect(url_for('main_wall'))
    
@app.route('/remove/user_nickname=<user_nickname>', methods=['GET'])
def rem_user(user_nickname):
    global twt_bot
    twt_bot.rem_user(user_nickname)
    return redirect(url_for('main_wall'))


@app.route('/', methods=['GET'])
def main_wall():
    if first_run:
        init_bot()
    tracking_users = Following.query.all()
    return render_template('index.html', tracking_users=tracking_users, bot=twt_bot)

@app.route('/<path:path>')
def catch_all(path):
    return redirect(url_for('main_wall')) 

if __name__=="__main__":
    global first_run
    first_run = True
    app.run(host='0.0.0.0', debug=True, port=8080)