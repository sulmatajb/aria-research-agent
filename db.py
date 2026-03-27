"""Shared SQLite task queue for ARIA agents."""
import sqlite3
import json
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'aria.db')


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init():
    with get_conn() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id   INTEGER,
                type        TEXT NOT NULL,
                payload     TEXT NOT NULL DEFAULT '{}',
                status      TEXT NOT NULL DEFAULT 'pending',
                assigned_to TEXT,
                result      TEXT,
                chat_id     INTEGER,
                created_at  TEXT DEFAULT (datetime('now')),
                updated_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS logs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                agent      TEXT NOT NULL,
                level      TEXT DEFAULT 'info',
                message    TEXT NOT NULL,
                task_id    INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS kv (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
        ''')


def create_task(type_, payload, parent_id=None, assigned_to=None, chat_id=None):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (type, payload, assigned_to, parent_id, chat_id) VALUES (?,?,?,?,?)",
            (type_, json.dumps(payload), assigned_to, parent_id, chat_id)
        )
        return cur.lastrowid


def get_pending_tasks(assigned_to, limit=5):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE assigned_to=? AND status='pending' ORDER BY created_at ASC LIMIT ?",
            (assigned_to, limit)
        ).fetchall()
        return [dict(r) for r in rows]


def get_done_children(parent_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE parent_id=? AND status IN ('done','failed')",
            (parent_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def all_children_done(parent_id):
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM tasks WHERE parent_id=?", (parent_id,)).fetchone()[0]
        done  = conn.execute("SELECT COUNT(*) FROM tasks WHERE parent_id=? AND status IN ('done','failed')", (parent_id,)).fetchone()[0]
        return total > 0 and total == done


def update_task(task_id, **kwargs):
    kwargs['updated_at'] = "datetime('now')"
    if 'result' in kwargs and not isinstance(kwargs['result'], str):
        kwargs['result'] = json.dumps(kwargs['result'])
    # updated_at is a SQLite expression, handle separately
    kwargs.pop('updated_at')
    sets = ', '.join(f"{k}=?" for k in kwargs) + ", updated_at=datetime('now')"
    vals = list(kwargs.values()) + [task_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE tasks SET {sets} WHERE id=?", vals)


def get_task(task_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None


def get_recent_tasks(limit=20):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_pending_telegram_responses():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE type='telegram_response' AND status='pending' ORDER BY created_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_tasks_needing_review():
    """Parent tasks (in_progress, assigned to supervisor) where all children are done."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT DISTINCT t.id FROM tasks t
               WHERE t.status='in_progress' AND t.assigned_to='supervisor'
               AND EXISTS (
                   SELECT 1 FROM tasks c WHERE c.parent_id=t.id
               )
               AND NOT EXISTS (
                   SELECT 1 FROM tasks c WHERE c.parent_id=t.id AND c.status NOT IN ('done','failed')
               )"""
        ).fetchall()
        result = []
        for row in rows:
            task = conn.execute("SELECT * FROM tasks WHERE id=?", (row[0],)).fetchone()
            if task:
                result.append(dict(task))
        return result


def log(agent, message, level='info', task_id=None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO logs (agent, level, message, task_id) VALUES (?,?,?,?)",
            (agent, level, message, task_id)
        )
    tag = {'info': '•', 'error': '✗', 'warn': '!'}.get(level, '•')
    print(f"[{agent.upper():12s}] {tag} {message}")


def save_kv(key, value):
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO kv (key, value) VALUES (?,?)", (key, str(value)))


def get_kv(key):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return row[0] if row else None
