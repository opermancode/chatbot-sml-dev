import sqlite3
import os
from datetime import datetime, timezone

_basedir = None


def _get_basedir():
    global _basedir
    if _basedir is None:
        _basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return _basedir


def get_db_path():
    instance_dir = os.path.join(_get_basedir(), 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    return os.path.join(instance_dir, 'chatlog.db')


def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL,
            start_time TEXT NOT NULL,
            last_activity TEXT NOT NULL,
            end_time TEXT,
            duration_seconds INTEGER DEFAULT 0,
            message_count INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            direction TEXT NOT NULL,
            message TEXT NOT NULL,
            response TEXT DEFAULT '',
            message_type TEXT DEFAULT 'text',
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
        );
    """)
    conn.commit()
    conn.close()


def get_or_create_session(phone, user_name=""):
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()

    cursor = conn.execute(
        "SELECT id, user_name FROM chat_sessions "
        "WHERE phone = ? AND end_time IS NULL "
        "AND datetime(last_activity) > datetime(?, '-30 minutes') "
        "ORDER BY last_activity DESC LIMIT 1",
        (phone, now)
    )
    row = cursor.fetchone()

    if row:
        session_id = row['id']
        existing_name = row['user_name']
        if user_name and user_name != existing_name:
            conn.execute("UPDATE chat_sessions SET user_name = ? WHERE id = ?", (user_name, session_id))
        conn.execute(
            "UPDATE chat_sessions SET last_activity = ?, message_count = message_count + 1 WHERE id = ?",
            (now, session_id)
        )
        conn.commit()
        conn.close()
        return session_id

    conn.execute(
        "UPDATE chat_sessions SET end_time = ?, duration_seconds = "
        "CAST(MAX(0, (julianday(?) - julianday(start_time)) * 86400) AS INTEGER) "
        "WHERE phone = ? AND end_time IS NULL",
        (now, now, phone)
    )

    cursor = conn.execute(
        "INSERT INTO chat_sessions (user_name, phone, start_time, last_activity, message_count) "
        "VALUES (?, ?, ?, ?, 1)",
        (user_name, phone, now, now)
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id


def log_message(phone, message, response, direction, message_type="text", user_name=""):
    session_id = get_or_create_session(phone, user_name)
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT INTO chat_messages (session_id, direction, message, response, message_type, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, direction, message, response, message_type, now)
    )
    conn.commit()
    conn.close()


def get_all_sessions(search=""):
    conn = get_connection()
    if search:
        cursor = conn.execute(
            "SELECT id, user_name, phone, start_time, last_activity, end_time, duration_seconds, message_count "
            "FROM chat_sessions WHERE user_name LIKE ? OR phone LIKE ? "
            "ORDER BY last_activity DESC",
            (f'%{search}%', f'%{search}%')
        )
    else:
        cursor = conn.execute(
            "SELECT id, user_name, phone, start_time, last_activity, end_time, duration_seconds, message_count "
            "FROM chat_sessions ORDER BY last_activity DESC"
        )
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_session_messages(session_id):
    conn = get_connection()
    cursor = conn.execute(
        "SELECT id, session_id, direction, message, response, message_type, created_at "
        "FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_session(session_id):
    conn = get_connection()
    cursor = conn.execute(
        "SELECT id, user_name, phone, start_time, last_activity, end_time, duration_seconds, message_count "
        "FROM chat_sessions WHERE id = ?",
        (session_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row


def total_message_count():
    conn = get_connection()
    cursor = conn.execute("SELECT COUNT(*) AS c FROM chat_messages")
    row = cursor.fetchone()
    conn.close()
    return row['c'] if row else 0


def today_message_count():
    conn = get_connection()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cursor = conn.execute(
        "SELECT COUNT(*) AS c FROM chat_messages WHERE created_at LIKE ?",
        (f"{today}%",)
    )
    row = cursor.fetchone()
    conn.close()
    return row['c'] if row else 0


def recent_messages(limit=10):
    conn = get_connection()
    cursor = conn.execute(
        "SELECT m.id, m.session_id, m.direction, m.message, m.response, "
        "m.message_type, m.created_at, s.phone, s.user_name "
        "FROM chat_messages m "
        "JOIN chat_sessions s ON s.id = m.session_id "
        "ORDER BY m.created_at DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


init_db()
