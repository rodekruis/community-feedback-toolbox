from flask import Blueprint, render_template
from flask_login import login_required, current_user
from flask import render_template, request, redirect, url_for, session, flash, send_file
from utils import query_items_by_partition_key, pandas_to_html, get_cosmos_db
import os
import pandas as pd
from datetime import datetime
import logging
cosmos_db = get_cosmos_db()
framework = Blueprint('framework', __name__)


@framework.route('/index_framework')
@login_required
def index_framework():
    return render_template('index_framework.html')


@framework.route('/name_framework', methods=['GET'])
@login_required
def name_framework():
    return render_template('name_framework.html')


def process_framework(framework_name):
    raw_data_path = 'data/framework_raw.xlsx'
    try:
        sheet_names = pd.ExcelFile(raw_data_path).sheet_names
        for sheet in sheet_names:
            df = pd.read_excel(raw_data_path, sheet_name=sheet)
            df.columns = df.columns.str.lower()
            if all(item in df.columns for item in ['type', 'category', 'code']):
                break
        df = df.fillna(method="ffill")
        df = df.replace({'\'': ''}, regex=True)
        for col in df.columns:
            df[col] = df[col].str.normalize('NFC')

        df.columns = df.columns.str.lower()
        for level in ['type', 'category', 'code']:
            df[level] = df[level].astype(str)
        data_to_save = []
        framework_id = int(round(datetime.now().timestamp()))
        for ix, row in df.iterrows():
            body = {
                'id': str(framework_id) + '_' + str(ix),
                'framework_name': str(framework_name),
                'framework_id': str(framework_id),
                'partitionKey': current_user.email
            }
            for key in row.keys():
                if key != 'id' and key != 'partitionKey':
                    body[key] = str(row[key])
            data_to_save.append(body)

        cosmos_container = cosmos_db.get_container_client('Framework')
        # save to cosmos db
        for entry in data_to_save:
            cosmos_container.create_item(body=entry)
        os.remove(raw_data_path)

        return df, framework_id
    except Exception as e:
        logging.exception(e)
        return 'error'


@framework.route('/create_framework', methods=['POST'])
@login_required
def create_framework():
    if 'framework_name' in request.form.keys():
        framework_name = request.form['framework_name']
        if framework_name == "":
            flash('Specify the name of the framework')
            return redirect(url_for('framework.name_framework'))
        if request.files['file'].filename == '':
            flash('Upload a file')
            return redirect(url_for('framework.name_framework'))
        f = request.files['file']
        f.save('data/framework_raw.xlsx')
        # upload the new framework
        df, framework_id = process_framework(framework_name=framework_name)
        if type(df) == str:
            if df == 'error':
                return render_template('upload_error_framework.html')
        columns, rows = pandas_to_html(df)
        return render_template('view_framework.html',
                               columns=columns,
                               rows=rows,
                               framework_name=framework_name,
                               framework_id=framework_id)
    else:
        return render_template('name_framework.html')


@framework.route("/download_framework_template", methods=['POST'])
@login_required
def download_template():
    return send_file('data/coding_framework_template.xlsx', as_attachment=True)


@framework.route('/list_framework', methods=['GET'])
@login_required
def list_framework(start_validate="false"):
    cosmos_container = cosmos_db.get_container_client('Framework')
    framework_data = pd.concat(
        [pd.DataFrame(query_items_by_partition_key(cosmos_container, "standard_coding_frameworks")),
         pd.DataFrame(query_items_by_partition_key(cosmos_container, current_user.email))],
        ignore_index=True)
    framework_data['framework_type'] = framework_data['framework_type'].fillna('custom')
    if len(framework_data) == 0:
        return render_template('no_framework.html')
    else:
        # fr_data = {}
        # for framework_id in framework_data['framework_id'].unique():
        #     framework_data_ = framework_data[framework_data['framework_id'] == framework_id]
        #     framework_name = framework_data_.framework_name.unique()[0]
        #     fr_data[framework_name] = framework_data_.framework_id.unique()[0]
        # return render_template('list_framework.html',
        #                        data=fr_data,
        #                        start_validate=start_validate)
        framework_data['select'] = 'select'
        framework_data['view'] = 'view'
        columns, rows = pandas_to_html(
            framework_data[['framework_id', 'framework_name', 'framework_type', 'view', 'select']].drop_duplicates(),
            replace_values={},
            replace_columns={
                'framework_name': 'framework name',
                'framework_type': 'framework type'
            }
        )
        print(rows)
        return render_template('list_framework.html',
                               columns=columns,
                               rows=rows,
                               start_validate=start_validate)


