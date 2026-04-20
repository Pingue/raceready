"""
Tests for raceready.py

Uses Flask's built-in test client for HTTP endpoints and flask-socketio's
test_client() for WebSocket events. Each test gets a fresh temporary SQLite
database via the `patch_db` fixture so tests are fully isolated.
"""

import pytest
import sqlite3
import raceready


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_db(tmp_path, monkeypatch):
    """Redirect all DB operations to a fresh temp DB for every test."""
    db_file = str(tmp_path / "test.sqlite3")
    monkeypatch.setattr(raceready, "db_path", db_file)
    monkeypatch.setattr(raceready, "current_checklist_id", None)
    # Initialise schema in the temp DB
    con = raceready.get_db_connection()
    con.close()


@pytest.fixture
def http(patch_db):
    raceready.app.config["TESTING"] = True
    with raceready.app.test_client() as client:
        yield client


@pytest.fixture
def ws(patch_db):
    raceready.app.config["TESTING"] = True
    sc = raceready.socketio.test_client(raceready.app)
    sc.get_received()  # discard the initial 'connected' event
    yield sc
    sc.disconnect()


def _seed_action(text="Check Audio", status=0, notes=""):
    """Insert an action directly into the test DB and return its id."""
    con = raceready.get_db_connection()
    cid = raceready.get_current_checklist_id()
    con.execute(
        'INSERT INTO actions (text, "order", status, checklist_id, notes) VALUES (?, 1, ?, ?, ?)',
        (text, status, cid, notes),
    )
    con.commit()
    cur = con.execute("SELECT last_insert_rowid()")
    row_id = cur.fetchone()[0]
    con.close()
    return row_id


# ---------------------------------------------------------------------------
# DB Migration
# ---------------------------------------------------------------------------

class TestDbMigration:
    def test_notes_column_added_to_existing_db(self, tmp_path, monkeypatch):
        """A DB that predates the notes column should have it added automatically."""
        db_file = str(tmp_path / "old.sqlite3")

        # Build a DB that looks like it was created before the notes column existed
        con = sqlite3.connect(db_file)
        con.execute("CREATE TABLE checklists (id INTEGER PRIMARY KEY, name TEXT, order_pos INTEGER DEFAULT 0)")
        con.execute("INSERT INTO checklists (name, order_pos) VALUES ('Default', 1)")
        con.execute('CREATE TABLE actions (id INTEGER PRIMARY KEY, text TEXT, "order" INT, status INT, checklist_id INT)')
        con.commit()
        con.close()

        monkeypatch.setattr(raceready, "db_path", db_file)
        monkeypatch.setattr(raceready, "current_checklist_id", None)

        con = raceready.get_db_connection()
        cur = con.cursor()
        cur.execute("PRAGMA table_info(actions)")
        columns = [col[1] for col in cur.fetchall()]
        con.close()

        assert "notes" in columns

    def test_default_db_path_is_not_slash_data(self):
        """_default_db_path() must return a script-relative path, not /data/db.sqlite3."""
        import os
        default = raceready._default_db_path()
        assert default != '/data/db.sqlite3'
        assert not default.startswith('/data/')
        assert default.endswith(os.path.join('data', 'db.sqlite3'))
        assert os.path.isabs(default)


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

