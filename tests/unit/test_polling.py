import importlib
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

from history import HistoryStore
from tests.unit.test_bot_replies import bot_module


def test_polling_resumes_offset_preserves_pending_and_acknowledges_processed_only(
        bot_module, monkeypatch, tmp_path):
    runner = importlib.import_module('run')
    database = tmp_path / 'history.sqlite3'
    HistoryStore(database).acknowledge(123, 50)
    monkeypatch.setenv('HISTORY_DB_PATH', str(database))
    monkeypatch.setenv('HEARTBEAT_PATH', str(tmp_path / 'heartbeat'))
    stopping = Event()
    monkeypatch.setattr(runner, 'Event', lambda: stopping)
    monkeypatch.setattr(runner.signal, 'signal', Mock())
    client = Mock()
    client.get_me.return_value = SimpleNamespace(id=123, username='EvanBot')
    client.get_updates.return_value = [SimpleNamespace(update_id=50), SimpleNamespace(update_id=51)]
    monkeypatch.setattr(bot_module, 'bot', client)
    process = Mock(side_effect=lambda _: stopping.set())
    monkeypatch.setattr(bot_module.dispatcher, 'process_update', process)
    runner.main()
    client.delete_webhook.assert_called_once_with(drop_pending_updates=False)
    assert client.get_updates.call_args.kwargs['offset'] == 50
    assert process.call_count == 1
    assert HistoryStore(database).next_update_id(123) == 51
    assert (tmp_path / 'heartbeat').exists()
