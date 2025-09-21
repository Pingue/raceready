from threading import Lock
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
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
current_checklist_id = None  # Will be set on first access

def get_current_checklist_id():
    """Get the current checklist ID, ensuring it exists in the database."""
    global current_checklist_id
    
    if current_checklist_id is None:
        con = get_db_connection()
        cur = con.cursor()
        # Get the first available checklist
        cur.execute('SELECT id FROM checklists ORDER BY id LIMIT 1')
        result = cur.fetchone()
        if result:
            current_checklist_id = result[0]
        else:
            # No checklists exist, create a default one
            cur.execute('INSERT INTO checklists (name) VALUES (?)', ('Default',))
            con.commit()
            current_checklist_id = cur.lastrowid
        con.close()
    
    return current_checklist_id

def cursortodict(cursor):
    desc = cursor.description
    column_names = [col[0] for col in desc]
    data = [dict(zip(column_names, row))  
            for row in cursor.fetchall()]
    return data

def get_db_connection():
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    # Create checklists table if it doesn't exist
    con.execute('CREATE TABLE IF NOT EXISTS checklists (id INTEGER PRIMARY KEY, name TEXT)')
    
    # Add order column if it doesn't exist
    cur = con.cursor()
    cur.execute("PRAGMA table_info(checklists)")
    columns = [column[1] for column in cur.fetchall()]
    if 'order_pos' not in columns:
        cur.execute('ALTER TABLE checklists ADD COLUMN order_pos INTEGER DEFAULT 0')
        # Set initial order values
        cur.execute('SELECT id FROM checklists ORDER BY id')
        checklists = cur.fetchall()
        for idx, checklist in enumerate(checklists):
            cur.execute('UPDATE checklists SET order_pos = ? WHERE id = ?', (idx + 1, checklist[0]))
        con.commit()
    
    # Check if checklists table is empty, and add a default entry if so
    cur.execute('SELECT COUNT(*) FROM checklists')
    if cur.fetchone()[0] == 0:
        cur.execute('INSERT INTO checklists (name, order_pos) VALUES (?, ?)', ('Default', 1))
        con.commit()
    # Create actions table if it doesn't exist
    con.execute('''
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY,
            text TEXT,
            "order" INT,
            status INT,
            checklist_id INT,
            FOREIGN KEY(checklist_id) REFERENCES checklists(id)
        )
    ''')
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
    cur.execute('SELECT id, status FROM actions WHERE text = ? AND checklist_id = ?', (title, get_current_checklist_id()))
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
    cur.execute('SELECT text FROM actions WHERE id = ? AND checklist_id = ?', (action_id, get_current_checklist_id()))
    result = cur.fetchone()
    con.close()

    if result is None:
        return jsonify({'error': 'Action not found'}), 404

    return jsonify({'text': result[0]}), 200

import uuid


@app.route("/companion_export", methods=["GET"])
def generate_companion_export():
    """HTTP route to serve the static Bitfocus Companion page export file."""
    return send_from_directory(
        'static',
        'raceready.companionconfig',
        as_attachment=True,
        download_name='raceready.companionconfig'
    )

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

@app.route('/toggle_by_normalised_id', methods=['POST'])
def toggle_by_normalised_id():
    data = request.get_json()
    normalised_index = data.get('normalised_index')
    if not normalised_index:
        return jsonify({'error': 'Missing normalised_index'}), 400

    con = get_db_connection()
    cur = con.cursor()
    cur.execute(
        'SELECT id, status FROM actions WHERE checklist_id = ? ORDER BY "order" LIMIT 1 OFFSET ?',
        (get_current_checklist_id(), int(normalised_index) - 1)
    )
    result = cur.fetchone()
    if result is None:
        con.close()
        return jsonify({'error': 'Action not found'}), 404

    action_id, current_status = result
    new_status = 1 - current_status
    cur.execute('UPDATE actions SET status = ? WHERE id = ?', (new_status, action_id))
    con.commit()
    cur.execute('SELECT * FROM actions WHERE id = ?', (action_id,))
    updated_action = cursortodict(cur)[0]
    con.close()
    update_all_clients(data=updated_action)
    return jsonify({'success': True, 'data': updated_action}), 200

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
    cur.execute('INSERT INTO actions VALUES (?, ?, ?, 0, ?)', (max_id + 1, data['text'], max_order + 1, get_current_checklist_id()))
    con.commit()
    cur.execute('SELECT * FROM actions WHERE `order` = ?', (max_order + 1,))
    data = cursortodict(cur)[0]
    update_all_clients(data=data)

