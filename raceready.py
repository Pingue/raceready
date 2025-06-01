from threading import Lock
from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
import structlog
import base64
import uuid
import os
import sqlite3

app = Flask(__name__)
db_path = os.environ.get('DB_PATH', '/data/db.sqlite3')
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)
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


@app.route('/toggle_by_title', methods=['POST'])
def toggle_by_title():
    """HTTP route to toggle the status of an action by its title."""
    data = request.get_json()
    if not data or 'title' not in data:
        return jsonify({'error': 'Missing title'}), 400

    title = data['title']

    con = get_db_connection()
    cur = con.cursor()
    cur.execute('SELECT id, status FROM actions WHERE text = ?', (title,))
    result = cur.fetchone()

    if result is None:
        con.close()
        return jsonify({'error': 'Action not found'}), 404

    action_id, current_status = result
    new_status = 1 - current_status  # Toggle the status (0 -> 1, 1 -> 0)

    cur.execute('UPDATE actions SET status = ? WHERE id = ?', (new_status, action_id))
    con.commit()
    cur.execute('SELECT * FROM actions WHERE id = ?', (action_id,))
    updated_action = cursortodict(cur)[0]
    con.close()

    # Notify all connected WebSocket clients
    update_all_clients(data=updated_action)

    return jsonify({'success': True, 'data': updated_action}), 200


@app.route('/action_title', methods=['GET'])
def get_action_title():
    """HTTP route to return the title (text) of an action by its ID."""
    action_id = request.args.get('id')
    if not action_id:
        return jsonify({'error': 'Missing id'}), 400

    try:
        action_id = int(action_id)
    except ValueError:
        return jsonify({'error': 'Invalid id'}), 400

    con = get_db_connection()
    cur = con.cursor()
    cur.execute('SELECT text FROM actions WHERE id = ?', (action_id,))
    result = cur.fetchone()
    con.close()

    if result is None:
        return jsonify({'error': 'Action not found'}), 404

    return jsonify({'text': result[0]}), 200

import uuid