@framework.route('/select_framework', methods=['POST'])
@login_required
def select_framework():
    if 'framework_id' in request.form.keys() and 'framework_name' in request.form.keys():
        session['framework_id'] = request.form['framework_id']
        session['framework_name'] = request.form['framework_name']
        if 'start_validate' not in request.form.keys():
            return redirect(url_for('main.index'))
        if request.form['start_validate'] == "true":
            return redirect(url_for('main.validate'))
        else:
            return redirect(url_for('main.index'))
    else:
        return render_template('list_framework.html')


@framework.route('/view_framework', methods=['POST'])
@login_required
def view_framework():
    if 'framework_id' in request.form.keys() and 'framework_name' in request.form.keys():
        framework_id = request.form['framework_id']
        framework_name = request.form['framework_name']
        cosmos_container = cosmos_db.get_container_client('Framework')
        framework_data = pd.concat(
            [pd.DataFrame(query_items_by_partition_key(cosmos_container, "standard_coding_frameworks")),
             pd.DataFrame(query_items_by_partition_key(cosmos_container, current_user.email))],
            ignore_index=True)
        framework_data = framework_data[framework_data['framework_id'] == request.form['framework_id']]
        framework_data = framework_data[['type', 'category', 'code']]
        # session['framework_data'] = framework_data.to_json(orient='split')
        columns, rows = pandas_to_html(framework_data)
        return render_template('view_framework.html',
                               columns=columns,
                               rows=rows,
                               framework_id=framework_id,
                               framework_name=framework_name)
    else:
        return render_template('list_framework.html')


@framework.route('/list_framework_delete', methods=['GET'])
@login_required
def list_framework_delete():
    cosmos_container = cosmos_db.get_container_client('Framework')
    framework_data = pd.DataFrame(query_items_by_partition_key(cosmos_container, current_user.email))
    if framework_data.empty:
        return render_template('no_framework.html')
    fr_data = {}
    for framework_name in framework_data['framework_name'].unique():
        fr_data[framework_name] = framework_data[framework_data['framework_name'] == framework_name].framework_id.unique()[0]
    if len(fr_data) == 0:
        return render_template('no_framework.html')
    else:
        return render_template('list_framework_delete.html',
                               data=fr_data)


@framework.route('/delete_framework_confirm', methods=['POST'])
@login_required
def delete_framework_confirm():
    if 'framework_id' in request.form.keys():
        session['framework_id'] = request.form['framework_id']
        return render_template('delete_framework_confirm.html',
                               framework_id=session['framework_id'])
    else:
        return render_template('list_framework_delete.html')


@framework.route('/delete_framework', methods=['POST'])
@login_required
def delete_framework():
    if 'framework_id' in request.form.keys():
        cosmos_container = cosmos_db.get_container_client('Framework')
        item_list = pd.DataFrame(query_items_by_partition_key(cosmos_container, current_user.email))
        item_list = item_list[item_list['framework_id'] == request.form['framework_id']]
        for ix, row in item_list.iterrows():
            cosmos_container.delete_item(item=str(row['id']), partition_key=str(current_user.email))
        return render_template('index_framework.html')
    else:
        return render_template('list_framework_delete.html')