def update_all_clients(data=None):
    con = get_db_connection()
    cur = con.cursor()
    log.info("Updating all clients", data=data)
    
    # Get current checklist name
    cur.execute('SELECT name FROM checklists WHERE id = ?', (get_current_checklist_id(),))
    result = cur.fetchone()
    current_phase = result[0] if result else "Default"
    
    if data is None:
        cur.execute('SELECT * FROM actions WHERE checklist_id = ? ORDER BY "order"', (get_current_checklist_id(),))
        actions = cursortodict(cur)
        # Add normalised_index
        log.info("----")
        for idx, action in enumerate(actions, start=1):
            action['normalised_index'] = idx
            log.info(action)
        log.info(actions)
        socketio.emit('all_data', {'actions': actions, 'current_phase': current_phase})
    else:
        # If partial, you may want to recalculate normalised_index for the current checklist
        cur.execute('SELECT * FROM actions WHERE checklist_id = ? ORDER BY "order"', (get_current_checklist_id(),))
        actions = cursortodict(cur)
        id_to_index = {a['id']: i+1 for i, a in enumerate(actions)}
        if isinstance(data, list):
            for d in data:
                d['normalised_index'] = id_to_index.get(d['id'])
        else:
            data['normalised_index'] = id_to_index.get(data['id'])
        socketio.emit('partial_data', data if isinstance(data, list) else [data])
        # Also send current phase for partial updates
        socketio.emit('current_phase', {'current_phase': current_phase})

@socketio.on('request_all_data')
def handle_message():
    con = get_db_connection()
    cur = con.cursor()
    cur.execute('SELECT * FROM actions WHERE checklist_id = ? ORDER BY `order`', (get_current_checklist_id(),))
    actions = cursortodict(cur)
    # Add normalised_index to each action
    for idx, action in enumerate(actions, start=1):
        action['normalised_index'] = idx
    
    # Get current checklist name
    cur.execute('SELECT name FROM checklists WHERE id = ?', (get_current_checklist_id(),))
    result = cur.fetchone()
    current_phase = result[0] if result else "Default"
    con.close()
    
    emit('all_data', {'actions': actions, 'current_phase': current_phase})

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

@app.route('/checklists', methods=['GET'])
def get_checklists():
    con = get_db_connection()
    cur = con.cursor()
    cur.execute('SELECT * FROM checklists ORDER BY order_pos, id')
    checklists = cursortodict(cur)
    con.close()
    return jsonify(checklists)

@app.route('/current_checklist', methods=['GET'])
def get_current_checklist():
    return jsonify({'current_checklist_id': get_current_checklist_id()})

@app.route('/set_checklist', methods=['POST'])
def set_checklist():
    global current_checklist_id
    data = request.get_json()
    checklist_id = data.get('checklist_id')
    if not checklist_id:
        return jsonify({'error': 'Missing checklist_id'}), 400
    current_checklist_id = int(checklist_id)
    # Reset all tasks for the new checklist
    con = get_db_connection()
    cur = con.cursor()
    cur.execute('UPDATE actions SET status = 0;')
    con.commit()
    con.close()
    update_all_clients()
    return jsonify({'success': True})

@app.route('/create_checklist', methods=['POST'])
def create_checklist():
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Missing checklist name'}), 400
    con = get_db_connection()
    cur = con.cursor()
    
    # Get the maximum order position and add 1
    cur.execute('SELECT MAX(order_pos) FROM checklists')
    max_order = cur.fetchone()[0]
    new_order = (max_order or 0) + 1
    
    cur.execute('INSERT INTO checklists (name, order_pos) VALUES (?, ?)', (name, new_order))
    con.commit()
    checklist_id = cur.lastrowid
    con.close()
    return jsonify({'success': True, 'id': checklist_id, 'name': name, 'order_pos': new_order}), 201

