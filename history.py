"""Persistent, bounded Telegram reply-chain history. No shared chat transcript."""
import sqlite3
import time
from contextlib import closing
from pathlib import Path


class HistoryStore:
    def __init__(self, path, max_messages=20, max_chars=16000, retention_days=7,
                 daily_user_limit=30, daily_group_limit=100):
        self.path = str(path)
        self.max_messages = max_messages
        self.max_chars = max_chars
        self.retention_seconds = retention_days * 86400
        self.daily_user_limit = daily_user_limit
        self.daily_group_limit = daily_group_limit
        if min(max_messages, max_chars, retention_days, daily_user_limit, daily_group_limit) <= 0:
            raise ValueError('History and daily limits must be positive')
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('''CREATE TABLE IF NOT EXISTS messages (
                chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL,
                thread_id INTEGER NOT NULL, parent_id INTEGER,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL, name TEXT, created_at INTEGER NOT NULL,
                PRIMARY KEY(chat_id, message_id))''')
            db.execute('CREATE INDEX IF NOT EXISTS messages_age ON messages(created_at)')
            db.execute('''CREATE TABLE IF NOT EXISTS polling_offsets (
                bot_id INTEGER PRIMARY KEY, next_update_id INTEGER NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS daily_usage (
                chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL,
                utc_day INTEGER NOT NULL, user_id INTEGER NOT NULL, group_id INTEGER,
                paid INTEGER NOT NULL DEFAULT 0 CHECK(paid IN (0, 1)),
                PRIMARY KEY(chat_id, message_id))''')
            db.execute('CREATE INDEX IF NOT EXISTS usage_user ON daily_usage(utc_day, user_id)')
            db.execute('CREATE INDEX IF NOT EXISTS usage_group ON daily_usage(utc_day, group_id)')

    def _connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def save_messages(self, chat_id, thread_id, messages):
        now = int(time.time())
        with closing(self._connect()) as db, db:
            for message in messages:
                # Never erase a known parent when Telegram supplies only a quoted message.
                db.execute('''INSERT OR IGNORE INTO messages
                    (chat_id, message_id, thread_id, parent_id, role, content, name, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (
                        chat_id, message['message_id'], thread_id or 0,
                        message.get('parent_id'), message['role'],
                        message['content'][:4096], message.get('name'), now))
            db.execute('DELETE FROM messages WHERE created_at <= ?',
                       (now - self.retention_seconds,))

    def load_chain(self, chat_id, thread_id, message_id):
        """Read ancestors of exactly this message, newest first then reverse."""
        history, seen, chars = [], set(), 0
        cutoff = int(time.time()) - self.retention_seconds
        with closing(self._connect()) as db:
            while message_id is not None and len(history) < self.max_messages:
                if message_id in seen:
                    break
                seen.add(message_id)
                row = db.execute('''SELECT parent_id, role, content, name FROM messages
                    WHERE chat_id = ? AND thread_id = ? AND message_id = ?
                    AND created_at > ?''',
                    (chat_id, thread_id or 0, message_id, cutoff)).fetchone()
                if row is None:
                    break
                parent_id, role, content, name = row
                if chars + len(content) > self.max_chars:
                    break
                item = {'role': role, 'content': content}
                if name and role == 'user':
                    item['name'] = name
                history.append(item)
                chars += len(content)
                message_id = parent_id
        return list(reversed(history))

    def next_update_id(self, bot_id):
        with closing(self._connect()) as db:
            row = db.execute('SELECT next_update_id FROM polling_offsets WHERE bot_id = ?',
                             (bot_id,)).fetchone()
        return row[0] if row else None

    def prune(self):
        with closing(self._connect()) as db, db:
            deleted = db.execute('DELETE FROM messages WHERE created_at <= ?',
                                 (int(time.time()) - self.retention_seconds,)).rowcount
            db.execute('DELETE FROM daily_usage WHERE utc_day < ?',
                       (int(time.time()) // 86400 - 7,))
        return deleted

    def reserve_usage(self, chat_id, message_id, user_id, group_id=None):
        """Reserve one slot atomically; pending slots are not paid usage."""
        day = int(time.time()) // 86400
        with closing(self._connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM daily_usage WHERE chat_id = ? AND message_id = ?',
                          (chat_id, message_id)).fetchone():
                return 'duplicate'
            user_count = db.execute('SELECT COUNT(*) FROM daily_usage WHERE utc_day = ? AND user_id = ?',
                                    (day, user_id)).fetchone()[0]
            if user_count >= self.daily_user_limit:
                return 'user'
            if group_id is not None:
                group_count = db.execute('SELECT COUNT(*) FROM daily_usage WHERE utc_day = ? AND group_id = ?',
                                         (day, group_id)).fetchone()[0]
                if group_count >= self.daily_group_limit:
                    return 'group'
            db.execute('''INSERT INTO daily_usage
                (chat_id, message_id, utc_day, user_id, group_id) VALUES (?, ?, ?, ?, ?)''',
                (chat_id, message_id, day, user_id, group_id))
        return None

    def mark_usage_paid(self, chat_id, message_id):
        with closing(self._connect()) as db, db:
            cursor = db.execute('UPDATE daily_usage SET paid = 1 WHERE chat_id = ? AND message_id = ?',
                                (chat_id, message_id))
            if cursor.rowcount != 1:
                raise RuntimeError('Usage reservation is missing')

    def release_usage(self, chat_id, message_id):
        with closing(self._connect()) as db, db:
            db.execute('DELETE FROM daily_usage WHERE chat_id = ? AND message_id = ? AND paid = 0',
                       (chat_id, message_id))

    def clear_pending_usage(self):
        """Remove unfinished reservations when the single polling process starts."""
        with closing(self._connect()) as db, db:
            return db.execute('DELETE FROM daily_usage WHERE paid = 0').rowcount

    def acknowledge(self, bot_id, next_update_id):
        with closing(self._connect()) as db, db:
            db.execute('''INSERT INTO polling_offsets VALUES (?, ?)
                ON CONFLICT(bot_id) DO UPDATE SET next_update_id = excluded.next_update_id''',
                (bot_id, next_update_id))
