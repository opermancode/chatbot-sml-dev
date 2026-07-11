import sqlite3
import os
from datetime import datetime, timezone, timedelta

_basedir = None
IST = timezone(timedelta(hours=5, minutes=30))


def _ist_now():
    return datetime.now(IST)


def _ist_date_str():
    return _ist_now().strftime("%Y-%m-%d")


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
            message_count INTEGER DEFAULT 0,
            session_date TEXT NOT NULL DEFAULT ''
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
    # Add session_date column if missing (migration for existing DBs)
    try:
        conn.execute("ALTER TABLE chat_sessions ADD COLUMN session_date TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def get_or_create_session(phone, user_name=""):
    conn = get_connection()
    now_ist = _ist_now()
    now_iso = now_ist.isoformat()
    today = _ist_date_str()

    cursor = conn.execute(
        "SELECT id, user_name, session_date FROM chat_sessions "
        "WHERE phone = ? AND end_time IS NULL "
        "ORDER BY last_activity DESC LIMIT 1",
        (phone,)
    )
    row = cursor.fetchone()

    if row:
        session_id = row['id']
        existing_name = row['user_name']
        sess_date = row['session_date'] or today

        if sess_date != today:
            conn.execute(
                "UPDATE chat_sessions SET end_time = ?, duration_seconds = "
                "CAST(MAX(0, (julianday(?) - julianday(start_time)) * 86400) AS INTEGER) "
                "WHERE id = ?",
                (now_iso, now_iso, session_id)
            )
        else:
            if user_name and user_name != existing_name:
                conn.execute("UPDATE chat_sessions SET user_name = ? WHERE id = ?", (user_name, session_id))
            conn.execute(
                "UPDATE chat_sessions SET last_activity = ?, message_count = message_count + 1 WHERE id = ?",
                (now_iso, session_id)
            )
            conn.commit()
            conn.close()
            return session_id

    cursor = conn.execute(
        "INSERT INTO chat_sessions (user_name, phone, start_time, last_activity, message_count, session_date) "
        "VALUES (?, ?, ?, ?, 1, ?)",
        (user_name, phone, now_iso, now_iso, today)
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id


def log_message(phone, message, response, direction, message_type="text", user_name=""):
    session_id = get_or_create_session(phone, user_name)
    now_iso = _ist_now().isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT INTO chat_messages (session_id, direction, message, response, message_type, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, direction, message, response, message_type, now_iso)
    )
    conn.commit()
    conn.close()


def get_all_sessions(search=""):
    conn = get_connection()
    if search:
        cursor = conn.execute(
            "SELECT id, user_name, phone, start_time, last_activity, end_time, duration_seconds, message_count, session_date "
            "FROM chat_sessions WHERE user_name LIKE ? OR phone LIKE ? "
            "ORDER BY last_activity DESC",
            (f'%{search}%', f'%{search}%')
        )
    else:
        cursor = conn.execute(
            "SELECT id, user_name, phone, start_time, last_activity, end_time, duration_seconds, message_count, session_date "
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
        "SELECT id, user_name, phone, start_time, last_activity, end_time, duration_seconds, message_count, session_date "
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
    today = _ist_date_str()
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


def format_ist_dt(iso_str):
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d-%b-%Y %I:%M %p")
    except Exception:
        return iso_str


def format_ist_date(iso_str):
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d-%b-%Y")
    except Exception:
        return iso_str


def format_ist_time(iso_str):
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%I:%M %p")
    except Exception:
        return iso_str


init_db()
