from threading import Lock
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import structlog

import os
import sqlite3

app = Flask(__name__)
db_path = os.environ.get('DB_PATH', '/data/db.sqlite3')
socketio = SocketIO(app)
log = structlog.get_logger()

def cursortodict(cursor):
    desc = cursor.description
    column_names = [col[0] for col in desc]
    data = [dict(zip(column_names, row))  
            for row in cursor.fetchall()]
    return data

def get_db_connection():
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute('CREATE TABLE IF NOT EXISTS actions (`id` INT PRIMARY KEY, `text` TEXT, `order` INT, `status` INT)')
    con.commit()
    
    return con

def get_current_git_tag():
    return os.popen('git describe --tags').read().strip()

@app.route('/')
def home():
    tag = get_current_git_tag()
    return render_template('index.html', tag=tag)

@app.route('/admin')
def admin():
    tag = get_current_git_tag()
    return render_template('admin.html', tag=tag)

@socketio.on('connect')
def handle_connect():
    log.info("client connected")
    emit('connected', 'Server connected')

@socketio.on('toggle_state')
def handle_toggle_state(data):
    log.info("Toggling state", data=data)
    con = get_db_connection()
    cur = con.cursor()
    if 'id' not in data:
        emit('error', 'Missing id')
        return
    cur.execute('UPDATE actions SET status = 1 - status WHERE id = ?', (data['id'],))
    con.commit()
    cur.execute('SELECT * FROM actions WHERE id = ?', (data['id'],))
    data = cursortodict(cur)[0]
    update_all_clients(data=data)

@socketio.on('delete')
def handle_delete(data):
    log.info("Deleting", data=data)
    con = get_db_connection()
    cur = con.cursor()
    if 'id' not in data:
        emit('error', 'Missing id')
        return
    cur.execute('DELETE FROM actions WHERE id = ?', (data['id'],))
    con.commit()
    emit('deleted', data['id'], broadcast=True)
    update_all_clients()

@socketio.on('save')
def handle_save(data):
    log.info("Saving", data=data)
    con = get_db_connection()
    cur = con.cursor()
    if 'id' not in data or 'text' not in data:
        emit('error', 'Missing id or text')
        return
    cur.execute('UPDATE actions SET text = ? WHERE id = ?', (data['text'], data['id']))
    con.commit()
    cur.execute('SELECT * FROM actions WHERE id = ?', (data['id'],))
    data = cursortodict(cur)[0]
    update_all_clients(data=data)

@socketio.on('up')
def handle_up(data):
    log.info("Moving up", data=data)
    con = get_db_connection()
    cur = con.cursor()
    if 'id' not in data:
        emit('error', 'Missing id')
        return
    cur.execute('SELECT `order` FROM actions WHERE id = ?', (data['id'],))
    order = cur.fetchone()[0]
    cur.execute('SELECT `id`, `order` FROM actions WHERE `order` < ? ORDER BY `order` DESC LIMIT 1', (order,))
    try:
        prev_id, prev_order = cur.fetchone()
    except TypeError:
        return
    cur.execute('UPDATE actions SET `order` = ? WHERE id = ?', (order, prev_id))
    cur.execute('UPDATE actions SET `order` = ? WHERE id = ?', (prev_order, data['id']))
    con.commit()
    update_all_clients()

@socketio.on('down')
def handle_down(data):
    log.info("Moving down", data=data)
    con = get_db_connection()
    cur = con.cursor()
    if 'id' not in data:
        emit('error', 'Missing id')
        return
    cur.execute('SELECT `order` FROM actions WHERE id = ?', (data['id'],))
    order = cur.fetchone()[0]
    log.info("Order", order=order)
    cur.execute('SELECT `id`, `order` FROM actions WHERE `order` > ? ORDER BY `order` ASC LIMIT 1', (order,))
    try:
        next_id, next_order = cur.fetchone()
    except TypeError:
        return
    cur.execute('UPDATE actions SET `order` = ? WHERE id = ?', (order, next_id))
    cur.execute('UPDATE actions SET `order` = ? WHERE id = ?', (next_order, data['id']))
    con.commit()
    update_all_clients()

@socketio.on('add')
def handle_add(data):
    log.info("Adding", data=data)
    con = get_db_connection()
    cur = con.cursor()
    if 'text' not in data:
        emit('error', 'Missing text')
        return
    max_id = cur.execute('SELECT MAX(`id`) FROM actions').fetchone()[0]
    log.info("Max id", max_id=max_id)
    if max_id is None:
        max_id = 0
    max_order = cur.execute('SELECT MAX(`order`) FROM actions').fetchone()[0]
    if max_order is None:
        max_order = 0
    cur.execute('INSERT INTO actions VALUES (?, ?, ?, 0)', (max_id + 1, data['text'], max_order + 1))
    con.commit()
    cur.execute('SELECT * FROM actions WHERE `order` = ?', (max_order + 1,))
    data = cursortodict(cur)[0]
    update_all_clients(data=data)

def update_all_clients(data=None):
    con = get_db_connection()
    cur = con.cursor()
    if data is None:
        cur.execute('SELECT * FROM actions ORDER BY `order`')
        data = cursortodict(cur)
        emit('all_data', data, broadcast=True)
    else:
        data = [data]
        emit('partial_data', data, broadcast=True)

@socketio.on('request_all_data')
def handle_message():
    con = get_db_connection()
    cur = con.cursor()
    cur.execute('SELECT * FROM actions ORDER BY `order`')
    data = cursortodict(cur)
    emit('all_data', data)

@socketio.on('delete')
def handle_delete(data):
    log.info("Deleting", data=data)
    con = get_db_connection()
    cur = con.cursor()
    if 'id' not in data:
        emit('error', 'Missing id')
        return
    cur.execute('DELETE FROM actions WHERE id = ?', (data['id'],))
    con.commit()
    emit('deleted', {'id': data['id']}, broadcast=True)

@socketio.on('reset_all')
def handle_reset_all():
    log.info("Resetting all")
    con = get_db_connection()
    cur = con.cursor()
    cur.execute('UPDATE actions SET status = 0')
    con.commit()
    update_all_clients()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    #app.run(debug=True, host='0.0.0.0', port=port)
    print("app running")
    socketio.run(app)