@app.route('/rename_checklist', methods=['POST'])
def rename_checklist():
    data = request.get_json()
    checklist_id = data.get('id')
    name = data.get('name')
    if not checklist_id or not name:
        return jsonify({'error': 'Missing id or name'}), 400
    con = get_db_connection()
    cur = con.cursor()
    cur.execute('UPDATE checklists SET name = ? WHERE id = ?', (name, checklist_id))
    con.commit()
    con.close()
    return jsonify({'success': True})

@app.route('/delete_checklist', methods=['POST'])
def delete_checklist():
    data = request.get_json()
    checklist_id = data.get('id')
    if not checklist_id:
        return jsonify({'error': 'Missing id'}), 400
    con = get_db_connection()
    cur = con.cursor()
    # Optionally: delete all actions for this checklist
    cur.execute('DELETE FROM actions WHERE checklist_id = ?', (checklist_id,))
    cur.execute('DELETE FROM checklists WHERE id = ?', (checklist_id,))
    con.commit()
    con.close()
    return jsonify({'success': True})

@socketio.on('toggle_state_by_normalised')
def handle_toggle_state_by_normalised(data):
    """WebSocket handler for toggling state by normalised_index in the current checklist."""
    log.info("Toggling state by normalised_index", data=data)
    normalised_index = data.get('normalised_index')
    if not normalised_index:
        emit('error', 'Missing normalised_index')
        return
    try:
        con = get_db_connection()
        cur = con.cursor()
        cur.execute(
            'SELECT id FROM actions WHERE checklist_id = ? ORDER BY "order" LIMIT 1 OFFSET ?',
            (get_current_checklist_id(), int(normalised_index) - 1)
        )
        result = cur.fetchone()
        if result is None:
            con.close()
            emit('error', 'Action not found')
            return
        action_id = result[0]
        action = toggle_state_logic(action_id)
        emit('success', action)
    except Exception as e:
        log.error("Error toggling state by normalised_index", error=str(e))
        emit('error', 'Internal server error')

@socketio.on('set_checklist')
def handle_set_checklist(data):
    """WebSocket handler for setting the current checklist."""
    global current_checklist_id
    log.info("Setting checklist", data=data)
    checklist_id = data.get('checklist_id')
    if not checklist_id:
        emit('error', 'Missing checklist_id')
        return
    try:
        current_checklist_id = int(checklist_id)
        # Reset all tasks for the new checklist
        con = get_db_connection()
        cur = con.cursor()
        cur.execute('UPDATE actions SET status = 0;')
        con.commit()
        con.close()
        update_all_clients()
    except Exception as e:
        log.error("Error setting checklist", error=str(e))
        emit('error', 'Internal server error')

@socketio.on('get_current_checklist')
def handle_get_current_checklist():
    """WebSocket handler for getting the current checklist."""
    emit('current_checklist', {'current_checklist_id': get_current_checklist_id()})

@socketio.on('get_checklists')
def handle_get_checklists():
    """WebSocket handler for getting all checklists."""
    con = get_db_connection()
    cur = con.cursor()
    cur.execute('SELECT * FROM checklists ORDER BY order_pos, id')
    checklists = cursortodict(cur)
    con.close()
    emit('checklists', checklists)

@socketio.on('next_checklist')
def handle_next_checklist():
    """WebSocket handler for switching to the next checklist."""
    global current_checklist_id
    log.info("Switching to next checklist")
    try:
        con = get_db_connection()
        cur = con.cursor()
        cur.execute('SELECT id FROM checklists ORDER BY id')
        checklist_ids = [row[0] for row in cur.fetchall()]
        con.close()
        
        if not checklist_ids:
            emit('error', 'No checklists available')
            return
            
        try:
            current_index = checklist_ids.index(get_current_checklist_id())
            next_index = (current_index + 1) % len(checklist_ids)  # Wrap around
            current_checklist_id = checklist_ids[next_index]
        except ValueError:
            # Current checklist ID not found, use first one
            current_checklist_id = checklist_ids[0]
        
        # Reset all tasks for the new checklist
        con = get_db_connection()
        cur = con.cursor()
        cur.execute('UPDATE actions SET status = 0;')
        con.commit()
        con.close()
        
        update_all_clients()
        log.info("Switched to checklist", checklist_id=current_checklist_id)
    except Exception as e:
        log.error("Error switching to next checklist", error=str(e))
        emit('error', 'Internal server error')

