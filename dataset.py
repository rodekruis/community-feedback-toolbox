from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from sqlalchemy import exc
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from models import Dataset
from flask import current_app
from utils import delete_feedback_data
db = current_app.config['SQLALCHEMY_DATABASE']
ds = Blueprint('dataset', __name__)


@ds.route('/index_ds')
@login_required
def index_ds():
    return render_template('index_ds.html')


@ds.route('/name_ds', methods=['GET'])
@login_required
def name_ds():
    return render_template('name_ds.html')


@ds.route('/create_ds', methods=['POST'])
@login_required
def create_ds():
    if 'ds_name' in request.form.keys():

        if request.form['ds_name'] == "":
            flash('Please specify the name of the dataset.')
            return redirect(url_for('dataset.name_ds'))
        if request.form['ds_place'] == "":
            flash('Please specify a place.')
            return redirect(url_for('dataset.name_ds'))
        if request.form['ds_date'] == "":
            flash('Please specify a date.')
            return redirect(url_for('dataset.name_ds'))

        # create ds
        ds = Dataset.query.filter_by(
            user_email=current_user.email,
            name=request.form['ds_name']
        ).first()  # if this returns a dataset, then the name already exists in database

        if ds:  # if a dataset is found, redirect back to name_ds
            flash(f"Dataset {request.form['ds_name']} already exists")
            return redirect(url_for('dataset.name_ds'))

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
        return redirect(url_for('main.index'))
    else:
        return render_template('name_ds.html')


@ds.route('/list_ds', methods=['GET'])
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


@ds.route('/select_ds', methods=['POST'])
@login_required
def select_ds():
    if 'ds_id' in request.form.keys() and 'ds_name' in request.form.keys():
        session['ds_id'] = request.form['ds_id']
        session['ds_name'] = request.form['ds_name']
        return redirect(url_for('main.index'))
    else:
        return render_template('list_ds.html')


@ds.route('/list_ds_delete', methods=['GET'])
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


@ds.route('/delete_ds_confirm', methods=['POST'])
@login_required
def delete_ds_confirm():
    if 'ds_id' in request.form.keys():
        session['ds_id'] = request.form['ds_id']
        return render_template('delete_ds_confirm.html',
                               ds_id=session['ds_id'])
    else:
        return render_template('list_ds_delete.html')


@ds.route('/delete_ds', methods=['POST'])
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


