import importlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def bot_module(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    monkeypatch.setenv('TELEGRAM_TOKEN', '123456:test-token')
    spec = importlib.util.spec_from_file_location(
        'config', Path(__file__).resolve().parents[2] / 'config.dist.py')
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    monkeypatch.setitem(__import__('sys').modules, 'config', config)
    module = importlib.import_module('bot')
    monkeypatch.setattr(module, 'bot', SimpleNamespace(id=123456, first_name='Evan', username='EvanBot'))
    monkeypatch.setattr(module, 'history_store', None)
    monkeypatch.setattr(module, 'usage_store', Mock(reserve_usage=Mock(return_value=None)))
    return module


def update(reply_user_id=None, text='Как твои дела?', chat_type='supergroup'):
    reply = None if reply_user_id is None else SimpleNamespace(
        from_user=SimpleNamespace(id=reply_user_id), text='Всё хорошо!', message_id=9)
    return SimpleNamespace(message=SimpleNamespace(
        chat={'type': chat_type}, reply_to_message=reply, text=text,
        entities=[], message_id=10, chat_id=-100, message_thread_id=None, is_topic_message=False,
        reply_text=Mock(return_value=SimpleNamespace(message_id=11, text='Отлично!')),
        from_user=SimpleNamespace(id=123, first_name='Test', last_name=None, username='tester')))


def test_reply_to_evan_without_mention_is_addressed(bot_module):
    assert bot_module.is_spoken_to(update(reply_user_id=123456), None)


def test_reply_to_someone_else_is_ignored(bot_module):
    assert not bot_module.is_spoken_to(update(reply_user_id=999), None)


@pytest.mark.parametrize('message', [update(), update(reply_user_id=999)])
def test_unaddressed_group_message_does_not_call_openai(bot_module, monkeypatch, message):
    call = Mock()
    monkeypatch.setattr(bot_module, 'call_chatgpt', call)
    bot_module.message(message, None)
    call.assert_not_called()
    message.message.reply_text.assert_not_called()


def test_private_chats_and_name_mentions_still_work(bot_module):
    assert bot_module.is_spoken_to(update(chat_type='private'), None)
    assert bot_module.is_spoken_to(update(text='Эван, как дела?'), None)


def test_group_reply_passes_assistant_history_and_sends_answer(bot_module, monkeypatch):
    call = Mock(return_value='Отлично!')
    monkeypatch.setattr(bot_module, 'call_chatgpt', call)
    message = update(reply_user_id=123456)
    bot_module.message(message, None)
    assert call.call_args.kwargs['history'] == [{'role': 'assistant', 'content': 'Всё хорошо!'}]
    assert message.message.reply_text.call_args.args[0] == 'Отлично!'


def test_openai_failure_gets_visible_reply(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, 'call_chatgpt', Mock(return_value=None))
    message = update(reply_user_id=123456)
    bot_module.message(message, None)
    assert 'Попробуй чуть позже' in message.message.reply_text.call_args.args[0]


def test_reply_loads_multiple_turns_after_store_reopen(bot_module, monkeypatch, tmp_path):
    from history import HistoryStore
    path = tmp_path / 'history.sqlite3'
    store = HistoryStore(path)
    monkeypatch.setattr(bot_module, 'history_store', store)
    call = Mock(return_value='Отлично!')
    monkeypatch.setattr(bot_module, 'call_chatgpt', call)
    first = update(reply_user_id=123456)
    bot_module.message(first, None)
    monkeypatch.setattr(bot_module, 'history_store', HistoryStore(path))
    second = update(reply_user_id=123456, text='А чем занимаешься?')
    second.message.message_id = 12
    second.message.reply_to_message.message_id = 11
    second.message.reply_text.return_value = SimpleNamespace(message_id=13, text='Гуляю!')
    bot_module.message(second, None)
    assert [item['content'] for item in call.call_args.kwargs['history']] == [
        'Всё хорошо!', 'Как твои дела?', 'Отлично!']


def test_new_message_does_not_use_previous_chain(bot_module, monkeypatch, tmp_path):
    from history import HistoryStore
    monkeypatch.setattr(bot_module, 'history_store', HistoryStore(tmp_path / 'history.sqlite3'))
    call = Mock(return_value='Отлично!')
    monkeypatch.setattr(bot_module, 'call_chatgpt', call)
    bot_module.message(update(reply_user_id=123456), None)
    new = update(text='Эван, что происходит?')
    new.message.message_id = 20
    bot_module.message(new, None)
    assert call.call_args.kwargs['history'] == []


def test_history_read_failure_still_answers(bot_module, monkeypatch):
    store = Mock()
    store.load_chain.side_effect = OSError('unavailable')
    monkeypatch.setattr(bot_module, 'history_store', store)
    call = Mock(return_value='Отлично!')
    monkeypatch.setattr(bot_module, 'call_chatgpt', call)
    bot_module.message(update(reply_user_id=123456), None)
    assert call.call_args.kwargs['history'] == [{'role': 'assistant', 'content': 'Всё хорошо!'}]


def test_normal_group_thread_metadata_does_not_split_reply_chain(bot_module, monkeypatch, tmp_path):
    from history import HistoryStore
    monkeypatch.setattr(bot_module, 'history_store', HistoryStore(tmp_path / 'history.sqlite3'))
    call = Mock(return_value='Отлично!')
    monkeypatch.setattr(bot_module, 'call_chatgpt', call)
    first = update(text='Эван, запомни слово маяк')
    bot_module.message(first, None)
    second = update(reply_user_id=123456, text='Какое слово?')
    second.message.message_id = 12
    second.message.message_thread_id = 10
    second.message.reply_to_message.message_id = 11
    second.message.reply_text.return_value = SimpleNamespace(message_id=13, text='Маяк!')
    bot_module.message(second, None)
    assert [m['content'] for m in call.call_args.kwargs['history']] == [
        'Эван, запомни слово маяк', 'Отлично!']


def test_forum_topic_keeps_its_scope(bot_module):
    message = update().message
    message.is_topic_message = True
    message.message_thread_id = 42
    assert bot_module.conversation_thread_id(message) == 42