class TestHttpEndpoints:
    def test_home_ok(self, http):
        assert http.get("/").status_code == 200

    def test_admin_ok(self, http):
        assert http.get("/admin").status_code == 200

    def test_toggle_by_title_missing_body(self, http):
        assert http.post("/toggle_by_title", json={}).status_code == 400

    def test_toggle_by_title_not_found(self, http):
        assert http.post("/toggle_by_title", json={"title": "Ghost Item"}).status_code == 404

    def test_toggle_by_title_toggles_status(self, http):
        _seed_action("Check Audio", status=0)
        resp = http.post("/toggle_by_title", json={"title": "Check Audio"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["status"] == 1  # 0 → 1

    def test_toggle_by_title_toggles_back(self, http):
        _seed_action("Check Audio", status=1)
        resp = http.post("/toggle_by_title", json={"title": "Check Audio"})
        assert resp.get_json()["data"]["status"] == 0  # 1 → 0

    def test_action_title_missing_id(self, http):
        assert http.get("/action_title").status_code == 400

    def test_action_title_invalid_id(self, http):
        assert http.get("/action_title?id=abc").status_code == 400

    def test_action_title_not_found(self, http):
        assert http.get("/action_title?id=9999").status_code == 404

    def test_action_title_returns_text(self, http):
        _seed_action("Check Cameras")
        con = raceready.get_db_connection()
        cur = con.execute("SELECT id FROM actions WHERE text='Check Cameras'")
        action_id = cur.fetchone()[0]
        con.close()

        resp = http.get(f"/action_title?id={action_id}")
        assert resp.status_code == 200
        assert resp.get_json()["text"] == "Check Cameras"

    def test_create_checklist(self, http):
        resp = http.post("/create_checklist", json={"name": "Pre-show"})
        assert resp.status_code == 201
        assert resp.get_json()["name"] == "Pre-show"

    def test_create_checklist_missing_name(self, http):
        assert http.post("/create_checklist", json={}).status_code == 400

    def test_delete_checklist(self, http):
        resp = http.post("/create_checklist", json={"name": "Temp"})
        cid = resp.get_json()["id"]

        http.post("/delete_checklist", json={"id": cid})

        ids = [c["id"] for c in http.get("/checklists").get_json()]
        assert cid not in ids

    def test_rename_checklist(self, http):
        resp = http.post("/create_checklist", json={"name": "Old Name"})
        cid = resp.get_json()["id"]

        http.post("/rename_checklist", json={"id": cid, "name": "New Name"})

        checklists = http.get("/checklists").get_json()
        names = {c["id"]: c["name"] for c in checklists}
        assert names[cid] == "New Name"


# ---------------------------------------------------------------------------
# WebSocket events
# ---------------------------------------------------------------------------

class TestWebSocketEvents:
    def test_add_creates_item_in_db(self, ws):
        ws.emit("add", {"text": "Check Stream"})
        ws.get_received()

        con = raceready.get_db_connection()
        cur = con.execute("SELECT text FROM actions WHERE text='Check Stream'")
        row = cur.fetchone()
        con.close()
        assert row is not None

    def test_add_item_appears_in_db(self, ws):
        # Separate from test_add_creates_item_in_db — verifies order is assigned
        ws.emit("add", {"text": "Check Comms"})
        ws.get_received()

        con = raceready.get_db_connection()
        cur = con.execute('SELECT text, "order" FROM actions WHERE text="Check Comms"')
        row = cur.fetchone()
        con.close()
        assert row is not None
        assert row[1] is not None  # order was set

    def test_delete_removes_item(self, ws):
        # broadcast=True in the handler excludes the sender, so we verify
        # the deletion via DB state rather than received events.
        action_id = _seed_action("Check Graphics")
        ws.emit("delete", {"id": action_id})
        ws.get_received()

        con = raceready.get_db_connection()
        cur = con.execute("SELECT id FROM actions WHERE id=?", (action_id,))
        assert cur.fetchone() is None
        con.close()

    def test_delete_missing_id_leaves_db_unchanged(self, ws):
        # Emitting delete without an id should be a no-op on the DB.
        action_id = _seed_action("Check Graphics")
        ws.emit("delete", {})
        ws.get_received()

        con = raceready.get_db_connection()
        cur = con.execute("SELECT id FROM actions WHERE id=?", (action_id,))
        assert cur.fetchone() is not None  # still there
        con.close()

    def test_save_persists_notes(self, ws):
        action_id = _seed_action("Check Replays", notes="")
        ws.emit("save", {"id": action_id, "text": "Check Replays", "notes": "HD only"})
        ws.get_received()

        con = raceready.get_db_connection()
        cur = con.execute("SELECT notes FROM actions WHERE id=?", (action_id,))
        assert cur.fetchone()[0] == "HD only"
        con.close()

    def test_save_persists_text(self, ws):
        action_id = _seed_action("Old Text")
        ws.emit("save", {"id": action_id, "text": "New Text"})
        ws.get_received()

        con = raceready.get_db_connection()
        cur = con.execute("SELECT text FROM actions WHERE id=?", (action_id,))
        assert cur.fetchone()[0] == "New Text"
        con.close()

    def test_toggle_state_flips_status(self, ws):
        action_id = _seed_action("Check Audio", status=0)
        ws.emit("toggle_state", {"id": action_id})
        ws.get_received()

        con = raceready.get_db_connection()
        cur = con.execute("SELECT status FROM actions WHERE id=?", (action_id,))
        assert cur.fetchone()[0] == 1
        con.close()

    def test_toggle_state_flips_back(self, ws):
        action_id = _seed_action("Check Audio", status=1)
        ws.emit("toggle_state", {"id": action_id})
        ws.get_received()

        con = raceready.get_db_connection()
        cur = con.execute("SELECT status FROM actions WHERE id=?", (action_id,))
        assert cur.fetchone()[0] == 0
        con.close()

    def test_reset_all_clears_statuses(self, ws):
        _seed_action("Item A", status=1)
        _seed_action("Item B", status=1)
        ws.emit("reset_all")
        ws.get_received()

        con = raceready.get_db_connection()
        cur = con.execute("SELECT SUM(status) FROM actions")
        assert cur.fetchone()[0] == 0
        con.close()

    def test_up_reorders_items(self, ws):
        con = raceready.get_db_connection()
        cid = raceready.get_current_checklist_id()
        con.execute('INSERT INTO actions (id, text, "order", status, checklist_id, notes) VALUES (1, "First", 1, 0, ?, "")', (cid,))
        con.execute('INSERT INTO actions (id, text, "order", status, checklist_id, notes) VALUES (2, "Second", 2, 0, ?, "")', (cid,))
        con.commit()
        con.close()

        ws.emit("up", {"id": 2})
        ws.get_received()

        con = raceready.get_db_connection()
        cur = con.execute('SELECT id FROM actions ORDER BY "order"')
        order = [r[0] for r in cur.fetchall()]
        con.close()
        assert order == [2, 1]

    def test_next_and_previous_checklist(self, ws):
        # Create a second checklist
        con = raceready.get_db_connection()
        con.execute("INSERT INTO checklists (name, order_pos) VALUES ('Second', 2)")
        con.commit()
        second_id = con.execute("SELECT id FROM checklists WHERE name='Second'").fetchone()[0]
        con.close()

        ws.emit("next_checklist")
        ws.get_received()
        assert raceready.current_checklist_id == second_id

        ws.emit("previous_checklist")
        ws.get_received()
        assert raceready.current_checklist_id != second_id