@app.route("/companion_export", methods=["GET"])
def generate_companion_export():
    """HTTP route to generate a Bitfocus Companion page export JSON."""
    con = get_db_connection()
    cur = con.cursor()
    cur.execute("SELECT id, text FROM actions ORDER BY `order`")
    actions = cur.fetchall()
    con.close()

    if not actions:
        return jsonify({"error": "No actions found"}), 404

    # Prepare controls grid
    controls = {
        "0": {"0": {"type": "pageup"}},  # Row 0
        "1": {"0": {"type": "pagenum"}},  # Row 1
        "2": {"0": {"type": "pagedown"}},  # Row 2
        "3": {  # Row 3
            "0": {  # Overall status button
                "type": "button",
                "style": {
                    "text": "RACE READY (reset)",
                    "textExpression": False,
                    "size": "auto",
                    "png64": None,
                    "alignment": "center:center",
                    "pngalignment": "center:center",
                    "color": 16777215,
                    "bgcolor": 0,
                    "show_topbar": "default",
                },
                "options": {
                    "relativeDelay": False,
                    "rotaryActions": False,
                    "stepAutoProgress": True,
                },
                "feedbacks": [
                    {
                        "id": base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b'=').decode('utf-8'),
                        # definitionId is required in future
                        # "definitionId": "RaceReadyState",
                        # instance_id=connectionId in future
                        "instance_id": "LKMfUhdXb1f2QGkvRrC5w",
                        "options": {},
                        # type will be "feedback" in future
                        "type": "RaceReadyOverallState",
                        "style": {"bgcolor": 65280, "color": 0},
                        "isInverted": False,
                    }
                ],
                "steps": {
                    "0": {
                        "action_sets": {
                            "down": [
                            {
                                "id": base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b'=').decode('utf-8'),
                                # action=definitionId in future
                                "action": "reset_all",
                                # instance=connectionId in future
                                "instance": "LKMfUhdXb1f2QGkvRrC5w",
                                "options": {},
                                # type is required in future
                                # "type": "action",
                            },
                        ],
                            "up": [],
                        },
                        "options": {"runWhileHeld": []},
                    }
                },
            }
        },
    }

    # Fill rows and columns with actions
    row = 0
    col = 1
    count = 1
    for idx, action in enumerate(actions):
        button = {
            "type": "button",
            "style": {
                "text": "$(raceready:actiontext" + str(action["id"]) + ")",
                "textExpression": False,
                "size": "auto",
                "png64": None,
                "alignment": "center:center",
                "pngalignment": "center:center",
                "color": 16777215,
                "bgcolor": 0,
                "show_topbar": "default",
            },
            "options": {
                "relativeDelay": False,
                "rotaryActions": False,
                "stepAutoProgress": True,
            },
            "feedbacks": [
                {
                    "id": base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b'=').decode('utf-8'),
                    # definitionId is required in future
                    # "definitionId": "RaceReadyState",
                    # instance_id=connectionId in future
                    "instance_id": "LKMfUhdXb1f2QGkvRrC5w",
                    "options": {"id": str(action["id"])},
                    # type will be "feedback" in future
                    "type": "RaceReadyState",
                    "style": {"bgcolor": 65280, "color": 0},
                    "isInverted": False,
                }
            ],
            "steps": {
                "0": {
                    "action_sets": {
                        "down": [
                            {
                                "id": base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b'=').decode('utf-8'),
                                # action=definitionId in future
                                "action": "toggle",
                                # instance=connectionId in future
                                "instance": "LKMfUhdXb1f2QGkvRrC5w",
                                "options": {"id": str(action["id"])},
                                # type is required in future
                                # "type": "action",
                            },
                        ],
                        "up": [],
                    },
                    "options": {"runWhileHeld": []},
                }
            },
        }

        # Add button to the grid
        if str(row) not in controls:
            controls[str(row)] = {}
        controls[str(row)][str(col)] = button

        # Move to the next column, and wrap to the next row if needed
        col += 1
        if col > 7:  # Max 8 columns (0-7)
            col = 1
            row += 1
        count += 1

    # Prepare the export JSON
    export_json = {
        "version": 6,
        "type": "page",
        "page": {
            "name": "Race Ready",
            "controls": controls,
            "gridSize": {"minColumn": 0, "maxColumn": 7, "minRow": 0, "maxRow": 3},
        },
        "instances": {
            "LKMfUhdXb1f2QGkvRrC5w": {
                "instance_type": "raceready",
                "moduleVersionId": "dev",
                "updatePolicy": "stable",
                "sortOrder": 1,
                "label": "raceready",
                "isFirstInit": False,
                "config": {
                    "host": "192.168.10.10",
                    "port": "5000"
                },
                "lastUpgradeIndex": -1,
                "enabled": True
            }
        },
        "oldPageNumber": 1,
    }

    # Force download with a specific filename
    response = jsonify(export_json)
    response.headers["Content-Disposition"] = (
        "attachment; filename=raceready.companionconfig"
    )
    return response


@socketio.on('connect')
def handle_connect():
    log.info("client connected")
    emit('connected', 'Server connected')

def toggle_state_logic(action_id):
    """Core logic for toggling the state of an action."""
    con = get_db_connection()
    cur = con.cursor()
    cur.execute('UPDATE actions SET status = 1 - status WHERE id = ?', (action_id,))
    con.commit()
    cur.execute('SELECT * FROM actions WHERE id = ?', (action_id,))
    action = cursortodict(cur)[0]
    con.close()
    update_all_clients(data=action)
    return action

@socketio.on('toggle_state')
def handle_toggle_state(data):
    """WebSocket handler for toggling state."""
    log.info("Toggling state", data=data)
    if 'id' not in data:
        emit('error', 'Missing id')
        return
    try:
        action = toggle_state_logic(data['id'])
        emit('success', action)
    except Exception as e:
        log.error("Error toggling state", error=str(e))
        emit('error', 'Internal server error')

@app.route('/toggle', methods=['GET'])
def toggle_state_http():
    """HTTP GET endpoint for toggling state."""
    action_id = request.args.get('id')
    if not action_id:
        return jsonify({'error': 'Missing id'}), 400
    try:
        action = toggle_state_logic(action_id)
        return jsonify({'success': True, 'data': action}), 200
    except Exception as e:
        log.error("Error toggling state", error=str(e))
        return jsonify({'error': 'Internal server error'}), 500

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
    log.info("Updating all clients", data=data)
    if data is None:
        cur.execute('SELECT * FROM actions ORDER BY `order`')
        data = cursortodict(cur)
        socketio.emit('all_data', data)
    else:
        data = [data]
        socketio.emit('partial_data', data)

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
    print("app running")
    socketio.run(app, host="0.0.0.0", port=port)
