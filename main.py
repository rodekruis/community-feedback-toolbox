from flask import Blueprint, render_template
from flask_login import login_required, current_user
from flask import render_template, redirect, request, send_file, session, url_for
from utils import get_feedback_entry, get_feedback_data, save_feedback_data, delete_feedback_data, \
    pandas_to_html, update_feedback_entry, get_cosmos_db, query_items_by_partition_key
import os
import pandas as pd
import numpy as np
from datetime import datetime
from framework import list_framework
import logging
import unicodedata as ud
cosmos_db = get_cosmos_db()
main = Blueprint('main', __name__)

@main.route('/automated_analysis_check', methods=['GET'])
@login_required
def automated_analysis_check():
    is_standard = is_framework_standard()
    if is_standard is None:
        return list_framework(start_validate="false")
    else:
        if is_standard:
            return render_template('automated_analysis_started.html')
        else:
            return render_template('automated_analysis_warning.html')



@main.route('/validate', methods=['GET'])
@login_required
def validate():
    data = get_feedback_data(user_email=current_user.email, ds_id=session['ds_id'], keep_id=True)
    if data is None:
        return render_template('no_data.html')
    else:
        data = data[['id', 'feedback message', 'type', 'category', 'code', 'validated']]
        data_to_validate = data[data['validated'] == 'No']
        if len(data_to_validate) == 0:
            return render_template('all_data_analyzed.html')
        message_to_validate = data_to_validate.iloc[0].to_dict()
        coding_framework = get_coding_framework()
        if coding_framework is None:
            return list_framework(start_validate="true")
        else:
            type_selected, category_selected, code_selected = "", "", ""
            if not pd.isna(message_to_validate['type']) and message_to_validate['type'] != "":
                type_selected = message_to_validate['type']
            if not pd.isna(message_to_validate['category']) and message_to_validate['category'] != "":
                category_selected = message_to_validate['category']
            if not pd.isna(message_to_validate['code']) and message_to_validate['code'] != "":
                code_selected = message_to_validate['code']

            # build framework dict
            framework_dict = {}
            for type_ in coding_framework['type'].unique():
                type_dict = {}
                dft = coding_framework[coding_framework['type'] == type_]
                for cat in dft['category'].unique():
                    type_dict[cat] = list(dft[dft['category'] == cat]['code'].unique())
                framework_dict[type_] = type_dict

            # if lower levels are selected and higher ones are not, fill them
            if code_selected != "" and (category_selected == "" or type_selected == ""):
                for type in framework_dict.keys():
                    for category in framework_dict[type].keys():
                        if code_selected in framework_dict[type][category]:
                            category_selected = category
                            type_selected = type
                            break

            # if selected not in framework, ignore
            if type_selected not in coding_framework['type'].unique():
                type_selected = ""
            if category_selected not in coding_framework['category'].unique():
                category_selected = ""
            if code_selected not in coding_framework['code'].unique():
                code_selected = ""

            return render_template('validate.html',
                                   message_id=message_to_validate['id'],
                                   message=message_to_validate['feedback message'],
                                   type_selected=type_selected,
                                   category_selected=category_selected,
                                   code_selected=code_selected,
                                   framework=framework_dict)


@main.route('/entry', methods=['POST', 'GET'])
@login_required
def feedback():
    """Get feedback data."""
    if 'ds_id' not in session.keys():
        return render_template('index_ds.html')

    if 'code' in request.form.keys():
        if request.form['code'].strip() == '':
            return render_template('input.html')
        else:
            code = str(request.form['code'])
    elif 'code' in request.args.keys():
        if request.args['code'].strip() == '':
            return render_template('input.html')
        else:
            code = str(request.args['code'])
    else:
        return render_template('input.html')

    feedback_data = get_feedback_entry(feedback_id=str(session['ds_id'])+str(code),
                                             user_email=current_user.email,
                                             ds_id=session['ds_id'])
    if feedback_data == "not_found":
        return render_template('entry_not_found.html')
    elif feedback_data == "no_data":
        return render_template('no_data.html')
    else:
        for internal_field in ['id', 'ds_id', 'partitionKey']:
            if internal_field in feedback_data.keys():
                feedback_data.pop(internal_field)
        return render_template('entry.html',
                               data=feedback_data)


@main.route('/validate_save', methods=['POST'])
@login_required
def validate_save():
    replace_body = {
        'validated_when': datetime.now().strftime("%m/%d/%Y, %H:%M:%S"),
        'validated_by': str(current_user.email).strip(),
        'validated': 'Yes'
    }
    for level in ['type', 'category', 'code']:
        if level in request.form.keys():
            replace_body[level] = request.form[level]
    result = update_feedback_entry(feedback_id=request.form['message_id'],
                                   user_email=current_user.email,
                                   ds_id=session['ds_id'],
                                   replace_body=replace_body)
    if result == "not_found":
        return render_template('entry_not_found.html')
    elif result == "no_data":
        return render_template('no_data.html')
    else:
        return validate()


def get_coding_framework():
    if 'framework_id' in session.keys():
        cosmos_container = cosmos_db.get_container_client('Framework')
        framework_data = pd.concat(
            [pd.DataFrame(query_items_by_partition_key(cosmos_container, "standard_coding_frameworks")),
             pd.DataFrame(query_items_by_partition_key(cosmos_container, current_user.email))],
            ignore_index=True)
        framework_data = framework_data[framework_data['framework_id'] == session['framework_id']]
        framework_data = framework_data[['type', 'category', 'code']]
        return framework_data
    else:
        return None


