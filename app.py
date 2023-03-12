from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import PendingRollbackError
import os
from datetime import timedelta, datetime
from urllib import parse
import secrets
import pandas as pd
from utils import delete_feedback_data, pandas_to_html
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
app = Flask(__name__)

server = "510-emergencies.database.windows.net"
database = "cea-app-users"
username = os.getenv("SQL_USERNAME")
password = os.getenv("SQL_PASSWORD")
driver = '{ODBC Driver 17 for SQL Server}'
odbc_str = 'DRIVER=' + driver + ';SERVER=' + server + ';PORT=1433;UID=' + username + ';DATABASE=' + database + ';PWD=' + password
app.config['SECRET_KEY'] = secrets.token_urlsafe(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mssql+pyodbc:///?odbc_connect=' + parse.quote_plus(odbc_str)
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
db = SQLAlchemy(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)  # primary keys are required by SQLAlchemy
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(100))

class Dataset(db.Model):
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)  # primary keys are required by SQLAlchemy
    user_email = db.Column(db.String(100))
    name = db.Column(db.String(100))
    place = db.Column(db.String(100))
    date = db.Column(db.String(100))

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# authentication #######################################################################################################

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


@login_manager.unauthorized_handler
def unauthorized_handler():
    return render_template('login.html')


def check_login(email):
    for try_ in range(100):
        try:
            user = User.query.filter_by(email=email).first()
            return user
        except PendingRollbackError:
            db.session.rollback()


@app.route('/login', methods=['GET'])
def login():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login_post():
    # login code goes here
    email = request.form.get('email')
    password = request.form.get('password')

    # check if connection still active
    user = check_login(email=email)

    # check if the user actually exists
    # take the user-supplied password, hash it, and compare it to the hashed password in the database
    if not user or user.password.strip() != password:
        flash('Please check your login details and try again')
        return redirect(url_for('login'))  # if the user doesn't exist or password is wrong, reload the page

    # if the above check passes, then we know the user has the right credentials
    login_user(user, remember=False, duration=timedelta(days=1))

    return render_template('index_ds.html')


@app.route('/signup', methods=['GET'])
def signup():
    return render_template('signup.html')


@app.route('/signup', methods=['POST'])
def signup_post():

    # code to validate and add user to database goes here
    email = request.form.get('email')
    name = request.form.get('name')
    password = request.form.get('password')

    if email == "" or name == "" or password == "":
        flash('Insert your email, name and password')
        return redirect(url_for('signup'))

    user = check_login(email=email)

    if user:  # if a user is found, we want to redirect back to signup page so user can try again
        flash('Email address already exists')
        return redirect(url_for('signup'))

    # create a new user with the form data. Hash the password so the plaintext version isn't saved.
    new_user = User(email=email, name=name, password=password)

    # add the new user to the database
    db.session.add(new_user)
    db.session.commit()

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('login'))

# dataset ##############################################################################################################

@app.route('/index_ds')
@login_required
def index_ds():
    return render_template('index_ds.html')


@app.route('/name_ds', methods=['GET'])
@login_required
def name_ds():
    return render_template('name_ds.html')


@app.route('/create_ds', methods=['POST'])
@login_required
def create_ds():
    if 'ds_name' in request.form.keys():

        if request.form['ds_name'] == "":
            flash('Specify the name of the dataset')
            return redirect(url_for('name_ds'))
        if request.form['ds_place'] == "":
            flash('Specify a location')
            return redirect(url_for('name_ds'))
        if request.form['ds_date'] == "":
            flash('Specify a date')
            return redirect(url_for('name_ds'))

        # create ds
        ds = Dataset.query.filter_by(
            user_email=current_user.email,
            name=request.form['ds_name']
        ).first()  # if this returns a dataset, then the name already exists in database

        if ds:  # if a dataset is found, redirect back to name_ds
            flash(f"Dataset {request.form['ds_name']} already exists")
            return redirect(url_for('name_ds'))

        # create a new dataset
        new_ds = Dataset(
            user_email=current_user.email,
            name=request.form['ds_name'],
            place=request.form['ds_place'],
            date=request.form['ds_date']
        )

        # add the new dataset to the database
        db.session.add(new_ds)
        db.session.commit()

        db.session.flush()

        session['ds_id'] = new_ds.id
        session['ds_name'] = request.form['ds_name']
        return redirect(url_for('main.upload_data'))
    else:
        return render_template('name_ds.html')


@app.route('/list_ds', methods=['GET'])
@login_required
def list_ds():
    datasets = Dataset.query.filter_by(user_email=current_user.email)
    ds_data = {}
    for ds in datasets:
        ds_data[ds.name] = ds.id
    if len(ds_data) == 0:
        return render_template('no_ds.html')
    else:
        return render_template('list_ds.html',
                               data=ds_data)


@app.route('/select_ds', methods=['POST'])
@login_required
def select_ds():
    if 'ds_id' in request.form.keys() and 'ds_name' in request.form.keys():
        session['ds_id'] = request.form['ds_id']
        session['ds_name'] = request.form['ds_name']
        return redirect(url_for('main.index'))
    else:
        return render_template('list_ds.html')


@app.route('/list_ds_delete', methods=['GET'])
@login_required
def list_ds_delete():
    datasets = Dataset.query.filter_by(user_email=current_user.email)
    ds_data = {}
    for ds in datasets:
        ds_data[ds.name] = ds.id
    if len(ds_data) == 0:
        return render_template('no_ds.html')
    else:
        return render_template('list_ds_delete.html',
                               data=ds_data)


@app.route('/delete_ds_confirm', methods=['POST'])
@login_required
def delete_ds_confirm():
    if 'ds_id' in request.form.keys():
        session['ds_id'] = request.form['ds_id']
        return render_template('delete_ds_confirm.html',
                               ds_id=session['ds_id'])
    else:
        return render_template('list_ds_delete.html')


@app.route('/delete_ds', methods=['POST'])
@login_required
def delete_ds():
    if 'ds_id' in request.form.keys():
        session['ds_id'] = request.form['ds_id']
        # delete feedback data
        delete_feedback_data(user_email=current_user.email, ds_id=session['ds_id'])
        # delete dataset
        ds_to_delete = Dataset.query.filter_by(id=session['ds_id']).first()
        db.session.delete(ds_to_delete)
        db.session.commit()
        return render_template('index_ds.html')
    else:
        return render_template('list_ds_delete.html')


# framework
from framework import framework as framework_blueprint
app.register_blueprint(framework_blueprint)

# main menu
from main import main as main_blueprint
app.register_blueprint(main_blueprint)


if __name__ == '__main__':
   app.run()
