from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

import history
from history import HistoryStore


def node(message_id, parent_id=None, text=None, role='user'):
    return dict(message_id=message_id, parent_id=parent_id, role=role,
                content=text or str(message_id))


@pytest.fixture
def store(tmp_path):
    return HistoryStore(tmp_path / 'history.sqlite3')


def contents(store, chat_id=1, thread_id=0, message_id=4):
    return [m['content'] for m in store.load_chain(chat_id, thread_id, message_id)]


def test_follows_only_parent_chain_and_survives_restart(store):
    store.save_messages(1, 0, [node(1), node(2, 1, role='assistant'),
                               node(3, 2), node(4, 3, role='assistant'),
                               node(5, 2, text='different branch')])
    assert contents(HistoryStore(store.path)) == ['1', '2', '3', '4']
    assert contents(store, message_id=5) == ['1', '2', 'different branch']


def test_no_cross_chat_or_topic_history(store):
    store.save_messages(1, 10, [node(1, text='chat one')])
    store.save_messages(2, 10, [node(1, text='chat two')])
    assert contents(store, chat_id=1, thread_id=10, message_id=1) == ['chat one']
    assert contents(store, chat_id=2, thread_id=10, message_id=1) == ['chat two']
    assert contents(store, thread_id=11, message_id=1) == []


def test_quoted_message_does_not_overwrite_known_parent(store):
    store.save_messages(1, 0, [node(1), node(2, 1, role='assistant')])
    store.save_messages(1, 0, [node(2, role='assistant')])
    assert contents(store, message_id=2) == ['1', '2']


def test_missing_parent_and_cycles_stop_safely(store):
    store.save_messages(1, 0, [node(1, 2), node(2, 1), node(4, 999)])
    assert contents(store) == ['4']
    assert contents(store, message_id=2) == ['1', '2']


def test_retention_filters_and_cleans_old_messages(store, monkeypatch):
    monkeypatch.setattr(history.time, 'time', lambda: 1000000)
    store.save_messages(1, 0, [node(1), node(2, 1)])
    monkeypatch.setattr(history.time, 'time', lambda: 1000000 + 7 * 86400)
    assert contents(store, message_id=2) == []
    assert store.prune() == 2
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT COUNT(*) FROM messages').fetchone()[0] == 0


def test_expired_ancestor_is_not_reintroduced_by_quote(store, monkeypatch):
    monkeypatch.setattr(history.time, 'time', lambda: 1000000)
    store.save_messages(1, 0, [node(1), node(2, 1)])
    monkeypatch.setattr(history.time, 'time', lambda: 1000000 + 7 * 86400)
    store.save_messages(1, 0, [node(2), node(3, 2)])
    assert contents(store, message_id=3) == ['3']


def test_size_and_message_count_limits(store):
    store.save_messages(1, 0, [node(i, i - 1 if i > 1 else None, text='abcd')
                               for i in range(1, 10)])
    assert len(HistoryStore(store.path, max_messages=3).load_chain(1, 0, 9)) == 3
    assert len(HistoryStore(store.path, max_chars=8).load_chain(1, 0, 9)) == 2


def test_independent_writes_do_not_lose_messages(store):
    def save(i):
        store.save_messages(1, 0, [node(i)])
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(save, range(1, 20)))
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT COUNT(*) FROM messages').fetchone()[0] == 19


def test_polling_offset_survives_restart_and_cleanup(store):
    store.acknowledge(123, 50)
    store.prune()
    reopened = HistoryStore(store.path)
    assert reopened.next_update_id(123) == 50
    assert reopened.next_update_id(456) is None