def is_framework_standard():
    if 'framework_id' in session.keys():
        cosmos_container = cosmos_db.get_container_client('Framework')
        framework_data = pd.DataFrame(query_items_by_partition_key(cosmos_container, "standard_coding_frameworks"))
        if len(framework_data[framework_data['framework_id'] == session['framework_id']]) == 0:
            return False
        else:
            return True
    else:
        return None


def process_data(partition_key):
    raw_data_path = 'data/data_raw.xlsx'
    try:
        sheet_names = pd.ExcelFile(raw_data_path).sheet_names
        for sheet in sheet_names:
            df = pd.read_excel(raw_data_path, sheet_name=sheet)
            df.columns = df.columns.str.lower()
            if 'feedback message' in df.columns:
                break
        df['feedback message'] = df['feedback message'].astype(str)
        df = df.drop([col for col in df.columns if col.startswith('_') if col != '_id'], axis=1)  # drop KoBo columns
        if 'type of feedback' in df.columns:
            df = df.rename(columns={'type of feedback': 'type'})
            df['type'] = df['type'].fillna('')
            if 'category' not in df.columns and 'code' not in df.columns:
                i = 1
                for level in ['category', 'code']:
                    df.insert(df.columns.tolist().index('type')+i, level, "")
                    i += 1
            else:
                df['category'] = df['category'].fillna('')
                df['code'] = df['code'].fillna('')
        else:
            for level in ['type', 'category', 'code']:
                if level not in df.columns:
                    df[level] = ''
        for level in ['type', 'category', 'code']:
            df[level] = df[level].replace({'\'': ''}, regex=True)
            df[level] = df[level].str.normalize('NFC')
        if 'validated' not in df.columns:
            df['validated'] = 'No'
        df = df.replace('nan', np.nan).dropna(subset=['feedback message'])

        save_feedback_data(data=df, ds_id=session['ds_id'], user_email=partition_key)
        os.remove(raw_data_path)
        return df
    except Exception as e:
        logging.exception(e)
        return 'error'


@main.route('/upload_data', methods=['GET'])
@login_required
def upload_data():
    return render_template('upload_data.html')


@main.route('/uploader', methods=['POST'])
@login_required
def uploader():
    f = request.files['file']
    f.save('data/data_raw.xlsx')
    # empty existing database
    delete_feedback_data(user_email=current_user.email, ds_id=session['ds_id'])
    # then upload the new one
    df = process_data(partition_key=current_user.email)
    if type(df) == str:
        if df == 'error':
            return render_template('upload_error.html')
    df = df[['feedback message', 'type', 'category', 'code', 'validated']]
    columns, rows = pandas_to_html(df)
    return render_template('view_data.html',
                           columns=columns,
                           rows=rows)


@main.route('/view_data', methods=['POST'])
@login_required
def view_data():
    data = get_feedback_data(user_email=current_user.email, ds_id=session['ds_id'])
    if data is None:
        return render_template('no_data.html')
    else:
        data = data[['feedback message', 'type', 'category', 'code', 'validated']]
        columns, rows = pandas_to_html(data)
        return render_template('view_data.html',
                               columns=columns,
                               rows=rows)


@main.route("/download_data", methods=['POST'])
@login_required
def download_data():
    data = get_feedback_data(user_email=current_user.email, ds_id=session['ds_id'])
    if data is None:
        return render_template('no_data.html')
    else:
        data_path = 'data/data_processed.xlsx'
        data.to_excel(data_path, index=False)
        writer = pd.ExcelWriter(data_path, engine='xlsxwriter')
        data.to_excel(writer, sheet_name='DATA', index=False)  # send df to writer
        worksheet = writer.sheets['DATA']  # pull worksheet object
        for idx, col in enumerate(data.columns):  # loop through all columns
            series = data[col]
            max_len = max((
                series.astype(str).map(len).max(),  # len of largest item
                len(str(series.name))  # len of column name/header
            )) + 1
            worksheet.set_column(idx, idx, max_len)  # set column width
        writer.save()
        return send_file(data_path, as_attachment=True)


@main.route("/download_template", methods=['POST'])
@login_required
def download_template():
    return send_file('data/feedback_data_template.xlsx', as_attachment=True)


@main.route('/')
@login_required
def index():
    if 'ds_name' not in session.keys():
        return redirect(url_for('list_ds'))
    else:
        if 'framework_name' in session.keys():
            framework_name = session['framework_name']
        else:
            framework_name = "None"
        data = get_feedback_data(user_email=current_user.email, ds_id=session['ds_id'])
        number_messages, number_messages_validated = 0, 0
        if data is not None:
            number_messages = len(data)
        if number_messages > 0 and 'validated' in data.columns:
            number_messages_validated = len(data[data['validated'] == 'Yes'])
        return render_template('index.html',
                               ds_name=str(session['ds_name']),
                               framework_name=str(framework_name),
                               number_messages=number_messages,
                               number_messages_validated=number_messages_validated)


@main.route('/profile')
def profile():
    return render_template('profile.html', name=current_user.name)