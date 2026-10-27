from concurrent.futures import ThreadPoolExecutor
import sqlite3
from unittest.mock import Mock

import pytest

import history
from history import HistoryStore
from tests.unit.test_bot_replies import bot_module, update


@pytest.fixture
def store(tmp_path):
    return HistoryStore(tmp_path / 'history.sqlite3', daily_user_limit=2, daily_group_limit=3)


def paid(store, chat_id, message_id, user_id, group_id=None):
    assert store.reserve_usage(chat_id, message_id, user_id, group_id) is None
    store.mark_usage_paid(chat_id, message_id)


def test_user_limit_across_groups_and_private_chat(store):
    paid(store, -1, 1, 42, -1)
    paid(store, -2, 2, 42, -2)
    assert store.reserve_usage(42, 3, 42) == 'user'
    assert store.reserve_usage(43, 1, 43) is None


def test_group_limit_shared_across_users_and_topics(store):
    for i in range(3):
        paid(store, -1, i, i + 10, -1)
    assert store.reserve_usage(-1, 4, 99, -1) == 'group'
    assert store.reserve_usage(-2, 4, 99, -2) is None


def test_unpaid_failure_releases_slot(store):
    assert store.reserve_usage(-1, 1, 42, -1) is None
    store.release_usage(-1, 1)
    paid(store, -1, 2, 42, -1)
    paid(store, -1, 3, 42, -1)
    assert store.reserve_usage(-1, 4, 42, -1) == 'user'


def test_paid_record_cannot_be_released_or_charged_twice(store):
    paid(store, -1, 1, 42, -1)
    store.mark_usage_paid(-1, 1)
    store.release_usage(-1, 1)
    assert store.reserve_usage(-1, 1, 42, -1) == 'duplicate'
    paid(store, -1, 2, 42, -1)
    assert store.reserve_usage(-1, 3, 42, -1) == 'user'


def test_utc_day_rollover_resets_both_limits(store, monkeypatch):
    monkeypatch.setattr(history.time, 'time', lambda: 86400 * 10 + 86399)
    for i in range(3):
        paid(store, -1, i, i + 10, -1)
    assert store.reserve_usage(-1, 4, 99, -1) == 'group'
    monkeypatch.setattr(history.time, 'time', lambda: 86400 * 11)
    assert store.reserve_usage(-1, 4, 10, -1) is None


def test_reservations_prevent_concurrent_limit_bypass(store):
    def reserve(i):
        return store.reserve_usage(-1, i, 42, -1)
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(reserve, range(10)))
    assert results.count(None) == 2
    assert results.count('user') == 8


def test_restart_clears_unfinished_reservations_but_keeps_paid_usage(store):
    paid(store, -1, 1, 42, -1)
    assert store.reserve_usage(-1, 2, 42, -1) is None
    reopened = HistoryStore(store.path, daily_user_limit=2, daily_group_limit=3)
    assert reopened.clear_pending_usage() == 1
    assert reopened.reserve_usage(-1, 3, 42, -1) is None
    assert reopened.reserve_usage(-1, 4, 42, -1) == 'user'


def test_cleanup_removes_old_usage_only(store, monkeypatch):
    monkeypatch.setattr(history.time, 'time', lambda: 86400 * 10)
    paid(store, -1, 1, 42, -1)
    monkeypatch.setattr(history.time, 'time', lambda: 86400 * 18)
    store.prune()
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT COUNT(*) FROM daily_usage').fetchone()[0] == 0


def test_paid_filtered_retries_count_one_message(bot_module, monkeypatch, store):
    monkeypatch.setattr(bot_module, 'usage_store', store)
    def call(user, prompt, history, on_success):
        on_success()
        on_success()
        return 'Ответ'
    monkeypatch.setattr(bot_module, 'call_chatgpt', call)
    msg = update(reply_user_id=123456).message
    assert bot_module.limited_chatgpt(msg, 'test', []) == ('Ответ', False)
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT COUNT(*), SUM(paid) FROM daily_usage').fetchone() == (1, 1)


def test_failed_api_call_releases_slot_and_sends_no_limit_reply(bot_module, monkeypatch, store):
    monkeypatch.setattr(bot_module, 'usage_store', store)
    monkeypatch.setattr(bot_module, 'call_chatgpt', Mock(return_value=None))
    msg = update(reply_user_id=123456).message
    assert bot_module.limited_chatgpt(msg, 'test', []) == (None, False)
    with sqlite3.connect(store.path) as db:
        assert db.execute('SELECT COUNT(*) FROM daily_usage').fetchone()[0] == 0


def test_no_paid_call_after_user_limit(bot_module, monkeypatch, store):
    monkeypatch.setattr(bot_module, 'usage_store', store)
    call = Mock()
    monkeypatch.setattr(bot_module, 'call_chatgpt', call)
    paid(store, -1, 1, 123, -1)
    paid(store, -1, 2, 123, -1)
    msg = update(reply_user_id=123456).message
    reply, limited = bot_module.limited_chatgpt(msg, 'test', [])
    assert limited and 'лимит' in reply.lower()
    call.assert_not_called()


def test_free_greeting_and_choice_do_not_touch_usage(bot_module, monkeypatch):
    usage = Mock()
    call = Mock()
    monkeypatch.setattr(bot_module, 'usage_store', usage)
    monkeypatch.setattr(bot_module, 'call_chatgpt', call)
    bot_module.message(update(text='Эван, привет'), None)
    usage.reserve_usage.assert_not_called()
    call.assert_not_called()


def test_storage_failure_refuses_paid_call(bot_module, monkeypatch):
    usage = Mock()
    usage.reserve_usage.side_effect = OSError('disk unavailable')
    call = Mock()
    monkeypatch.setattr(bot_module, 'usage_store', usage)
    monkeypatch.setattr(bot_module, 'call_chatgpt', call)
    assert bot_module.limited_chatgpt(update().message, 'test', []) == (None, False)
    call.assert_not_called()


def test_accounting_error_after_success_keeps_reserved_slot(bot_module, monkeypatch):
    usage = Mock()
    usage.reserve_usage.return_value = None
    usage.mark_usage_paid.side_effect = OSError('disk unavailable')
    monkeypatch.setattr(bot_module, 'usage_store', usage)
    def call(user, prompt, history, on_success):
        on_success()
    monkeypatch.setattr(bot_module, 'call_chatgpt', call)
    assert bot_module.limited_chatgpt(update().message, 'test', []) == (None, False)
    usage.release_usage.assert_not_called()


def test_duplicate_paid_message_does_not_call_api_or_reply(bot_module, monkeypatch, store):
    monkeypatch.setattr(bot_module, 'usage_store', store)
    call = Mock()
    monkeypatch.setattr(bot_module, 'call_chatgpt', call)
    msg = update(reply_user_id=123456).message
    paid(store, msg.chat_id, msg.message_id, msg.from_user.id, msg.chat_id)
    assert bot_module.limited_chatgpt(msg, 'test', []) == (None, True)
    call.assert_not_called()