@socketio.on('previous_checklist')
def handle_previous_checklist():
    """WebSocket handler for switching to the previous checklist."""
    global current_checklist_id
    log.info("Switching to previous checklist")
    try:
        con = get_db_connection()
        cur = con.cursor()
        cur.execute('SELECT id FROM checklists ORDER BY id')
        checklist_ids = [row[0] for row in cur.fetchall()]
        con.close()
        
        if not checklist_ids:
            emit('error', 'No checklists available')
            return
            
        try:
            current_index = checklist_ids.index(get_current_checklist_id())
            prev_index = (current_index - 1) % len(checklist_ids)  # Wrap around
            current_checklist_id = checklist_ids[prev_index]
        except ValueError:
            # Current checklist ID not found, use last one
            current_checklist_id = checklist_ids[-1]
        
        # Reset all tasks for the new checklist
        con = get_db_connection()
        cur = con.cursor()
        cur.execute('UPDATE actions SET status = 0;')
        con.commit()
        con.close()
        
        update_all_clients()
        log.info("Switched to checklist", checklist_id=current_checklist_id)
    except Exception as e:
        log.error("Error switching to previous checklist", error=str(e))
        emit('error', 'Internal server error')

@socketio.on('move_checklist_up')
def handle_move_checklist_up(data):
    """WebSocket handler for moving a checklist up in order."""
    log.info("Moving checklist up", data=data)
    checklist_id = data.get('id')
    if not checklist_id:
        emit('error', 'Missing checklist id')
        return
    
    try:
        con = get_db_connection()
        cur = con.cursor()
        
        # Get current order position
        cur.execute('SELECT order_pos FROM checklists WHERE id = ?', (checklist_id,))
        result = cur.fetchone()
        if not result:
            con.close()
            emit('error', 'Checklist not found')
            return
        
        current_order = result[0]
        
        # Find the checklist with the previous order position
        cur.execute('SELECT id, order_pos FROM checklists WHERE order_pos < ? ORDER BY order_pos DESC LIMIT 1', (current_order,))
        prev_result = cur.fetchone()
        
        if prev_result:
            prev_id, prev_order = prev_result
            # Swap the order positions
            cur.execute('UPDATE checklists SET order_pos = ? WHERE id = ?', (prev_order, checklist_id))
            cur.execute('UPDATE checklists SET order_pos = ? WHERE id = ?', (current_order, prev_id))
            con.commit()
        
        con.close()
        emit('checklist_moved', {'success': True})
        # Refresh checklists for all clients
        handle_get_checklists()
    except Exception as e:
        log.error("Error moving checklist up", error=str(e))
        emit('error', 'Internal server error')

@socketio.on('move_checklist_down')
def handle_move_checklist_down(data):
    """WebSocket handler for moving a checklist down in order."""
    log.info("Moving checklist down", data=data)
    checklist_id = data.get('id')
    if not checklist_id:
        emit('error', 'Missing checklist id')
        return
    
    try:
        con = get_db_connection()
        cur = con.cursor()
        
        # Get current order position
        cur.execute('SELECT order_pos FROM checklists WHERE id = ?', (checklist_id,))
        result = cur.fetchone()
        if not result:
            con.close()
            emit('error', 'Checklist not found')
            return
        
        current_order = result[0]
        
        # Find the checklist with the next order position
        cur.execute('SELECT id, order_pos FROM checklists WHERE order_pos > ? ORDER BY order_pos ASC LIMIT 1', (current_order,))
        next_result = cur.fetchone()
        
        if next_result:
            next_id, next_order = next_result
            # Swap the order positions
            cur.execute('UPDATE checklists SET order_pos = ? WHERE id = ?', (next_order, checklist_id))
            cur.execute('UPDATE checklists SET order_pos = ? WHERE id = ?', (current_order, next_id))
            con.commit()
        
        con.close()
        emit('checklist_moved', {'success': True})
        # Refresh checklists for all clients
        handle_get_checklists()
    except Exception as e:
        log.error("Error moving checklist down", error=str(e))
        emit('error', 'Internal server error')

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    print("app running")
    socketio.run(app, host="0.0.0.0", port=port)
